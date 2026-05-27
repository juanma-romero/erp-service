import requests
import json
from datetime import datetime
from typing import Dict, Any
from .base_client import BaseFrappeClient

class AccountingService(BaseFrappeClient):
    # Mapa de cuentas por modo de pago (origen de los fondos)
    ACCOUNT_BY_MOP = {
        "Cash": "1110 - Efectivo - Vz",
        "Wire Transfer": "1212 - Ueno - Vz",
    }

    def create_journal_entry(self, concept_account: str, amount: float, method: str, remark: str = "Registro de gasto") -> Dict[str, Any]:
        """
        Crea un Asiento Contable (Journal Entry) en ERPNext.
        """
        # Determinar el modo de pago (origen de los fondos)
        mop = "Wire Transfer" if method.lower() in ("transferencia", "transf", "banco") else "Cash"
        
        if mop not in self.ACCOUNT_BY_MOP:
            raise Exception(f"Método de pago '{method}' no soportado contablemente.")
            
        origin_account = self.ACCOUNT_BY_MOP[mop]
        
        # Construir el payload del Asiento Contable
        posting_date = datetime.now().strftime("%Y-%m-%d")
        
        journal_doc = {
            "doctype": "Journal Entry",
            "voucher_type": "Journal Entry",
            "posting_date": posting_date,
            "user_remark": remark,
            "accounts": [
                {
                    "account": concept_account,
                    "debit_in_account_currency": amount,
                    "credit_in_account_currency": 0
                },
                {
                    "account": origin_account,
                    "debit_in_account_currency": 0,
                    "credit_in_account_currency": amount
                }
            ]
        }
        
        api_url = f"{self.url}/api/resource/Journal Entry"
        
        try:
            # 1. Crear el Journal Entry
            res_post = requests.post(api_url, headers=self.headers, json=journal_doc)
            
            if res_post.status_code != 200:
                error_msg = res_post.json().get("exc", res_post.text)
                print(f"Error al crear Journal Entry: {error_msg}")
                raise Exception(f"Error al crear asiento: {res_post.text}")
                
            res_post.raise_for_status()
            je_name = res_post.json()["data"]["name"]
            
            # 2. Someter (Submit) el Journal Entry para que tenga efecto contable
            res_submit = requests.put(f"{api_url}/{je_name}", headers=self.headers, json={"docstatus": 1})
            res_submit.raise_for_status()
            
            return {
                "success": True,
                "journal_entry": je_name,
                "message": "Asiento contable registrado correctamente."
            }
            
        except Exception as e:
            print(f"Error en create_journal_entry: {str(e)}")
            raise Exception(f"Error en ERPNext: {str(e)}")
