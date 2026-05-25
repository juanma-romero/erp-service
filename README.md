# ERP Service

Microservicio en Python (FastAPI) encargado de interconectar el chatbot Voraz y los sistemas de IA con la instancia local de ERPNext (Frappe).

## Funcionalidades Actuales
- **Gestión Unificada de Clientes (Customers):** Arquitectura JID-first. El ID de cada cliente en ERPNext es su WhatsApp JID, evitando colisiones. Sincronización automática de PushNames e identificación fluida desde móvil.
- **Consulta de Pedidos Pendientes:** Obtención de Sales Orders en estado `Submitted` y mapeo estructurado.
- **Creación y Reemplazo de Pedidos:** Flujos robustos integrados con el asistente de IA.
- **Cobros Integrados con Resolución por JID:** Registro automático de facturas (Sales Invoices) y recibos de cobro (Payment Entries) resolviendo el JID o número del cliente al último pedido activo.
- **Sincronización de Clientes (`POST /api/customers/sync`):** Endpoint de alta eficiencia para dar de alta o actualizar contactos.

## Estructura
- `/services/frappe_client.py`: Clase que engloba toda la comunicación REST con ERPNext.
- `main.py`: Rutas principales FastAPI (REST API).
