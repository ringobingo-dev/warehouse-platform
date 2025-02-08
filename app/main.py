import uuid
import time
import logging
from logging.config import dictConfig
from uuid import UUID
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.middleware.cors import CORSMiddleware
from app.database import ItemNotFoundError, DatabaseError, ValidationError
from app.config import get_settings
from app.routes import customer_router, warehouse_router, room_router, inventory_router

# Configure logging
logging_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        },
        "access": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        },
    },
    "handlers": {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
        "access": {
            "formatter": "access",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
    },
    "loggers": {
        "warehouse_service": {"handlers": ["default"], "level": "INFO"},
        "warehouse_access": {"handlers": ["access"], "level": "INFO"},
    },
}

dictConfig(logging_config)
logger = logging.getLogger("warehouse_service")
access_logger = logging.getLogger("warehouse_access")

settings = get_settings()

# Create FastAPI application
app = FastAPI(
    title="Warehouse Management Service",
    description="API for managing warehouses and customers",
    version="1.0.0",
    docs_url=None,  # Disable default docs
    redoc_url=None  # Disable default redoc
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers with explicit prefixes
app.include_router(customer_router, prefix="/api/v1/customers")
app.include_router(warehouse_router, prefix="/api/v1/warehouses")
app.include_router(room_router, prefix="/api/v1/rooms")
app.include_router(inventory_router, prefix="/api/v1/inventory")

# Validation helpers
def validate_uuid(id_str: str, entity_type: str = "UUID") -> UUID:
    """Validate UUID string format and return UUID object."""
    try:
        return UUID(id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {entity_type} ID format"
        )

# Error handlers
@app.exception_handler(ItemNotFoundError)
async def item_not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={"detail": str(exc)}
    )

@app.exception_handler(ValidationError)
async def validation_error_handler(request, exc):
    return JSONResponse(
        status_code=422,
        content={"detail": str(exc)}
    )

@app.exception_handler(DatabaseError)
async def database_error_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)}
    )

# Logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    # Add request ID to request state
    request.state.request_id = request_id
    
    access_logger.info(
        f"Request started request_id={request_id} method={request.method} path={request.url.path}"
    )
    
    try:
        response = await call_next(request)
        process_time = (time.time() - start_time) * 1000
        access_logger.info(
            f"Request completed request_id={request_id} status_code={response.status_code} duration={process_time:.2f}ms"
        )
        response.headers["X-Request-ID"] = request_id
        return response
    except Exception as e:
        process_time = (time.time() - start_time) * 1000
        access_logger.error(
            f"Request failed request_id={request_id} error={str(e)} duration={process_time:.2f}ms"
        )
        raise

# Error handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "request_id": request.state.request_id
        },
    )

# Custom docs endpoint with configuration
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=app.title + " - API Documentation",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        swagger_js_url="/static/swagger-ui-bundle.js",
        swagger_css_url="/static/swagger-ui.css",
    )

# Health check endpoint
@app.get("/health", tags=["health"])
async def health_check():
    return {
        "status": "healthy",
        "version": app.version,
        "environment": settings.ENV
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.ENV == "development"
    )

