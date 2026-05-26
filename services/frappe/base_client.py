import requests

class BaseFrappeClient:
    def __init__(self, url: str, api_key: str, api_secret: str):
        self.url = url.rstrip("/")
        self.headers = {}
        if api_key and api_secret:
            self.headers["Authorization"] = f"token {api_key}:{api_secret}"
            self.headers["Accept"] = "application/json"
            self.headers["Content-Type"] = "application/json"
