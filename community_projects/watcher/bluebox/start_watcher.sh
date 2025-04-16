#!/bin/bash

cd /home/bower/hailo-rpi5-examples
source setup_env.sh
cd ./community_projects/watcher/bluebox
python bluebox.py --use-frame --input rpi  > ~/bluebox.log 2>&1 &

