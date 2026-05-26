import requests
import json
from typing import List, Dict, Any
from .base_client import BaseFrappeClient

class PaymentService(BaseFrappeClient):
    # Mapa de cuentas por modo de pago (configuradas en ERPNext para la empresa Voraz)
    # Claves: nombre exacto del Mode of Payment en ERPNext
    # Valores: nombre exacto de la cuenta contable (Account)
    ACCOUNT_BY_MOP = {
        "Efectivo": "1110 - Efectivo - Vz",
        "Transferencia bancaria": "1212 - Ueno - Vz",
    }

    def register_payment(self, order_name: str, amount: float, method: str) -> Dict[str, Any]:
        """
        Registra un pago para una orden.
        Si la orden no tiene una factura (Sales Invoice), la genera primero.
        Luego genera el Payment Entry por el monto y método especificados.
        
        La cuenta destino (paid_to) se asigna según el modo de pago usando ACCOUNT_BY_MOP.
        Para Transferencia bancaria se generan automáticamente reference_no y reference_date.
        """
        from datetime import datetime
        
        # 1. Buscar si ya existe una factura (Sales Invoice) para esta orden
        api_url_si = f"{self.url}/api/resource/Sales Invoice"
        params_si = {
            "filters": json.dumps([
                ["Sales Invoice Item", "sales_order", "=", order_name],
                ["docstatus", "=", 1]
            ]),
            "fields": '["name", "outstanding_amount", "status"]'
        }
        
        si_name = None
        try:
            res_si = requests.get(api_url_si, headers=self.headers, params=params_si)
            res_si.raise_for_status()
            invoices = res_si.json().get("data", [])
            
            # Buscamos una factura que aún tenga saldo pendiente
            for inv in invoices:
                if float(inv.get("outstanding_amount", 0)) > 0:
                    si_name = inv["name"]
                    break
            
            # Si hay facturas pero todas están pagadas
            if invoices and not si_name:
                raise Exception("El pedido ya está completamente pagado o facturado.")
                
        except Exception as e:
            if "completamente pagado" in str(e):
                raise
            print(f"Error buscando facturas para {order_name}: {str(e)}")

        # 2. Si no hay factura con saldo pendiente, generamos una nueva desde la orden
        if not si_name:
            try:
                make_si_url = f"{self.url}/api/method/erpnext.selling.doctype.sales_order.sales_order.make_sales_invoice"
                res_make_si = requests.post(make_si_url, headers=self.headers, json={"source_name": order_name})
                res_make_si.raise_for_status()
                si_doc = res_make_si.json().get("message", {})
                
                if not si_doc.get("items"):
                    raise Exception("No hay artículos pendientes de facturar en esta orden.")
                    
                # Guardar la factura
                res_post_si = requests.post(api_url_si, headers=self.headers, json=si_doc)
                if res_post_si.status_code != 200:
                    print("Error al crear Sales Invoice:", res_post_si.text)
                res_post_si.raise_for_status()
                si_name = res_post_si.json()["data"]["name"]
                
                # Someter la factura
                res_submit_si = requests.put(f"{api_url_si}/{si_name}", headers=self.headers, json={"docstatus": 1})
                res_submit_si.raise_for_status()
                
            except Exception as e:
                print(f"Error generando Sales Invoice para {order_name}: {str(e)}")
                raise Exception(f"Error al generar la factura: {str(e)}")

        # 3. Generar el Payment Entry a partir de la factura
        try:
            make_pe_url = f"{self.url}/api/method/erpnext.accounts.doctype.payment_entry.payment_entry.get_payment_entry"
            res_make_pe = requests.post(make_pe_url, headers=self.headers, json={"dt": "Sales Invoice", "dn": si_name})
            res_make_pe.raise_for_status()
            pe_doc = res_make_pe.json().get("message", {})
            
            # Determinar modo de pago y cuenta destino
            mop = "Transferencia bancaria" if method.lower() in ("transferencia", "transf", "banco") else "Efectivo"
            pe_doc["mode_of_payment"] = mop
            
            # Asignar cuenta destino correcta según el modo de pago
            # Esto es necesario porque get_payment_entry devuelve una cuenta genérica
            # que no coincide con la configurada para el modo de pago, causando error 417.
            if mop in self.ACCOUNT_BY_MOP:
                pe_doc["paid_to"] = self.ACCOUNT_BY_MOP[mop]
            
            if amount > 0:
                pe_doc["paid_amount"] = amount
                pe_doc["received_amount"] = amount
                pe_doc["base_paid_amount"] = amount
                pe_doc["base_received_amount"] = amount
                
                allocated_total = 0
                for ref in pe_doc.get("references", []):
                    outstanding = float(ref.get("outstanding_amount", 0))
                    to_allocate = min(amount - allocated_total, outstanding)
                    ref["allocated_amount"] = to_allocate
                    allocated_total += to_allocate
                pe_doc["unallocated_amount"] = max(0, amount - allocated_total)
                
            if mop == "Transferencia bancaria":
                pe_doc["reference_no"] = f"REF-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                pe_doc["reference_date"] = datetime.now().strftime("%Y-%m-%d")
                
            # Guardar el Payment Entry
            api_url_pe = f"{self.url}/api/resource/Payment Entry"
            res_post_pe = requests.post(api_url_pe, headers=self.headers, json=pe_doc)
            if res_post_pe.status_code != 200:
                print("Error al crear Payment Entry:", res_post_pe.text)
            res_post_pe.raise_for_status()
            pe_name = res_post_pe.json()["data"]["name"]
            
            # Someter el Payment Entry
            res_submit_pe = requests.put(f"{api_url_pe}/{pe_name}", headers=self.headers, json={"docstatus": 1})
            res_submit_pe.raise_for_status()
            
            return {
                "success": True,
                "payment_entry": pe_name,
                "sales_invoice": si_name
            }
            
        except Exception as e:
            print(f"Error registrando Payment Entry para {si_name}: {str(e)}")
            raise Exception(f"Error al registrar el pago: {str(e)}")

