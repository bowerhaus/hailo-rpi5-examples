import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
import gtts
from playsound import playsound
import datetime
import json
from logger_config import logger
from gstreamer_pigeonator_app import GStreamerPigeonatorApp

import threading
from web_server import app as web_app
from time import sleep
from deterrent_manager import DeterrentManager
from watcher_base import WatcherBase, watcher_base_callback

# Load configuration from config.json
with open('config.json', 'r') as config_file:
    config = json.load(config_file)
    logger.info(f"Loaded config: {config}")

HELLO = "hello.mp3"

# Inheritance from WatcherBase
class PigeonatorWatcher(WatcherBase):
    def __init__(self, config):
        super().__init__(config)
        
        # Set logger to use the pigeonator logger
        self.logger = logger
        
        logger.info(f"Looking for {self.class_to_track.upper()}")

        # Initialize DeterrentManager
        self.deterrent_manager = DeterrentManager(config)
        self.deter_delay_seconds = config.get('DETER_DELAY_SECONDS', 8)

    def active_tracking(self, class_detections):
        """Override to add deterrent trigger logic"""
        super().active_tracking(class_detections)
        
        # Check if the pigeon has been tracked for DETER_DELAY_SECONDS, and if so, trigger deterrent
        if self.tracking_start_time:
            tracking_duration = (datetime.datetime.now() - self.tracking_start_time).total_seconds()
            if tracking_duration >= self.deter_delay_seconds:
                self.deterrent_manager.trigger_deterrent()

    def stop_active_tracking(self):
        """Override to add pigeon-specific behavior"""
        super().stop_active_tracking()
        # Reset the deterrent trigger
        self.deterrent_manager.reset_deterrent_trigger()


if __name__ == "__main__":
    # Create an instance of the user app callback class
    tts = gtts.gTTS(f"Hello Pigeonator")
    tts.save(HELLO) 
    playsound(HELLO, 0)
    
    # Start web server first.
    web_server_thread = threading.Thread(target=web_app.run, kwargs={'host': '0.0.0.0', 'port': 5000})
    web_server_thread.daemon = True
    web_server_thread.start()
    
    sleep(1)  # Give web server time to initialize.
    
    # Create the watcher app instance and run it
    user_data = PigeonatorWatcher(config)
    app = GStreamerPigeonatorApp(watcher_base_callback, user_data)
    user_data.app = app
    app.run()