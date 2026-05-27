import requests
import json
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
            
        # Extraer fecha corta para la obligatoria
        short_date = delivery_date_str.split(" ")[0] if delivery_date_str else ""
        
        new_order = {
            "customer": customer_id,
            "transaction_date": short_date,
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
            
            return order_name
            
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

    def resolve_order_for_customer(self, jid: str) -> str:
        """
        Dado un JID de WhatsApp (ej: '19292551824@s.whatsapp.net'),
        busca el Customer en ERPNext por JID, móvil o nombre
        y devuelve el nombre del último Sales Order activo del cliente.
        Lanza Exception si no se encuentra ningún pedido activo o si no existe el cliente.
        """
        phone = jid.split('@')[0]  # Extraer solo el número
        api_url = f"{self.url}/api/resource/Customer"
        
        customers = []
        
        # 1. Intentar buscar por JID directo (clave de documento 'name')
        try:
            res = requests.get(api_url, headers=self.headers, params={
                "filters": json.dumps([["name", "=", jid]]),
                "fields": '["name", "customer_name"]'
            })
            res.raise_for_status()
            customers = res.json().get("data", [])
        except Exception as e:
            print(f"[resolve_order_for_customer] Error buscando por JID directo: {str(e)}")

        # 2. Si no, intentar buscar por mobile_no exacto
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

        # 3. Si no, intentar buscar por name (ID) conteniendo el teléfono
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

        # 4. Fallback final: customer_name conteniendo el teléfono
        if not customers:
            try:
                res = requests.get(api_url, headers=self.headers, params={
                    "filters": json.dumps([["customer_name", "like", f"%{phone}%"]]),
                    "fields": '["name", "customer_name"]'
                })
                res.raise_for_status()
                customers = res.json().get("data", [])
            except Exception as e:
                print(f"[resolve_order_for_customer] Error en fallback de customer_name: {str(e)}")
                
        if not customers:
            raise Exception(f"No se encontró ningún cliente con el número {phone} o JID {jid} en ERPNext.")
        
        # Usar el primer match y buscar su último pedido activo
        customer_id = customers[0]["name"]
        latest = self.get_latest_active_order(customer_id)
        
        if not latest:
            raise Exception(f"El cliente '{customers[0].get('customer_name', customer_id)}' no tiene pedidos activos pendientes de cobro.")
        
        return latest["name"]

