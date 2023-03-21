# Signal and Discord bot that works with ESP32CAM as security camera

## Signal DBus setup
https://github.com/Xamyrz/signal-cli-pi

## Installatian
1. Clone this repository
2. install requirements.txt with pip
3. Change config.yml to your specifications
4. Run SignalMain.py or DiscordMain.py

## Discord usage
These commands are sent in a DM with the bot
1. `!start` to start looking for movement
2. `!stop` to stop looking for movement
3. `!sendlast` to send the last 5 seconds of video
4. `!removeall` to remove all recordings sent to you

## Signal usage
These commands are sent in a group chat with the bot
1. `!start` to start looking for movement
2. `!stop` to stop looking for movement
3. `!last` to send the last 5 seconds of video
