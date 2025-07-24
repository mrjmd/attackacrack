import requests
from flask import current_app

class OpenPhoneService:
    def __init__(self):
        self.base_url = "https://api.openphone.com/v1"

    def send_sms(self, to_number, from_number_id, body):
        """
        Sends an SMS message using the OpenPhone API.
        """
        api_key = current_app.config.get('OPENPHONE_API_KEY')
        
        if not api_key:
            print("ERROR: OpenPhone API Key is not configured.")
            return None, "API Key not configured."

        url = f"{self.base_url}/messages"
        headers = {"Authorization": api_key}
        
        # --- THIS IS THE FIX ---
        # The payload has been updated to match the OpenPhone API documentation
        # based on the error message provided.
        payload = {
            "from": from_number_id,  # The key should be 'from'
            "to": [to_number],       # The 'to' field must be a list
            "content": body          # The message content key is 'content'
        }
        # -------------------------
        
        try:
            response = requests.post(url, headers=headers, json=payload, verify=False)
            response.raise_for_status()
            return response.json(), None
        except requests.exceptions.RequestException as e:
            print(f"Error sending SMS via OpenPhone: {e}")
            if e.response is not None:
                print(f"--> Server Response: {e.response.text}")
            return None, str(e)
