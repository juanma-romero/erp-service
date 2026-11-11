from fastapi import APIRouter, HTTPException
from dependencies import inventory_service

router = APIRouter()

@router.get("/top-items")
async def get_top_items(limit: int = 5):
    try:
        return inventory_service.get_top_items(limit)
    except Exception as e:
        print(f"Error en get_top_items: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al consultar inventario: {str(e)}")
