import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    ERPNEXT_URL: str = os.getenv("ERPNEXT_URL", "http://localhost:8080")
    ERPNEXT_API_KEY: str = os.getenv("ERPNEXT_API_KEY", "")
    ERPNEXT_API_SECRET: str = os.getenv("ERPNEXT_API_SECRET", "")

settings = Settings()
