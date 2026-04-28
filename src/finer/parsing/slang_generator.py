import pandas as pd
import json
import os
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def generate_slang_json(excel_path: str, output_path: str):
    """
    Reads the user's slang Excel and converts it into a standardized JSON for the SlangMapper.
    """
    logging.info(f"Generating slang mapping from {excel_path}...")
    
    if not os.path.exists(excel_path):
        logging.error(f"Excel file not found at {excel_path}")
        return

    try:
        # Read the Excel file
        df = pd.read_excel(excel_path)
        
        # We expect Column 0 to be the 'Slang' and Column 1 to be the 'Meaning/Normalization'
        # Let's clean up the column names for easier processing
        df.columns = ['slang', 'meaning']
        
        mapping = {}
        for _, row in df.iterrows():
            slang = str(row['slang']).strip()
            meaning = str(row['meaning']).strip()
            
            if slang and meaning and slang != 'nan' and meaning != 'nan':
                # Split multiple slang terms if they are in the same cell (e.g., "鹅/企鹅")
                terms = [t.strip() for t in slang.replace('、', '/').split('/')]
                for term in terms:
                    # For now, we store (Meaning, Ticker=None)
                    # Advanced logic could extract Tickers if present in the meaning string
                    mapping[term] = [meaning, None]
        
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2)
            
        logging.info(f"Successfully generated {len(mapping)} slang rules to {output_path}")

    except Exception as e:
        logging.error(f"Error during slang generation: {e}")

if __name__ == "__main__":
    EXCEL_FILE = "/Users/zhouhongyuan/Desktop/finer/词语个人理解（持续更新）.xlsx"
    OUTPUT_FILE = "/Users/zhouhongyuan/Desktop/finer/data/config/slang.json"
    generate_slang_json(EXCEL_FILE, OUTPUT_FILE)
