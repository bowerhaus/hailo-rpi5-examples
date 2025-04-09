#!/bin/bash

cd /home/bower/hailo-rpi5-examples
source setup_env.sh
cd ./community_projects/watcher/helen-o-matic
python helen_o_matic.py --use-frame --hef-path "models/helen-o-matic.v7.yolov8p.hef" --labels-json "models/helen-o-matic.v5-labels.json" --input rpi  > ~/helen-o-matic.log 2>&1 &


