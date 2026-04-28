import requests
import os
import json
import logging
from dotenv import load_dotenv
from typing import Dict, List, Any, Optional

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("IFindMCPClient")

class IFindMCPClient:
    """
    A unified client for iFind MCP Servers (Stock, Fund, EDB, News) over HTTP.
    """
    
    SERVER_URLS = {
        "stock": os.getenv("IFIND_MCP_STOCK_URL"),
        "fund": os.getenv("IFIND_MCP_FUND_URL"),
        "edb": os.getenv("IFIND_MCP_EDB_URL"),
        "news": os.getenv("IFIND_MCP_NEWS_URL")
    }

    def __init__(self, server_type: str = "fund"):
        self.server_type = server_type.lower()
        self.base_url = self.SERVER_URLS.get(self.server_type)
        self.auth_token = os.getenv("IFIND_MCP_AUTH_TOKEN")
        
        if not self.base_url:
            raise ValueError(f"Server URL for type '{server_type}' not found in environment.")
        if not self.auth_token:
            raise ValueError("IFIND_MCP_AUTH_TOKEN not found in environment.")

    def _get_headers(self):
        return {
            "Authorization": self.auth_token,
            "Content-Type": "application/json"
        }

    def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools on the specified MCP server."""
        payload = {
            "jsonrpc": "2.0",
            "id": "list_tools_v1",
            "method": "tools/list",
            "params": {}
        }
        url = f"{self.base_url}/tools/list"
        logger.info(f"Listing tools for {self.server_type} server at {url}")
        
        try:
            res = requests.post(url, headers=self._get_headers(), json=payload, timeout=20)
            res.raise_for_status()
            data = res.json()
            if "error" in data:
                logger.error(f"MCP JSON-RPC Error: {data['error']}")
                return []
            return data.get("result", {}).get("tools", [])
        except Exception as e:
            logger.error(f"Failed to list tools: {e}")
            return []

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a specific tool with arguments."""
        payload = {
            "jsonrpc": "2.0",
            "id": f"call_{tool_name}_{os.urandom(4).hex()}",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }
        
        # We try both the root URL and /tools/call if needed.
        # Based on successful probe, we'll try the root first, but some servers might need /tools/call
        url = self.base_url 
        logger.info(f"Calling tool '{tool_name}' on {self.server_type} server")
        
        try:
            res = requests.post(url, headers=self._get_headers(), json=payload, timeout=60)
            # If 404 or 405, try /tools/call
            if res.status_code in [404, 405]:
                alt_url = f"{self.base_url}/tools/call"
                logger.info(f"Retry with alternate endpoint: {alt_url}")
                res = requests.post(alt_url, headers=self._get_headers(), json=payload, timeout=60)
            
            res.raise_for_status()
            data = res.json()
            if "error" in data:
                logger.error(f"MCP Call Tool Error: {data['error']}")
                return {"ok": False, "error": data["error"]}
                
            # MCP return usually has 'content' or 'result'
            result = data.get("result", {})
            return {"ok": True, "data": result}
        except Exception as e:
            logger.error(f"Failed to call tool '{tool_name}': {e}")
            return {"ok": False, "error": str(e)}

    # Convenience method
    @classmethod
    def quick_call(cls, server_type: str, tool_name: str, arguments: Dict[str, Any]):
        client = cls(server_type)
        return client.call_tool(tool_name, arguments)

if __name__ == "__main__":
    # Example usage
    try:
        client = IFindMCPClient("fund")
        tools = client.list_tools()
        print(f"Funds found: {len(tools)} tools")
        
        result = client.call_tool("search_funds", {"query": "南方基金"})
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Error: {e}")
