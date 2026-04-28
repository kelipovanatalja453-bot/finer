from src.utils.mcp_client import IFindMCPClient
import json

def verify_all():
    servers = ["stock", "fund", "edb", "news"]
    results = {}
    
    for s_type in servers:
        print(f"--- Probing {s_type} ---")
        try:
            client = IFindMCPClient(s_type)
            tools = client.list_tools()
            if tools:
                results[s_type] = f"OK ({len(tools)} tools)"
            else:
                results[s_type] = "WARN: Empty tool list"
        except Exception as e:
            results[s_type] = f"ERROR: {e}"
            
    print("\n--- Status Report ---")
    print(json.dumps(results, indent=4))

if __name__ == "__main__":
    verify_all()
