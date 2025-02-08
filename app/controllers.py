import logging
from typing import Dict, List, Optional, Any, Type
from uuid import UUID
from fastapi import HTTPException, status
from pydantic import BaseModel

from app.models import (
    CustomerCreate, CustomerResponse,
    WarehouseCreate, WarehouseResponse,
    RoomCreate, RoomResponse
)
from app.services import WarehouseService
from app.utils import (
    handle_validation_error,
    handle_database_error,
    format_warehouse_response,
    format_room_response
)

logger = logging.getLogger(__name__)

class BaseController:
    def __init__(self, service: Optional[WarehouseService] = None):
        if service is None:
            raise ValueError("Service instance is required")
        self.service = service

    async def handle_error(self, error: Exception, operation: str) -> None:
        """Handle and log errors from operations."""
        logger.error(f"Error during {operation}: {str(error)}")
        if isinstance(error, HTTPException):
            raise error
        if "not found" in str(error).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(error)
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(error)
        )

    def validate_request(self, data: BaseModel) -> None:
        """Validate incoming request data."""
        if not data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Request data is required"
            )

    def format_response(self, data: Dict, response_model: Type[BaseModel]) -> Dict:
        """Format response data according to the response model."""
        try:
            return response_model(**data).dict()
        except Exception as e:
            logger.error(f"Error formatting response: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error formatting response"
            )

class CustomerController(BaseController):
    async def create_customer(self, customer_data: CustomerCreate) -> Dict:
        """Create a new customer."""
        try:
            self.validate_request(customer_data)
            result = await self.service.create_customer(customer_data)
            return self.format_response(result, CustomerResponse)
        except Exception as e:
            await self.handle_error(e, "customer creation")

    async def update_customer(self, customer_id: UUID, customer_data: Dict) -> Dict:
        """Update an existing customer."""
        try:
            result = await self.service.update_customer(customer_id, customer_data)
            return self.format_response(result, CustomerResponse)
        except Exception as e:
            await self.handle_error(e, "customer update")

    async def get_customer(self, customer_id: UUID) -> Dict:
        """Get customer details."""
        try:
            result = await self.service.get_customer(customer_id)
            return self.format_response(result, CustomerResponse)
        except Exception as e:
            await self.handle_error(e, "customer retrieval")

    async def list_customers(self, skip: int = 0, limit: int = 100) -> List[Dict]:
        """List all customers with pagination."""
        try:
            results = await self.service.list_customers(skip, limit)
            return [self.format_response(r, CustomerResponse) for r in results]
        except Exception as e:
            await self.handle_error(e, "customer listing")

    async def delete_customer(self, customer_id: UUID) -> Dict:
        """Delete a customer."""
        try:
            await self.service.delete_customer(customer_id)
            return {"message": "Customer deleted successfully"}
        except Exception as e:
            await self.handle_error(e, "customer deletion")

class WarehouseController(BaseController):
    async def create_warehouse(self, warehouse_data: WarehouseCreate) -> Dict:
        """Create a new warehouse."""
        try:
            self.validate_request(warehouse_data)
            result = await self.service.create_warehouse(warehouse_data)
            return self.format_response(result, WarehouseResponse)
        except Exception as e:
            await self.handle_error(e, "warehouse creation")

    async def update_warehouse(self, warehouse_id: UUID, warehouse_data: Dict) -> Dict:
        """Update an existing warehouse."""
        try:
            result = await self.service.update_warehouse(warehouse_id, warehouse_data)
            return self.format_response(result, WarehouseResponse)
        except Exception as e:
            await self.handle_error(e, "warehouse update")

    async def get_warehouse(self, warehouse_id: UUID) -> Dict:
        """Get warehouse details."""
        try:
            result = await self.service.get_warehouse(warehouse_id)
            return self.format_response(result, WarehouseResponse)
        except Exception as e:
            await self.handle_error(e, "warehouse retrieval")

    async def list_warehouses(self, skip: int = 0, limit: int = 100) -> List[Dict]:
        """List all warehouses with pagination."""
        try:
            results = await self.service.list_warehouses(skip, limit)
            return [self.format_response(r, WarehouseResponse) for r in results]
        except Exception as e:
            await self.handle_error(e, "warehouse listing")

    async def delete_warehouse(self, warehouse_id: UUID) -> Dict:
        """Delete a warehouse."""
        try:
            await self.service.delete_warehouse(warehouse_id)
            return {"message": "Warehouse deleted successfully"}
        except Exception as e:
            await self.handle_error(e, "warehouse deletion")

class RoomController(BaseController):
    async def create_room(self, warehouse_id: UUID, room_data: RoomCreate) -> Dict:
        """Create a new room in a warehouse."""
        try:
            self.validate_request(room_data)
            result = await self.service.create_room(warehouse_id, room_data)
            return self.format_response(result, RoomResponse)
        except Exception as e:
            await self.handle_error(e, "room creation")

    async def update_room(self, warehouse_id: UUID, room_id: UUID, room_data: Dict) -> Dict:
        """Update an existing room."""
        try:
            result = await self.service.update_room(warehouse_id, room_id, room_data)
            return self.format_response(result, RoomResponse)
        except Exception as e:
            await self.handle_error(e, "room update")

    async def get_room(self, warehouse_id: UUID, room_id: UUID) -> Dict:
        """Get room details."""
        try:
            result = await self.service.get_room(warehouse_id, room_id)
            return self.format_response(result, RoomResponse)
        except Exception as e:
            await self.handle_error(e, "room retrieval")

    async def list_rooms(self, warehouse_id: UUID, skip: int = 0, limit: int = 100) -> List[Dict]:
        """List all rooms in a warehouse with pagination."""
        try:
            results = await self.service.list_rooms(warehouse_id, skip, limit)
            return [self.format_response(r, RoomResponse) for r in results]
        except Exception as e:
            await self.handle_error(e, "room listing")

    async def delete_room(self, warehouse_id: UUID, room_id: UUID) -> Dict:
        """Delete a room."""
        try:
            await self.service.delete_room(warehouse_id, room_id)
            return {"message": "Room deleted successfully"}
        except Exception as e:
            await self.handle_error(e, "room deletion")

