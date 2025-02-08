import pytest
from decimal import Decimal
from unittest.mock import MagicMock, AsyncMock
from fastapi import FastAPI, HTTPException, status
from fastapi.testclient import TestClient
from app.main import app as fastapi_app
from app.models import (
    CustomerCreate,
    CustomerResponse,
    CustomerUpdate,
    WarehouseCreate,
    WarehouseResponse,
    WarehouseUpdate,
    RoomCreate,
    RoomResponse,
    RoomStatus,
    RoomDimensions,
    VerificationStatus,
    InventoryCreate,
    InventoryResponse
)
from datetime import datetime, timezone
from uuid import UUID, uuid4
import json
from typing import Dict, List, Optional, Any, AsyncGenerator, Union
from app.database import ItemNotFoundError, ValidationError, DatabaseError, ConflictError
import uuid
import httpx
import pytest_asyncio
from app.utils import json_dumps
from httpx import Response

class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for handling special types in test data.
    
    Handles:
    - Decimal values (converted to strings)
    - UUID objects (converted to strings)
    - datetime objects (converted to ISO format strings)
    - Pydantic models (converted using model_dump)
    - Enum values (converted using value property)
    """
    def default(self, obj):
        if isinstance(obj, Decimal):
            return format_decimal(obj)
        if isinstance(obj, (datetime, UUID)):
            return str(obj)
        if isinstance(obj, uuid4):
            return str(obj)
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        if hasattr(obj, "value"):  # Handle enum values
            return obj.value
        return super().default(obj)

def format_decimal(value: Decimal) -> str:
    """Helper function to consistently format decimal values as strings."""
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return str(value)

class CustomTestClient:
    """Custom test client for handling async operations and JSON serialization."""
    
    def __init__(self, app: FastAPI):
        """Initialize the test client with a FastAPI app."""
        self.app = app
        self.client = TestClient(app)
        self.json_encoder = CustomJSONEncoder
        
    def _prepare_json(self, **kwargs) -> dict:
        """Prepare request kwargs by encoding JSON with custom encoder."""
        if "json" in kwargs:
            kwargs["content"] = json.dumps(kwargs.pop("json"), cls=self.json_encoder).encode()
            if "headers" not in kwargs:
                kwargs["headers"] = {}
            kwargs["headers"]["Content-Type"] = "application/json"
        return kwargs
        
    async def get(self, url: str, **kwargs) -> Response:
        """Send a GET request."""
        kwargs = self._prepare_json(**kwargs)
        return self.client.get(url, **kwargs)
        
    async def post(self, url: str, **kwargs) -> Response:
        """Send a POST request."""
        kwargs = self._prepare_json(**kwargs)
        return self.client.post(url, **kwargs)
        
    async def put(self, url: str, **kwargs) -> Response:
        """Send a PUT request."""
        kwargs = self._prepare_json(**kwargs)
        return self.client.put(url, **kwargs)
        
    async def delete(self, url: str, **kwargs) -> Response:
        """Send a DELETE request."""
        kwargs = self._prepare_json(**kwargs)
        return self.client.delete(url, **kwargs)
        
    async def patch(self, url: str, **kwargs) -> Response:
        """Send a PATCH request."""
        kwargs = self._prepare_json(**kwargs)
        return self.client.patch(url, **kwargs)
        
    async def __aenter__(self):
        """Enter async context."""
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context."""
        await self.close()
        
    async def close(self):
        """Close the test client."""
        pass

@pytest.fixture
def mock_customer_db(test_customer):
    """Mock customer database with proper timestamps and model validation."""
    class MockCustomerDB:
        """Mock customer database with proper timestamps and model validation."""
        def create_customer_response(self, customer: dict) -> CustomerResponse:
            """Create a properly formatted customer response with timestamps."""
            if 'created_at' not in customer:
                customer['created_at'] = datetime.now(timezone.utc)
            if 'updated_at' not in customer:
                customer['updated_at'] = datetime.now(timezone.utc)
            if 'verification_status' not in customer:
                customer['verification_status'] = VerificationStatus.PENDING
            return CustomerResponse(**customer)

        def __init__(self):
            # Base DB methods
            self.create_item = AsyncMock(name='create_item')
            self.get_item = AsyncMock(name='get_item')
            self.update_item = AsyncMock(name='update_item')
            self.delete_item = AsyncMock(name='delete_item')
            self.list_items = AsyncMock(name='list_items')
            
            # Customer-specific methods
            self.get_customer = AsyncMock(name='get_customer')
            self.create_customer = AsyncMock(name='create_customer')
            self.update_customer = AsyncMock(name='update_customer')
            self.delete_customer = AsyncMock(name='delete_customer')
            self.list_customers = AsyncMock(name='list_customers')
            self.get_by_email = AsyncMock(name='get_by_email')
            self.verify_customer = AsyncMock(name='verify_customer')
            
            # Map base methods to customer-specific methods
            self.create_item.side_effect = self.create_customer
            self.get_item.side_effect = self.get_customer
            self.update_item.side_effect = self.update_customer
            self.delete_item.side_effect = self.delete_customer
            self.list_items.side_effect = self.list_customers

    mock_db = MockCustomerDB()
    
    # Set up default behaviors using the helper method
    mock_db.get_customer.return_value = mock_db.create_customer_response(test_customer)
    mock_db.create_customer.return_value = mock_db.create_customer_response(test_customer)
    mock_db.update_customer.return_value = mock_db.create_customer_response(test_customer)
    mock_db.list_customers.return_value = [mock_db.create_customer_response(test_customer)]
    mock_db.get_by_email.return_value = mock_db.create_customer_response(test_customer)
    
    return mock_db

@pytest_asyncio.fixture
async def test_app(mock_customer_db, mock_warehouse_db, mock_room_db, mock_inventory_db):
    """Create test FastAPI application with mocked database dependencies.
    
    This fixture sets up a test FastAPI application with properly configured mock
    database dependencies. Each mock database is configured to return properly
    formatted response objects.
    
    Args:
        mock_customer_db: Mock customer database fixture
        mock_warehouse_db: Mock warehouse database fixture
        mock_room_db: Mock room database fixture
        mock_inventory_db: Mock inventory database fixture
        
    Returns:
        FastAPI: Configured test application
    """
    from app.main import app
    
    # Configure mock databases
    app.state.customer_db = mock_customer_db
    app.state.warehouse_db = mock_warehouse_db
    app.state.room_db = mock_room_db
    app.state.inventory_db = mock_inventory_db
    
    return app

@pytest_asyncio.fixture
async def client(test_app: FastAPI) -> AsyncGenerator[CustomTestClient, None]:
    """Create a test client for async operations.
    
    This fixture provides a test client that properly handles async operations
    and JSON serialization. It ensures that the client is properly closed after
    each test.
    
    Args:
        test_app: The FastAPI test application
        
    Returns:
        AsyncGenerator[CustomTestClient, None]: Test client for async operations
    """
    async with CustomTestClient(test_app) as client:
        yield client

@pytest.fixture
def test_customer():
    """Create a test customer."""
    customer_id = "12345678-1234-5678-1234-567812345678"  # Fixed UUID for testing
    return {
        "id": customer_id,
        "name": "Test Customer",
        "email": "test@example.com",
        "phone_number": "+1234567890",
        "address": "123 Test Street, Test City, TS 12345",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "verification_status": VerificationStatus.PENDING
    }

@pytest.fixture
def test_warehouse(test_customer):
    """Create a test warehouse."""
    warehouse_id = "87654321-4321-8765-4321-876543210987"  # Fixed UUID for testing
    return {
        "id": warehouse_id,
        "name": "Test Warehouse",
        "address": "123 Test Street, Warehouse City, WH 12345",
        "total_capacity": format_decimal(Decimal("1000.00")),
        "customer_id": test_customer["id"],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "available_capacity": format_decimal(Decimal("1000.00")),
        "rooms": []
    }

@pytest.fixture
def mock_customer_data():
    return {
        "name": "New Company",
        "email": "new@example.com",
        "phone_number": "+1987654321",
        "address": "789 New Street, New City, NS 54321"
    }

@pytest.fixture
def mock_warehouse_data():
    return {
        'name': 'New Warehouse',
        'address': '321 Storage Street, Warehouse City, WC 13579',
        'total_capacity': format_decimal(Decimal('4000.00')),
        'customer_id': str(uuid4())
    }

@pytest.fixture
def mock_warehouse_db(test_warehouse):
    """Mock warehouse database with proper timestamps and model validation."""
    class MockWarehouseDB:
        def create_warehouse_response(self, warehouse: dict) -> WarehouseResponse:
            """Create a properly formatted warehouse response with timestamps."""
            if 'created_at' not in warehouse:
                warehouse['created_at'] = datetime.now(timezone.utc)
            if 'updated_at' not in warehouse:
                warehouse['updated_at'] = datetime.now(timezone.utc)
            return WarehouseResponse(**warehouse)

        def __init__(self):
            # Base DB methods
            self.create_item = AsyncMock(name='create_item')
            self.get_item = AsyncMock(name='get_item')
            self.update_item = AsyncMock(name='update_item')
            self.delete_item = AsyncMock(name='delete_item')
            self.list_items = AsyncMock(name='list_items')
            
            # Warehouse-specific methods
            self.get_warehouse = AsyncMock(name='get_warehouse')
            self.create_warehouse = AsyncMock(name='create_warehouse')
            self.update_warehouse = AsyncMock(name='update_warehouse')
            self.delete_warehouse = AsyncMock(name='delete_warehouse')
            self.list_warehouses = AsyncMock(name='list_warehouses')
            self.list_by_customer = AsyncMock(name='list_by_customer')
            self.calculate_warehouse_utilization = AsyncMock(name='calculate_warehouse_utilization')
            self.check_availability = AsyncMock(name='check_availability')
            self.get_inventory_levels = AsyncMock(name='get_inventory_levels')
            
            # Room operations within warehouses
            self.create_room = AsyncMock(name='create_room')
            self.get_room = AsyncMock(name='get_room')
            self.update_room = AsyncMock(name='update_room')
            self.delete_room = AsyncMock(name='delete_room')
            self.list_rooms = AsyncMock(name='list_rooms')
            self.get_rooms = AsyncMock(name='get_rooms')
            
            # Map base methods to warehouse-specific methods
            self.create_item.side_effect = self.create_warehouse
            self.get_item.side_effect = self.get_warehouse
            self.update_item.side_effect = self.update_warehouse
            self.delete_item.side_effect = self.delete_warehouse
            self.list_items.side_effect = self.list_warehouses

            # Set up error cases
            self.get_warehouse.side_effect = lambda id: None if id != test_warehouse['id'] else self.create_warehouse_response(test_warehouse)
            self.delete_warehouse.side_effect = lambda id: None if id != test_warehouse['id'] else None
            self.update_warehouse.side_effect = lambda id, data: None if id != test_warehouse['id'] else self.create_warehouse_response({**test_warehouse, **data.model_dump()})

    mock_db = MockWarehouseDB()
    
    # Set up default behaviors using the helper method
    mock_db.create_warehouse.return_value = mock_db.create_warehouse_response(test_warehouse)
    mock_db.list_warehouses.return_value = [mock_db.create_warehouse_response(test_warehouse)]
    mock_db.list_by_customer.return_value = [mock_db.create_warehouse_response(test_warehouse)]
    mock_db.list_items.return_value = [mock_db.create_warehouse_response(test_warehouse)]
    
    # Set up default behaviors for room operations
    default_room = {
        'id': str(uuid4()),
        'name': 'Test Room',
        'warehouse_id': test_warehouse['id'],
        'capacity': Decimal('200.00'),
        'temperature': Decimal('20.00'),
        'humidity': Decimal('50.00'),
        'dimensions': {
            'length': Decimal('10.00'),
            'width': Decimal('10.00'),
            'height': Decimal('10.00')
        },
        'status': RoomStatus.ACTIVE,
        'available_capacity': Decimal('200.00'),
        'created_at': datetime.now(timezone.utc),
        'updated_at': datetime.now(timezone.utc)
    }
    
    mock_db.create_room.return_value = default_room
    mock_db.get_room.return_value = default_room
    mock_db.list_rooms.return_value = [default_room]
    mock_db.get_rooms.return_value = [default_room]
    
    # Set up default behaviors for utilization and availability
    mock_db.calculate_warehouse_utilization.return_value = {'total_capacity': Decimal('1000.00'), 'used_capacity': Decimal('0'), 'utilization_percentage': Decimal('0')}
    mock_db.check_availability.return_value = {'available': True, 'total_capacity': Decimal('1000.00'), 'used_capacity': Decimal('0'), 'available_capacity': Decimal('1000.00')}
    mock_db.get_inventory_levels.return_value = {'total_items': 0, 'items_by_sku': {}}
    
    return mock_db

@pytest.fixture
def mock_room_db(test_warehouse):
    """Mock room database with proper timestamps and model validation."""
    class MockRoomDB:
        def create_room_response(self, room: dict) -> RoomResponse:
            """Create a properly formatted room response with timestamps."""
            if 'created_at' not in room:
                room['created_at'] = datetime.now(timezone.utc)
            if 'updated_at' not in room:
                room['updated_at'] = datetime.now(timezone.utc)
            if 'status' not in room:
                room['status'] = RoomStatus.ACTIVE
            if 'available_capacity' not in room:
                room['available_capacity'] = room.get('capacity', Decimal('0'))
            if 'dimensions' not in room:
                room['dimensions'] = {
                    'length': Decimal('10.00'),
                    'width': Decimal('10.00'),
                    'height': Decimal('10.00')
                }
            return RoomResponse(**room)

        def __init__(self):
            # Base DB methods
            self.create_item = AsyncMock(name='create_item')
            self.get_item = AsyncMock(name='get_item')
            self.update_item = AsyncMock(name='update_item')
            self.delete_item = AsyncMock(name='delete_item')
            self.list_items = AsyncMock(name='list_items')
            
            # Room-specific methods
            self.get_room = AsyncMock(name='get_room')
            self.create_room = AsyncMock(name='create_room')
            self.update_room = AsyncMock(name='update_room')
            self.delete_room = AsyncMock(name='delete_room')
            self.list_rooms = AsyncMock(name='list_rooms')
            self.get_room_conditions = AsyncMock(name='get_room_conditions')
            
            # Map base methods to room-specific methods
            self.create_item.side_effect = self.create_room
            self.get_item.side_effect = self.get_room
            self.update_item.side_effect = self.update_room
            self.delete_item.side_effect = self.delete_room
            self.list_items.side_effect = self.list_rooms

            # Set up validation error cases
            def validate_room_capacity(room_data):
                if hasattr(room_data, 'capacity') and room_data.capacity <= Decimal('0'):
                    raise ValidationError("Room capacity must be greater than 0")
                if hasattr(room_data, 'temperature') and (room_data.temperature < Decimal('-20') or room_data.temperature > Decimal('40')):
                    raise ValidationError("Room temperature must be between -20°C and 40°C")
                if hasattr(room_data, 'humidity') and (room_data.humidity < Decimal('0') or room_data.humidity > Decimal('100')):
                    raise ValidationError("Room humidity must be between 0% and 100%")

            def handle_room_update(room_id, update_data):
                if not any(r['id'] == room_id for r in self.list_rooms.return_value):
                    return None
                validate_room_capacity(update_data)
                updated_room = {**self.get_room.return_value, **update_data.model_dump()}
                return self.create_room_response(updated_room)

            def handle_room_delete(room_id):
                room = next((r for r in self.list_rooms.return_value if r['id'] == room_id), None)
                if not room:
                    return None
                if Decimal(room['capacity']) != Decimal(room['available_capacity']):
                    raise ConflictError("Cannot delete room with existing inventory")
                return None

            self.update_room.side_effect = handle_room_update
            self.delete_room.side_effect = handle_room_delete

    mock_db = MockRoomDB()
    
    # Set up default behaviors
    default_room = {
        'id': str(uuid4()),
        'name': 'Test Room',
        'warehouse_id': test_warehouse['id'],
        'capacity': Decimal('200.00'),
        'temperature': Decimal('20.00'),
        'humidity': Decimal('50.00'),
        'dimensions': {
            'length': Decimal('10.00'),
            'width': Decimal('10.00'),
            'height': Decimal('10.00')
        },
        'status': RoomStatus.ACTIVE,
        'available_capacity': Decimal('200.00'),
        'created_at': datetime.now(timezone.utc),
        'updated_at': datetime.now(timezone.utc)
    }
    
    mock_db.create_room.return_value = mock_db.create_room_response(default_room)
    mock_db.get_room.return_value = mock_db.create_room_response(default_room)
    mock_db.list_rooms.return_value = [mock_db.create_room_response(default_room)]
    mock_db.get_room_conditions.return_value = {
        'temperature': default_room['temperature'],
        'humidity': default_room['humidity']
    }
    
    return mock_db

@pytest.fixture
def test_room(test_warehouse):
    """Create a test room."""
    room_id = "98765432-5678-4321-8765-432109876543"  # Fixed UUID for testing
    return {
        "id": room_id,
        "name": "Test Room",
        "capacity": format_decimal(Decimal("100.00")),
        "temperature": format_decimal(Decimal("20.50")),
        "humidity": format_decimal(Decimal("50")),
        "dimensions": {
            "length": format_decimal(Decimal("10.00")),
            "width": format_decimal(Decimal("8.00")),
            "height": format_decimal(Decimal("4.00"))
        },
        "warehouse_id": test_warehouse["id"],
        "status": RoomStatus.ACTIVE,
        "available_capacity": format_decimal(Decimal("100.00")),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

@pytest.fixture
def valid_warehouse_data(test_customer):
    """Create valid warehouse data for testing."""
    return WarehouseCreate(
        name="Test Warehouse",
        address="123 Test Street, Warehouse City, WH 12345",
        total_capacity=Decimal("1000.00"),
        customer_id=UUID(test_customer["id"]),  # Use the test customer's ID
        rooms=[]
    )

@pytest.fixture
def valid_room_data(test_warehouse):
    """Create valid room data for testing."""
    return RoomCreate(
        name="Test Room",
        capacity=Decimal("100.00"),
        temperature=Decimal("20.50"),
        humidity=Decimal("50"),
        status=RoomStatus.ACTIVE,
        warehouse_id=UUID(test_warehouse["id"]),  # Use the test warehouse's ID
        dimensions=RoomDimensions(
            length=Decimal("10.00"),
            width=Decimal("8.00"),
            height=Decimal("4.00")
        )
    )

@pytest.fixture
def valid_customer_data():
    return CustomerCreate(
        name="Test Customer",
        email="test@example.com",
        phone_number="1234567890",
        address="123 Customer St"
    )

@pytest.fixture
def existing_customer(valid_customer_data):
    return CustomerResponse(
        id=uuid.uuid4(),
        name=valid_customer_data.name,
        email=valid_customer_data.email,
        phone_number=valid_customer_data.phone_number,
        address=valid_customer_data.address,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )

@pytest.fixture
def existing_warehouse(valid_warehouse_data):
    return WarehouseResponse(
        id=uuid.uuid4(),
        name=valid_warehouse_data.name,
        address=valid_warehouse_data.address,
        total_capacity=format_decimal(valid_warehouse_data.total_capacity),
        customer_id=valid_warehouse_data.customer_id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        available_capacity=format_decimal(Decimal("1000.00")),
        rooms=[]
    )

@pytest.fixture
def existing_room(valid_room_data):
    return RoomResponse(
        id=uuid.uuid4(),
        name=valid_room_data.name,
        capacity=format_decimal(valid_room_data.capacity),
        temperature=format_decimal(valid_room_data.temperature),
        humidity=format_decimal(valid_room_data.humidity),
        status=valid_room_data.status,
        warehouse_id=valid_room_data.warehouse_id,
        dimensions=RoomDimensions(
            length=format_decimal(valid_room_data.dimensions.length),
            width=format_decimal(valid_room_data.dimensions.width),
            height=format_decimal(valid_room_data.dimensions.height)
        ),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        available_capacity=format_decimal(Decimal("100.00"))
    )

@pytest.fixture
def sample_inventory_data():
    return {
        'sku': 'TEST-SKU-001',
        'name': 'Test Inventory Item',
        'description': 'Test Inventory Item Description',
        'quantity': format_decimal(Decimal('100.00')),
        'unit': 'kg',
        'room_id': str(uuid4()),
        'warehouse_id': str(uuid4())
    }

@pytest.fixture
def test_inventory(test_room):
    """Create a test inventory item."""
    return {
        "id": str(uuid4()),
        "sku": "TEST-SKU-001",
        "name": "Test Inventory Item",
        "description": "Test Inventory Item Description",
        "quantity": format_decimal(Decimal("100.00")),
        "unit": "kg",
        "room_id": test_room["id"],
        "warehouse_id": test_room["warehouse_id"],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

@pytest.fixture
def valid_inventory_data(test_room):
    """Create valid inventory data for testing."""
    return InventoryCreate(
        sku="TEST-SKU-001",
        name="Test Inventory Item",
        description="Test Inventory Item Description",
        quantity=Decimal("100.00"),
        unit="kg",
        room_id=UUID(test_room["id"]),
        warehouse_id=UUID(test_room["warehouse_id"])
    )

@pytest.fixture
def existing_inventory(test_inventory):
    """Create an existing inventory response for testing."""
    return InventoryResponse(
        id=UUID(test_inventory["id"]),
        sku=test_inventory["sku"],
        description=test_inventory["description"],
        quantity=Decimal(test_inventory["quantity"]),
        room_id=UUID(test_inventory["room_id"]),
        warehouse_id=UUID(test_inventory["warehouse_id"]),
        created_at=test_inventory["created_at"],
        updated_at=test_inventory["updated_at"]
    )

@pytest.fixture
def mock_inventory_db(test_inventory):
    """Mock inventory database with proper timestamps and model validation."""
    class MockInventoryDB:
        def create_inventory_response(self, inventory: dict) -> InventoryResponse:
            """Create a properly formatted inventory response with timestamps."""
            if 'created_at' not in inventory:
                inventory['created_at'] = datetime.now(timezone.utc)
            if 'updated_at' not in inventory:
                inventory['updated_at'] = datetime.now(timezone.utc)
            # Ensure required fields are present
            if 'name' not in inventory and 'description' in inventory:
                inventory['name'] = inventory['description']
            if 'unit' not in inventory:
                inventory['unit'] = 'kg'
            return InventoryResponse(**inventory)

        def __init__(self):
            # Base DB methods
            self.create_item = AsyncMock(name='create_item')
            self.get_item = AsyncMock(name='get_item')
            self.update_item = AsyncMock(name='update_item')
            self.delete_item = AsyncMock(name='delete_item')
            self.list_items = AsyncMock(name='list_items')
            
            # Inventory-specific methods
            self.get_inventory = AsyncMock(name='get_inventory')
            self.create_inventory = AsyncMock(name='create_inventory')
            self.update_inventory = AsyncMock(name='update_inventory')
            self.delete_inventory = AsyncMock(name='delete_inventory')
            self.transfer_inventory = AsyncMock(name='transfer_inventory')
            self.get_inventory_history = AsyncMock(name='get_inventory_history')
            self.search_inventory = AsyncMock(name='search_inventory')
            self.list_inventory = AsyncMock(name='list_inventory')
            self.list_by_room = AsyncMock(name='list_by_room')
            self.list_by_warehouse = AsyncMock(name='list_by_warehouse')
            self.list_by_customer = AsyncMock(name='list_by_customer')
            
            # Map base methods to inventory-specific methods
            self.create_item.side_effect = self.create_inventory
            self.get_item.side_effect = self.get_inventory
            self.update_item.side_effect = self.update_inventory
            self.delete_item.side_effect = self.delete_inventory
            self.list_items.side_effect = self.list_by_warehouse

    mock_db = MockInventoryDB()
    
    # Set up default behaviors using the helper method
    mock_db.get_inventory.return_value = mock_db.create_inventory_response(test_inventory)
    mock_db.create_inventory.return_value = mock_db.create_inventory_response(test_inventory)
    mock_db.update_inventory.return_value = mock_db.create_inventory_response(test_inventory)
    mock_db.transfer_inventory.return_value = mock_db.create_inventory_response(test_inventory)
    
    # Set up default behaviors for listing operations
    mock_db.list_inventory.return_value = [mock_db.create_inventory_response(test_inventory)]
    mock_db.list_by_warehouse.return_value = [mock_db.create_inventory_response(test_inventory)]
    mock_db.list_by_room.return_value = [mock_db.create_inventory_response(test_inventory)]
    mock_db.list_by_customer.return_value = [mock_db.create_inventory_response(test_inventory)]
    mock_db.search_inventory.return_value = [mock_db.create_inventory_response(test_inventory)]
    mock_db.list_items.return_value = [mock_db.create_inventory_response(test_inventory)]
    
    # Set up history with a sample entry
    mock_db.get_inventory_history.return_value = [{
        'timestamp': datetime.now(timezone.utc),
        'action': 'CREATE',
        'quantity': test_inventory['quantity'],
        'room_id': test_inventory['room_id']
    }]
    
    return mock_db
