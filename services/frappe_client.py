import requests
import json
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

    def get_or_create_customer(self, contact_name: str, jid: str) -> str:
        """
        Busca un cliente por su JID (ID) o número de teléfono.
        Si no existe, lo crea asegurando que su ID de documento en ERPNext sea el JID,
        y luego le asigna su nombre descriptivo de forma limpia.
        """
        if not jid:
            # Fallback si no hay JID por alguna razón
            name = contact_name.strip() if contact_name else "Cliente General"
            api_url = f"{self.url}/api/resource/Customer"
            params = {
                "filters": json.dumps([["customer_name", "=", name]]),
                "fields": '["name"]'
            }
            res = requests.get(api_url, headers=self.headers, params=params)
            res.raise_for_status()
            data = res.json().get("data", [])
            if data:
                return data[0]["name"]
            
            # Crear Cliente General
            new_customer = {
                "customer_name": name,
                "customer_type": "Individual"
            }
            res_post = requests.post(api_url, headers=self.headers, json=new_customer)
            res_post.raise_for_status()
            return res_post.json()["data"]["name"]

        phone = jid.split('@')[0]
        friendly_name = contact_name.strip() if (contact_name and contact_name != "Desconocido") else ""
        
        api_url = f"{self.url}/api/resource/Customer"

        # 1. Buscar primero por JID directo (clave de documento 'name' en ERPNext)
        params_jid = {
            "filters": json.dumps([["name", "=", jid]]),
            "fields": '["name", "customer_name"]'
        }
        try:
            res_jid = requests.get(api_url, headers=self.headers, params=params_jid)
            res_jid.raise_for_status()
            data_jid = res_jid.json().get("data", [])
            
            if data_jid:
                customer_id = data_jid[0]["name"]
                current_name = data_jid[0].get("customer_name")
                
                # Si tenemos un nombre amigable real y el actual en ERP es genérico o diferente, lo actualizamos
                if friendly_name and current_name != friendly_name:
                    print(f"[get_or_create_customer] Actualizando nombre de {customer_id} a '{friendly_name}'")
                    try:
                        requests.put(f"{api_url}/{customer_id}", headers=self.headers, json={"customer_name": friendly_name})
                    except Exception as u_err:
                        print(f"Error actualizando nombre amigable: {str(u_err)}")
                        
                return customer_id
        except Exception as e:
            print(f"Error buscando por JID: {str(e)}")

        # 2. Si no se encontró por JID, buscar por el número de teléfono en 'mobile_no'
        params_phone = {
            "filters": json.dumps([["mobile_no", "=", phone]]),
            "fields": '["name", "customer_name"]'
        }
        try:
            res_phone = requests.get(api_url, headers=self.headers, params=params_phone)
            res_phone.raise_for_status()
            data_phone = res_phone.json().get("data", [])
            
            if data_phone:
                customer_id = data_phone[0]["name"]
                current_name = data_phone[0].get("customer_name")
                
                # Si tenemos un nombre amigable real y el actual en ERP es genérico o diferente, lo actualizamos
                if friendly_name and current_name != friendly_name:
                    print(f"[get_or_create_customer] Actualizando nombre de {customer_id} a '{friendly_name}'")
                    try:
                        requests.put(f"{api_url}/{customer_id}", headers=self.headers, json={"customer_name": friendly_name})
                    except Exception as u_err:
                        print(f"Error actualizando nombre amigable: {str(u_err)}")
                        
                return customer_id
        except Exception as e:
            print(f"Error buscando por teléfono: {str(e)}")

        # 3. Si no existe, crear el cliente.
        # Para forzar a que ERPNext asigne el JID como ID de documento (clave 'name'),
        # primero creamos el Customer usando el JID como su 'customer_name'.
        print(f"[get_or_create_customer] Creando nuevo cliente con ID (JID): {jid}")
        new_customer = {
            "customer_name": jid,
            "customer_type": "Individual",
            "mobile_no": phone
        }
        
        try:
            res_post = requests.post(api_url, headers=self.headers, json=new_customer)
            if res_post.status_code != 200:
                print("Error de validación Frappe al crear Customer:", res_post.text)
            res_post.raise_for_status()
            customer_id = res_post.json()["data"]["name"] # Será el JID
            
            # 4. Ahora que el documento se llama con el JID, actualizamos su 'customer_name'
            # con el nombre amigable real si está disponible, o un nombre por defecto
            final_name = friendly_name if friendly_name else f"Cliente {phone}"
            print(f"[get_or_create_customer] Asignando nombre amigable definitivo '{final_name}' a {customer_id}")
            
            requests.put(f"{api_url}/{customer_id}", headers=self.headers, json={"customer_name": final_name})
            
            return customer_id
            
        except Exception as e:
            print(f"Error creando Customer {jid}: {str(e)}")
            raise Exception(f"No se pudo crear el cliente para el número {phone}. Error: {str(e)}")
            
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
        "Efectivo": "1110 - Efectivo - Vz",
        "Transferencia bancaria": "1212 - Ueno - Vz",
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

