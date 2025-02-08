from fastapi import FastAPI
from app.database import CustomerDB, WarehouseDB

# Database dependency functions
async def get_customer_db(app: FastAPI):
    """Get customer database instance."""
    if not hasattr(app.state, 'customer_db'):
        db = CustomerDB()
        app.state.customer_db = db
    return app.state.customer_db

async def get_warehouse_db(app: FastAPI):
    """Get warehouse database instance."""
    if not hasattr(app.state, 'warehouse_db'):
        db = WarehouseDB()
        app.state.warehouse_db = db
    return app.state.warehouse_db 