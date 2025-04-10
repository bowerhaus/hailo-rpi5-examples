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
from gstreamer_peetronic_app import GStreamerPeetronicApp

import threading
from web_server import app as web_app
from time import sleep
from watcher_base import WatcherBase, watcher_base_callback

# Load configuration from config.json or from environment variable if specified
config_file = os.environ.get('WATCHER_CONFIG_FILE', 'config.json')
logger.info(f"Loading configuration from: {config_file}")
with open(config_file, 'r') as config_file:
    config = json.load(config_file)
    logger.info(f"Loaded config: {config}")

HELLO = "hello.mp3"

# Inheritance from WatcherBase
class PeetronicWatcher(WatcherBase):
    def __init__(self, config):
        super().__init__(config)
        
        # Set logger to use the peetronic logger
        self.logger = logger
        
        logger.info(f"Looking for {self.class_to_track.upper()}")

if __name__ == "__main__":
    # Create an instance of the user app callback class
    tts = gtts.gTTS(f"Hello Peetronic")
    tts.save(HELLO) 
    user_data = PeetronicWatcher(config)
    user_data.playsound_async(HELLO)
    
    # Start web server first.
    web_server_kwargs = {'host': '0.0.0.0', 'port': 5003}
    
    # Check if SSL should be used
    if config.get('USE_SSL', False):
        web_server_kwargs['ssl_context'] = ('certificate/peetronic.pem', 'certificate/peetronic-privkey.pem')
        logger.info("Starting web server with SSL enabled")
    else:
        logger.info("Starting web server without SSL")
    
    web_server_thread = threading.Thread(target=web_app.run, kwargs=web_server_kwargs)
    web_server_thread.daemon = True
    web_server_thread.start()
    
    sleep(1)  # Give web server time to initialize.
    
    # Create the watcher app instance and run it
    app = GStreamerPeetronicApp(watcher_base_callback, user_data)
    user_data.app = app
    app.run()