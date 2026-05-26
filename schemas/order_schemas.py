from pydantic import BaseModel
from typing import List, Optional

class ProductoItem(BaseModel):
    item_code: str
    cantidad: float

class OrderPayload(BaseModel):
    remoteJid: str
    contactName: str
    fecha_hora_entrega: str
    productos: List[ProductoItem]
    #monto_total: Optional[int] = 0
