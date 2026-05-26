from pydantic import BaseModel

class CustomerSyncPayload(BaseModel):
    remoteJid: str
    contactName: str
