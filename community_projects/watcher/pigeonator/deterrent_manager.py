import datetime
from logger_config import logger
from linktap import LinkTap  # Import LinkTap class
import threading
import time

class DeterrentManager:
    def __init__(self, config):
        self.linktap_username = config.get('LINKTAP_USERNAME')
        self.linktap_apikey = config.get('LINKTAP_APIKEY')
        self.linktap_gatewayid = config.get('LINKTAP_GATEWAYID')
        self.linktap_taplinkerid = config.get('LINKTAP_TAPLINKERID')
        self.watering_duration_sec = config.get('WATERING_DURATION_SEC')
        self.linktap = LinkTap(self.linktap_username, self.linktap_apikey)
        self.watering_triggered = False
        self.deter_rate_limit_seconds = config.get('DETER_RATE_LIMIT_SECONDS', 60)
        self.last_deterrent_time = None
        self.watering_on = config.get('WATERING_ON', True)

    def _run_linktap_call(self):
        """Helper function to run the LinkTap API call."""
        try:
            # Compute minutes and seconds from total seconds
            minutes = self.watering_duration_sec // 60
            seconds = self.watering_duration_sec % 60

            # Call LinkTap API to turn on watering
            self.linktap.activate_instant_mode(
                gatewayId=self.linktap_gatewayid,
                taplinkerId=self.linktap_taplinkerid,
                action=True,
                duration=minutes,
                durationSec=seconds,
                eco=False
            )
            logger.info("Watering triggered via LinkTap API")
            return True
        except Exception as e:
            logger.error(f"Error calling LinkTap API: {e}, {self.linktap_gatewayid}, {self.linktap_taplinkerid}, {self.watering_duration_sec}")
            return False

    def trigger_deterrent(self):
        if self.watering_on:
            now = datetime.datetime.now()
            if self.last_deterrent_time is None or (now - self.last_deterrent_time).total_seconds() >= self.deter_rate_limit_seconds:
                if not self.watering_triggered:
                    # Create and start a new thread to run the LinkTap API call
                    self.watering_triggered = True  # Prevent re-triggering
                    self.last_deterrent_time = now
                    threading.Thread(target=self._run_linktap_call, daemon=True).start()

    def reset_deterrent_trigger(self):
        """Reset the watering triggered flag."""
        self.watering_triggered = False
