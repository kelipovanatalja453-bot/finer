import requests
import os
from dotenv import load_dotenv

load_dotenv()

def test_auth():
    refresh_token = os.getenv("IFIND_REFRESH_TOKEN")
    if not refresh_token:
        print("Error: IFIND_REFRESH_TOKEN not found in .env")
        return
    
    url = "https://ft.10jqka.com.cn/api/v1/get_access_token"
    headers = {
        "Content-Type": "application/json",
        "refresh_token": refresh_token
    }
    
    try:
        response = requests.post(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            if data.get("errorcode") == 0:
                print("✅ Successfully retrieved access_token")
                # print(f"Access Token: {data.get('access_token')[:10]}...")
            else:
                print(f"❌ Failed to retrieve access_token: {data.get('errmsg')}")
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    test_auth()
