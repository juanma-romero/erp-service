import calendar
import json
import os
import urllib.parse
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

from .base_client import BaseFrappeClient

# Directorio con los meses cerrados pre-procesados (ventas_YYYY-MM.json).
VENTAS_CACHE_DIR = Path(os.getenv("VENTAS_CACHE_DIR", "/app/data/contabilidad"))

# Paraguay: UTC-3 todo el año (sin horario de verano desde oct-2024).
_PY_TZ = timezone(timedelta(hours=-3))


def _hoy() -> date:
    return datetime.now(_PY_TZ).date()


def _is_delivery(item: dict) -> bool:
    return item.get("item_code") == "deli" or item.get("item_group") == "Services"


class ReportService(BaseFrappeClient):
    # ------------------------------------------------------------------
    # Resumen de ventas por Delivery Note (sin cambios)
    # ------------------------------------------------------------------
    def get_sales_summary(self, date_from: str, date_to: str):
        api_url = f"{self.url}/api/resource/Delivery Note"
        filters_list = [
            ["docstatus", "=", 1],
            ["posting_date", ">=", date_from],
            ["posting_date", "<=", date_to],
        ]
        params = {
            "filters": json.dumps(filters_list),
            "fields": '["name", "grand_total", "posting_date", "customer_name"]',
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

    # ------------------------------------------------------------------
    # Núcleo: agregación en vivo desde ERPNext (Sales Order por delivery_date)
    # ------------------------------------------------------------------
    def aggregate_period_live(self, date_from: str, date_to: str) -> dict:
        """Consulta ERPNext y devuelve datos crudos agregados por día.

        {
          "ordenes": int,
          "diario": {fecha: {fecha, pedidos, bruto_gs, delivery_gs, neto_gs}},
          "productos_por_dia": {fecha: {item_code: {item_name, cantidad, monto_gs}}}
        }
        Es la única función que toca ERPNext; el script de meses cerrados la reutiliza.
        """
        api_url = f"{self.url}/api/resource/Sales Order"
        filters_list = [
            ["docstatus", "=", 1],
            ["delivery_date", ">=", date_from],
            ["delivery_date", "<=", date_to],
        ]
        params = {
            "filters": json.dumps(filters_list),
            "fields": '["name", "delivery_date"]',
            "limit_page_length": 0,  # sin tope (ERPNext trunca en 20 por defecto)
        }
        response = requests.get(api_url, headers=self.headers, params=params)
        response.raise_for_status()
        orders = response.json().get("data", [])

        diario: dict = {}
        productos_por_dia: dict = {}
        ordenes = 0

        for order in orders:
            d_date = order.get("delivery_date", "")
            try:
                o_detail_url = f"{self.url}/api/resource/Sales Order/{urllib.parse.quote(order['name'])}"
                res = requests.get(o_detail_url, headers=self.headers)
                res.raise_for_status()
                o_data = res.json().get("data", {})
            except Exception:
                continue

            ordenes += 1
            items = o_data.get("items", [])
            deli_amount = sum(float(i.get("amount", 0)) for i in items if _is_delivery(i))
            grand_total = float(o_data.get("grand_total", 0))

            dia = diario.setdefault(
                d_date,
                {"fecha": d_date, "pedidos": 0, "bruto_gs": 0.0, "delivery_gs": 0.0, "neto_gs": 0.0},
            )
            dia["pedidos"] += 1
            dia["bruto_gs"] += grand_total
            dia["delivery_gs"] += deli_amount
            dia["neto_gs"] += grand_total - deli_amount

            prods = productos_por_dia.setdefault(d_date, {})
            for item in items:
                if _is_delivery(item):
                    continue
                code = item.get("item_code", "?")
                p = prods.setdefault(
                    code,
                    {"item_name": item.get("item_name", code), "cantidad": 0.0, "monto_gs": 0.0},
                )
                p["cantidad"] += float(item.get("qty", 0))
                p["monto_gs"] += float(item.get("amount", 0))

        return {"ordenes": ordenes, "diario": diario, "productos_por_dia": productos_por_dia}

    # ------------------------------------------------------------------
    # Caché de meses cerrados + fusión
    # ------------------------------------------------------------------
    @staticmethod
    def _cache_path(year: int, month: int) -> Path:
        return VENTAS_CACHE_DIR / f"ventas_{year:04d}-{month:02d}.json"

    @staticmethod
    def _load_closed_month(year: int, month: int):
        """Lee el JSON congelado de un mes cerrado. None si no existe o está corrupto."""
        try:
            with open(ReportService._cache_path(year, month), encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, ValueError, OSError):
            return None

    @staticmethod
    def _split_months(d_from: date, d_to: date):
        """Parte [d_from, d_to] en tramos (year, month, desde, hasta) por mes calendario."""
        cursor = d_from
        while cursor <= d_to:
            last_day = calendar.monthrange(cursor.year, cursor.month)[1]
            seg_to = min(d_to, date(cursor.year, cursor.month, last_day))
            yield cursor.year, cursor.month, cursor, seg_to
            cursor = seg_to + timedelta(days=1)

    def _collect(self, date_from: str, date_to: str) -> dict:
        """Junta datos diarios/productos del rango: disco para meses cerrados, vivo para el resto."""
        d_from = date.fromisoformat(date_from)
        d_to = date.fromisoformat(date_to)
        mes_actual = _hoy().replace(day=1)

        diario: dict = {}
        productos_por_dia: dict = {}
        ordenes = 0
        usados_cache = usados_vivo = 0
        live_ranges = []  # tramos a pedir a ERPNext (se consolidan contiguos)

        for year, month, seg_from, seg_to in self._split_months(d_from, d_to):
            cerrado = date(year, month, 1) < mes_actual
            cache = self._load_closed_month(year, month) if cerrado else None
            if cache is None:
                live_ranges.append((seg_from, seg_to))
                continue

            usados_cache += 1
            f_iso, t_iso = seg_from.isoformat(), seg_to.isoformat()
            for fecha, dia in cache.get("diario_por_fecha", {}).items():
                if f_iso <= fecha <= t_iso:
                    diario[fecha] = dict(dia)
                    ordenes += dia.get("pedidos", 0)
            for fecha, prods in cache.get("productos_por_dia", {}).items():
                if f_iso <= fecha <= t_iso:
                    productos_por_dia[fecha] = {k: dict(v) for k, v in prods.items()}

        # Consolidar tramos vivos contiguos para minimizar llamadas a ERPNext
        merged = []
        for a, b in live_ranges:
            if merged and merged[-1][1] + timedelta(days=1) == a:
                merged[-1] = (merged[-1][0], b)
            else:
                merged.append((a, b))
        for a, b in merged:
            usados_vivo += 1
            live = self.aggregate_period_live(a.isoformat(), b.isoformat())
            ordenes += live["ordenes"]
            diario.update(live["diario"])
            productos_por_dia.update(live["productos_por_dia"])

        if usados_cache and usados_vivo:
            fuente = "mixto"
        elif usados_cache:
            fuente = "cache"
        else:
            fuente = "vivo"
        return {
            "ordenes": ordenes,
            "diario": diario,
            "productos_por_dia": productos_por_dia,
            "fuente": fuente,
        }

    # ------------------------------------------------------------------
    # Endpoints públicos (mismo contrato de respuesta que antes, + "fuente")
    # ------------------------------------------------------------------
    def get_net_sales_summary(self, date_from: str, date_to: str):
        """Venta bruta, delivery y venta neta por fecha de entrega (Sales Order delivery_date).

        Meses cerrados: se leen del JSON pre-procesado. Mes en curso: ERPNext en vivo.
        """
        data = self._collect(date_from, date_to)
        diario = [data["diario"][k] for k in sorted(data["diario"])]
        for d in diario:
            d["bruto_gs"] = round(d["bruto_gs"])
            d["delivery_gs"] = round(d["delivery_gs"])
            d["neto_gs"] = round(d["neto_gs"])

        total_pedidos = sum(d["pedidos"] for d in diario)
        total_bruto = sum(d["bruto_gs"] for d in diario)
        total_delivery = sum(d["delivery_gs"] for d in diario)
        total_neto = sum(d["neto_gs"] for d in diario)
        promedio_neto = round(total_neto / total_pedidos) if total_pedidos > 0 else 0

        return {
            "periodo": {"desde": date_from, "hasta": date_to},
            "fuente": data["fuente"],
            "total_pedidos": total_pedidos,
            "total_bruto_gs": total_bruto,
            "total_delivery_gs": total_delivery,
            "total_neto_gs": total_neto,
            "promedio_neto_por_pedido_gs": promedio_neto,
            "canales": [
                {
                    "canal": "WhatsApp",
                    "porcentaje": 100,
                    "neto_gs": total_neto,
                    "estado": "Activo",
                },
                {
                    "canal": "Otros / Web / Local",
                    "porcentaje": 0,
                    "neto_gs": 0,
                    "estado": "Pendiente: Identificar canal de venta",
                },
            ],
            "diario": diario,
        }

    def get_sales_by_product(self, date_from: str, date_to: str):
        data = self._collect(date_from, date_to)
        if not data["ordenes"]:
            return {
                "periodo": {"desde": date_from, "hasta": date_to},
                "fuente": data["fuente"],
                "productos": [],
            }

        totals: dict = {}
        for prods in data["productos_por_dia"].values():
            for code, p in prods.items():
                t = totals.setdefault(
                    code,
                    {"item_code": code, "item_name": p["item_name"], "cantidad_total": 0.0, "monto_total_gs": 0.0},
                )
                t["cantidad_total"] += p["cantidad"]
                t["monto_total_gs"] += p["monto_gs"]

        sorted_products = sorted(totals.values(), key=lambda x: x["cantidad_total"], reverse=True)
        for p in sorted_products:
            p["cantidad_total"] = round(p["cantidad_total"], 2)
            p["monto_total_gs"] = round(p["monto_total_gs"])

        return {
            "periodo": {"desde": date_from, "hasta": date_to},
            "fuente": data["fuente"],
            "total_ordenes_analizadas": data["ordenes"],
            "productos": sorted_products,
        }
