import requests
import os
from dotenv import load_dotenv

load_dotenv()

def inspect_auth():
    refresh_token = os.getenv("IFIND_REFRESH_TOKEN")
    url = "https://quantapi.51ifind.com/api/v1/get_access_token"
    headers = {
        "Content-Type": "application/json",
        "refresh_token": refresh_token
    }
    
    response = requests.post(url, headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Body: {response.text}")

if __name__ == "__main__":
    inspect_auth()
