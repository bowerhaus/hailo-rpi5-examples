#!/bin/bash

cd /home/bower/hailo-rpi5-examples
source setup_env.sh
cd ./community_projects/watcher/peetronic
python peetronic.py --use-frame --hef-path models/peetronic.v1.yolov8p.hef --labels-json models/peetronic.v1-labels.json --input rpi  > ~/peetronic.log 2>&1 &

