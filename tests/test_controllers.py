import pytest
from uuid import uuid4, UUID
from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import HTTPException
from pydantic import BaseModel, ValidationError

from app.controllers import (
    BaseController,
    CustomerController,
    WarehouseController,
    RoomController
)
from app.models import (
    CustomerCreate,
    CustomerResponse,
    WarehouseCreate,
    WarehouseResponse,
    RoomCreate,
    RoomResponse,
    RoomDimensions,
    RoomStatus,
    CustomerUpdate,
    WarehouseUpdate,
    RoomUpdate
)
from app.services import WarehouseService

# Test Data Fixtures
@pytest.fixture
def mock_warehouse_db():
    return MagicMock()

@pytest.fixture
def mock_inventory_db():
    return MagicMock()

@pytest.fixture
def mock_customer_db():
    return MagicMock()

@pytest.fixture
def warehouse_service(mock_warehouse_db, mock_inventory_db, mock_customer_db):
    return WarehouseService(
        warehouse_db=mock_warehouse_db,
        inventory_db=mock_inventory_db,
        customer_db=mock_customer_db
    )

@pytest.fixture
def valid_customer_data():
    return CustomerCreate(
        name="Test Customer",
        email="test@example.com",
        phone_number="1234567890",
        address="123 Test St"
    )

@pytest.fixture
def valid_warehouse_data():
    return WarehouseCreate(
        name="Test Warehouse",
        address="123 Warehouse St",
        total_capacity=Decimal("1000.00"),
        customer_id=UUID('95c47d79-b85a-4162-a0f8-7922885371ca'),
        rooms=[]
    )

@pytest.fixture
def valid_room_data():
    return RoomCreate(
        name="Test Room",
        capacity=Decimal("100.00"),
        temperature=Decimal("20.00"),
        humidity=Decimal("50.00"),
        dimensions=RoomDimensions(
            length=Decimal("10.00"),
            width=Decimal("8.00"),
            height=Decimal("4.00")
        ),
        warehouse_id=UUID('de1d6bfb-9b29-4ded-b458-1d89a9ca6384'),
        status=RoomStatus.ACTIVE
    )

# Base Controller Tests
@pytest.mark.asyncio
async def test_base_controller_validate_request(warehouse_service):
    controller = BaseController(service=warehouse_service)
    
    # Test valid request
    request_data = {"field": "value"}
    result = controller.validate_request(request_data)  # Not async
    assert result is None  # validate_request returns None

    # Test invalid request
    with pytest.raises(HTTPException) as exc:
        controller.validate_request(None)  # Not async
    assert exc.value.status_code == 400

@pytest.mark.asyncio
async def test_base_controller_handle_error():
    # Create mocks
    mock_warehouse_db = AsyncMock()
    mock_inventory_db = AsyncMock()
    mock_customer_db = AsyncMock()
    
    # Create service with correct parameters
    warehouse_service = WarehouseService(
        warehouse_db=mock_warehouse_db,
        inventory_db=mock_inventory_db,
        customer_db=mock_customer_db
    )
    
    controller = BaseController(service=warehouse_service)
    error_msg = "Test error"
    
    with pytest.raises(HTTPException) as exc:
        await controller.handle_error(ValueError(error_msg), "test operation")
    
    assert exc.value.status_code == 500
    assert error_msg in str(exc.value.detail)

@pytest.mark.asyncio
async def test_base_controller_format_response(warehouse_service):
    controller = BaseController(service=warehouse_service)
    
    # Test successful response
    data = {
        "id": UUID('95c47d79-b85a-4162-a0f8-7922885371ca'),
        "name": "Test Customer",
        "email": "test@example.com",
        "phone_number": "1234567890",
        "address": "123 Test St",
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "verification_status": "PENDING"
    }
    result = controller.format_response(data, CustomerResponse)
    assert isinstance(result, dict)
    assert result["name"] == data["name"]

# Customer Controller Tests
@pytest.mark.asyncio
async def test_customer_controller_create_customer(warehouse_service, valid_customer_data):
    controller = CustomerController(service=warehouse_service)
    
    mock_response = {
        "id": UUID('95c47d79-b85a-4162-a0f8-7922885371ca'),
        "name": valid_customer_data.name,
        "email": valid_customer_data.email,
        "phone_number": valid_customer_data.phone_number,
        "address": valid_customer_data.address,
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "verification_status": "PENDING"
    }
    controller.service.create_customer = AsyncMock(return_value=mock_response)
    
    result = await controller.create_customer(valid_customer_data)
    assert isinstance(result, dict)
    assert result["name"] == valid_customer_data.name

@pytest.mark.asyncio
async def test_customer_controller_get_customer(warehouse_service):
    controller = CustomerController(service=warehouse_service)
    
    customer_id = UUID('95c47d79-b85a-4162-a0f8-7922885371ca')
    mock_response = {
        "id": customer_id,
        "name": "Test Customer",
        "email": "test@example.com",
        "phone_number": "1234567890",
        "address": "123 Test St",
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "verification_status": "PENDING"
    }
    controller.service.get_customer = AsyncMock(return_value=mock_response)
    
    result = await controller.get_customer(customer_id)
    assert isinstance(result, dict)
    assert result["id"] == customer_id

@pytest.mark.asyncio
async def test_customer_controller_update_customer(warehouse_service, valid_customer_data):
    controller = CustomerController(service=warehouse_service)
    
    customer_id = UUID('95c47d79-b85a-4162-a0f8-7922885371ca')
    update_data = CustomerUpdate(
        name="Updated Customer",
        phone_number="0987654321"
    )
    
    mock_response = {
        "id": customer_id,
        "name": update_data.name,
        "email": valid_customer_data.email,
        "phone_number": update_data.phone_number,
        "address": valid_customer_data.address,
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "verification_status": "PENDING"
    }
    controller.service.update_customer = AsyncMock(return_value=mock_response)
    
    result = await controller.update_customer(customer_id, update_data)
    assert isinstance(result, dict)
    assert result["name"] == update_data.name
    assert result["phone_number"] == update_data.phone_number

@pytest.mark.asyncio
async def test_customer_controller_list_customers(warehouse_service):
    controller = CustomerController(service=warehouse_service)
    
    mock_customers = [
        {
            "id": UUID('95c47d79-b85a-4162-a0f8-7922885371ca'),
            "name": f"Customer {i}",
            "email": f"customer{i}@example.com",
            "phone_number": f"123456789{i}",
            "address": f"123 Test St {i}",
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "verification_status": "PENDING"
        } for i in range(3)
    ]
    controller.service.list_customers = AsyncMock(return_value=mock_customers)
    
    result = await controller.list_customers()
    assert isinstance(result, list)
    assert len(result) == 3
    assert all(isinstance(customer, dict) for customer in result)
    assert all(customer["name"].startswith("Customer") for customer in result)

@pytest.mark.asyncio
async def test_customer_controller_delete_customer(warehouse_service):
    controller = CustomerController(service=warehouse_service)
    
    customer_id = UUID('95c47d79-b85a-4162-a0f8-7922885371ca')
    controller.service.delete_customer = AsyncMock(return_value=True)
    
    result = await controller.delete_customer(customer_id)
    assert isinstance(result, dict)
    assert result["message"] == "Customer deleted successfully"
    controller.service.delete_customer.assert_called_once_with(customer_id)

# Warehouse Controller Tests
@pytest.mark.asyncio
async def test_warehouse_controller_create_warehouse(warehouse_service, valid_warehouse_data):
    controller = WarehouseController(service=warehouse_service)
    
    mock_response = {
        "id": UUID('de1d6bfb-9b29-4ded-b458-1d89a9ca6384'),
        "name": valid_warehouse_data.name,
        "address": valid_warehouse_data.address,
        "total_capacity": valid_warehouse_data.total_capacity,
        "customer_id": valid_warehouse_data.customer_id,
        "rooms": [],
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "available_capacity": valid_warehouse_data.total_capacity
    }
    controller.service.create_warehouse = AsyncMock(return_value=mock_response)
    
    result = await controller.create_warehouse(valid_warehouse_data)
    assert isinstance(result, dict)
    assert result["name"] == valid_warehouse_data.name

@pytest.mark.asyncio
async def test_warehouse_controller_get_warehouse(warehouse_service):
    controller = WarehouseController(service=warehouse_service)
    
    warehouse_id = UUID('de1d6bfb-9b29-4ded-b458-1d89a9ca6384')
    mock_response = {
        "id": warehouse_id,
        "name": "Test Warehouse",
        "address": "123 Warehouse St",
        "total_capacity": Decimal('1000.00'),
        "customer_id": UUID('95c47d79-b85a-4162-a0f8-7922885371ca'),
        "rooms": [],
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "available_capacity": Decimal('1000.00')
    }
    controller.service.get_warehouse = AsyncMock(return_value=mock_response)
    
    result = await controller.get_warehouse(warehouse_id)
    assert isinstance(result, dict)
    assert result["id"] == warehouse_id

@pytest.mark.asyncio
async def test_warehouse_controller_update_warehouse(warehouse_service, valid_warehouse_data):
    controller = WarehouseController(service=warehouse_service)
    
    warehouse_id = UUID('de1d6bfb-9b29-4ded-b458-1d89a9ca6384')
    update_data = WarehouseUpdate(
        name="Updated Warehouse",
        total_capacity=Decimal('2000.00')
    )
    
    mock_response = {
        "id": warehouse_id,
        "name": update_data.name,
        "address": valid_warehouse_data.address,
        "total_capacity": update_data.total_capacity,
        "customer_id": valid_warehouse_data.customer_id,
        "rooms": [],
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "available_capacity": update_data.total_capacity
    }
    controller.service.update_warehouse = AsyncMock(return_value=mock_response)
    
    result = await controller.update_warehouse(warehouse_id, update_data)
    assert isinstance(result, dict)
    assert result["name"] == update_data.name
    assert result["total_capacity"] == update_data.total_capacity

@pytest.mark.asyncio
async def test_warehouse_controller_list_warehouses(warehouse_service):
    controller = WarehouseController(service=warehouse_service)
    
    mock_warehouses = [
        {
            "id": UUID('de1d6bfb-9b29-4ded-b458-1d89a9ca6384'),
            "name": f"Warehouse {i}",
            "address": f"123 Warehouse St {i}",
            "total_capacity": Decimal('1000.00'),
            "customer_id": UUID('95c47d79-b85a-4162-a0f8-7922885371ca'),
            "rooms": [],
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "available_capacity": Decimal('1000.00')
        } for i in range(3)
    ]
    controller.service.list_warehouses = AsyncMock(return_value=mock_warehouses)
    
    result = await controller.list_warehouses()
    assert isinstance(result, list)
    assert len(result) == 3
    assert all(isinstance(warehouse, dict) for warehouse in result)
    assert all(warehouse["name"].startswith("Warehouse") for warehouse in result)

@pytest.mark.asyncio
async def test_warehouse_controller_delete_warehouse(warehouse_service):
    controller = WarehouseController(service=warehouse_service)
    
    warehouse_id = UUID('de1d6bfb-9b29-4ded-b458-1d89a9ca6384')
    controller.service.delete_warehouse = AsyncMock(return_value=True)
    
    result = await controller.delete_warehouse(warehouse_id)
    assert isinstance(result, dict)
    assert result["message"] == "Warehouse deleted successfully"
    controller.service.delete_warehouse.assert_called_once_with(warehouse_id)

@pytest.mark.asyncio
async def test_warehouse_controller_create_success(warehouse_service, valid_warehouse_data):
    controller = WarehouseController(service=warehouse_service)
    
    # Create expected response
    warehouse_response = WarehouseResponse(
        id=UUID('de1d6bfb-9b29-4ded-b458-1d89a9ca6384'),
        name=valid_warehouse_data.name,
        address=valid_warehouse_data.address,
        total_capacity=valid_warehouse_data.total_capacity,
        customer_id=valid_warehouse_data.customer_id,
        rooms=[],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        available_capacity=valid_warehouse_data.total_capacity
    )
    
    # Set up mock
    warehouse_service.create_warehouse = AsyncMock()
    warehouse_service.create_warehouse.return_value = warehouse_response
    
    # Execute test
    result = await controller.create_warehouse(valid_warehouse_data)
    
    # Verify results
    assert isinstance(result, dict)
    assert result["name"] == valid_warehouse_data.name
    assert result["total_capacity"] == valid_warehouse_data.total_capacity
    warehouse_service.create_warehouse.assert_called_once_with(valid_warehouse_data)

@pytest.mark.asyncio
async def test_warehouse_controller_update_success(valid_warehouse_data):
    """Test successful warehouse update through controller."""
    warehouse_service = WarehouseService(
        warehouse_db=AsyncMock(),
        inventory_db=AsyncMock(),
        customer_db=AsyncMock()
    )
    controller = WarehouseController(warehouse_service)
    
    # Set up mock response
    warehouse_service.update_warehouse.return_value = WarehouseResponse(
        id=uuid4(),
        name="Updated Warehouse",
        address=valid_warehouse_data.address,
        total_capacity=valid_warehouse_data.total_capacity,
        customer_id=valid_warehouse_data.customer_id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        available_capacity=valid_warehouse_data.total_capacity,
        rooms=[]
    )
    
    result = await controller.update_warehouse(uuid4(), {"name": "Updated Warehouse"})
    assert result["name"] == "Updated Warehouse"

# Room Controller Tests
@pytest.mark.asyncio
async def test_room_controller_create_room(warehouse_service, valid_room_data):
    controller = RoomController(service=warehouse_service)
    
    mock_response = {
        "id": UUID('f47ac10b-58cc-4372-a567-0e02b2c3d479'),
        "name": valid_room_data.name,
        "capacity": valid_room_data.capacity,
        "temperature": valid_room_data.temperature,
        "humidity": valid_room_data.humidity,
        "dimensions": valid_room_data.dimensions.dict(),
        "warehouse_id": valid_room_data.warehouse_id,
        "status": valid_room_data.status,
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "available_capacity": valid_room_data.capacity
    }
    controller.service.create_room = AsyncMock(return_value=mock_response)
    
    result = await controller.create_room(valid_room_data.warehouse_id, valid_room_data)
    assert isinstance(result, dict)
    assert result["name"] == valid_room_data.name

@pytest.mark.asyncio
async def test_room_controller_get_room(warehouse_service):
    controller = RoomController(service=warehouse_service)
    
    warehouse_id = UUID('de1d6bfb-9b29-4ded-b458-1d89a9ca6384')
    room_id = UUID('f47ac10b-58cc-4372-a567-0e02b2c3d479')
    
    mock_response = {
        "id": room_id,
        "name": "Test Room",
        "capacity": Decimal('100.00'),
        "temperature": Decimal('20.00'),
        "humidity": Decimal('50.00'),
        "dimensions": {
            "length": Decimal('10.00'),
            "width": Decimal('8.00'),
            "height": Decimal('4.00')
        },
        "warehouse_id": warehouse_id,
        "status": RoomStatus.ACTIVE,
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "available_capacity": Decimal('100.00')
    }
    controller.service.get_room = AsyncMock(return_value=mock_response)
    
    result = await controller.get_room(warehouse_id, room_id)
    assert isinstance(result, dict)
    assert result["id"] == room_id

@pytest.mark.asyncio
async def test_room_controller_update_room(warehouse_service, valid_room_data):
    controller = RoomController(service=warehouse_service)
    
    warehouse_id = UUID('de1d6bfb-9b29-4ded-b458-1d89a9ca6384')
    room_id = UUID('f47ac10b-58cc-4372-a567-0e02b2c3d479')
    
    update_data = RoomUpdate(
        name="Updated Room",
        temperature=Decimal('22.00'),
        humidity=Decimal('55.00')
    )
    
    mock_response = {
        "id": room_id,
        "name": update_data.name,
        "capacity": valid_room_data.capacity,
        "temperature": update_data.temperature,
        "humidity": update_data.humidity,
        "dimensions": valid_room_data.dimensions.dict(),
        "warehouse_id": warehouse_id,
        "status": valid_room_data.status,
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "available_capacity": valid_room_data.capacity
    }
    controller.service.update_room = AsyncMock(return_value=mock_response)
    
    result = await controller.update_room(warehouse_id, room_id, update_data)
    assert isinstance(result, dict)
    assert result["name"] == update_data.name
    assert result["temperature"] == update_data.temperature
    assert result["humidity"] == update_data.humidity

@pytest.mark.asyncio
async def test_room_controller_list_rooms(warehouse_service):
    controller = RoomController(service=warehouse_service)
    
    warehouse_id = UUID('de1d6bfb-9b29-4ded-b458-1d89a9ca6384')
    
    mock_rooms = [
        {
            "id": UUID('f47ac10b-58cc-4372-a567-0e02b2c3d479'),
            "name": f"Room {i}",
            "capacity": Decimal('100.00'),
            "temperature": Decimal('20.00'),
            "humidity": Decimal('50.00'),
            "dimensions": {
                "length": Decimal('10.00'),
                "width": Decimal('8.00'),
                "height": Decimal('4.00')
            },
            "warehouse_id": warehouse_id,
            "status": RoomStatus.ACTIVE,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "available_capacity": Decimal('100.00')
        } for i in range(3)
    ]
    controller.service.list_rooms = AsyncMock(return_value=mock_rooms)
    
    result = await controller.list_rooms(warehouse_id)
    assert isinstance(result, list)
    assert len(result) == 3
    assert all(isinstance(room, dict) for room in result)
    assert all(room["name"].startswith("Room") for room in result)

@pytest.mark.asyncio
async def test_room_controller_delete_room(warehouse_service):
    controller = RoomController(service=warehouse_service)
    
    warehouse_id = UUID('de1d6bfb-9b29-4ded-b458-1d89a9ca6384')
    room_id = UUID('f47ac10b-58cc-4372-a567-0e02b2c3d479')
    
    controller.service.delete_room = AsyncMock(return_value=True)
    
    result = await controller.delete_room(warehouse_id, room_id)
    assert isinstance(result, dict)
    assert result["message"] == "Room deleted successfully"
    controller.service.delete_room.assert_called_once_with(warehouse_id, room_id)

# Error Cases
@pytest.mark.asyncio
async def test_customer_controller_create_customer_error(warehouse_service, valid_customer_data):
    controller = CustomerController(service=warehouse_service)
    
    error_message = "Failed to create customer"
    controller.service.create_customer = AsyncMock(side_effect=ValueError(error_message))
    
    with pytest.raises(HTTPException) as exc:
        await controller.create_customer(valid_customer_data)
    assert exc.value.status_code == 500
    assert error_message in str(exc.value.detail)

@pytest.mark.asyncio
async def test_warehouse_controller_get_warehouse_not_found(warehouse_service):
    controller = WarehouseController(service=warehouse_service)
    
    warehouse_id = UUID('de1d6bfb-9b29-4ded-b458-1d89a9ca6384')
    error_message = "Warehouse not found"
    controller.service.get_warehouse = AsyncMock(side_effect=ValueError(error_message))
    
    with pytest.raises(HTTPException) as exc:
        await controller.get_warehouse(warehouse_id)
    assert exc.value.status_code == 404
    assert error_message in str(exc.value.detail)

@pytest.mark.asyncio
async def test_room_controller_update_room_validation_error():
    # Create mocks
    mock_warehouse_db = AsyncMock()
    mock_inventory_db = AsyncMock()
    
    # Create service with correct parameters
    warehouse_service = WarehouseService(
        warehouse_db=mock_warehouse_db,
        inventory_db=mock_inventory_db
    )
    
    controller = RoomController(service=warehouse_service)
    
    # Set up test data
    warehouse_id = UUID('de1d6bfb-9b29-4ded-b458-1d89a9ca6384')
    room_id = UUID('95c47d79-b85a-4162-a0f8-7922885371ca')
    invalid_update = {"temperature": -10}  # Invalid temperature
    
    # Set up mock to raise validation error
    warehouse_service.update_room = AsyncMock(
        side_effect=ValidationError("Invalid temperature value")
    )
    
    # Execute test
    with pytest.raises(HTTPException) as exc:
        await controller.update_room(warehouse_id, room_id, invalid_update)
    
    assert exc.value.status_code == 422
    assert "Invalid temperature value" in str(exc.value.detail) 