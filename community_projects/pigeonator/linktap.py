import sys
import requests

class LinkTapError(Exception):
     def __init__(self, message):
         self.message = message

class LinkTap:
    def __init__(self, username, apiKey):
        self.base_url = "https://www.link-tap.com/api/"
        self.username = username
        self.apiKey = apiKey

    def call_api(self, url, payload):
        r = requests.post(url, data=payload)
        if r.status_code == requests.codes.ok:
            data = r.json()
            if data["result"] == "error":
                raise LinkTapError("API returned error (code={r.status_code})")
            elif data is None:
                raise LinkTapError("Failed to return data (code={r.status_code})")
            else:
                return data
        else:
            raise LinkTapError(f"Failed to connect to API (code={r.status_code})")

    def activate_instant_mode(self, gatewayId, taplinkerId, action, duration, durationSec, eco):
        url = self.base_url + "activateInstantMode"

        # autoBack:  Re-activate watering plan after Instant Mode
        auto_back = "true"

        if action:
            action = "true"
        else:
            action = "false"

        if eco:
            eco = "true"
        else:
            eco = "false"

        payload = {
            "username": self.username,
            "apiKey": self.apiKey,
            "gatewayId": gatewayId,
            "taplinkerId": taplinkerId,
            "action": action,
            "duration": duration,
            "durationSec": durationSec,
            "eco": eco,
            "autoBack": auto_back,
        }
        ret = self.call_api(url, payload)
        return ret

    def activate_interval_mode(self, gatewayId, taplinkerId):
        url = self.base_url + "activateIntervalMode"

        payload = {
            "username": self.username,
            "apiKey": self.apiKey,
            "gatewayId": gatewayId,
            "taplinkerId": taplinkerId,
        }
        ret = self.call_api(url, payload)
        return ret

    def activate_odd_even_mode(self, gatewayId, taplinkerId):
        url = self.base_url + "activateOddEvenMode"

        payload = {
            "username": self.username,
            "apiKey": self.apiKey,
            "gatewayId": gatewayId,
            "taplinkerId": taplinkerId,
        }
        ret = self.call_api(url, payload)
        return ret

    def activate_seven_day_mode(self, gatewayId, taplinkerId):
        url = self.base_url + "activateSevenDayMode"

        payload = {
            "username": self.username,
            "apiKey": self.apiKey,
            "gatewayId": gatewayId,
            "taplinkerId": taplinkerId,
        }
        ret = self.call_api(url, payload)
        return ret

    def activate_month_mode(self, gatewayId, taplinkerId):
        url = self.base_url + "activateMonthMode"

        payload = {
            "username": self.username,
            "apiKey": self.apiKey,
            "gatewayId": gatewayId,
            "taplinkerId": taplinkerId,
        }
        ret = self.call_api(url, payload)
        return ret

    def get_all_devices(self):
        url = self.base_url + "getAllDevices"
        payload = {"username": self.username, "apiKey": self.apiKey}
        ret = self.call_api(url, payload)
        return ret

    def get_watering_status(self, taplinkerId):
        url = self.base_url + "getWateringStatus"
        payload = {
            "username": self.username,
            "apiKey": self.apiKey,
            "taplinkerId": taplinkerId,
        }
        ret = self.call_api(url, payload)
        return ret
