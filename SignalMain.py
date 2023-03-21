import os
os.environ["OPENCV_LOG_LEVEL"]="SILENT"
import cv2
import socket
import asyncio
from threading import Thread, Event
from pydbus import SystemBus
from gi.repository import GLib

from datetime import datetime, timedelta, timezone

import requests
import yaml

with open('config.yml', 'r') as file:
    config = yaml.safe_load(file)



'''
INFO SECTION
- if you want to monitor raw parameters of ESP32CAM, open the browser and go to http://192.168.x.x/status
- command can be sent through an HTTP get composed in the following way http://192.168.x.x/control?var=VARIABLE_NAME&val=VALUE (check varname and value in status)
'''

watch = False
file_name = ""
content = None
secGroup = config['signal']['secretGroup']

# ESP32 URL

def set_resolution(url: str, index: int=1, verbose: bool=False):
    try:
        if verbose:
            resolutions = "10: UXGA(1600x1200)\n9: SXGA(1280x1024)\n8: XGA(1024x768)\n7: SVGA(800x600)\n6: VGA(640x480)\n5: CIF(400x296)\n4: QVGA(320x240)\n3: HQVGA(240x176)\n0: QQVGA(160x120)"
            print("available resolutions\n{}".format(resolutions))
            return True

        if index in [10, 9, 8, 7, 6, 5, 4, 3, 0]:
            requests.get(url + "/control?var=framesize&val={}".format(index))
            return True
        else:
            print("Wrong index")
            return False
    except:
        print("SET_RESOLUTION: something went wrong")
        return False

def set_quality(url: str, value: int=1, verbose: bool=False):
    try:
        if value >= 10 and value <=63:
            requests.get(url + "/control?var=quality&val={}".format(value))
    except:
        print("SET_QUALITY: something went wrong")

def set_awb(url: str, awb: int=1):
    try:
        awb = not awb
        requests.get(url + "/control?var=awb&val={}".format(1 if awb else 0))
    except:
        print("SET_QUALITY: something went wrong")
    return awb

def check_event(event_time, sec=5):
    return event_time < datetime.now() - timedelta(seconds=sec)

async def receiveContent(socCli):
    content = socCli.recv(6)
    return content

def esp32camRun(finishEvent, sendLast, files, client):
    global content, threadSoc
    URL = config['ESP32URL']
    recordingsPath = config['recordingsPath']
    AWB = True

    start_recording = False

    cap = None

    try:
        cap = cv2.VideoCapture(URL + ":81/stream")
    except:
        asyncio.run(sendMsg(client, "Error opening video stream, ESP not connected?",[], secGroup))
        print("Error opening video stream")

    sent = False
    while not set_resolution(URL, index=8) and not finishEvent.is_set():
        if sent == False:
            sent = True
            asyncio.run(sendMsg(client, "Error opening video stream, trying to Reconnecting to ESP",[], secGroup))
        try:
            cap = cv2.VideoCapture(URL + ":81/stream")
        except:
            asyncio.run(sendMsg(client, "Error opening video stream, ESP not connected?",[], secGroup))
            print("Error opening video stream")
    
    if not finishEvent.is_set():
        asyncio.run(sendMsg(client, "Connected!",[], secGroup))

    last_time = None

    out = None

    lastFrames = []
    recordFrames = []
    xySet = False
    xSize = None
    ySize = None
    while True:
        #recv data from client in async

        if(finishEvent.is_set()):
            if(out != None):
                out.release()
                asyncio.run(sendMsg(client, "",[recordingsPath+file_name], secGroup))
            asyncio.run(sendMsg(client, "Stopped watching!",[], secGroup))
            break
        if sendLast.is_set() and not start_recording:
            last_time = datetime.now()
            last_time = last_time - timedelta(seconds=5)
            file_nameTwo = str(last_time.strftime("%d-%m-%Y--%H-%M-%S"))+"_Before.mp4"
            files.append(file_nameTwo)
            outTwo = cv2.VideoWriter("recordings/"+file_nameTwo, cv2.VideoWriter_fourcc(*'mp4v'), 20, (xSize, ySize))
            for f in lastFrames:
                outTwo.write(f)
            outTwo.release()
            asyncio.run(sendMsg(client, "",[recordingsPath+file_nameTwo], secGroup))
            sendLast.clear()
        if cap.isOpened():
            if len(files) > 20:
                for i in range(10):
                    try:
                        os.remove("recordings/"+files[i])
                        print("removed "+files[i])
                    except FileNotFoundError:
                        print("File not found "+files[i])
                files = files[10:]
                print(files)

            ret, frame = cap.read()
            if not xySet:
                xSize = frame.shape[1]
                ySize = frame.shape[0]
                xySet = True
            frame = cv2.flip(frame, flipCode=-1)
            if ret:
                if content == b"motio1":
                    start_recording = True
                    if last_time == None:
                        asyncio.run(sendMsg(client, "Movement detected!",[], secGroup))
                        last_time = datetime.now()
                        file_name = str(last_time.strftime("%d-%m-%Y--%H-%M-%S"))+".mp4"
                        files.append(file_name)

                if start_recording:
                    if len(lastFrames) > 30:
                        last_time = datetime.now()
                        last_time = last_time - timedelta(seconds=5)
                        recordFrames = lastFrames
                        lastFrames = []
                    recordFrames.append(frame)

                if start_recording and check_event(last_time, 50):
                    start_recording = False
                    last_time = None
                    out = cv2.VideoWriter("recordings/"+file_name, cv2.VideoWriter_fourcc(*'mp4v'), len(recordFrames)/55, (xSize, ySize))
                    for f in recordFrames:
                        out.write(f)
                    out.release()
                    out = None
                    asyncio.run(sendMsg(client, "", [recordingsPath+file_name], secGroup))
                    print("Video Saved")
                    recordFrames = []

                if len(lastFrames) > 80:
                    lastFrames.pop(0)
                if not start_recording:
                    lastFrames.append(frame)

            else:
                start_recording = False
                asyncio.run(sendMsg(client, "Error opening video stream, trying to reconnect to ESP", [], secGroup))
                cap.release()
                if(len(recordFrames) > 0):
                    out = cv2.VideoWriter("recordings/"+file_name, cv2.VideoWriter_fourcc(*'mp4v'), len(recordFrames)/55, (xSize, ySize))
                    for f in recordFrames:
                        out.write(f)
                    out.release()
                    asyncio.run(sendMsg(client, "",[recordingsPath+file_name], secGroup))
                    out = None
                    recordFrames = []
                if lastFrames != []:
                    last_time = datetime.now()
                    last_time = last_time - timedelta(seconds=5)
                    file_nameTwo = str(last_time.strftime("%d-%m-%Y--%H-%M-%S"))+"_Before.mp4"
                    files.append(file_nameTwo)
                    outTwo = cv2.VideoWriter("recordings/"+file_nameTwo, cv2.VideoWriter_fourcc(*'mp4v'), 20, (xSize, ySize))
                    for f in lastFrames:
                        outTwo.write(f)
                    outTwo.release()
                    asyncio.run(sendMsg(client, "", [recordingsPath+file_nameTwo], secGroup))
                    lastFrames = []
                print("Error opening video stream")

                sendLast.clear()
                esp32camRun(finishEvent, sendLast, files, client)

                break
            key = cv2.waitKey(1)

            if key == ord('r'):
                idx = int(input("Select resolution index: "))
                set_resolution(URL, index=idx, verbose=True)

            elif key == ord('q'):
                val = int(input("Set quality (10 - 63): "))
                set_quality(URL, value=val)

            elif key == ord('a'):
                AWB = set_awb(URL, AWB)

            elif key == 27:
                break
        else:
            try:
                cap = cv2.VideoCapture(URL + ":81/stream")
            except:
                asyncio.run(sendMsg(client, "Error opening video stream, ESP not connected?", [], secGroup))
            set_resolution(URL, index=8)
                    
            # cv2.imshow("frame", frame)


    cv2.destroyAllWindows()
    cap.release()


def socketReceive(s):
    global content
    socCli, addr, = s.accept()
    print("Connected by", addr)
    while True:
        try:
            if socCli.send(b"hihihi"):
                content = socCli.recv(6)
        except:
            print("disconnected ", addr)
            socCli, addr, = s.accept()
            print("Connected by", addr)


task = None
finishEvent = Event()
sendLast = Event()
threadESP = None
threadSoc = None
watching = False
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(('0.0.0.0', config['socketPort']))
s.listen(1)

threadSoc = Thread(target=socketReceive, args=(s,))
threadSoc.start()


def msgRcv (timestamp, source, groupID, message, attachments):
    global finishEvent, sendLast, threadESP, threadSoc, files, watching, s
    if not groupID:
        print ("Message", message, "received from", source)
    else:
        if groupID == secGroup:
            print ("Message", message, "received in secret group")
            if message == "!start":
                    if watching and not sendLast.is_set():
                        signal.sendGroupMessage("I'm already watching!", [], secGroup)
                    else:
                        files = os.listdir('recordings/')
                        watching = True
                        finishEvent = Event()
                        sendLast = Event()
                        threadESP = Thread(target=esp32camRun, args=(finishEvent, sendLast, files, signal))
                        threadESP.start()
            if message == "!stop":
                if threadESP != None:
                    finishEvent.set()
                    threadESP.join()
                    watching = False
            if message == "!last":
                sendLast.set()
                
        print ("Message", message, "received in group", signal.getGroupName (groupID))
    return

async def sendMsg(s, msg, attachments, groupId):
    s.sendGroupMessage(msg, attachments, groupId)

bus = SystemBus()
loop = GLib.MainLoop()

signal = bus.get('org.asamk.Signal')

signal.sendMessage("hi, Bot just started", [], config['signal']['myNumber'])
signal.onMessageReceived = msgRcv

loop.run()
