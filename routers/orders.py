from fastapi import APIRouter, HTTPException
from typing import Optional
from schemas.order_schemas import OrderPayload
from dependencies import order_service, customer_service

router = APIRouter()

@router.get("/pending")
async def get_pending_orders(date: Optional[str] = None):
    try:
        orders = order_service.get_submitted_sales_orders(target_date=date)
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

@router.post("")
async def create_new_order(payload: OrderPayload):
    try:
        customer_id = customer_service.get_or_create_customer(payload.contactName, payload.remoteJid)
        
        items = [{"item_code": p.item_code, "cantidad": p.cantidad} for p in payload.productos]
        
        order_result = order_service.create_sales_order(
            customer_id=customer_id,
            delivery_date_str=payload.fecha_hora_entrega,
            items=items
        )
        
        return {
            "success": True, 
            "order_name": order_result["order_name"], 
            "grand_total": order_result["grand_total"],
            "customer": customer_id
        }
        
    except Exception as e:
        print(f"Error creating order: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{order_id}/deliver")
async def deliver_order(order_id: str):
    try:
        # Si no es un ID directo de Sales Order (ej. SAL-ORD-...), resolvemos por cliente (JID/teléfono/nombre)
        resolved_order_id = order_id
        upper_id = order_id.upper()
        is_sales_order = upper_id.startswith("SAL") or ("-" in order_id and not "@" in order_id and any(c.isalpha() for c in order_id) and any(c.isdigit() for c in order_id) and not any(m in order_id.lower() for m in ["cliente", "contact"]))
        if not is_sales_order:
            print(f"[deliver_order] Identificador no es Sales Order ('{order_id}'), resolviendo cliente...")
            resolved_order_id = order_service.resolve_order_for_customer(order_id)
            print(f"[deliver_order] '{order_id}' resuelto a orden: {resolved_order_id}")

        dn_name = order_service.mark_order_as_delivered(resolved_order_id)
        return {"success": True, "order_id": resolved_order_id, "message": "Pedido entregado correctamente", "delivery_note": dn_name}
    except Exception as e:
        print(f"Error delivering order {order_id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{order_id}/cancel")
async def cancel_order(order_id: str):
    try:
        order_service.cancel_sales_order(order_id)
        return {"success": True, "message": "Pedido cancelado correctamente"}
    except Exception as e:
        print(f"Error cancelling order {order_id}: {str(e)}")
        raise HTTPException(status_code=409, detail=str(e))

@router.post("/replace_latest")
async def replace_latest_order(payload: OrderPayload):
    try:
        customer_id = customer_service.get_or_create_customer(payload.contactName, payload.remoteJid)
        
        last_order = order_service.get_latest_active_order(customer_id)
        if last_order:
            print(f"Cancelando última orden activa {last_order['name']} para reemplazo.")
            order_service.cancel_sales_order(last_order["name"])
            
        items = [{"item_code": p.item_code, "cantidad": p.cantidad} for p in payload.productos]
        order_result = order_service.create_sales_order(
            customer_id=customer_id,
            delivery_date_str=payload.fecha_hora_entrega,
            items=items
        )
        
        return {
            "success": True, 
            "order_name": order_result["order_name"], 
            "grand_total": order_result["grand_total"],
            "cancelled_order": last_order["name"] if last_order else None
        }
    except Exception as e:
        print(f"Error replacing order: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
