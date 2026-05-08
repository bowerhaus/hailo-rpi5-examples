#!/bin/bash

cd /home/bower/hailo-rpi5-examples
source setup_env.sh
cd ./community_projects/watcher/pigeonator
python pigeonator.py --use-frame --hef-path "$VIRTUAL_ENV/lib/python3.11/site-packages/resources/yolov8s_h8l.hef" --labels-json models/coco-labels.json --input rpi  > ~/pigeonator-lawn.log 2>&1 &
