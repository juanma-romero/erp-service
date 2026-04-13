import pandas as pd
import json

file_path = '/home/demian/Documents/cerebro/voraz-main/ProductoVM11Abr.xlsx'

try:
    df = pd.read_excel(file_path)
    df = df.astype(str)
    records = df.to_dict(orient='records')
    print("EXTRACTED CATALOG:")
    print(json.dumps(records, indent=2, ensure_ascii=False))
except Exception as e:
    print(f"Error reading excel: {e}")
