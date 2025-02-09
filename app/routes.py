from typing import List
from uuid import UUID
from fastapi import APIRouter, HTTPException, Depends, status, Query, Request
from fastapi.responses import JSONResponse
from app.models import (
    CustomerCreate,
    CustomerResponse,
    CustomerUpdate,
    WarehouseCreate,
    WarehouseResponse,
    WarehouseUpdate,
    RoomCreate,
    RoomResponse,
    InventoryCreate,
    InventoryResponse
)
from app.database import (
    CustomerDB,
    WarehouseDB,
    RoomDB,
    InventoryDB,
    ItemNotFoundError,
    ValidationError,
    DatabaseError,
    ConflictError
)

# Initialize routers
customer_router = APIRouter()
warehouse_router = APIRouter()
room_router = APIRouter()
inventory_router = APIRouter()

async def get_customer_db(request: Request) -> CustomerDB:
    """Get customer database instance."""
    if not hasattr(request.app.state, 'customer_db'):
        request.app.state.customer_db = CustomerDB()
    return request.app.state.customer_db

async def get_warehouse_db(request: Request) -> WarehouseDB:
    """Get warehouse database instance."""
    if not hasattr(request.app.state, 'warehouse_db'):
        request.app.state.warehouse_db = WarehouseDB()
    return request.app.state.warehouse_db

async def get_room_db(request: Request) -> RoomDB:
    """Get room database instance."""
    if not hasattr(request.app.state, 'room_db'):
        request.app.state.room_db = RoomDB()
    return request.app.state.room_db

async def get_inventory_db(request: Request) -> InventoryDB:
    """Get inventory database instance."""
    if not hasattr(request.app.state, 'inventory_db'):
        request.app.state.inventory_db = InventoryDB()
    return request.app.state.inventory_db

# Customer routes
@customer_router.post(
    "/",
    response_model=CustomerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new customer",
    tags=["customers"]
)
async def create_customer(
    customer: CustomerCreate,
    db: CustomerDB = Depends(get_customer_db)
):
    try:
        return await db.create_item(customer)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except ConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@customer_router.get(
    "/{customer_id}",
    response_model=CustomerResponse,
    summary="Get customer by ID",
    tags=["customers"]
)
async def get_customer(
    customer_id: str,
    db: CustomerDB = Depends(get_customer_db)
):
    """
    Retrieve a customer by their ID.
    """
    try:
        # Validate UUID format
        try:
            customer_id_uuid = UUID(customer_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid customer ID format"
            )
            
        customer = await db.get_item(str(customer_id_uuid))
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Customer {customer_id} not found"
            )
        return customer
    except ItemNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer {customer_id} not found"
        )
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@customer_router.get(
    "/",
    response_model=List[CustomerResponse],
    summary="List all customers",
    tags=["customers"]
)
async def list_customers(
    db: CustomerDB = Depends(get_customer_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, gt=0, le=100)
):
    """
    Retrieve a list of customers with pagination.
    """
    return await db.list_items(skip=skip, limit=limit)

@customer_router.patch(
    "/{customer_id}",
    response_model=CustomerResponse,
    summary="Update customer",
    tags=["customers"]
)
async def update_customer(
    customer_id: str,
    customer: CustomerUpdate,
    db: CustomerDB = Depends(get_customer_db)
):
    """
    Update a customer's information.
    """
    try:
        # Validate UUID format
        try:
            customer_id_uuid = UUID(customer_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid customer ID format"
            )
            
        return await db.update_item(str(customer_id_uuid), customer)
    except ItemNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer {customer_id} not found"
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@customer_router.delete(
    "/{customer_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete customer",
    tags=["customers"]
)
async def delete_customer(
    customer_id: str,
    db: CustomerDB = Depends(get_customer_db)
):
    """
    Delete a customer by their ID.
    """
    try:
        # Validate UUID format
        try:
            customer_id_uuid = UUID(customer_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid customer ID format"
            )
            
        await db.delete_item(str(customer_id_uuid))
    except ItemNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer {customer_id} not found"
        )
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@customer_router.get(
    "/email/{email}",
    response_model=CustomerResponse,
    summary="Get customer by email"
)
async def get_customer_by_email(
    email: str,
    db: CustomerDB = Depends(get_customer_db)
):
    """
    Retrieve a customer by their email address.
    """
    try:
        return await db.get_by_email(email)
    except ItemNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer with email {email} not found"
        )
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# Warehouse routes
@warehouse_router.post(
    "/",
    response_model=WarehouseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new warehouse",
    tags=["warehouses"]
)
async def create_warehouse(
    warehouse: WarehouseCreate,
    db: WarehouseDB = Depends(get_warehouse_db)
):
    try:
        return await db.create_warehouse(warehouse)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except ConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@warehouse_router.get(
    "/{warehouse_id}",
    response_model=WarehouseResponse,
    summary="Get warehouse by ID",
    tags=["warehouses"]
)
async def get_warehouse(
    warehouse_id: str,
    db: WarehouseDB = Depends(get_warehouse_db)
):
    try:
        # Validate UUID format
        try:
            warehouse_id_uuid = UUID(warehouse_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid warehouse ID format"
            )
            
        warehouse = await db.get_warehouse(str(warehouse_id_uuid))
        if not warehouse:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Warehouse {warehouse_id} not found"
            )
        return warehouse
    except ItemNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Warehouse {warehouse_id} not found"
        )
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@warehouse_router.get(
    "/",
    response_model=List[WarehouseResponse],
    summary="List warehouses by customer",
    tags=["warehouses"]
)
async def list_warehouses_by_customer(
    customer_id: UUID,
    db: WarehouseDB = Depends(get_warehouse_db)
):
    try:
        return await db.list_by_customer(str(customer_id))
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@warehouse_router.patch(
    "/{warehouse_id}",
    response_model=WarehouseResponse,
    summary="Update warehouse",
    tags=["warehouses"]
)
async def update_warehouse(
    warehouse_id: str,
    update_data: WarehouseUpdate,
    db: WarehouseDB = Depends(get_warehouse_db)
):
    try:
        # Validate UUID format
        try:
            warehouse_id_uuid = UUID(warehouse_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid warehouse ID format"
            )
            
        return await db.update_warehouse(str(warehouse_id_uuid), update_data)
    except ItemNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Warehouse {warehouse_id} not found"
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@warehouse_router.delete(
    "/{warehouse_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete warehouse",
    tags=["warehouses"]
)
async def delete_warehouse(
    warehouse_id: str,
    db: WarehouseDB = Depends(get_warehouse_db)
):
    try:
        # Validate UUID format
        try:
            warehouse_id_uuid = UUID(warehouse_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid warehouse ID format"
            )
            
        await db.delete_warehouse(str(warehouse_id_uuid))
    except ItemNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Warehouse {warehouse_id} not found"
        )
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@warehouse_router.get(
    "/{warehouse_id}/availability",
    response_model=dict,
    summary="Check warehouse availability"
)
async def check_warehouse_availability(
    warehouse_id: str,
    db: WarehouseDB = Depends(get_warehouse_db)
):
    """
    Check the current availability status of a warehouse.
    Returns capacity information and current usage.
    """
    try:
        availability = await db.check_availability(warehouse_id)
        return {
            "warehouse_id": warehouse_id,
            "available": availability["available"],
            "total_capacity": availability["total_capacity"],
            "used_capacity": availability["used_capacity"],
            "available_capacity": availability["available_capacity"]
        }
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail="Warehouse not found"
        )

@warehouse_router.get(
    "/{warehouse_id}/rooms",
    response_model=List[RoomResponse],
    summary="List rooms by warehouse",
    tags=["rooms"]
)
async def list_rooms_by_warehouse(
    warehouse_id: str,
    db: RoomDB = Depends(get_room_db)
):
    try:
        # Validate UUID format
        try:
            warehouse_id_uuid = UUID(warehouse_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid warehouse ID format"
            )
            
        try:
            return await db.list_rooms(str(warehouse_id_uuid))
        except ItemNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        except DatabaseError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing rooms: {str(e)}"
        )

# Room routes
@room_router.post(
    "/",
    response_model=RoomResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new room",
    tags=["rooms"]
)
async def create_room(
    room: RoomCreate,
    db: RoomDB = Depends(get_room_db)
):
    try:
        return await db.create_room(room)
    except ItemNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except ConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@room_router.get(
    "/{room_id}",
    response_model=RoomResponse,
    summary="Get room by ID",
    tags=["rooms"]
)
async def get_room(
    room_id: str,
    db: RoomDB = Depends(get_room_db)
):
    try:
        # Validate UUID format
        try:
            room_id_uuid = UUID(room_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid room ID format"
            )
            
        room = await db.get_room(str(room_id_uuid))
        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Room {room_id} not found"
            )
        return room
    except ItemNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Room {room_id} not found"
        )
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@room_router.patch(
    "/{room_id}",
    response_model=RoomResponse,
    summary="Update room",
    tags=["rooms"]
)
async def update_room(
    room_id: str,
    update_data: dict,
    db: RoomDB = Depends(get_room_db)
):
    try:
        # Validate UUID format
        try:
            room_id_uuid = UUID(room_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid room ID format"
            )
            
        return await db.update_room(str(room_id_uuid), update_data)
    except ItemNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Room {room_id} not found"
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@room_router.delete(
    "/{room_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete room",
    tags=["rooms"]
)
async def delete_room(
    room_id: str,
    db: RoomDB = Depends(get_room_db)
):
    try:
        # Validate UUID format
        try:
            room_id_uuid = UUID(room_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid room ID format"
            )
            
        await db.delete_room(str(room_id_uuid))
    except ItemNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Room {room_id} not found"
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@room_router.get(
    "/{room_id}/conditions",
    response_model=dict,
    summary="Get room conditions",
    tags=["rooms"]
)
async def get_room_conditions(
    room_id: str,
    db: RoomDB = Depends(get_room_db)
):
    try:
        room = await db.get_room(room_id)
        return {
            "temperature": room.temperature,
            "humidity": room.humidity
        }
    except ItemNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Room {room_id} not found"
        )
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# Inventory routes
@inventory_router.post(
    "/",
    response_model=InventoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add inventory",
    tags=["inventory"]
)
async def add_inventory(
    inventory: InventoryCreate,
    db: InventoryDB = Depends(get_inventory_db)
):
    try:
        return await db.create_inventory(inventory)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except ConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@inventory_router.get(
    "/{inventory_id}",
    response_model=InventoryResponse,
    summary="Get inventory by ID",
    tags=["inventory"]
)
async def get_inventory(
    inventory_id: str,
    db: InventoryDB = Depends(get_inventory_db)
):
    try:
        # Validate UUID format
        try:
            inventory_id_uuid = UUID(inventory_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid inventory ID format"
            )
            
        inventory = await db.get_inventory(str(inventory_id_uuid))
        if not inventory:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Inventory {inventory_id} not found"
            )
        return inventory
    except ItemNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inventory {inventory_id} not found"
        )
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@inventory_router.patch(
    "/{inventory_id}",
    response_model=InventoryResponse,
    summary="Update inventory",
    tags=["inventory"]
)
async def update_inventory(
    inventory_id: str,
    update_data: dict,
    db: InventoryDB = Depends(get_inventory_db)
):
    try:
        # Validate UUID format
        try:
            inventory_id_uuid = UUID(inventory_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid inventory ID format"
            )
            
        return await db.update_inventory(str(inventory_id_uuid), update_data)
    except ItemNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inventory {inventory_id} not found"
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@inventory_router.delete(
    "/{inventory_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete inventory",
    tags=["inventory"]
)
async def delete_inventory(
    inventory_id: str,
    db: InventoryDB = Depends(get_inventory_db)
):
    try:
        # Validate UUID format
        try:
            inventory_id_uuid = UUID(inventory_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid inventory ID format"
            )
            
        await db.delete_inventory(str(inventory_id_uuid))
    except ItemNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inventory {inventory_id} not found"
        )
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@inventory_router.post(
    "/{inventory_id}/transfer",
    response_model=InventoryResponse,
    summary="Transfer inventory",
    tags=["inventory"]
)
async def transfer_inventory(
    inventory_id: str,
    transfer_data: dict,
    db: InventoryDB = Depends(get_inventory_db)
):
    try:
        return await db.transfer_inventory(inventory_id, transfer_data)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except ItemNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inventory {inventory_id} not found"
        )
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@inventory_router.get(
    "/{inventory_id}/history",
    response_model=List[dict],
    summary="Get inventory history",
    tags=["inventory"]
)
async def get_inventory_history(
    inventory_id: str,
    db: InventoryDB = Depends(get_inventory_db)
):
    try:
        return await db.get_inventory_history(inventory_id)
    except ItemNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inventory {inventory_id} not found"
        )
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@inventory_router.get(
    "/search",
    response_model=List[InventoryResponse],
    summary="Search inventory",
    tags=["inventory"]
)
async def search_inventory(
    sku: str = None,
    warehouse_id: UUID = None,
    db: InventoryDB = Depends(get_inventory_db)
):
    try:
        return await db.search_inventory(sku=sku, warehouse_id=warehouse_id)
    except DatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

