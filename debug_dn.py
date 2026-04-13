import os
from dotenv import load_dotenv
from services.frappe_client import FrappeClient

load_dotenv()

client = FrappeClient(
    url=os.getenv("ERPNEXT_URL", "http://localhost:8080"),
    api_key=os.getenv("ERPNEXT_API_KEY"),
    api_secret=os.getenv("ERPNEXT_API_SECRET")
)

def test_make_dn():
    orders = client.get_submitted_sales_orders()
    if not orders:
        print("No pending orders found.")
        return
    
    order = orders[0]
    order_name = order['name']
    print(f"Attempting to make delivery note for {order_name}")
    import requests

    api_url = f"{client.url}/api/method/erpnext.selling.doctype.sales_order.sales_order.make_delivery_note"
    data = {"source_name": order_name}
    res = requests.post(api_url, headers=client.headers, json=data)
    print(res.status_code)
    try:
        dn_doc = res.json().get("message", {})
        print("DN doc generated")
        
        # Save it
        post_url = f"{client.url}/api/resource/Delivery Note"
        res_post = requests.post(post_url, headers=client.headers, json=dn_doc)
        print("Saved status:", res_post.status_code)
        dn_name = res_post.json()["data"]["name"]
        
        # Submit
        submit_url = f"{post_url}/{dn_name}"
        res_submit = requests.put(submit_url, headers=client.headers, json={"docstatus": 1})
        print("Submit status:", res_submit.status_code)
        
    except Exception as e:
        print("Error:", e, res.text)

test_make_dn()
