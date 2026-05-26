from pydantic import BaseModel

class PaymentPayload(BaseModel):
    amount: float = 0
    method: str = "efectivo"
