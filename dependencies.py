from config import settings
from services.frappe.order_service import OrderService
from services.frappe.customer_service import CustomerService
from services.frappe.payment_service import PaymentService
from services.frappe.report_service import ReportService
from services.frappe.accounting_service import AccountingService
from services.frappe.inventory_service import InventoryService

order_service = OrderService(
    url=settings.ERPNEXT_URL,
    api_key=settings.ERPNEXT_API_KEY,
    api_secret=settings.ERPNEXT_API_SECRET
)

customer_service = CustomerService(
    url=settings.ERPNEXT_URL,
    api_key=settings.ERPNEXT_API_KEY,
    api_secret=settings.ERPNEXT_API_SECRET
)

payment_service = PaymentService(
    url=settings.ERPNEXT_URL,
    api_key=settings.ERPNEXT_API_KEY,
    api_secret=settings.ERPNEXT_API_SECRET
)

report_service = ReportService(
    url=settings.ERPNEXT_URL,
    api_key=settings.ERPNEXT_API_KEY,
    api_secret=settings.ERPNEXT_API_SECRET
)

accounting_service = AccountingService(
    url=settings.ERPNEXT_URL,
    api_key=settings.ERPNEXT_API_KEY,
    api_secret=settings.ERPNEXT_API_SECRET
)

inventory_service = InventoryService(
    url=settings.ERPNEXT_URL,
    api_key=settings.ERPNEXT_API_KEY,
    api_secret=settings.ERPNEXT_API_SECRET
)
