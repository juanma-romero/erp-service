# ERP Service

Microservicio en Python (FastAPI) encargado de interconectar el chatbot Voraz y los sistemas de IA con la instancia local de ERPNext (Frappe).

## Funcionalidades Actuales
- **Gestión Unificada de Clientes (Customers):** Arquitectura JID-first. El ID de cada cliente en ERPNext es su WhatsApp JID, evitando colisiones. Sincronización automática de PushNames e identificación fluida desde móvil.
- **Consulta de Pedidos Pendientes:** Obtención de Sales Orders en estado `Submitted` y mapeo estructurado.
- **Creación y Reemplazo de Pedidos:** Flujos robustos integrados con el asistente de IA.
- **Cobros Integrados con Resolución por JID:** Registro automático de facturas (Sales Invoices) y recibos de cobro (Payment Entries) resolviendo el JID o número del cliente al último pedido activo.
- **Sincronización de Clientes (`POST /api/customers/sync`):** Endpoint de alta eficiencia para dar de alta o actualizar contactos.
- **Registro de Compras y Gastos (`POST /api/accounting/expense`):** Generación directa de Asientos Contables (Journal Entries) en ERPNext para un registro rápido sin flujos operativos complejos.

## Estructura
- `/config.py`: Configuraciones y variables de entorno.
- `/dependencies.py`: Instanciación e inyección de los servicios para los routers.
- `/main.py`: Inicialización de la app FastAPI y conexión de los routers.
- `/routers/`: Endpoints divididos por dominio (`orders.py`, `customers.py`, `payments.py`, `reports.py`, `accounting.py`).
- `/schemas/`: Modelos y esquemas de datos de Pydantic.
- `/services/frappe/`: Cliente HTTP base y servicios especializados por dominio (`order_service.py`, `customer_service.py`, `payment_service.py`, `report_service.py`, `accounting_service.py`) para interactuar con ERPNext de forma desacoplada.
