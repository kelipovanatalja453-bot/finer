import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

def explore_mcp():
    url = os.getenv("IFIND_MCP_FUND_URL")
    token = os.getenv("IFIND_MCP_AUTH_TOKEN")
    
    if not url or not token:
        print("Error: Missing URL or Token in .env")
        return

    headers = {
        "Authorization": token,
        "Content-Type": "application/json"
    }

    # As per MCP spec over HTTP, initial discovery is often via tools/list
    # Try different common MCP endpoint patterns
    endpoints = ["/tools/list", "/tools", ""]
    
    for endpoint in endpoints:
        full_url = f"{url}{endpoint}"
        print(f"--- Probing {full_url} ---")
        try:
            # MCP spec usually uses JSON-RPC 2.0
            payload = {
                "jsonrpc": "2.0",
                "id": "1",
                "method": "tools/list",
                "params": {}
            }
            res = requests.post(full_url, headers=headers, json=payload, timeout=10)
            print(f"Status: {res.status_code}")
            if res.status_code == 200:
                print("Success! Body:")
                print(json.dumps(res.json(), indent=2, ensure_ascii=False))
                break
            else:
                print(f"Body: {res.text[:200]}")
        except Exception as e:
            print(f"Error calling {endpoint}: {e}")

if __name__ == "__main__":
    explore_mcp()
