# ERP Service

Microservicio en Python (FastAPI) encargado de interconectar el chatbot Voraz y los sistemas de IA con la instancia local de ERPNext (Frappe).

## Funcionalidades Actuales (Fase 1)
- Consulta de pedidos pendientes (Sales Orders en estado `Submitted`).
- Mapeo transparente al formato requerido por el comando `/listado` de `whatsapp-baileys`.

## Instalación y Uso Local

1. Crea tu entorno virtual:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```
2. Instala dependencias:
   ```bash
   pip install -r requirements.txt
   ```
3. Configura el `.env`. Tienes que colocar un **API Key** y **API Secret** en ERPNext asociado a un usuario manager.
   ```env
   ERPNEXT_URL=http://localhost:8080
   ERPNEXT_API_KEY=tu_key
   ERPNEXT_API_SECRET=tu_secret
   PORT=8001
   ```
4. Ejecuta el servidor estableciendo el puerto manual:
   ```bash
   uvicorn main:app --port 8001 --reload
   ```

## Estructura
- `/services/frappe_client.py`: Clase que engloba toda la comunicación REST con ERPNext.
- `main.py`: Rutas principales FastAPI (REST API).
