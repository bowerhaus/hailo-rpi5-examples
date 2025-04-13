#!/bin/bash

cd /home/bower/hailo-rpi5-examples
source setup_env.sh
cd ./community_projects/watcher/pigeonator
python pigeonator.py --use-frame --hef-path models/pigeonator-mk3-b.v4.yolov8p.hef --labels-json models/pigeonator-mk3-b.v3-labels.json --input rpi  > ~/pigeonator.log 2>&1 &


