import requests
import json
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
from .base_client import BaseFrappeClient

class OrderService(BaseFrappeClient):
    def get_submitted_sales_orders(self, target_date: str = None) -> List[Dict[str, Any]]:
        """
        Consulta Sales Orders cuyo docstatus sea 1 (Submitted) 
        y no estén completamente facturadas/entregadas (status pendiente).
        """
        api_url = f"{self.url}/api/resource/Sales Order"
        
        # docstatus = 1 es Submitted
        # status en ERPNext: 
        # 'To Deliver' (facturado pero no entregado, ej pago anticipado).
        # 'To Deliver and Bill' (ni entregado ni facturado).
        filters_list = [["status", "in", ["To Deliver", "To Deliver and Bill"]]]
        if target_date:
            filters_list.append(["delivery_date", "=", target_date])
            
        params = {
            "filters": json.dumps(filters_list),
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

    def create_sales_order(self, customer_id: str, delivery_date_str: str, items: List[Dict]) -> str:
        """
        Crea el Sales Order con los productos mapeados y lo envía como Submitted.
        """
        api_url = f"{self.url}/api/resource/Sales Order"
        
        # Mapear a la estructura de items de Frappe
        frappe_items = []
        for item in items:
            frappe_items.append({
                "item_code": item["item_code"],
                "qty": float(item["cantidad"])
            })
            
        # Extraer fecha corta para la obligatoria de entrega y fecha actual en Paraguay
        tz_py = timezone(timedelta(hours=-3))
        today_py = datetime.now(tz_py).strftime("%Y-%m-%d")
        short_date = delivery_date_str.split(" ")[0] if delivery_date_str else today_py
        
        new_order = {
            "customer": customer_id,
            "transaction_date": today_py,
            "delivery_date": short_date,
            "custom_dia_y_hora_entrega": delivery_date_str,
            "items": frappe_items,
            "docstatus": 0 # Siempre crear en Draft primero
        }
        
        try:
            res = requests.post(api_url, headers=self.headers, json=new_order)
            if res.status_code != 200:
                print("Error de ERPNext al crear orden:", res.text)
            res.raise_for_status()
            
            order_name = res.json()["data"]["name"]
            
            # 2. Someter la orden para que cambie de estado oficialmente a 'To Deliver and Bill'
            submit_url = f"{api_url}/{order_name}"
            res_submit = requests.put(submit_url, headers=self.headers, json={"docstatus": 1})
            res_submit.raise_for_status()
            
            data_submitted = res_submit.json().get("data", {})
            grand_total = data_submitted.get("grand_total") or res.json().get("data", {}).get("grand_total", 0)
            
            return {
                "order_name": order_name,
                "grand_total": grand_total
            }
            
        except Exception as e:
            print(f"Error creando Sales Order: {str(e)}")
            raise

    def mark_order_as_delivered(self, order_name: str) -> str:
        """
        Crea y somete (docstatus=1) un Delivery Note a partir de un Sales Order.
        Esto cambia internamente el pedido a estado 'Delivered' o 'To Bill'.
        """
        # 1. Generar mapeo preliminar de Delivery Note desde el SO
        api_url = f"{self.url}/api/method/erpnext.selling.doctype.sales_order.sales_order.make_delivery_note"
        data = {"source_name": order_name}
        
        try:
            res_make = requests.post(api_url, headers=self.headers, json=data)
            res_make.raise_for_status()
            dn_doc = res_make.json().get("message", {})
            
            if not dn_doc:
                raise Exception("Frappe no retornó el documento Delivery Note preliminar.")
                
            # 2. Guardar el Delivery Note transitorio a la DB
            post_url = f"{self.url}/api/resource/Delivery Note"
            res_post = requests.post(post_url, headers=self.headers, json=dn_doc)
            
            if res_post.status_code != 200:
                print(f"Error de validación al crear DN para {order_name}:", res_post.text)
            res_post.raise_for_status()
            
            dn_name = res_post.json().get("data", {}).get("name")
            
            # 3. Hacer Submit para cambiar inventario y estatus del pedido
            if dn_name:
                submit_url = f"{post_url}/{dn_name}"
                res_submit = requests.put(submit_url, headers=self.headers, json={"docstatus": 1})
                res_submit.raise_for_status()
                return dn_name
            else:
                raise Exception("El sistema no retorno ID al crear el Delivery Note.")
                
        except requests.exceptions.HTTPError as e:
            print(f"API HTTP Error marking order as delivered ({order_name}): {res_make.text if 'res_make' in locals() else str(e)}")
            raise Exception(f"Error de ERPNext al dar por entregado: {str(e)}")
        except Exception as e:
            print(f"Error procesando entrega de {order_name}: {str(e)}")
            raise

    def cancel_sales_order(self, order_name: str) -> None:
        """
        Cancela un Sales Order poniendo su docstatus en 2.
        Frappe validará si el documento puede ser cancelado (ej, si no hay pagos vinculados).
        """
        api_url = f"{self.url}/api/resource/Sales Order/{order_name}"
        data = {"docstatus": 2}
        try:
            res = requests.put(api_url, headers=self.headers, json=data)
            
            # Revisar si hay un texto descriptivo del error en el JSON
            if res.status_code != 200:
                error_detail = "Error desconocido al intentar cancelar."
                try:
                    res_json = res.json()
                    # Frappe suele usar "exc" o "server_messages" 
                    if "_server_messages" in res_json:
                        import json
                        messages = json.loads(res_json["_server_messages"])
                        # Obtenemos texto crudo
                        import ast
                        texts = [ast.literal_eval(msg).get("message", "") for msg in messages if "message" in ast.literal_eval(msg)]
                        if texts:
                            error_detail = " ".join(texts)
                except Exception:
                    error_detail = res.text
                print(f"Cancel Validation Failed: {error_detail}")
                raise Exception(error_detail)
                
            res.raise_for_status()
        except requests.exceptions.HTTPError as e:
            print(f"API HTTP Error cancelling order {order_name}: {str(e)}")
            raise Exception(f"Error de red/API ERPNext al cancelar: {str(e)}")
        except Exception as e:
            print(f"Excepcion interna al cancelar {order_name}: {str(e)}")
            raise

    def get_latest_active_order(self, customer_id: str) -> Dict[str, Any]:
        """
        Busca el último Sales Order enviado (docstatus=1) para un cliente 
        que aún esté pendiente de entrega.
        """
        api_url = f"{self.url}/api/resource/Sales Order"
        filters_list = [
            ["customer", "=", customer_id],
            ["docstatus", "=", 1],
            ["status", "in", ["To Deliver", "To Deliver and Bill"]]
        ]
        params = {
            "filters": json.dumps(filters_list),
            "fields": '["name"]',
            "order_by": "creation desc",
            "limit_page_length": 1
        }
        
        try:
            res = requests.get(api_url, headers=self.headers, params=params)
            res.raise_for_status()
            data = res.json().get("data", [])
            return data[0] if data else None
        except Exception as e:
            print(f"Error fetching latest active order for {customer_id}: {str(e)}")
            return None

    # Mapa de cuentas por modo de pago (configuradas en ERPNext para la empresa Voraz)
    # Claves: nombre exacto del Mode of Payment en ERPNext
    # Valores: nombre exacto de la cuenta contable (Account)
    ACCOUNT_BY_MOP = {
        "Cash": "Efectivo - Vz",
        "Wire Transfer": "1212 - Ueno - Vz",
    }

    def resolve_order_for_customer(self, identifier: str) -> str:
        """
        Dado un identificador (JID, teléfono o nombre/apellido del cliente),
        busca el Customer en ERPNext y devuelve el nombre del último Sales Order activo.
        Lanza Exception si no se encuentra cliente o si no tiene pedidos activos.
        """
        raw_id = identifier.strip()
        api_url = f"{self.url}/api/resource/Customer"
        
        customers = []
        phone = ''
        if '@' in raw_id:
            phone = raw_id.split('@')[0]
        else:
            digits = ''.join(c for c in raw_id if c.isdigit())
            if len(digits) >= 6:
                phone = digits

        # 1. Si parece teléfono o JID:
        if phone:
            # 1.1 JID directo en name
            try:
                res = requests.get(api_url, headers=self.headers, params={
                    "filters": json.dumps([["name", "=", raw_id]]),
                    "fields": '["name", "customer_name"]'
                })
                res.raise_for_status()
                customers = res.json().get("data", [])
            except Exception as e:
                print(f"[resolve_order_for_customer] Error buscando por JID directo: {str(e)}")

            # 1.2 mobile_no exacto
            if not customers:
                try:
                    res = requests.get(api_url, headers=self.headers, params={
                        "filters": json.dumps([["mobile_no", "=", phone]]),
                        "fields": '["name", "customer_name"]'
                    })
                    res.raise_for_status()
                    customers = res.json().get("data", [])
                except Exception as e:
                    print(f"[resolve_order_for_customer] Error buscando por mobile_no: {str(e)}")

            # 1.3 name like %phone%
            if not customers:
                try:
                    res = requests.get(api_url, headers=self.headers, params={
                        "filters": json.dumps([["name", "like", f"%{phone}%"]]),
                        "fields": '["name", "customer_name"]'
                    })
                    res.raise_for_status()
                    customers = res.json().get("data", [])
                except Exception as e:
                    print(f"[resolve_order_for_customer] Error buscando por ID conteniendo teléfono: {str(e)}")

        # 2. Si no hubo match por teléfono o el identificador es un nombre:
        if not customers:
            # 2.1 customer_name like %identifier%
            try:
                res = requests.get(api_url, headers=self.headers, params={
                    "filters": json.dumps([["customer_name", "like", f"%{raw_id}%"]]),
                    "fields": '["name", "customer_name"]'
                })
                res.raise_for_status()
                customers = res.json().get("data", [])
            except Exception as e:
                print(f"[resolve_order_for_customer] Error buscando por customer_name like: {str(e)}")

        # 2.2 name (ID) like %identifier% (útil si el customer ID se guardó con nombre)
        if not customers:
            try:
                res = requests.get(api_url, headers=self.headers, params={
                    "filters": json.dumps([["name", "like", f"%{raw_id}%"]]),
                    "fields": '["name", "customer_name"]'
                })
                res.raise_for_status()
                customers = res.json().get("data", [])
            except Exception as e:
                print(f"[resolve_order_for_customer] Error buscando por name like raw_id: {str(e)}")
                
        if not customers:
            raise Exception(f"No se encontró ningún cliente asociado a '{raw_id}' en ERPNext.")
        
        # Usar el primer match y buscar su último pedido activo
        customer_id = customers[0]["name"]
        customer_disp = customers[0].get('customer_name', customer_id)
        latest = self.get_latest_active_order(customer_id)
        
        if not latest:
            raise Exception(f"El cliente '{customer_disp}' no tiene pedidos activos pendientes de cobro.")
        
        return latest["name"]

