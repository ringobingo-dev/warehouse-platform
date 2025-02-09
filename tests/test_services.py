import pytest
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Any
from fastapi import HTTPException
from app.models import (
    CustomerCreate, CustomerResponse,
    WarehouseCreate, WarehouseResponse,
    RoomCreate, RoomResponse,
    RoomStatus,
    InventoryCreate, InventoryResponse,
    VerificationStatus,
    WarehouseUpdate
)
from app.services import WarehouseService
from app.utils import handle_database_error
from app.database import ItemNotFoundError, ValidationError, DatabaseError
from uuid import UUID
from unittest.mock import AsyncMock

@pytest.fixture
def warehouse_service(mock_warehouse_db, mock_customer_db):
    return WarehouseService(warehouse_db=mock_warehouse_db, customer_db=mock_customer_db)

@pytest.fixture
def valid_warehouse_data():
    return WarehouseCreate(
        name="Test Warehouse",
        address="123 Test St",
        total_capacity=Decimal("1000.00"),
        customer_id=uuid.uuid4(),
        rooms=[]
    )

@pytest.fixture
def valid_room_data():
    return RoomCreate(
        name="Test Room",
        capacity=Decimal("100.00"),
        temperature=Decimal("20.00"),
        humidity=Decimal("50.00"),
        dimensions={
            "length": Decimal("10.0"),
            "width": Decimal("8.0"),
            "height": Decimal("4.0")
        },
        warehouse_id=uuid.uuid4()
    )

@pytest.fixture
def valid_inventory_data():
    return InventoryCreate(
        product_name="Test Product",
        quantity=Decimal("10.00"),
        unit_weight=Decimal("1.00"),
        total_weight=Decimal("10.00"),
        room_id=uuid.uuid4()
    )

# Database Operation Tests
@pytest.mark.asyncio
async def test_create_warehouse_success(warehouse_service, valid_warehouse_data, mock_customer_db):
    """Test successful warehouse creation."""
    mock_customer_db.get_customer.return_value = True
    
    # Convert warehouse data to dict if it's a Pydantic model
    warehouse_dict = valid_warehouse_data.model_dump() if hasattr(valid_warehouse_data, 'model_dump') else valid_warehouse_data
    
    # Set up mock response
    mock_response = {
        "id": str(uuid.uuid4()),
        **warehouse_dict,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "available_capacity": warehouse_dict["total_capacity"],
        "rooms": []
    }
    
    warehouse_service.warehouse_db.create_warehouse.return_value = WarehouseResponse(**mock_response)
    
    response = await warehouse_service.create_warehouse(valid_warehouse_data)
    assert response.id is not None
    assert response.name == valid_warehouse_data.name
    assert response.total_capacity == valid_warehouse_data.total_capacity

@pytest.mark.asyncio
async def test_create_warehouse_customer_not_found(warehouse_service, valid_warehouse_data, mock_customer_db):
    """Test warehouse creation with non-existent customer."""
    mock_customer_db.get_customer.side_effect = ItemNotFoundError("Customer not found")
    
    with pytest.raises(ValueError, match="Customer .* not found"):
        await warehouse_service.create_warehouse(valid_warehouse_data)

@pytest.mark.asyncio
async def test_get_warehouse_success(mock_warehouse_db, mock_customer_db, test_warehouse):
    """Test successful warehouse retrieval"""
    service = WarehouseService(warehouse_db=mock_warehouse_db, customer_db=mock_customer_db)
    result = await service.get_warehouse(test_warehouse["id"])
    
    assert result is not None
    assert str(result.id) == test_warehouse["id"]
    assert result.name == test_warehouse["name"]

@pytest.mark.asyncio
async def test_get_warehouse_not_found(warehouse_service, mock_warehouse_db):
    """Test warehouse retrieval with non-existent ID."""
    mock_warehouse_db.get_warehouse.side_effect = ItemNotFoundError("Warehouse not found")
    with pytest.raises(HTTPException) as exc_info:
        await warehouse_service.get_warehouse(str(uuid.uuid4()))
    assert exc_info.value.status_code == 404

@pytest.mark.asyncio
async def test_create_warehouse_with_rooms(warehouse_service, valid_warehouse_data):
    """Test warehouse creation with multiple rooms."""
    response = await warehouse_service.create_warehouse(valid_warehouse_data)
    assert len(response.rooms) == len(valid_warehouse_data.rooms)
    for room in response.rooms:
        assert room.room_id is not None
        assert room.dimensions.width > 0
        assert room.dimensions.length > 0
        assert room.dimensions.height > 0

@pytest.mark.asyncio
async def test_update_warehouse_success(mock_warehouse_db, mock_customer_db, test_warehouse):
    """Test successful warehouse update"""
    service = WarehouseService(warehouse_db=mock_warehouse_db, customer_db=mock_customer_db)
    update_data = WarehouseUpdate(name="Updated Warehouse")
    
    mock_warehouse_db.update_warehouse.return_value = {
        **test_warehouse,
        "name": update_data.name,
        "updated_at": datetime.now(timezone.utc)
    }
    
    result = await service.update_warehouse(test_warehouse["id"], update_data)
    
    assert result is not None
    assert str(result.id) == test_warehouse["id"]
    assert result.name == update_data.name

# Business Logic Tests
@pytest.mark.asyncio
async def test_calculate_room_capacity(mock_warehouse_db, mock_customer_db, test_room):
    """Test room capacity calculation"""
    service = WarehouseService(warehouse_db=mock_warehouse_db, customer_db=mock_customer_db)
    room_data = {
        "dimensions": {
            "length": Decimal("10.0"),
            "width": Decimal("8.0"),
            "height": Decimal("4.0")
        }
    }
    capacity = await service.calculate_room_capacity(room_data)
    
    assert isinstance(capacity, Decimal)
    assert capacity > Decimal("0")

@pytest.mark.asyncio
async def test_validate_room_dimensions(warehouse_service, valid_room_data):
    """Test room dimension validation."""
    valid_room_data.dimensions.width = -1
    with pytest.raises(ValueError) as exc_info:
        await warehouse_service.create_room(str(valid_room_data.warehouse_id), valid_room_data)
    assert "width must be positive" in str(exc_info.value)

# Customer Verification Tests
@pytest.mark.asyncio
async def test_create_customer_with_verification(warehouse_service, valid_customer_data):
    """Test customer creation with verification."""
    response = await warehouse_service.create_customer(valid_customer_data)
    assert response.customer_id is not None
    assert response.verification_status == "PENDING"

@pytest.mark.asyncio
async def test_verify_customer_success(warehouse_service, existing_customer):
    """Test successful customer verification."""
    # Create initial customer with PENDING status
    initial_customer = CustomerResponse(
        id=existing_customer.id,
        name=existing_customer.name,
        email=existing_customer.email,
        phone_number=existing_customer.phone_number,
        address=existing_customer.address,
        created_at=existing_customer.created_at,
        updated_at=existing_customer.updated_at,
        verification_status=VerificationStatus.PENDING
    )
    
    # Create expected response with VERIFIED status
    expected_response = CustomerResponse(
        id=existing_customer.id,
        name=existing_customer.name,
        email=existing_customer.email,
        phone_number=existing_customer.phone_number,
        address=existing_customer.address,
        created_at=existing_customer.created_at,
        updated_at=existing_customer.updated_at,
        verification_status=VerificationStatus.VERIFIED
    )
    
    # Setup mocks
    warehouse_service.customer_db.get_customer = AsyncMock(return_value=initial_customer)
    warehouse_service.customer_db.update_item = AsyncMock(return_value=expected_response)
    
    # Test verification
    response = await warehouse_service.verify_customer(
        existing_customer.customer_id,
        {"verification_status": VerificationStatus.VERIFIED}
    )
    assert response.verification_status == VerificationStatus.VERIFIED

@pytest.mark.asyncio
async def test_verify_customer_invalid_transition(warehouse_service, existing_customer):
    """Test invalid verification status transition."""
    # Create customer with REJECTED status
    initial_customer = CustomerResponse(
        id=existing_customer.id,
        name=existing_customer.name,
        email=existing_customer.email,
        phone_number=existing_customer.phone_number,
        address=existing_customer.address,
        created_at=existing_customer.created_at,
        updated_at=existing_customer.updated_at,
        verification_status=VerificationStatus.REJECTED
    )
    
    warehouse_service.customer_db.get_customer = AsyncMock(return_value=initial_customer)
    
    # Test invalid transition from REJECTED to PENDING
    with pytest.raises(ValueError, match="Invalid status transition"):
        await warehouse_service.verify_customer(
            existing_customer.customer_id,
            {"verification_status": VerificationStatus.PENDING}
        )

# Error Handling Tests
@pytest.mark.asyncio
async def test_warehouse_not_found(warehouse_service):
    """Test warehouse not found error."""
    warehouse_service.warehouse_db.get_warehouse.side_effect = ItemNotFoundError("Warehouse not found")
    with pytest.raises(HTTPException) as exc_info:
        await warehouse_service.get_warehouse(str(uuid.uuid4()))
    assert exc_info.value.status_code == 404

@pytest.mark.asyncio
async def test_check_room_availability(warehouse_service, existing_room):
    """Test room availability check."""
    mock_room = {
        "id": str(existing_room.id),
        "name": existing_room.name,
        "capacity": existing_room.capacity,
        "temperature": existing_room.temperature,
        "humidity": existing_room.humidity,
        "dimensions": existing_room.dimensions.model_dump(),
        "warehouse_id": str(existing_room.warehouse_id),
        "status": existing_room.status,
        "available_capacity": existing_room.available_capacity,
        "created_at": existing_room.created_at,
        "updated_at": existing_room.updated_at
    }
    warehouse_service.warehouse_db.get_room.return_value = mock_room
    available = await warehouse_service.check_room_availability(
        str(existing_room.warehouse_id),
        str(existing_room.id),
        width=2.0,
        length=2.0,
        height=2.0
    )
    assert isinstance(available, bool)

@pytest.mark.asyncio
async def test_invalid_room_update(warehouse_service, existing_room):
    """Test invalid room update."""
    mock_room = {
        "id": str(existing_room.id),
        "name": existing_room.name,
        "capacity": existing_room.capacity,
        "temperature": existing_room.temperature,
        "humidity": existing_room.humidity,
        "dimensions": existing_room.dimensions.model_dump(),
        "warehouse_id": str(existing_room.warehouse_id),
        "status": existing_room.status,
        "available_capacity": existing_room.available_capacity,
        "created_at": existing_room.created_at,
        "updated_at": existing_room.updated_at
    }
    warehouse_service.warehouse_db.get_room.return_value = mock_room
    warehouse_service.warehouse_db.update_room.return_value = mock_room
    with pytest.raises(ValueError) as exc_info:
        await warehouse_service.update_room(
            str(existing_room.warehouse_id),
            str(existing_room.id),
            {"max_weight_capacity": -100}
        )
    assert "weight capacity must be positive" in str(exc_info.value)

# Transaction Tests
@pytest.mark.asyncio
async def test_warehouse_creation_transaction(mock_warehouse_db, mock_customer_db, test_customer, valid_warehouse_data):
    """Test warehouse creation transaction"""
    service = WarehouseService(warehouse_db=mock_warehouse_db, customer_db=mock_customer_db)
    mock_warehouse_db.create_warehouse.return_value = {
        "id": str(uuid.uuid4()),
        "name": valid_warehouse_data.name,
        "address": valid_warehouse_data.address,
        "total_capacity": str(valid_warehouse_data.total_capacity),
        "customer_id": str(valid_warehouse_data.customer_id),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "available_capacity": str(valid_warehouse_data.total_capacity),
        "rooms": []
    }
    
    result = await service.create_warehouse(valid_warehouse_data)
    
    assert result is not None
    assert result.name == valid_warehouse_data.name
    assert str(result.customer_id) == str(valid_warehouse_data.customer_id)

# Space Management Tests
@pytest.mark.asyncio
async def test_calculate_warehouse_utilization(mock_warehouse_db, mock_customer_db, test_warehouse, test_inventory):
    """Test warehouse utilization calculation"""
    service = WarehouseService(warehouse_db=mock_warehouse_db, customer_db=mock_customer_db)
    mock_warehouse_db.get_inventory_levels.return_value = {
        "total_items": 1,
        "items_by_sku": {
            test_inventory["sku"]: {
                "quantity": test_inventory["quantity"],
                "total_weight": "100.00"
            }
        }
    }
    
    result = await service.calculate_warehouse_utilization(test_warehouse["id"])
    
    assert isinstance(result["utilization_percentage"], Decimal)
    assert result["utilization_percentage"] >= Decimal("0")
    assert result["utilization_percentage"] <= Decimal("100")

# Room Tests
@pytest.mark.asyncio
async def test_create_room_success(warehouse_service, valid_room_data, mock_warehouse_db):
    """Test successful room creation."""
    mock_warehouse_db.get_warehouse.return_value = True
    mock_warehouse_db.create_room.return_value = {
        "id": str(uuid.uuid4()),
        **valid_room_data.model_dump(),
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    }
    response = await warehouse_service.create_room(str(uuid.uuid4()), valid_room_data)
    assert response.id is not None
    assert response.name == valid_room_data.name

@pytest.mark.asyncio
async def test_update_room_status(warehouse_service, mock_warehouse_db):
    """Test room status update."""
    room_id = str(uuid.uuid4())
    warehouse_id = str(uuid.uuid4())
    mock_room = {
        "id": room_id,
        "status": RoomStatus.ACTIVE,
        "name": "Test Room",
        "capacity": Decimal("100.00"),
        "temperature": Decimal("20.00"),
        "humidity": Decimal("50.00"),
        "dimensions": {
            "length": Decimal("10.0"),
            "width": Decimal("8.0"),
            "height": Decimal("4.0")
        },
        "warehouse_id": warehouse_id,
        "available_capacity": Decimal("100.00"),
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    }
    mock_warehouse_db.get_room.return_value = mock_room
    mock_warehouse_db.update_room.return_value = {
        **mock_room,
        "status": RoomStatus.MAINTENANCE
    }
    response = await warehouse_service.update_room_status(
        warehouse_id, room_id, RoomStatus.MAINTENANCE
    )
    assert response.status == RoomStatus.MAINTENANCE

# Inventory Tests
@pytest.mark.asyncio
async def test_add_inventory_success(warehouse_service, valid_inventory_data, mock_warehouse_db):
    """Test successful inventory addition."""
    mock_warehouse_db.get_warehouse.return_value = WarehouseResponse(
        id=uuid.uuid4(),
        name="Test Warehouse",
        address="123 Test St",
        total_capacity=Decimal("1000.00"),
        customer_id=uuid.uuid4(),
        created_at=datetime.now(),
        updated_at=datetime.now(),
        available_capacity=Decimal("1000.00")
    )
    mock_warehouse_db.get_inventory_levels.return_value = []
    mock_warehouse_db.add_inventory.return_value = {
        "id": str(uuid.uuid4()),
        "product_name": valid_inventory_data.product_name,
        "quantity": valid_inventory_data.quantity,
        "unit_weight": valid_inventory_data.unit_weight,
        "total_weight": valid_inventory_data.total_weight,
        "room_id": str(valid_inventory_data.room_id),
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    }
    response = await warehouse_service.add_inventory(str(uuid.uuid4()), valid_inventory_data)
    assert response.product_name == valid_inventory_data.product_name
    assert response.quantity == valid_inventory_data.quantity

@pytest.mark.asyncio
async def test_add_inventory_insufficient_capacity(warehouse_service, valid_inventory_data):
    """Test inventory addition with insufficient capacity."""
    # Mock warehouse with very low capacity
    mock_warehouse = WarehouseResponse(
        id=uuid.uuid4(),
        name="Test Warehouse",
        address="123 Test St",
        total_capacity=Decimal("5.00"),  # Set low capacity
        customer_id=uuid.uuid4(),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        available_capacity=Decimal("5.00"),
        rooms=[]
    )
    
    # Mock get_warehouse to return our mock warehouse with low capacity
    async def mock_get_warehouse(warehouse_id):
        return mock_warehouse
    warehouse_service.warehouse_db.get_warehouse.side_effect = mock_get_warehouse
    
    # Mock empty current inventory
    warehouse_service.warehouse_db.get_inventory.return_value = []
    
    # Set inventory data with weight exceeding capacity
    valid_inventory_data.quantity = Decimal("10.00")
    valid_inventory_data.unit_weight = Decimal("1.00")
    valid_inventory_data.total_weight = Decimal("10.00")
    
    # Try to add inventory that exceeds capacity
    with pytest.raises(ValueError, match="Insufficient warehouse capacity"):
        await warehouse_service.add_inventory(str(mock_warehouse.id), valid_inventory_data)

# Validation Tests
@pytest.mark.asyncio
async def test_validate_status_transition(warehouse_service):
    """Test room status transition validation."""
    assert warehouse_service._validate_status_transition(
        RoomStatus.ACTIVE, RoomStatus.MAINTENANCE
    ) is True
    assert warehouse_service._validate_status_transition(
        RoomStatus.ACTIVE, RoomStatus.ACTIVE
    ) is False

@pytest.mark.asyncio
async def test_validate_warehouse_capacity(warehouse_service, valid_warehouse_data):
    """Test warehouse capacity validation."""
    assert warehouse_service._validate_warehouse_capacity(valid_warehouse_data.model_dump()) is True
    valid_warehouse_data.total_capacity = Decimal("-1.00")
    assert warehouse_service._validate_warehouse_capacity(valid_warehouse_data.model_dump()) is False

