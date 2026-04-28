import json
import os
import time
from src.utils.mcp_client import IFindMCPClient

def fetch_all():
    client = IFindMCPClient("news")
    tickers = ["泡泡玛特", "老铺黄金"]
    queries = [
        "{ticker} 研报 评级 目标价",
        "{ticker} 业绩预期 2025 2026",
        "{ticker} 业务亮点 深度研究"
    ]
    
    start_date = "2025-01-01"
    end_date = "2026-04-01"
    
    db = {ticker: [] for ticker in tickers}
    
    for ticker in tickers:
        print(f"--- Fetching for {ticker} ---")
        for q_template in queries:
            query = q_template.format(ticker=ticker)
            print(f"Query: {query}")
            
            # Using search_news as it usually covers reports in many news feeds
            # If search_notice is better, we can also try it.
            res = client.call_tool("search_news", {
                "query": query,
                "time_start": start_date,
                "time_end": end_date,
                "size": 20
            })
            
            if res.get("ok"):
                # The data structure from MCP is usually in data['result']['data'] or similar
                # Let's extract the informative parts.
                # In previous explore_mcp.py, result['tools'] showed segments 
                # but search_news output sample showed snippets.
                data = res.get("data", {})
                # If there's high-level data key
                segments = data.get("segments", []) or data.get("result", [])
                if segments:
                    db[ticker].extend(segments)
                    print(f"  Got {len(segments)} segments")
                else:
                    # In some cases it's a JSON string in a certain field
                    raw_data = data.get("data", "")
                    if isinstance(raw_data, str) and raw_data:
                        try:
                            parsed = json.loads(raw_data)
                            db[ticker].extend(parsed)
                            print(f"  Parses {len(parsed)} from string")
                        except:
                            db[ticker].append(raw_data)
                    else:
                        print(f"  No segments found in: {data.keys()}")
            else:
                print(f"  Error: {res.get('error')}")
            
            # Rate limiting / polite pause
            time.sleep(1)

    # Persist
    output_path = "data/reports_analysis_v2.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
    
    print(f"\n--- Complete! Saved to {output_path} ---")

if __name__ == "__main__":
    fetch_all()
