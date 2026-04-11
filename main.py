import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from services.frappe_client import FrappeClient
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="ERP Service for Voraz")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

frappe_client = FrappeClient(
    url=os.getenv("ERPNEXT_URL", "http://localhost:8080"),
    api_key=os.getenv("ERPNEXT_API_KEY"),
    api_secret=os.getenv("ERPNEXT_API_SECRET")
)

@app.get("/api/orders/pending")
async def get_pending_orders():
    """
    Obtiene los pedidos en estado 'Submitted' desde ERPNext
    y los mapea al formato requerido por WhatsApp /listado
    """
    try:
        orders = frappe_client.get_submitted_sales_orders()
        formatted_orders = []
        
        for order in orders:
            # Map Items
            mapped_items = []
            for item in order.get("items", []):
                mapped_items.append({
                    "cantidad": item.get("qty", 1),
                    "nombre": item.get("item_name") or item.get("item_code", "Producto desconocido")
                })
            
            formatted_orders.append({
                "numero_pedido": order.get("name"),
                "contactName": order.get("customer_name") or order.get("customer"),
                "fecha_hora_entrega": order.get("custom_dia_y_hora_entrega") or order.get("delivery_date") or order.get("transaction_date"),
                "productos": mapped_items,
                "monto_total": f"$ {order.get('grand_total', 0):.0f}"
            })
            
        return formatted_orders

    except Exception as e:
        print(f"Error fetching pending orders: {str(e)}")
        raise HTTPException(status_code=500, detail="Error de conexión con ERPNext")
