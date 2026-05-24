#!/bin/bash
# Simple script to run the bot listener in the background
PID_FILE=$HOME/torrent-hybrid/logs/bot.pid
LOG_FILE=$HOME/torrent-hybrid/logs/bot_listener.log

if [ -f $PID_FILE ]; then
    kill $(cat $PID_FILE) 2>/dev/null
    rm $PID_FILE
fi

nohup /usr/bin/python3 $HOME/torrent-hybrid/scripts/bot_listener.py >> $LOG_FILE 2>&1 &
echo $! > $PID_FILE
echo 'Bot listener started in background with PID $!'
