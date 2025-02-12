#!/bin/bash

cd /home/bower/hailo-rpi5-examples
source setup_env.sh
cd ./community_projects/watcher

# Check if there is a process with the name "Hailo Detection"
if pgrep -x "Hailo Detection" > /dev/null
then
    echo "Hailo process is already running."
else
    echo "No Hailo process found. Starting the Python program."
    python watcher.py --use-fram --input rpi  > ~/watcher.log 2>&1 &
fi

