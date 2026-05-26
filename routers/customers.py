from fastapi import APIRouter, HTTPException
from schemas.customer_schemas import CustomerSyncPayload
from dependencies import customer_service

router = APIRouter()

@router.post("/sync")
async def sync_customer(payload: CustomerSyncPayload):
    try:
        customer_id = customer_service.get_or_create_customer(payload.contactName, payload.remoteJid)
        return {"success": True, "customer": customer_id}
    except Exception as e:
        print(f"Error syncing customer: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
