from fastapi import APIRouter, HTTPException
from schemas.accounting_schemas import ExpensePayload
from dependencies import accounting_service

router = APIRouter()

@router.post("/expense")
async def create_expense(payload: ExpensePayload):
    try:
        result = accounting_service.create_journal_entry(
            concept_account=payload.concept_account,
            amount=payload.amount,
            method=payload.method,
            remark=payload.remark
        )
        return result
    except Exception as e:
        print(f"Error registering expense: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
