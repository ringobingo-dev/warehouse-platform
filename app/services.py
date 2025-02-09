import logging
from typing import Dict, List, Optional, Any
from uuid import UUID
from datetime import datetime, timezone
from app.database import WarehouseDB, CustomerDB, ItemNotFoundError, InventoryDB, OperationError, ValidationError
from app.models import (
    WarehouseCreate,
    WarehouseResponse,
    WarehouseUpdate,
    CustomerCreate,
    CustomerResponse,
    CustomerUpdate,
    RoomCreate,
    RoomResponse,
    RoomStatus,
    InventoryCreate,
    InventoryResponse,
    VerificationStatus
)
from fastapi import HTTPException, status
from decimal import Decimal

logger = logging.getLogger(__name__)

class WarehouseService:
    def __init__(self, warehouse_db: WarehouseDB, inventory_db: InventoryDB, customer_db: CustomerDB):
        self.warehouse_db = warehouse_db
        self.inventory_db = inventory_db
        self.customer_db = customer_db

    async def create_warehouse(self, warehouse_data: WarehouseCreate) -> WarehouseResponse:
        """Create a new warehouse."""
        logger.info(f"Creating warehouse for customer {warehouse_data.customer_id}")
        
        try:
            # Check if customer exists
            await self.warehouse_db.get_customer(warehouse_data.customer_id)
            
            # Create warehouse
            warehouse_dict = await self.warehouse_db.create_warehouse(warehouse_data)
            warehouse = WarehouseResponse(**warehouse_dict)
            logger.info(f"Created warehouse {warehouse.id}")
            return warehouse
        except ItemNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )

    async def get_warehouse(self, warehouse_id: str | UUID) -> WarehouseResponse:
        """Get warehouse by ID."""
        logger.info(f"Retrieving warehouse {warehouse_id}")
        try:
            warehouse_dict = await self.warehouse_db.get_warehouse(UUID(str(warehouse_id)))
            if not warehouse_dict:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Warehouse {warehouse_id} not found"
                )
            return WarehouseResponse(**warehouse_dict)
        except ItemNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )

    async def update_warehouse(
        self, warehouse_id: str | UUID, update_data: Dict[str, Any]
    ) -> WarehouseResponse:
        """Update warehouse details."""
        logger.info(f"Updating warehouse {warehouse_id}")
        
        # Check if warehouse exists
        warehouse = await self.get_warehouse(warehouse_id)
        if not warehouse:
            raise ItemNotFoundError(f"Warehouse {warehouse_id} not found")
        
        # Validate update data
        if "total_capacity" in update_data:
            if not self._validate_warehouse_capacity({**warehouse.model_dump(), **update_data}):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Invalid warehouse capacity configuration"
                )
        
        # Update warehouse
        updated_warehouse_dict = await self.warehouse_db.update_warehouse(UUID(str(warehouse_id)), update_data)
        logger.info(f"Updated warehouse {warehouse_id}")
        return WarehouseResponse(**updated_warehouse_dict)

    async def delete_warehouse(self, warehouse_id_str: str) -> None:
        """Delete a warehouse."""
        try:
            # Check if warehouse exists
            warehouse = await self.get_warehouse(warehouse_id_str)
            
            # Check for inventory
            inventory = await self.warehouse_db.get_inventory(warehouse_id_str)
            if inventory:
                raise ValidationError("Cannot delete warehouse with existing inventory")

            logger.info(f"Deleting warehouse {warehouse_id_str}")
            await self.warehouse_db.delete_warehouse(warehouse_id_str)
            logger.info(f"Deleted warehouse {warehouse_id_str}")
        except ItemNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        except ValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e)
            )

    async def create_room(self, warehouse_id: str, room_data: RoomCreate) -> RoomResponse:
        """Create a new room in a warehouse."""
        logger.info(f"Creating room in warehouse {warehouse_id}")
        
        # Verify warehouse exists
        warehouse = await self.get_warehouse(warehouse_id)
        
        # Validate room dimensions
        dimensions = room_data.dimensions
        if dimensions.width <= 0:
            raise ValueError("width must be positive")
        if dimensions.length <= 0:
            raise ValueError("length must be positive")
        if dimensions.height <= 0:
            raise ValueError("height must be positive")
        
        # Create room
        room_dict = await self.warehouse_db.create_room(warehouse_id, room_data)
        room_dict["available_capacity"] = room_dict["capacity"]
        room = RoomResponse(**room_dict)
        
        # Update warehouse total capacity
        await self._update_warehouse_capacity(warehouse_id)
        
        logger.info(f"Created room {room.id} in warehouse {warehouse_id}")
        return room

    async def update_room(
        self, warehouse_id: str, room_id: str, room_data: Dict[str, Any]
    ) -> RoomResponse:
        """
        Update room properties with validation.
        
        Args:
            warehouse_id: UUID of the warehouse containing the room
            room_id: UUID of the room to update
            room_data: Update data for the room
            
        Returns:
            RoomResponse: Updated room details
            
        Raises:
            ValueError: If room not found or validation fails
        """
        logger.info(f"Updating room {room_id} in warehouse {warehouse_id}")
        
        # Get current room state
        room = await self.get_room(warehouse_id, room_id)
        
        # Validate updates
        if "max_weight_capacity" in room_data and room_data["max_weight_capacity"] <= 0:
            raise ValueError("weight capacity must be positive")
            
        if any(key in room_data for key in ["length", "width", "height"]):
            if room.current_utilization > 0:
                raise ValueError("Cannot modify dimensions of room with inventory")
            
            if not self._validate_room_dimensions(
                await self.get_warehouse(warehouse_id),
                {**room.model_dump(), **room_data}
            ):
                raise ValueError("Invalid room dimensions")
        
        # Update room
        updated_room = await self.warehouse_db.update_room(
            warehouse_id, room_id, room_data
        )
        
        # Update warehouse capacity if dimensions changed
        if any(key in room_data for key in ["length", "width", "height"]):
            await self._update_warehouse_capacity(warehouse_id)
        
        logger.info(f"Updated room {room_id}")
        return RoomResponse(**updated_room)

    async def delete_room(self, warehouse_id: str, room_id: str) -> None:
        """
        Delete a room after validation checks.
        
        Args:
            warehouse_id: UUID of the warehouse containing the room
            room_id: UUID of the room to delete
            
        Raises:
            ValueError: If room has inventory or validation fails
        """
        logger.info(f"Deleting room {room_id} from warehouse {warehouse_id}")
        
        # Get room and check inventory
        room = await self.get_room(warehouse_id, room_id)
        if room.current_utilization > 0:
            raise ValueError("Cannot delete room with existing inventory")
        
        # Delete room
        await self.warehouse_db.delete_room(warehouse_id, room_id)
        
        # Update warehouse capacity
        await self._update_warehouse_capacity(warehouse_id)
        
        logger.info(f"Deleted room {room_id}")

    async def get_room(self, warehouse_id: str, room_id: str) -> RoomResponse:
        """
        Get room details.
        
        Args:
            warehouse_id: UUID of the warehouse containing the room
            room_id: UUID of the room to retrieve
            
        Returns:
            RoomResponse: Room details
            
        Raises:
            ValueError: If room not found
        """
        logger.info(f"Getting room {room_id} from warehouse {warehouse_id}")
        room_dict = await self.warehouse_db.get_room(warehouse_id, room_id)
        if not room_dict:
            raise ValueError(f"Room {room_id} not found")
        return RoomResponse(**room_dict)

    async def list_rooms(self, warehouse_id: str) -> List[RoomResponse]:
        """
        List all rooms in a warehouse.
        
        Args:
            warehouse_id: UUID of the warehouse
            
        Returns:
            List[RoomResponse]: List of room details
            
        Raises:
            ItemNotFoundError: If warehouse not found
        """
        logger.info(f"Listing rooms for warehouse {warehouse_id}")
        try:
            # Verify warehouse exists
            warehouse = await self.get_warehouse(warehouse_id)
            if not warehouse:
                raise ItemNotFoundError(f"Warehouse {warehouse_id} not found")
            
            rooms = await self.warehouse_db.get_rooms(warehouse_id)
            return [RoomResponse(**room) for room in rooms]
        except Exception as e:
            logger.error(f"Error listing rooms for warehouse {warehouse_id}: {str(e)}")
            raise

    async def update_room_status(
        self, warehouse_id: str, room_id: str, status: RoomStatus
    ) -> RoomResponse:
        """
        Update room status with validation of allowed transitions.
        
        Args:
            warehouse_id: UUID of the warehouse containing the room
            room_id: UUID of the room to update
            status: New status for the room
            
        Returns:
            RoomResponse: Updated room details
            
        Raises:
            ValueError: If status transition not allowed
        """
        logger.info(f"Updating status of room {room_id} to {status}")
        
        room = await self.get_room(warehouse_id, room_id)
        if not self._validate_status_transition(room.status, status):
            raise ValueError(f"Invalid status transition from {room.status} to {status}")
        
        updated_room = await self.warehouse_db.update_room(
            warehouse_id, room_id, {"status": status}
        )
        
        logger.info(f"Updated room {room_id} status to {status}")
        return RoomResponse(**updated_room)

    async def update_room_dimensions(self, warehouse_id: str, room_id: str, length: Decimal, width: Decimal, height: Decimal) -> RoomResponse:
        """Update room dimensions."""
        logger.info(f"Updating dimensions of room {room_id}")
        try:
            # Get the room
            room = await self.get_room(warehouse_id, room_id)
            if not room:
                raise ItemNotFoundError(f"Room {room_id} not found")

            # Check if room has inventory
            inventory = await self.inventory_db.list_by_room(room_id)
            if inventory:
                raise ValueError("Cannot modify dimensions of room with inventory")

            # Validate dimensions
            if not all(dim > 0 for dim in [length, width, height]):
                raise ValidationError("All dimensions must be positive")

            # Get all rooms to validate total warehouse capacity
            rooms = await self.list_rooms(warehouse_id)
            total_volume = sum(
                self._calculate_room_volume(r) for r in rooms 
                if r.id != UUID(room_id)  # Exclude current room
            )

            # Calculate new room volume
            new_volume = length * width * height
            if total_volume + new_volume > self.MAX_WAREHOUSE_VOLUME:
                raise ValidationError("New dimensions would exceed maximum warehouse volume")

            # Update room dimensions
            update_data = {
                "dimensions": {
                    "length": str(length),
                    "width": str(width),
                    "height": str(height)
                }
            }
            updated_room = await self.warehouse_db.update_room(warehouse_id, room_id, update_data)
            logger.info(f"Updated room {room_id} dimensions")
            return RoomResponse(**updated_room)
        except Exception as e:
            logger.error(f"Error updating room dimensions: {str(e)}")
            raise

    def _validate_status_transition(self, current: RoomStatus, new: RoomStatus) -> bool:
        """Validate if a status transition is allowed."""
        allowed_transitions = {
            RoomStatus.ACTIVE: [RoomStatus.MAINTENANCE, RoomStatus.DECOMMISSIONED],
            RoomStatus.MAINTENANCE: [RoomStatus.ACTIVE, RoomStatus.DECOMMISSIONED],
            RoomStatus.DECOMMISSIONED: [RoomStatus.ACTIVE]
        }
        return new in allowed_transitions.get(current, [])

    def _validate_room_dimensions(self, warehouse: WarehouseResponse, room_data: Dict[str, Any]) -> bool:
        """Validate room dimensions against warehouse constraints."""
        try:
            dimensions = room_data.get("dimensions")
            if not dimensions:
                return False
            
            # Check if all dimensions are positive
            if not all(getattr(dimensions, dim, 0) > 0 for dim in ["length", "width", "height"]):
                return False
            
            # Additional validation can be added here
            return True
        except Exception:
            return False

    async def _update_warehouse_capacity(self, warehouse_id: str) -> None:
        """Update warehouse total capacity based on room dimensions."""
        rooms = await self.list_rooms(warehouse_id)
        total_capacity = sum(
            room.dimensions.length * room.dimensions.width * room.dimensions.height
            for room in rooms
            if room.status == RoomStatus.ACTIVE
        )
        await self.warehouse_db.update_warehouse(
            warehouse_id, {"total_capacity": total_capacity}
        )

    async def list_warehouses(
        self, customer_id: Optional[str] = None
    ) -> List[WarehouseResponse]:
        """
        List all warehouses, optionally filtered by customer.
        
        Args:
            customer_id: Optional customer ID to filter by
            
        Returns:
            List[WarehouseResponse]: List of warehouses
        """
        logger.info("Listing warehouses" + (f" for customer {customer_id}" if customer_id else ""))
        return await self.warehouse_db.list_warehouses(customer_id)

    async def add_inventory(
        self, warehouse_id: str, inventory_data: InventoryCreate
    ) -> InventoryResponse:
        """Add inventory to a warehouse with capacity validation."""
        logger.info(f"Adding inventory to warehouse {warehouse_id}")
        
        # Check warehouse exists and has capacity
        warehouse = await self.get_warehouse(warehouse_id)
        if not warehouse:
            raise ItemNotFoundError(f"Warehouse {warehouse_id} not found")
            
        # Verify room exists and belongs to warehouse
        room = await self.get_room(warehouse_id, str(inventory_data.room_id))
        if not room:
            raise ItemNotFoundError(f"Room {inventory_data.room_id} not found")
        if str(room.warehouse_id) != warehouse_id:
            raise ValidationError("Room does not belong to specified warehouse")
        
        current_level = await self.get_inventory_levels(warehouse_id)
        
        # Calculate total weight
        total_weight = inventory_data.quantity * inventory_data.unit_weight
        
        # Check if warehouse has enough capacity
        used_capacity = sum(item.total_weight for item in current_level)
        if used_capacity + total_weight > warehouse.total_capacity:
            raise ValidationError("Insufficient warehouse capacity")
            
        # Check room capacity
        if Decimal(str(total_weight)) > Decimal(str(room.available_capacity)):
            raise ValidationError("Insufficient room capacity")
            
        # Add inventory
        inventory = await self.warehouse_db.add_inventory(warehouse_id, inventory_data)
        
        # Update room utilization
        room_capacity = Decimal(str(room.capacity))
        current_utilization = (Decimal(str(total_weight)) / room_capacity) * Decimal('100.00')
        await self.warehouse_db.update_room(
            warehouse_id,
            str(inventory_data.room_id),
            {"current_utilization": current_utilization}
        )
        
        logger.info(f"Added inventory to warehouse {warehouse_id}")
        return InventoryResponse(**inventory)

    async def get_inventory_levels(self, warehouse_id: str) -> List[InventoryResponse]:
        """Get inventory levels for a warehouse."""
        logger.info(f"Getting inventory levels for warehouse {warehouse_id}")
        try:
            return await self.inventory_db.list_by_warehouse(warehouse_id)
        except ItemNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )

    def _validate_warehouse_capacity(self, warehouse_data: Dict[str, Any]) -> bool:
        """Validate warehouse capacity configuration."""
        try:
            capacity = Decimal(str(warehouse_data.get("total_capacity", 0)))
            return capacity > 0
        except (TypeError, ValueError):
            return False

    async def _check_warehouse_capacity(self, warehouse_id: str, inventory_data: InventoryCreate) -> bool:
        """Check if warehouse has sufficient capacity for new inventory."""
        try:
            # Get current inventory levels
            current_level = await self.inventory_db.list_by_warehouse(warehouse_id)
            
            # Calculate total weight of current inventory
            used_capacity = sum(
                Decimal(str(item.total_weight)) 
                for item in current_level
            )
            
            # Calculate new inventory weight
            new_weight = inventory_data.quantity * inventory_data.unit_weight
            
            # Get warehouse capacity
            warehouse = await self.get_warehouse(warehouse_id)
            total_capacity = Decimal(str(warehouse.total_capacity))
            
            return used_capacity + new_weight <= total_capacity
        except Exception as e:
            logger.error(f"Error checking warehouse capacity: {str(e)}")
            raise ValidationError(f"Error checking warehouse capacity: {str(e)}")

    async def create_customer(self, customer_data: CustomerCreate) -> CustomerResponse:
        """Create a new customer."""
        logger.info(f"Creating customer {customer_data.name}")
        customer = await self.customer_db.create_customer(customer_data)
        logger.info(f"Created customer {customer.id}")
        return customer

    def _validate_verification_status_transition(
        self, current_status: VerificationStatus, new_status: VerificationStatus
    ) -> bool:
        """Validate if the verification status transition is allowed."""
        allowed_transitions = {
            VerificationStatus.PENDING: {VerificationStatus.VERIFIED, VerificationStatus.REJECTED},
            VerificationStatus.VERIFIED: {VerificationStatus.REJECTED},
            VerificationStatus.REJECTED: {VerificationStatus.VERIFIED}
        }
        return new_status in allowed_transitions.get(current_status, set())

    async def verify_customer(self, customer_id: UUID, verification_data: Dict[str, Any]) -> CustomerResponse:
        """Verify customer and update verification status."""
        logger.info(f"Verifying customer {customer_id}")
        try:
            customer = await self.customer_db.get_customer(str(customer_id))
            if not customer:
                raise ValueError(f"Customer {customer_id} not found")
            
            # Get new status
            new_status = VerificationStatus(verification_data.get("verification_status", VerificationStatus.VERIFIED))
            current_status = VerificationStatus(customer.verification_status)
            
            # Validate status transition
            if not self._validate_verification_status_transition(current_status, new_status):
                raise ValueError(f"Invalid status transition from {current_status} to {new_status}")
            
            # Update verification status
            updated_customer = await self.customer_db.update_item(
                str(customer_id),
                {"verification_status": new_status}
            )
            return updated_customer
        except ItemNotFoundError:
            raise ValueError(f"Customer {customer_id} not found")

    async def calculate_warehouse_utilization(self, warehouse_id: str) -> dict:
        """Calculate the utilization of a warehouse."""
        warehouse = await self.warehouse_db.get_warehouse(warehouse_id)
        if not warehouse:
            raise ItemNotFoundError(f"Warehouse with ID {warehouse_id} not found")

        rooms = await self.warehouse_db.list_rooms(warehouse_id)
        if not rooms:
            return {
                "total_capacity": Decimal('0'),
                "total_used": Decimal('0'),
                "utilization_percentage": Decimal('0')
            }

        total_capacity = Decimal('0')
        total_used = Decimal('0')

        for room in rooms:
            if room.get('status') == RoomStatus.ACTIVE:
                room_capacity = await self.calculate_room_capacity(room)
                total_capacity += room_capacity
                
                inventory_items = await self.warehouse_db.list_inventory_by_room(room["id"])
                room_used = sum(
                    Decimal(str(item.get("total_weight", 0)))
                    for item in inventory_items
                )
                total_used += room_used

        utilization_percentage = (
            (total_used / total_capacity) * Decimal('100')
            if total_capacity > 0
            else Decimal('0')
        )

        return {
            "total_capacity": total_capacity,
            "total_used": total_used,
            "utilization_percentage": utilization_percentage.quantize(Decimal('0.01'))
        }

    async def check_room_availability(
        self,
        warehouse_id: str,
        room_id: str,
        width: float,
        length: float,
        height: float
    ) -> bool:
        """Check if a room has available space for given dimensions."""
        logger.info(f"Checking availability for room {room_id}")
        
        try:
            # Get room details
            room = await self.get_room(warehouse_id, room_id)
            if not room:
                raise ValueError(f"Room {room_id} not found")
            
            # Calculate required volume
            required_volume = width * length * height
            
            # Calculate available volume
            available_volume = room.available_capacity
            
            return available_volume >= required_volume
        except Exception as e:
            logger.error(f"Error checking room availability: {str(e)}")
            raise

    async def get_customer(self, customer_id: str) -> dict:
        """Get a customer by ID."""
        customer = await self.customer_db.get_customer(customer_id)
        if not customer:
            raise ItemNotFoundError(f"Customer with ID {customer_id} not found")
        return customer

    async def calculate_room_capacity(self, room: dict) -> Decimal:
        """Calculate the capacity of a room based on its dimensions."""
        if isinstance(room, dict) and 'dimensions' in room:
            dimensions = room['dimensions']
            length = Decimal(str(dimensions['length']))
            width = Decimal(str(dimensions['width']))
            height = Decimal(str(dimensions['height']))
            return length * width * height
        raise ValueError("Invalid room data format")

    async def list_inventory_by_room(self, room_id: str) -> List[InventoryResponse]:
        """List all inventory items in a room."""
        try:
            # First validate the room exists
            room = await self.warehouse_db.get_room_by_id(room_id)
            if not room:
                raise ItemNotFoundError(f"Room with id {room_id} not found")
            
            # Get inventory for the room
            inventory_items = await self.inventory_db.list_by_room(room_id)
            return inventory_items
        except Exception as e:
            logger.error(f"Error listing inventory for room {room_id}: {str(e)}")
            raise

    async def search_inventory(self, sku: str) -> List[InventoryResponse]:
        """Search inventory by SKU."""
        try:
            if not sku or not isinstance(sku, str):
                raise ValidationError("A valid SKU string is required for search")
            
            inventory_items = await self.inventory_db.search_by_sku(sku)
            return [InventoryResponse(**item) for item in inventory_items]
        except ValidationError as e:
            logger.error(f"Validation error searching inventory with SKU {sku}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error searching inventory with SKU {sku}: {str(e)}")
            raise ValidationError(f"Error searching inventory: {str(e)}")

