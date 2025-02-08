import pytest
from decimal import Decimal
from uuid import UUID, uuid4
from datetime import datetime, timezone
from pydantic import ValidationError

from app.models import (
    RoomStatus,
    RoomDimensions,
    RoomBase,
    RoomCreate,
    RoomResponse,
    RoomUpdate,
    WarehouseBase,
    WarehouseCreate,
    WarehouseResponse,
    WarehouseUpdate,
    CustomerBase,
    CustomerCreate,
    CustomerUpdate,
    CustomerResponse,
    InventoryBase,
    InventoryCreate,
    InventoryUpdate,
    InventoryResponse
)

# Test Room Models
def test_room_dimensions_valid():
    """Test valid room dimensions."""
    dimensions = RoomDimensions(
        length=Decimal("10.00"),
        width=Decimal("8.00"),
        height=Decimal("4.00")
    )
    assert dimensions.length == Decimal("10.00")
    assert dimensions.width == Decimal("8.00")
    assert dimensions.height == Decimal("4.00")

def test_room_dimensions_invalid():
    """Test invalid room dimensions."""
    with pytest.raises(ValidationError):
        RoomDimensions(length=Decimal("-1.00"), width=Decimal("8.00"), height=Decimal("4.00"))
    with pytest.raises(ValidationError):
        RoomDimensions(length=Decimal("10.00"), width=Decimal("-1.00"), height=Decimal("4.00"))
    with pytest.raises(ValidationError):
        RoomDimensions(length=Decimal("10.00"), width=Decimal("8.00"), height=Decimal("-1.00"))

def test_room_base_valid():
    """Test valid room base model."""
    room = RoomBase(
        name="Test Room",
        capacity=Decimal("100.00"),
        temperature=Decimal("20.00"),
        humidity=Decimal("50.00"),
        dimensions=RoomDimensions(
            length=Decimal("10.00"),
            width=Decimal("8.00"),
            height=Decimal("4.00")
        ),
        warehouse_id=uuid4()
    )
    assert room.name == "Test Room"
    assert room.capacity == Decimal("100.00")
    assert room.temperature == Decimal("20.00")
    assert room.humidity == Decimal("50.00")

def test_room_base_invalid():
    """Test invalid room base model."""
    with pytest.raises(ValidationError):
        RoomBase(
            name="",  # Empty name
            capacity=Decimal("100.00"),
            temperature=Decimal("20.00"),
            humidity=Decimal("50.00"),
            dimensions=RoomDimensions(
                length=Decimal("10.00"),
                width=Decimal("8.00"),
                height=Decimal("4.00")
            ),
            warehouse_id=uuid4()
        )

def test_room_create():
    """Test room create model."""
    room = RoomCreate(
        name="Test Room",
        capacity=Decimal("100.00"),
        temperature=Decimal("20.00"),
        humidity=Decimal("50.00"),
        dimensions=RoomDimensions(
            length=Decimal("10.00"),
            width=Decimal("8.00"),
            height=Decimal("4.00")
        ),
        warehouse_id=uuid4(),
        status=RoomStatus.ACTIVE
    )
    assert room.status == RoomStatus.ACTIVE

def test_room_response():
    """Test room response model."""
    room_id = uuid4()
    room = RoomResponse(
        id=room_id,
        name="Test Room",
        capacity=Decimal("100.00"),
        temperature=Decimal("20.00"),
        humidity=Decimal("50.00"),
        dimensions=RoomDimensions(
            length=Decimal("10.00"),
            width=Decimal("8.00"),
            height=Decimal("4.00")
        ),
        warehouse_id=uuid4(),
        status=RoomStatus.ACTIVE,
        available_capacity=Decimal("100.00"),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    assert room.room_id == room_id

# Test Warehouse Models
def test_warehouse_base_valid():
    """Test valid warehouse base model."""
    warehouse = WarehouseBase(
        name="Test Warehouse",
        address="123 Test St",
        total_capacity=Decimal("1000.00"),
        customer_id=uuid4()
    )
    assert warehouse.name == "Test Warehouse"
    assert warehouse.total_capacity == Decimal("1000.00")

def test_warehouse_base_invalid():
    """Test invalid warehouse base model."""
    with pytest.raises(ValidationError):
        WarehouseBase(
            name="",  # Empty name
            address="123 Test St",
            total_capacity=Decimal("1000.00"),
            customer_id=uuid4()
        )

def test_warehouse_create():
    """Test warehouse create model."""
    warehouse = WarehouseCreate(
        name="Test Warehouse",
        address="123 Test St",
        total_capacity=Decimal("1000.00"),
        customer_id=uuid4(),
        rooms=[]
    )
    assert isinstance(warehouse.rooms, list)

def test_warehouse_response():
    """Test warehouse response model."""
    warehouse_id = uuid4()
    warehouse = WarehouseResponse(
        id=warehouse_id,
        name="Test Warehouse",
        address="123 Test St",
        total_capacity=Decimal("1000.00"),
        customer_id=uuid4(),
        rooms=[],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        available_capacity=Decimal("1000.00")
    )
    assert warehouse.warehouse_id == warehouse_id

# Test Customer Models
def test_customer_base_valid():
    """Test valid customer base model."""
    customer = CustomerBase(
        name="Test Customer",
        email="test@example.com",
        phone_number="1234567890",
        address="123 Customer St"
    )
    assert customer.name == "Test Customer"
    assert customer.email == "test@example.com"

def test_customer_base_invalid():
    """Test invalid customer base model."""
    with pytest.raises(ValidationError):
        CustomerBase(
            name="",  # Empty name
            email="invalid-email",  # Invalid email
            phone_number="123",  # Too short
            address="123 Customer St"
        )

def test_customer_response():
    """Test customer response model."""
    customer_id = uuid4()
    customer = CustomerResponse(
        id=customer_id,
        name="Test Customer",
        email="test@example.com",
        phone_number="1234567890",
        address="123 Customer St",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        verification_status="PENDING"
    )
    assert customer.customer_id == customer_id

# Test Inventory Models
def test_inventory_base_valid():
    """Test valid inventory base model."""
    inventory = InventoryBase(
        sku="TEST-SKU-001",
        name="Test Inventory Item",
        description="Test Inventory Item Description",
        quantity=Decimal("100.00"),
        unit="kg",
        room_id=uuid4(),
        warehouse_id=uuid4()
    )
    assert inventory.sku == "TEST-SKU-001"
    assert inventory.name == "Test Inventory Item"
    assert inventory.description == "Test Inventory Item Description"
    assert inventory.quantity == Decimal("100.00")
    assert inventory.unit == "kg"

def test_inventory_base_invalid_total_weight():
    """Test inventory base model with invalid total weight."""
    with pytest.raises(ValidationError):
        InventoryBase(
            product_name="Test Product",
            quantity=Decimal("10.00"),
            unit_weight=Decimal("1.00"),
            total_weight=Decimal("15.00")  # Incorrect total weight
        )

def test_inventory_create():
    """Test inventory create model."""
    inventory = InventoryCreate(
        sku="TEST-SKU-001",
        name="Test Inventory Item",
        description="Test Inventory Item Description",
        quantity=Decimal("100.00"),
        unit="kg",
        room_id=uuid4(),
        warehouse_id=uuid4()
    )
    assert inventory.sku == "TEST-SKU-001"
    assert inventory.name == "Test Inventory Item"
    assert inventory.description == "Test Inventory Item Description"
    assert inventory.quantity == Decimal("100.00")
    assert inventory.unit == "kg"

def test_inventory_response():
    """Test inventory response model."""
    inventory = InventoryResponse(
        id=uuid4(),
        sku="TEST-SKU-001",
        name="Test Inventory Item",
        description="Test Inventory Item Description",
        quantity=Decimal("100.00"),
        unit="kg",
        room_id=uuid4(),
        warehouse_id=uuid4(),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    assert inventory.sku == "TEST-SKU-001"
    assert inventory.name == "Test Inventory Item"
    assert inventory.description == "Test Inventory Item Description"
    assert inventory.quantity == Decimal("100.00")
    assert inventory.unit == "kg"

