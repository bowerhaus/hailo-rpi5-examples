#!/bin/bash

cd /home/bower/hailo-rpi5-examples
source setup_env.sh
cd ./community_projects/pigeonator
python pigeonator.py --use-frame --input rpi  > ~/pigeonator.log 2>&1 &


