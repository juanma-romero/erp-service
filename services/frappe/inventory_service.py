import json
import requests
from typing import Dict, Any, List
from .base_client import BaseFrappeClient


class InventoryService(BaseFrappeClient):
    def get_top_items(self, limit: int = 5) -> Dict[str, Any]:
        """
        Consulta en ERPNext el Top de insumos por valor y el inventario total.
        """
        api_method_url = f"{self.url}/api/method/frappe.client.get_list"

        # 1. Consulta agregada del Top N de insumos ordenados por valor desc
        params = {
            "doctype": "Bin",
            "filters": json.dumps([["actual_qty", "!=", 0]]),
            "fields": json.dumps([
                "item_code",
                {"SUM": "actual_qty", "as": "qty"},
                {"SUM": "stock_value", "as": "valor"},
            ]),
            "group_by": "item_code",
            "order_by": "valor desc",
            "limit_page_length": limit,
        }

        res = requests.get(api_method_url, headers=self.headers, params=params)
        res.raise_for_status()
        raw_items = res.json().get("message")
        if raw_items is None:
            raw_items = res.json().get("data", [])
        raw_items = raw_items or []

        # 2. Consulta agregada del total de inventario (sin group_by ni limit)
        total_params = {
            "doctype": "Bin",
            "filters": json.dumps([["actual_qty", "!=", 0]]),
            "fields": json.dumps([
                {"SUM": "stock_value", "as": "total"},
            ]),
        }

        res_total = requests.get(api_method_url, headers=self.headers, params=total_params)
        res_total.raise_for_status()
        raw_total = res_total.json().get("message")
        if raw_total is None:
            raw_total = res_total.json().get("data", [])
        raw_total = raw_total or []

        total_inventario = 0.0
        if raw_total and isinstance(raw_total, list) and len(raw_total) > 0:
            first_row = raw_total[0]
            if isinstance(first_row, dict):
                total_inventario = float(first_row.get("total") or 0.0)
        total_inventario = round(total_inventario, 2)

        # 3. Traer nombres legibles y UOM de los códigos del top
        item_codes = [it.get("item_code") for it in raw_items if it.get("item_code")]
        name_map = {}
        uom_map = {}

        if item_codes:
            item_url = f"{self.url}/api/resource/Item"
            item_params = {
                "filters": json.dumps([["name", "in", item_codes]]),
                "fields": json.dumps(["name", "item_name", "stock_uom"]),
                "limit_page_length": len(item_codes),
            }
            res_items = requests.get(item_url, headers=self.headers, params=item_params)
            res_items.raise_for_status()
            items_data = res_items.json().get("data", [])

            for item in items_data:
                code = item.get("name")
                if code:
                    name_map[code] = item.get("item_name") or code
                    if item.get("stock_uom"):
                        uom_map[code] = item.get("stock_uom")

            # Fallback opcional para uom desde Bin si algún ítem no trajo stock_uom
            missing_uom = [c for c in item_codes if not uom_map.get(c)]
            if missing_uom:
                try:
                    bin_params = {
                        "doctype": "Bin",
                        "filters": json.dumps([["item_code", "in", missing_uom]]),
                        "fields": json.dumps(["item_code", "stock_uom"]),
                        "limit_page_length": len(missing_uom),
                    }
                    res_bin = requests.get(api_method_url, headers=self.headers, params=bin_params)
                    res_bin.raise_for_status()
                    bin_data = res_bin.json().get("message") or res_bin.json().get("data", [])
                    for b in bin_data:
                        c = b.get("item_code")
                        if c and b.get("stock_uom"):
                            uom_map[c] = b.get("stock_uom")
                except Exception as e:
                    print(f"Advertencia al consultar stock_uom en Bin: {e}")

        # 4. Calcular métricas por ítem
        items = []
        for it in raw_items:
            code = it.get("item_code", "")
            qty = float(it.get("qty") or 0.0)
            valor = float(it.get("valor") or 0.0)
            valuation_rate = round(valor / qty, 2) if qty != 0 else 0.0
            porcentaje = round((valor / total_inventario) * 100, 2) if total_inventario > 0 else 0.0
            item_name = name_map.get(code, code)
            uom = uom_map.get(code, "")

            items.append({
                "item_code": code,
                "item_name": item_name,
                "qty": qty,
                "uom": uom,
                "valuation_rate": valuation_rate,
                "valor": valor,
                "porcentaje": porcentaje,
            })

        return {
            "total_inventario": total_inventario,
            "items": items,
        }
