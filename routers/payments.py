from fastapi import APIRouter, HTTPException
from schemas.payment_schemas import PaymentPayload
from dependencies import payment_service, order_service

router = APIRouter()

@router.post("/{order_id}/pay")
async def pay_order(order_id: str, payload: PaymentPayload):
    resolved_order_id = order_id
    try:
        # Si no es un ID directo de Sales Order (ej. SAL-ORD-..., SALES-ORD-...), resolvemos por cliente
        upper_id = order_id.upper()
        is_sales_order = upper_id.startswith("SAL") or ("-" in order_id and not "@" in order_id and any(c.isalpha() for c in order_id) and any(c.isdigit() for c in order_id) and not any(m in order_id.lower() for m in ["cliente", "contact"]))
        if not is_sales_order:
            print(f"[pay_order] Identificador no es Sales Order ('{order_id}'), resolviendo cliente...")
            resolved_order_id = order_service.resolve_order_for_customer(order_id)
            print(f"[pay_order] '{order_id}' resuelto a orden: {resolved_order_id}")
        
        result = payment_service.register_payment(resolved_order_id, payload.amount, payload.method)
        result["order_id"] = resolved_order_id
        return result
    except Exception as e:
        print(f"Error registering payment for order {order_id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
