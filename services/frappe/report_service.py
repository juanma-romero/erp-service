import requests
import json
from .base_client import BaseFrappeClient

class ReportService(BaseFrappeClient):
    def get_sales_summary(self, date_from: str, date_to: str):
        api_url = f"{self.url}/api/resource/Sales Order"
        filters_list = [
            ["docstatus", "=", 1],
            ["transaction_date", ">=", date_from],
            ["transaction_date", "<=", date_to],
        ]
        params = {
            "filters": json.dumps(filters_list),
            "fields": '["name", "grand_total", "transaction_date", "customer_name"]',
            "limit_page_length": 500,
        }
        response = requests.get(api_url, headers=self.headers, params=params)
        response.raise_for_status()
        orders = response.json().get("data", [])

        total_gs = sum(float(o.get("grand_total", 0)) for o in orders)
        total_pedidos = len(orders)
        promedio = round(total_gs / total_pedidos) if total_pedidos > 0 else 0

        return {
            "periodo": {"desde": date_from, "hasta": date_to},
            "total_gs": round(total_gs),
            "total_pedidos": total_pedidos,
            "promedio_por_pedido_gs": promedio,
        }

    def get_sales_by_product(self, date_from: str, date_to: str):
        api_url = f"{self.url}/api/resource/Sales Order"
        filters_list = [
            ["docstatus", "=", 1],
            ["transaction_date", ">=", date_from],
            ["transaction_date", "<=", date_to],
        ]
        params = {
            "filters": json.dumps(filters_list),
            "fields": '["name"]',
            "limit_page_length": 500,
        }
        response = requests.get(api_url, headers=self.headers, params=params)
        response.raise_for_status()
        orders = response.json().get("data", [])

        if not orders:
            return {"periodo": {"desde": date_from, "hasta": date_to}, "productos": []}

        product_totals = {}
        items_api_url = f"{self.url}/api/resource/Sales Order Item"
        order_names = [o["name"] for o in orders]

        items_filters = [
            ["parent", "in", order_names],
        ]
        items_params = {
            "filters": json.dumps(items_filters),
            "fields": '["item_code", "item_name", "qty", "amount"]',
            "limit_page_length": 2000,
        }
        items_response = requests.get(items_api_url, headers=self.headers, params=items_params)
        items_response.raise_for_status()
        items = items_response.json().get("data", [])

        for item in items:
            code = item.get("item_code", "?")
            if code not in product_totals:
                product_totals[code] = {
                    "item_code": code,
                    "item_name": item.get("item_name", code),
                    "cantidad_total": 0,
                    "monto_total_gs": 0,
                }
            product_totals[code]["cantidad_total"] += float(item.get("qty", 0))
            product_totals[code]["monto_total_gs"] += float(item.get("amount", 0))

        sorted_products = sorted(
            product_totals.values(),
            key=lambda x: x["cantidad_total"],
            reverse=True
        )

        for p in sorted_products:
            p["cantidad_total"] = round(p["cantidad_total"], 2)
            p["monto_total_gs"] = round(p["monto_total_gs"])

        return {
            "periodo": {"desde": date_from, "hasta": date_to},
            "total_ordenes_analizadas": len(orders),
            "productos": sorted_products,
        }
