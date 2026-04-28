import os
import json
import requests
import time
from dotenv import load_dotenv

load_dotenv()

class IFindClient:
    """
    A client to interact with the 同花顺 iFinD HTTP API (QuantAPI).
    """
    AUTH_URL = "https://quantapi.10jqka.com.cn/api/v1/get_access_token"
    # Endpoints depend on the function used
    BASE_URL = "https://quantapi.10jqka.com.cn/api/v1"

    def __init__(self):
        self.refresh_token = os.getenv("IFIND_REFRESH_TOKEN")
        self.access_token = None
        self.token_expiry = 0
        if not self.refresh_token:
            raise ValueError("IFIND_REFRESH_TOKEN not found in environment variables.")

    def _get_access_token(self):
        """Fetch a valid access_token using the refresh_token."""
        # Simple caching logic: check if we have a token (expiry logic can be added later)
        if self.access_token and time.time() < self.token_expiry:
            return self.access_token

        headers = {
            "Content-Type": "application/json",
            "refresh_token": self.refresh_token
        }
        
        response = requests.post(self.AUTH_URL, headers=headers)
        if response.status_code != 200:
            raise Exception(f"Auth failed with status {response.status_code}: {response.text}")
        
        data = response.json()
        if data.get("errorcode") != 0:
            raise Exception(f"Auth error: {data.get('errmsg')}")
        
        self.access_token = data["data"]["access_token"]
        # Access token usually lasts 7 days, we'll refresh every hour for safety or just check error codes
        self.token_expiry = time.time() + 3600 
        return self.access_token

    def request(self, func, codes, indicators, params=""):
        """
        Generic data request to the appropriate service endpoint.
        """
        token = self._get_access_token()
        
        # Route to the correct service
        endpoint_map = {
            "THS_BD": f"{self.BASE_URL}/basic_data_service",
            "THS_DS": f"{self.BASE_URL}/data_sequence_service",
            "THS_HistoryQuotes": f"{self.BASE_URL}/history_quotation"
        }
        
        url = endpoint_map.get(func, f"{self.BASE_URL}/thsapi")
        
        payload = {
            "codes": codes,
            "indicators": indicators,
            "params": params
        }
        
        headers = {
            "Content-Type": "application/json",
            "access_token": token
        }
        
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code != 200:
            print(f"DEBUG: Status {response.status_code}, Body: {response.text}")
            raise Exception(f"Request failed with status {response.status_code}")
        
        data = response.json()
        # errorcode -4210 often means parameter mismatch for that specific service
        if data.get("errorcode") != 0:
            if data.get("errorcode") in [403, 401]:
                self.access_token = None
                return self.request(func, codes, indicators, params)
            raise Exception(f"API error ({func}): {data.get('errmsg')} (Code: {data.get('errorcode')})")
        
        return data

    def get_fund_holdings(self, fund_code, date):
        """
        Retrieve fund holdings for a specific date.
        """
        # Indicator for fund portfolio stock holdings
        # Usually: ths_fund_stock_portfolio_stock_name_fund or similar
        # Based on iFind docs, THS_BD for fund holdings often uses specific indicator combinations
        return self.request(
            func="THS_BD",
            codes=fund_code,
            indicators="ths_fund_stock_portfolio_stock_name_fund,ths_fund_stock_portfolio_stock_code_fund,ths_fund_stock_portfolio_ratio_fund",
            params=f"{date},0"
        )

if __name__ == "__main__":
    # Quick test
    client = IFindClient()
    try:
        # Example: E Fund Blue Chip Select (张坤) - 008892.OF
        res = client.get_fund_holdings("008892.OF", "2023-12-31")
        print(json.dumps(res, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Error: {e}")
