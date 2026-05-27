from pydantic import BaseModel

class ExpensePayload(BaseModel):
    concept_account: str
    amount: float
    method: str = "efectivo"
    remark: str = "Registro de gasto"
