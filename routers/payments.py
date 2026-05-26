from fastapi import APIRouter, HTTPException
from schemas.payment_schemas import PaymentPayload
from dependencies import payment_service, order_service

router = APIRouter()

@router.post("/{order_id}/pay")
async def pay_order(order_id: str, payload: PaymentPayload):
    resolved_order_id = order_id
    try:
        if "@" in order_id:
            print(f"[pay_order] Detectado JID '{order_id}', resolviendo último pedido activo...")
            resolved_order_id = order_service.resolve_order_for_customer(order_id)
            print(f"[pay_order] JID '{order_id}' resuelto a orden: {resolved_order_id}")
        
        result = payment_service.register_payment(resolved_order_id, payload.amount, payload.method)
        result["order_id"] = resolved_order_id
        return result
    except Exception as e:
        print(f"Error registering payment for order {order_id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
