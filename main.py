from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import orders, customers, payments, reports

app = FastAPI(title="ERP Service for Voraz")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(orders.router, prefix="/api/orders", tags=["Orders"])
app.include_router(customers.router, prefix="/api/customers", tags=["Customers"])
app.include_router(payments.router, prefix="/api/orders", tags=["Payments"])
app.include_router(reports.router, prefix="/api/sales", tags=["Reports"])
