import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from services.frappe_client import FrappeClient
from typing import Optional
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
async def get_pending_orders(date: Optional[str] = None):
    """
    Obtiene los pedidos en estado 'Submitted' desde ERPNext
    y los mapea al formato requerido por WhatsApp /listado
    """
    try:
        orders = frappe_client.get_submitted_sales_orders(target_date=date)
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

from pydantic import BaseModel
from typing import List, Optional

class ProductoItem(BaseModel):
    item_code: str
    cantidad: float

class OrderPayload(BaseModel):
    remoteJid: str
    contactName: str
    fecha_hora_entrega: str
    productos: List[ProductoItem]
    monto_total: Optional[int] = 0

@app.post("/api/orders")
async def create_new_order(payload: OrderPayload):
    """
    Recibe la estructura del pedido extraída por la IA,
    crea el cliente si no existe y luego genera el Sales Order en ERPNext.
    """
    try:
        # 1. Obtener o crear Customer
        customer_id = frappe_client.get_or_create_customer(payload.contactName, payload.remoteJid)
        
        # 2. Transcribir productos a lista de diccionarios
        items = [{"item_code": p.item_code, "cantidad": p.cantidad} for p in payload.productos]
        
        # 3. Crear Sales Order
        order_name = frappe_client.create_sales_order(
            customer_id=customer_id,
            delivery_date_str=payload.fecha_hora_entrega,
            items=items
        )
        
        return {"success": True, "order_name": order_name, "customer": customer_id}
        
    except Exception as e:
        print(f"Error creating order: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/orders/{order_id}/deliver")
async def deliver_order(order_id: str):
    """
    Marca un pedido como entregado mediante la generación y validación de 
    un Delivery Note en ERPNext.
    """
    try:
        dn_name = frappe_client.mark_order_as_delivered(order_id)
        return {"success": True, "message": "Pedido entregado correctamente", "delivery_note": dn_name}
    except Exception as e:
        print(f"Error delivering order {order_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/orders/{order_id}/cancel")
async def cancel_order(order_id: str):
    """
    Cancela un pedido (docstatus: 2). Captura validaciones rigurosas 
    de ERPNext en caso de pagos bloqueantes.
    """
    try:
        frappe_client.cancel_sales_order(order_id)
        return {"success": True, "message": "Pedido cancelado correctamente"}
    except Exception as e:
        print(f"Error cancelling order {order_id}: {str(e)}")
        # Devuelve el mensaje de ERPNext para que el frontend/bot sepa por qué falló
        raise HTTPException(status_code=409, detail=str(e))

@app.post("/api/orders/replace_latest")
async def replace_latest_order(payload: OrderPayload):
    """
    Sustituye la última orden del cliente por los datos ingresados en el payload.
    Para ello, busca y anula silenciosamente el último SO, creando uno nuevo.
    """
    try:
        # 1. Obtener customer
        customer_id = frappe_client.get_or_create_customer(payload.contactName, payload.remoteJid)
        
        # 2. Cancelar el último pedido activo de este cliente
        last_order = frappe_client.get_latest_active_order(customer_id)
        if last_order:
            print(f"Cancelando última orden activa {last_order['name']} para reemplazo.")
            frappe_client.cancel_sales_order(last_order["name"])
            
        # 3. Crear el nuevo
        items = [{"item_code": p.item_code, "cantidad": p.cantidad} for p in payload.productos]
        new_order_name = frappe_client.create_sales_order(
            customer_id=customer_id,
            delivery_date_str=payload.fecha_hora_entrega,
            items=items
        )
        
        return {
            "success": True, 
            "order_name": new_order_name, 
            "cancelled_order": last_order["name"] if last_order else None
        }
    except Exception as e:
        print(f"Error replacing order: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
