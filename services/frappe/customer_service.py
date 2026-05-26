import requests
import json
from typing import List, Dict, Any
from .base_client import BaseFrappeClient

class CustomerService(BaseFrappeClient):
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
            
