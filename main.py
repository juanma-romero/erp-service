import os
import json
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


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINTS DE INFORMES — usados por el Agente IA
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/sales/summary")
async def get_sales_summary(date_from: str, date_to: str):
    """
    Resumen de ventas entre dos fechas (YYYY-MM-DD).
    Devuelve: total_gs, total_pedidos, promedio_por_pedido.
    Consumido por el agente IA para responder consultas de ventas generales.
    """
    try:
        api_url = f"{frappe_client.url}/api/resource/Sales Order"
        filters_list = [
            ["docstatus", "=", 1],
            ["transaction_date", ">=", date_from],
            ["transaction_date", "<=", date_to],
        ]
        params = {
            "filters": json.dumps(filters_list),
            "fields": '["name", "grand_total", "transaction_date", "customer_name"]',
            "limit_page_length": 500,
        }
        import requests as req
        response = req.get(api_url, headers=frappe_client.headers, params=params)
        response.raise_for_status()
        orders = response.json().get("data", [])

        total_gs = sum(float(o.get("grand_total", 0)) for o in orders)
        total_pedidos = len(orders)
        promedio = round(total_gs / total_pedidos) if total_pedidos > 0 else 0

        return {
            "periodo": {"desde": date_from, "hasta": date_to},
            "total_gs": round(total_gs),
            "total_pedidos": total_pedidos,
            "promedio_por_pedido_gs": promedio,
        }

    except Exception as e:
        print(f"Error en get_sales_summary: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al consultar ventas: {str(e)}")


@app.get("/api/sales/by-product")
async def get_sales_by_product(date_from: str, date_to: str):
    """
    Detalle de ventas desagregado por producto entre dos fechas (YYYY-MM-DD).
    Devuelve lista ordenada por cantidad vendida.
    Consumido por el agente IA para responder consultas de productos más vendidos.
    """
    try:
        import requests as req

        # 1. Traer los Sales Orders del período
        api_url = f"{frappe_client.url}/api/resource/Sales Order"
        filters_list = [
            ["docstatus", "=", 1],
            ["transaction_date", ">=", date_from],
            ["transaction_date", "<=", date_to],
        ]
        params = {
            "filters": json.dumps(filters_list),
            "fields": '["name"]',
            "limit_page_length": 500,
        }
        response = req.get(api_url, headers=frappe_client.headers, params=params)
        response.raise_for_status()
        orders = response.json().get("data", [])

        if not orders:
            return {"periodo": {"desde": date_from, "hasta": date_to}, "productos": []}

        # 2. Agregar cantidades por producto usando la Sales Order Items API
        product_totals: dict = {}
        items_api_url = f"{frappe_client.url}/api/resource/Sales Order Item"
        order_names = [o["name"] for o in orders]

        items_filters = [
            ["parent", "in", order_names],
        ]
        items_params = {
            "filters": json.dumps(items_filters),
            "fields": '["item_code", "item_name", "qty", "amount"]',
            "limit_page_length": 2000,
        }
        items_response = req.get(items_api_url, headers=frappe_client.headers, params=items_params)
        items_response.raise_for_status()
        items = items_response.json().get("data", [])

        for item in items:
            code = item.get("item_code", "?")
            if code not in product_totals:
                product_totals[code] = {
                    "item_code": code,
                    "item_name": item.get("item_name", code),
                    "cantidad_total": 0,
                    "monto_total_gs": 0,
                }
            product_totals[code]["cantidad_total"] += float(item.get("qty", 0))
            product_totals[code]["monto_total_gs"] += float(item.get("amount", 0))

        # Ordenar por cantidad descendente
        sorted_products = sorted(
            product_totals.values(),
            key=lambda x: x["cantidad_total"],
            reverse=True
        )

        # Redondear montos
        for p in sorted_products:
            p["cantidad_total"] = round(p["cantidad_total"], 2)
            p["monto_total_gs"] = round(p["monto_total_gs"])

        return {
            "periodo": {"desde": date_from, "hasta": date_to},
            "total_ordenes_analizadas": len(orders),
            "productos": sorted_products,
        }

    except Exception as e:
        print(f"Error en get_sales_by_product: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al consultar ventas por producto: {str(e)}")

