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
        
        order_name = order_service.create_sales_order(
            customer_id=customer_id,
            delivery_date_str=payload.fecha_hora_entrega,
            items=items
        )
        
        return {"success": True, "order_name": order_name, "customer": customer_id}
        
    except Exception as e:
        print(f"Error creating order: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{order_id}/deliver")
async def deliver_order(order_id: str):
    try:
        dn_name = order_service.mark_order_as_delivered(order_id)
        return {"success": True, "message": "Pedido entregado correctamente", "delivery_note": dn_name}
    except Exception as e:
        print(f"Error delivering order {order_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

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
        new_order_name = order_service.create_sales_order(
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
