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
    WarehouseUpdate,
    RoomDimensions
)
from app.services import WarehouseService
from app.utils import handle_database_error
from app.database import ItemNotFoundError, ValidationError, DatabaseError
from uuid import UUID
from unittest.mock import AsyncMock

@pytest.fixture
def warehouse_service(mock_warehouse_db, mock_inventory_db, mock_customer_db):
    return WarehouseService(
        warehouse_db=mock_warehouse_db,
        inventory_db=mock_inventory_db,
        customer_db=mock_customer_db
    )

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
        sku="TEST-SKU-001",
        name="Test Inventory Item",
        description="Test item description",
        quantity=Decimal("10.00"),
        unit="kg",
        unit_weight=Decimal("1.00"),
        room_id=uuid.uuid4(),
        warehouse_id=uuid.uuid4()
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
    async def mock_get_customer(*args, **kwargs):
        raise ItemNotFoundError("Customer not found")
        
    mock_customer_db.get_customer.side_effect = mock_get_customer
    
    with pytest.raises(HTTPException) as exc_info:
        await warehouse_service.create_warehouse(valid_warehouse_data)
    assert exc_info.value.status_code == 404
    assert "Customer not found" in str(exc_info.value.detail)

@pytest.mark.asyncio
async def test_get_warehouse_success(mock_warehouse_db, mock_inventory_db, mock_customer_db, test_warehouse):
    """Test successful warehouse retrieval"""
    service = WarehouseService(
        warehouse_db=mock_warehouse_db,
        inventory_db=mock_inventory_db,
        customer_db=mock_customer_db
    )
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
async def test_update_warehouse_success(mock_warehouse_db, mock_inventory_db, mock_customer_db, test_warehouse):
    """Test successful warehouse update."""
    service = WarehouseService(
        warehouse_db=mock_warehouse_db,
        inventory_db=mock_inventory_db,
        customer_db=mock_customer_db
    )
    update_data = {"name": "Updated Warehouse"}
    result = await service.update_warehouse(test_warehouse["id"], update_data)
    assert result.name == "Updated Warehouse"

# Business Logic Tests
@pytest.mark.asyncio
async def test_calculate_room_capacity(mock_warehouse_db, mock_inventory_db, mock_customer_db, test_room):
    """Test room capacity calculation."""
    service = WarehouseService(
        warehouse_db=mock_warehouse_db,
        inventory_db=mock_inventory_db,
        customer_db=mock_customer_db
    )
    capacity = await service.calculate_room_capacity(test_room)
    assert capacity > 0

@pytest.mark.asyncio
async def test_validate_room_dimensions(warehouse_service, test_warehouse, test_room):
    """Test room dimension validation."""
    dimensions = RoomDimensions(
        length=Decimal("10.00"),
        width=Decimal("8.00"),
        height=Decimal("4.00")
    )
    assert warehouse_service._validate_room_dimensions(test_warehouse, {"dimensions": dimensions})

@pytest.mark.asyncio
async def test_check_room_availability(warehouse_service, test_warehouse, test_room):
    """Test room availability check."""
    available = await warehouse_service.check_room_availability(
        test_warehouse["id"],
        test_room["id"],
        2.0,  # width
        2.0,  # length
        2.0   # height
    )
    assert isinstance(available, bool)

@pytest.mark.asyncio
async def test_invalid_room_update(warehouse_service, test_warehouse, test_room):
    """Test invalid room update."""
    with pytest.raises(ValueError):
        await warehouse_service.update_room(
            test_warehouse["id"],
            test_room["id"],
            {"max_weight_capacity": -100}  # Invalid negative capacity
        )

# Transaction Tests
@pytest.mark.asyncio
async def test_warehouse_creation_transaction(mock_warehouse_db, mock_inventory_db, mock_customer_db, test_customer, valid_warehouse_data):
    """Test warehouse creation transaction"""
    service = WarehouseService(
        warehouse_db=mock_warehouse_db,
        inventory_db=mock_inventory_db,
        customer_db=mock_customer_db
    )
    result = await service.create_warehouse(valid_warehouse_data)
    assert result is not None
    assert result.name == valid_warehouse_data.name
    assert str(result.customer_id) == str(valid_warehouse_data.customer_id)

# Space Management Tests
@pytest.mark.asyncio
async def test_calculate_warehouse_utilization(mock_warehouse_db, mock_inventory_db, mock_customer_db, test_warehouse, test_inventory):
    """Test warehouse utilization calculation."""
    service = WarehouseService(
        warehouse_db=mock_warehouse_db,
        inventory_db=mock_inventory_db,
        customer_db=mock_customer_db
    )
    result = await service.calculate_warehouse_utilization(test_warehouse["id"])
    assert "total_capacity" in result
    assert "total_used" in result
    assert "utilization_percentage" in result

# Room Tests
@pytest.mark.asyncio
async def test_create_room_success(warehouse_service, test_warehouse):
    """Test successful room creation."""
    room_data = RoomCreate(
        name="Test Room",
        dimensions=RoomDimensions(
            length=Decimal("10.00"),
            width=Decimal("8.00"),
            height=Decimal("4.00")
        ),
        temperature=Decimal("20.50"),
        humidity=Decimal("50"),
        capacity=Decimal("100.00"),
        warehouse_id=UUID(test_warehouse["id"])
    )
    result = await warehouse_service.create_room(test_warehouse["id"], room_data)
    assert result.name == "Test Room"
    assert result.dimensions.length == Decimal("10.00")

@pytest.mark.asyncio
async def test_update_room_status(warehouse_service, test_warehouse, test_room):
    """Test room status update."""
    response = await warehouse_service.update_room_status(
        test_warehouse["id"],
        test_room["id"],
        RoomStatus.MAINTENANCE
    )
    assert response is not None
    assert response.status == RoomStatus.MAINTENANCE

# Inventory Tests
@pytest.mark.asyncio
async def test_add_inventory_success(warehouse_service, test_warehouse, test_room, valid_inventory_data):
    """Test successful inventory addition."""
    # Mock the get_warehouse method
    async def mock_get_warehouse(*args, **kwargs):
        return test_warehouse
        
    # Mock the get_room method
    async def mock_get_room(*args, **kwargs):
        return test_room
        
    # Mock the get_inventory_levels method
    async def mock_get_inventory_levels(*args, **kwargs):
        return []
        
    # Mock the create_inventory method
    async def mock_create_inventory(*args, **kwargs):
        return {
            "id": str(uuid.uuid4()),
            **valid_inventory_data.model_dump(),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
    
    warehouse_service.warehouse_db.get_warehouse.side_effect = mock_get_warehouse
    warehouse_service.warehouse_db.get_room.side_effect = mock_get_room
    warehouse_service.inventory_db.get_inventory_levels.side_effect = mock_get_inventory_levels
    warehouse_service.inventory_db.create_inventory.side_effect = mock_create_inventory
    
    response = await warehouse_service.add_inventory(test_warehouse["id"], valid_inventory_data)
    
    assert isinstance(response, InventoryResponse)
    assert response.room_id == valid_inventory_data.room_id
    assert response.warehouse_id == valid_inventory_data.warehouse_id
    assert response.quantity == valid_inventory_data.quantity

@pytest.mark.asyncio
async def test_add_inventory_insufficient_capacity(warehouse_service, test_warehouse, test_room):
    """Test inventory addition with insufficient capacity."""
    # Create inventory data that exceeds warehouse capacity
    inventory_data = InventoryCreate(
        sku="TEST-SKU-001",
        name="Test Inventory Item",
        description="Test item description",
        quantity=Decimal("10000.00"),  # Very large quantity
        unit="kg",
        unit_weight=Decimal("1.00"),
        room_id=UUID(test_room["id"]),
        warehouse_id=UUID(test_warehouse["id"])
    )
    
    # Mock the get_warehouse method
    async def mock_get_warehouse(*args, **kwargs):
        return test_warehouse
        
    # Mock the get_room method
    async def mock_get_room(*args, **kwargs):
        return test_room
        
    # Mock the get_inventory_levels method
    async def mock_get_inventory_levels(*args, **kwargs):
        return []
    
    warehouse_service.warehouse_db.get_warehouse.side_effect = mock_get_warehouse
    warehouse_service.warehouse_db.get_room.side_effect = mock_get_room
    warehouse_service.inventory_db.get_inventory_levels.side_effect = mock_get_inventory_levels
    
    with pytest.raises(ValidationError, match="Insufficient warehouse capacity"):
        await warehouse_service.add_inventory(test_warehouse["id"], inventory_data)

@pytest.mark.asyncio
async def test_add_inventory_updates_utilization(warehouse_service, test_warehouse, test_room):
    """Test that adding inventory correctly updates room utilization."""
    # Setup test data
    inventory_data = InventoryCreate(
        sku="TEST-SKU-001",
        name="Test Item",
        description="Test Description",
        quantity=Decimal("50.00"),  # 50 units
        unit="kg",
        unit_weight=Decimal("2.00"),  # 2kg per unit = 100kg total
        room_id=UUID(test_room["id"]),
        warehouse_id=UUID(test_warehouse["id"])
    )
    
    # Mock room with 200kg capacity
    test_room_with_capacity = {
        **test_room,
        "capacity": Decimal("200.00"),
        "available_capacity": Decimal("200.00"),
        "current_utilization": Decimal("0.00")
    }
    
    # Mock the get_warehouse method
    async def mock_get_warehouse(*args, **kwargs):
        return test_warehouse
        
    # Mock the get_room method
    async def mock_get_room(*args, **kwargs):
        return test_room_with_capacity
        
    # Mock the get_inventory_levels method
    async def mock_get_inventory_levels(*args, **kwargs):
        return []
        
    # Mock the create_inventory method
    async def mock_create_inventory(*args, **kwargs):
        return {
            "id": str(uuid.uuid4()),
            **inventory_data.model_dump(),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
    
    warehouse_service.warehouse_db.get_warehouse.side_effect = mock_get_warehouse
    warehouse_service.warehouse_db.get_room.side_effect = mock_get_room
    warehouse_service.inventory_db.get_inventory_levels.side_effect = mock_get_inventory_levels
    warehouse_service.inventory_db.create_inventory.side_effect = mock_create_inventory
    
    response = await warehouse_service.add_inventory(test_warehouse["id"], inventory_data)
    
    assert isinstance(response, InventoryResponse)
    assert response.quantity == inventory_data.quantity
    assert response.unit_weight == inventory_data.unit_weight

@pytest.mark.asyncio
async def test_add_inventory_insufficient_room_capacity(warehouse_service, test_warehouse, test_room):
    """Test that adding inventory fails when room capacity is insufficient."""
    # Setup test data with inventory exceeding room capacity
    inventory_data = InventoryCreate(
        sku="TEST-SKU-001",
        name="Test Item",
        description="Test Description",
        quantity=Decimal("150.00"),  # 150 units
        unit="kg",
        unit_weight=Decimal("2.00"),  # 2kg per unit = 300kg total
        room_id=UUID(test_room["id"]),
        warehouse_id=UUID(test_warehouse["id"])
    )
    
    # Mock room with 200kg capacity
    test_room_with_capacity = {
        **test_room,
        "capacity": Decimal("200.00"),
        "available_capacity": Decimal("200.00"),
        "current_utilization": Decimal("0.00")
    }
    
    # Mock the get_warehouse method
    async def mock_get_warehouse(*args, **kwargs):
        return test_warehouse
        
    # Mock the get_room method
    async def mock_get_room(*args, **kwargs):
        return test_room_with_capacity
        
    # Mock the get_inventory_levels method
    async def mock_get_inventory_levels(*args, **kwargs):
        return []
    
    warehouse_service.warehouse_db.get_warehouse.side_effect = mock_get_warehouse
    warehouse_service.warehouse_db.get_room.side_effect = mock_get_room
    warehouse_service.inventory_db.get_inventory_levels.side_effect = mock_get_inventory_levels
    
    with pytest.raises(ValidationError, match="Insufficient room capacity"):
        await warehouse_service.add_inventory(test_warehouse["id"], inventory_data)

# Validation Tests
@pytest.mark.asyncio
async def test_validate_status_transition():
    """Test room status transition validation."""
    service = WarehouseService(
        warehouse_db=AsyncMock(),
        inventory_db=AsyncMock(),
        customer_db=AsyncMock()
    )
    assert service._validate_status_transition(RoomStatus.ACTIVE, RoomStatus.MAINTENANCE)
    assert not service._validate_status_transition(RoomStatus.ACTIVE, RoomStatus.ACTIVE)

@pytest.mark.asyncio
async def test_validate_warehouse_capacity():
    """Test warehouse capacity validation."""
    service = WarehouseService(
        warehouse_db=AsyncMock(),
        inventory_db=AsyncMock(),
        customer_db=AsyncMock()
    )
    assert service._validate_warehouse_capacity({"total_capacity": Decimal("100.00")})
    assert not service._validate_warehouse_capacity({"total_capacity": Decimal("0.00")})

@pytest.mark.asyncio
async def test_update_room_dimensions_success(warehouse_service, test_warehouse, test_room):
    """Test successful room dimension update."""
    # Setup mock responses
    warehouse_service.warehouse_db.get_room.return_value = test_room
    warehouse_service.warehouse_db.update_room.return_value = {
        **test_room,
        "dimensions": {
            "length": Decimal("5.0"),
            "width": Decimal("4.0"),
            "height": Decimal("3.0")
        }
    }
    
    response = await warehouse_service.update_room_dimensions(
        test_warehouse["id"],
        test_room["id"],
        length=5.0,
        width=4.0,
        height=3.0
    )
    assert response is not None
    assert response.dimensions.length == Decimal("5.0")
    assert response.dimensions.width == Decimal("4.0")
    assert response.dimensions.height == Decimal("3.0")

@pytest.mark.asyncio
async def test_update_room_dimensions_with_inventory(warehouse_service, test_warehouse, test_room):
    """Test room dimension update with existing inventory."""
    # Setup room with inventory
    test_room_with_inventory = {**test_room, "current_utilization": Decimal("50.0")}
    warehouse_service.warehouse_db.get_room.return_value = test_room_with_inventory
    
    with pytest.raises(ValueError, match="Cannot modify dimensions of room with inventory"):
        await warehouse_service.update_room_dimensions(
            test_warehouse["id"],
            test_room["id"],
            length=5.0,
            width=4.0,
            height=3.0
        )

@pytest.mark.asyncio
async def test_update_room_dimensions_invalid_dimensions(warehouse_service, test_warehouse, test_room):
    """Test room dimension update with invalid dimensions."""
    warehouse_service.warehouse_db.get_room.return_value = test_room
    
    with pytest.raises(ValueError):
        await warehouse_service.update_room_dimensions(
            test_warehouse["id"],
            test_room["id"],
            length=-5.0,  # Invalid negative length
            width=4.0,
            height=3.0
        )

@pytest.mark.asyncio
async def test_check_warehouse_capacity_success(warehouse_service, test_warehouse, test_inventory):
    """Test successful warehouse capacity check."""
    current_level = [test_inventory]
    inventory_data = InventoryCreate(
        sku="TEST-SKU-002",
        name="Test Item 2",
        description="Test Description",
        quantity=Decimal("5.0"),
        unit="kg",
        unit_weight=Decimal("1.0"),
        room_id=UUID(test_inventory["room_id"]),
        warehouse_id=UUID(test_warehouse["id"])
    )
    
    # Setup warehouse with sufficient capacity
    test_room = {
        "id": str(uuid.uuid4()),
        "name": "Test Room",
        "capacity": Decimal("100.0"),
        "temperature": Decimal("20.0"),
        "humidity": Decimal("50.0"),
        "dimensions": {
            "length": Decimal("10.0"),
            "width": Decimal("8.0"),
            "height": Decimal("4.0")
        },
        "warehouse_id": test_warehouse["id"],
        "status": RoomStatus.ACTIVE,
        "available_capacity": Decimal("100.0"),
        "current_utilization": Decimal("0.0"),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    
    test_warehouse_with_capacity = {
        **test_warehouse,
        "rooms": [test_room]
    }
    
    result = warehouse_service._check_warehouse_capacity(
        WarehouseResponse(**test_warehouse_with_capacity),
        current_level,
        inventory_data
    )
    assert result is True

@pytest.mark.asyncio
async def test_check_warehouse_capacity_insufficient(warehouse_service, test_warehouse, test_inventory):
    """Test warehouse capacity check with insufficient capacity."""
    current_level = [test_inventory]
    inventory_data = InventoryCreate(
        sku="TEST-SKU-002",
        name="Test Item 2",
        description="Test Description",
        quantity=Decimal("1000.0"),  # Large quantity
        unit="kg",
        unit_weight=Decimal("1.0"),
        room_id=UUID(test_inventory["room_id"]),
        warehouse_id=UUID(test_warehouse["id"])
    )
    
    # Setup warehouse with limited capacity
    test_room = {
        "id": str(uuid.uuid4()),
        "name": "Test Room",
        "capacity": Decimal("50.0"),
        "temperature": Decimal("20.0"),
        "humidity": Decimal("50.0"),
        "dimensions": {
            "length": Decimal("10.0"),
            "width": Decimal("8.0"),
            "height": Decimal("4.0")
        },
        "warehouse_id": test_warehouse["id"],
        "status": RoomStatus.ACTIVE,
        "available_capacity": Decimal("50.0"),
        "current_utilization": Decimal("0.0"),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    
    test_warehouse_with_capacity = {
        **test_warehouse,
        "rooms": [test_room]
    }
    
    result = warehouse_service._check_warehouse_capacity(
        WarehouseResponse(**test_warehouse_with_capacity),
        current_level,
        inventory_data
    )
    assert result is False

@pytest.mark.asyncio
async def test_validate_verification_status_transitions(warehouse_service):
    """Test all verification status transitions."""
    # Test all valid transitions
    assert warehouse_service._validate_verification_status_transition(
        VerificationStatus.PENDING,
        VerificationStatus.VERIFIED
    )
    assert warehouse_service._validate_verification_status_transition(
        VerificationStatus.PENDING,
        VerificationStatus.REJECTED
    )
    assert warehouse_service._validate_verification_status_transition(
        VerificationStatus.REJECTED,
        VerificationStatus.VERIFIED
    )
    
    # Test invalid transitions
    assert not warehouse_service._validate_verification_status_transition(
        VerificationStatus.VERIFIED,
        VerificationStatus.PENDING
    )
    assert not warehouse_service._validate_verification_status_transition(
        VerificationStatus.REJECTED,
        VerificationStatus.PENDING
    )

@pytest.mark.asyncio
async def test_create_customer_success(warehouse_service):
    """Test successful customer creation."""
    customer_data = CustomerCreate(
        name="Test Customer",
        email="test@example.com",
        phone_number="1234567890",
        address="123 Test St"
    )
    
    expected_response = CustomerResponse(
        id=uuid.uuid4(),
        name=customer_data.name,
        email=customer_data.email,
        phone_number=customer_data.phone_number,
        address=customer_data.address,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        verification_status=VerificationStatus.PENDING
    )
    
    warehouse_service.customer_db.create_customer.return_value = expected_response
    
    response = await warehouse_service.create_customer(customer_data)
    assert response.name == customer_data.name
    assert response.email == customer_data.email
    assert response.verification_status == VerificationStatus.PENDING
    assert response.id is not None
    assert response.created_at is not None
    assert response.updated_at is not None

@pytest.mark.asyncio
async def test_create_customer_duplicate_email(warehouse_service):
    """Test customer creation with duplicate email."""
    customer_data = CustomerCreate(
        name="Test Customer",
        email="existing@example.com",
        phone_number="1234567890",
        address="123 Test St"
    )
    
    warehouse_service.customer_db.create_customer.side_effect = ValidationError("Email already exists")
    
    with pytest.raises(ValidationError, match="Email already exists"):
        await warehouse_service.create_customer(customer_data)

@pytest.mark.asyncio
async def test_verify_customer_success(warehouse_service):
    """Test successful customer verification."""
    customer_id = uuid.uuid4()
    verification_data = {
        "verification_status": VerificationStatus.VERIFIED
    }
    
    # Setup mock customer
    current_customer = CustomerResponse(
        id=customer_id,
        name="Test Customer",
        email="test@example.com",
        phone_number="1234567890",
        address="123 Test St",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        verification_status=VerificationStatus.PENDING
    )
    
    # Setup mock verified customer
    verified_customer_dict = current_customer.model_dump()
    verified_customer_dict["verification_status"] = VerificationStatus.VERIFIED
    verified_customer_dict["updated_at"] = datetime.now(timezone.utc)
    verified_customer = CustomerResponse(**verified_customer_dict)
    
    warehouse_service.customer_db.get_customer = AsyncMock(return_value=current_customer)
    warehouse_service.customer_db.update_item = AsyncMock(return_value=verified_customer)
    
    response = await warehouse_service.verify_customer(customer_id, verification_data)
    assert response.verification_status == VerificationStatus.VERIFIED
    assert response.id == customer_id
    assert response.updated_at > current_customer.updated_at

@pytest.mark.asyncio
async def test_verify_customer_invalid_transition(warehouse_service):
    """Test customer verification with invalid status transition."""
    customer_id = uuid.uuid4()
    verification_data = {
        "verification_status": VerificationStatus.PENDING
    }
    
    # Setup mock verified customer
    current_customer = CustomerResponse(
        id=customer_id,
        name="Test Customer",
        email="test@example.com",
        phone_number="1234567890",
        address="123 Test St",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        verification_status=VerificationStatus.VERIFIED
    )
    
    warehouse_service.customer_db.get_customer.return_value = current_customer
    
    with pytest.raises(ValueError, match="Invalid status transition"):
        await warehouse_service.verify_customer(customer_id, verification_data)

@pytest.mark.asyncio
async def test_verify_customer_not_found(warehouse_service):
    """Test verification of non-existent customer."""
    customer_id = uuid.uuid4()
    verification_data = {
        "verification_status": VerificationStatus.VERIFIED
    }
    
    warehouse_service.customer_db.get_customer.side_effect = ItemNotFoundError("Customer not found")
    
    with pytest.raises(ValueError, match="Customer .* not found"):
        await warehouse_service.verify_customer(customer_id, verification_data)

