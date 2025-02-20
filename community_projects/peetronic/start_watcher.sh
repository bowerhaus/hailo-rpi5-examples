#!/bin/bash

cd /home/bower/hailo-rpi5-examples
source setup_env.sh
cd ./community_projects/peetronic
python peetronic.py --use-frame --input rpi  > ~/peetronic.log 2>&1 &

