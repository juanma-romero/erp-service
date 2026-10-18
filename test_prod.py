import os
import requests
from dotenv import load_dotenv

# Las credenciales se leen del entorno (.env), nunca hardcodeadas en el código.
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

url = os.getenv("ERPNEXT_URL", "https://vorazadmin.site")
api_key = os.getenv("ERPNEXT_API_KEY")
api_secret = os.getenv("ERPNEXT_API_SECRET")

if not api_key or not api_secret:
    raise SystemExit("Faltan ERPNEXT_API_KEY / ERPNEXT_API_SECRET en el entorno (.env)")

headers = {
    "Authorization": f"token {api_key}:{api_secret}",
    "Content-Type": "application/json",
}

try:
    print(f"Connecting to {url}...")
    res = requests.get(
        f"{url}/api/resource/Delivery Note",
        headers=headers,
        params={"limit_page_length": 5, "fields": '["name", "posting_date", "grand_total", "customer_name"]'},
    )
    print("DN Status:", res.status_code)
    print("DN Data:", res.json())
except Exception as e:
    print("Error:", e)
