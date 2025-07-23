import requests
from flask import current_app # Import current_app

def send_sms(phone_number, message):
    """
    Sends an SMS using the OpenPhone API.
    """
    # Get the API key from the current Flask app's configuration
    api_key = current_app.config.get('OPENPHONE_API_KEY')
    if not api_key:
        print("Error: OPENPHONE_API_KEY is not configured.")
        return None

    url = "https://api.openphone.co/v1/sms"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "to": phone_number,
        "body": message
    }
    
    try:
        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()  # Raises an HTTPError for bad responses
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error sending SMS: {e}")
        return None

