import requests
from flask import current_app

class OpenPhoneService:
    def __init__(self):
        # We remove the self.api_key from here to avoid the context error.
        self.base_url = "https://api.openphone.com/v1"

    def send_sms(self, to_number, from_number_id, body):
        """
        Sends an SMS message using the OpenPhone API.
        """
        # Get the API key just-in-time, when the app context is available.
        api_key = current_app.config.get('OPENPHONE_API_KEY')
        
        if not api_key:
            print("ERROR: OpenPhone API Key is not configured.")
            return None, "API Key not configured."

        url = f"{self.base_url}/messages"
        headers = {"Authorization": api_key}
        payload = {
            "phoneNumberId": from_number_id,
            "to": to_number,
            "body": body
        }
        
        try:
            # Using verify=False as we did for the dashboard
            response = requests.post(url, headers=headers, json=payload, verify=False)
            response.raise_for_status()
            return response.json(), None
        except requests.exceptions.RequestException as e:
            print(f"Error sending SMS via OpenPhone: {e}")
            return None, str(e)
