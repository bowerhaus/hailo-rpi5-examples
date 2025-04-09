import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gstreamer_watcher_app import GStreamerWatcherApp, SOURCE_PIPELINE, DISPLAY_PIPELINE
from logger_config import logger

class GStreamerHelenOMaticApp(GStreamerWatcherApp):
    """
    GStreamer app for Helen-O-Matic.
    Inherits from GStreamerWatcherApp.
    """
    
    def __init__(self, app_callback, user_data):
        """
        Initialize the Helen-O-Matic application.
        
        Args:
            app_callback: Callback function to process frames.
            user_data: User data to pass to the callback.
        """
        super().__init__(app_callback, user_data)
        logger.info("Helen-O-Matic application initialized")
        
        # Any Helen-O-Matic-specific configuration can be added here

