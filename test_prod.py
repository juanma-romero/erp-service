import requests
import json
import os

url = "https://febo.digital"
api_key = "9eece4c19bc2d54"
api_secret = "71fcecc66fba045"

headers = {
    "Authorization": f"token {api_key}:{api_secret}",
    "Content-Type": "application/json"
}

try:
    print(f"Connecting to {url}...")
    res = requests.get(
        f"{url}/api/resource/Delivery Note",
        headers=headers,
        params={"limit_page_length": 5, "fields": '["name", "posting_date", "grand_total", "customer_name"]'}
    )
    print("DN Status:", res.status_code)
    print("DN Data:", res.json())
except Exception as e:
    print("Error:", e)
