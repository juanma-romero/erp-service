import os
from services.frappe_client import FrappeClient
from dotenv import load_dotenv

load_dotenv()

client = FrappeClient(
    url=os.getenv("ERPNEXT_URL", "http://localhost:8080"),
    api_key=os.getenv("ERPNEXT_API_KEY"),
    api_secret=os.getenv("ERPNEXT_API_SECRET")
)

order = client.get_sales_order("SAL-ORD-2026-00315")
print("\n--- CLAVES DEL PEDIDO ---")
for key in order.keys():
    if "entrega" in key.lower() or "date" in key.lower() or "dia" in key.lower() or "time" in key.lower():
        print(f"{key}: {order[key]}")
