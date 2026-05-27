import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    ERPNEXT_URL: str = os.getenv("ERPNEXT_URL", "http://localhost:8080")
    ERPNEXT_API_KEY: str = os.getenv("ERPNEXT_API_KEY", "")
    ERPNEXT_API_SECRET: str = os.getenv("ERPNEXT_API_SECRET", "")
    ACCOUNT_CASH: str = os.getenv("ACCOUNT_CASH", "1110 - Efectivo - Vz")
    ACCOUNT_BANK: str = os.getenv("ACCOUNT_BANK", "1212 - Ueno - Vz")

settings = Settings()
