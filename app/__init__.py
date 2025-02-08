"""
Warehouse Management Service

A service for managing warehouses, rooms, and customers with DynamoDB backend.
"""
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from decimal import Decimal
import json
from app.config import get_settings

# Package metadata
__version__ = "0.1.0"
__author__ = "Warehouse Team"
__license__ = "Private"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

settings = get_settings()

# Custom JSON encoder for Decimal
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        return super().default(obj)

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Warehouse Management Service",
        description="API for managing warehouses and customers",
        version="1.0.0",
        docs_url=None,  # Disable default docs
        redoc_url=None,  # Disable default redoc
        json_encoder=DecimalEncoder,
        default_response_class=JSONResponse
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return app

# Default application instance
app = create_app()

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown events."""
    # Startup
    logger.info("Starting Warehouse Management Service")
    # Add any startup initialization here
    yield
    # Shutdown
    logger.info("Shutting down Warehouse Management Service")
    # Add any cleanup here

app.lifespan = lifespan

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": __version__}

