#!/bin/bash

cd /home/bower/hailo-rpi5-examples
source setup_env.sh
cd ./community_projects/watcher/helen-o-matic
python helen_o_matic.py --use-frame --input rpi  > ~/helen-o-matic.log 2>&1 &


