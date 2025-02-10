#!/bin/bash

cd /home/bower/hailo-rpi5-examples
source setup_env.sh
cd ./community_projects/watcher
python watcher.py --input rpi  > ~/watcher.log 2>&1 &


