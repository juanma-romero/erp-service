import requests
from typing import List, Dict, Any

class FrappeClient:
    def __init__(self, url: str, api_key: str, api_secret: str):
        self.url = url.rstrip("/")
        self.api_key = api_key
        self.api_secret = api_secret
        self.headers = {}
        
        if self.api_key and self.api_secret:
            self.headers["Authorization"] = f"token {self.api_key}:{self.api_secret}"
            self.headers["Accept"] = "application/json"
            self.headers["Content-Type"] = "application/json"

    def get_submitted_sales_orders(self) -> List[Dict[str, Any]]:
        """
        Consulta Sales Orders cuyo docstatus sea 1 (Submitted) 
        y no estén completamente facturadas/entregadas (status pendiente).
        """
        api_url = f"{self.url}/api/resource/Sales Order"
        
        # docstatus = 1 es Submitted
        # status en ERPNext: 
        # 'To Deliver' (facturado pero no entregado, ej pago anticipado).
        # 'To Deliver and Bill' (ni entregado ni facturado).
        params = {
            "filters": '[["status", "in", ["To Deliver", "To Deliver and Bill"]]]',
            "fields": '["name", "customer", "customer_name", "delivery_date", "custom_dia_y_hora_entrega", "transaction_date", "grand_total"]',
            "limit_page_length": 20,
            "order_by": "custom_dia_y_hora_entrega asc"
        }
        
        try:
            response = requests.get(api_url, headers=self.headers, params=params)
            response.raise_for_status()
            data = response.json().get("data", [])
            
            # Frappe API doclist no devuelve las tablas hijas (items). 
            # Traemos el detalle full de cada una.
            detailed_orders = []
            for order in data:
                detailed_order = self.get_sales_order(order["name"])
                if detailed_order:
                    detailed_orders.append(detailed_order)
            
            return detailed_orders
            
        except requests.exceptions.RequestException as e:
            print(f"FrappeClient Error HTTP: {str(e)}")
            raise
            
    def get_sales_order(self, order_name: str) -> Dict[str, Any]:
        """
        Obtiene el detalle completo de un Sales Order incluyendo sus items.
        """
        api_url = f"{self.url}/api/resource/Sales Order/{order_name}"
        try:
            response = requests.get(api_url, headers=self.headers)
            response.raise_for_status()
            return response.json().get("data", {})
        except requests.exceptions.RequestException as e:
            print(f"FrappeClient Error HTTP getting {order_name}: {str(e)}")
            return {}
