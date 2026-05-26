from fastapi import APIRouter, HTTPException
from dependencies import report_service

router = APIRouter()

@router.get("/summary")
async def get_sales_summary(date_from: str, date_to: str):
    try:
        return report_service.get_sales_summary(date_from, date_to)
    except Exception as e:
        print(f"Error en get_sales_summary: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al consultar ventas: {str(e)}")

@router.get("/by-product")
async def get_sales_by_product(date_from: str, date_to: str):
    try:
        return report_service.get_sales_by_product(date_from, date_to)
    except Exception as e:
        print(f"Error en get_sales_by_product: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al consultar ventas por producto: {str(e)}")
