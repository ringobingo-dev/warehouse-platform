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
from app.database import (
    ItemNotFoundError,
    ValidationError,
    DatabaseError,
    ConflictError,
    BaseDB
)
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
    return {
        "id": "87654321-4321-8765-4321-876543210987",
        "name": "Test Warehouse",
        "address": "123 Test Street, Warehouse City, WH 12345",
        "total_capacity": "1000.00",
        "customer_id": test_customer["id"],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "available_capacity": "1000.00",
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
    class MockWarehouseDB(BaseDB[WarehouseCreate, WarehouseResponse]):
        def __init__(self):
            super().__init__(table_name="warehouses")
            self.response_model = WarehouseResponse
            self.get_warehouse = AsyncMock()
            self.create_warehouse = AsyncMock()
            self.update_warehouse = AsyncMock()
            self.delete_warehouse = AsyncMock()
            self.list_warehouses = AsyncMock()
            self.list_by_customer = AsyncMock()
            self.get_customer = AsyncMock()
            # Add missing methods
            self.get_room = AsyncMock()
            self.create_room = AsyncMock()
            self.search_inventory = AsyncMock()
            self.get_inventory_levels = AsyncMock()
            self.add_inventory = AsyncMock()
            self.list_inventory_by_room = AsyncMock()

        def create_warehouse_response(self, warehouse_data: dict) -> WarehouseResponse:
            """Create a properly formatted warehouse response with timestamps."""
            if 'created_at' not in warehouse_data:
                warehouse_data['created_at'] = datetime.now(timezone.utc)
            if 'updated_at' not in warehouse_data:
                warehouse_data['updated_at'] = datetime.now(timezone.utc)
            if 'available_capacity' not in warehouse_data:
                warehouse_data['available_capacity'] = warehouse_data.get('total_capacity', '0.00')
            if 'rooms' not in warehouse_data:
                warehouse_data['rooms'] = []
            if 'id' not in warehouse_data:
                warehouse_data['id'] = test_warehouse['id']
            return WarehouseResponse(**warehouse_data)

        async def handle_create_warehouse(self, warehouse_data: Union[WarehouseCreate, dict]):
            try:
                # Handle both Pydantic model and dict inputs
                if hasattr(warehouse_data, 'model_dump'):
                    warehouse_dict = warehouse_data.model_dump()
                else:
                    warehouse_dict = warehouse_data.copy()
                
                warehouse_dict['id'] = test_warehouse['id']  # Use test ID for consistency
                warehouse_dict['created_at'] = datetime.now(timezone.utc)
                warehouse_dict['updated_at'] = datetime.now(timezone.utc)
                warehouse_dict['available_capacity'] = warehouse_dict.get('total_capacity', '0.00')
                warehouse_dict['rooms'] = []
                return self.create_warehouse_response(warehouse_dict)
            except Exception as e:
                raise DatabaseError(f"Error creating warehouse: {str(e)}")

        async def handle_get_warehouse(self, warehouse_id: UUID):
            try:
                if str(warehouse_id) == str(test_warehouse["id"]):
                    return self.create_warehouse_response(test_warehouse)
                raise ItemNotFoundError(f"Warehouse {warehouse_id} not found")
            except ItemNotFoundError:
                raise
            except Exception as e:
                raise DatabaseError(f"Error getting warehouse: {str(e)}")

        async def handle_update_warehouse(self, warehouse_id: UUID, update_data: WarehouseUpdate):
            try:
                warehouse = test_warehouse.copy()
                if str(warehouse_id) != str(warehouse["id"]):
                    raise ItemNotFoundError(f"Warehouse {warehouse_id} not found")

                updated_warehouse = {
                    "id": warehouse_id,
                    "name": update_data.name if update_data.name is not None else warehouse["name"],
                    "address": update_data.address if update_data.address is not None else warehouse["address"],
                    "total_capacity": str(update_data.total_capacity) if update_data.total_capacity is not None else warehouse["total_capacity"],
                    "customer_id": warehouse["customer_id"],
                    "created_at": warehouse["created_at"],
                    "updated_at": datetime.now(timezone.utc),
                    "available_capacity": warehouse["available_capacity"]
                }
                
                return WarehouseResponse(**updated_warehouse)
            except ItemNotFoundError:
                raise
            except Exception as e:
                raise DatabaseError(f"Error updating warehouse: {str(e)}")

        async def handle_list_by_customer(self, customer_id: UUID):
            if str(customer_id) == str(test_warehouse["customer_id"]):
                return [test_warehouse]
            return []

        async def handle_get_room(self, room_id: UUID):
            """Handle get room requests."""
            try:
                if str(room_id) == str(test_room["id"]):
                    return test_room
                raise ItemNotFoundError(f"Room {room_id} not found")
            except ItemNotFoundError:
                raise
            except Exception as e:
                raise DatabaseError(f"Error getting room: {str(e)}")

        async def handle_create_room(self, room_data: RoomCreate):
            """Handle create room requests."""
            try:
                room_dict = room_data.model_dump()
                room_dict['id'] = test_room['id']
                room_dict['created_at'] = datetime.now(timezone.utc)
                room_dict['updated_at'] = datetime.now(timezone.utc)
                room_dict['available_capacity'] = room_dict.get('capacity', '0.00')
                return RoomResponse(**room_dict)
            except Exception as e:
                raise DatabaseError(f"Error creating room: {str(e)}")

        async def handle_search_inventory(self, query: str):
            """Handle inventory search requests."""
            return [test_inventory]

        async def handle_get_inventory_levels(self, warehouse_id: UUID):
            """Handle get inventory levels requests."""
            return {
                'total_capacity': Decimal('1000.00'),
                'used_capacity': Decimal('0.00'),
                'available_capacity': Decimal('1000.00')
            }

        async def handle_add_inventory(self, warehouse_id: UUID, inventory_data: dict):
            """Handle add inventory requests."""
            try:
                inventory_dict = {
                    "id": str(uuid4()),
                    **inventory_data,
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc)
                }
                return InventoryResponse(**inventory_dict)
            except Exception as e:
                raise DatabaseError(f"Error adding inventory: {str(e)}")

        async def handle_list_inventory_by_room(self, room_id: UUID):
            """Handle list inventory by room requests."""
            return [test_inventory]

    mock_db = MockWarehouseDB()
    
    # Set up the mock methods with their handlers
    mock_db.create_warehouse.side_effect = mock_db.handle_create_warehouse
    mock_db.get_warehouse.side_effect = mock_db.handle_get_warehouse
    mock_db.update_warehouse.side_effect = mock_db.handle_update_warehouse
    mock_db.list_by_customer.side_effect = mock_db.handle_list_by_customer
    mock_db.list_warehouses.return_value = [mock_db.create_warehouse_response(test_warehouse)]
    mock_db.get_customer.return_value = mock_db.create_warehouse_response(test_warehouse)

    # Set up new mock methods
    mock_db.get_room.side_effect = mock_db.handle_get_room
    mock_db.create_room.side_effect = mock_db.handle_create_room
    mock_db.search_inventory.side_effect = mock_db.handle_search_inventory
    mock_db.get_inventory_levels.side_effect = mock_db.handle_get_inventory_levels
    mock_db.add_inventory.side_effect = mock_db.handle_add_inventory
    mock_db.list_inventory_by_room.side_effect = mock_db.handle_list_inventory_by_room
    
    return mock_db

@pytest.fixture
def mock_room_db(test_warehouse):
    """Mock room database with proper timestamps and model validation."""
    class MockRoomDB(BaseDB[RoomCreate, RoomResponse]):
        def __init__(self):
            self.response_model = RoomResponse
            # Base DB methods
            self.get_room = AsyncMock()
            self.create_room = AsyncMock()
            self.update_room = AsyncMock()
            self.delete_room = AsyncMock()
            self.list_rooms = AsyncMock()
            self.get_warehouse = AsyncMock()

            async def handle_get_warehouse(warehouse_id):
                if str(warehouse_id) == str(test_warehouse["id"]):
                    return test_warehouse
                raise ItemNotFoundError(f"Warehouse {warehouse_id} not found")

            self.get_warehouse.side_effect = handle_get_warehouse

            async def handle_list_rooms(warehouse_id=None):
                try:
                    # Check if warehouse exists
                    if warehouse_id:
                        warehouse = await self.get_warehouse(warehouse_id)
                        if not warehouse:
                            raise ItemNotFoundError(f"Warehouse {warehouse_id} not found")
                    
                    # Return test room for the test warehouse
                    if str(warehouse_id) == str(test_warehouse["id"]):
                        # Convert test_room data to match database format
                        room_data = {
                            "id": test_room["id"],
                            "name": test_room["name"],
                            "capacity": Decimal(test_room["capacity"]),
                            "temperature": Decimal(test_room["temperature"]),
                            "humidity": Decimal(test_room["humidity"]),
                            "dimensions": RoomDimensions(
                                length=Decimal(test_room["dimensions"]["length"]),
                                width=Decimal(test_room["dimensions"]["width"]),
                                height=Decimal(test_room["dimensions"]["height"])
                            ),
                            "warehouse_id": test_room["warehouse_id"],
                            "status": test_room["status"],
                            "available_capacity": Decimal(test_room["available_capacity"]),
                            "created_at": test_room["created_at"],
                            "updated_at": test_room["updated_at"]
                        }
                        return [RoomResponse(**room_data)]
                    
                    # For any other warehouse ID, return empty list
                    return []
                except ItemNotFoundError as e:
                    raise ItemNotFoundError(str(e))
                except Exception as e:
                    raise DatabaseError(f"Error listing rooms: {str(e)}")

            self.list_rooms.side_effect = handle_list_rooms

    mock_db = MockRoomDB()
    return mock_db

@pytest.fixture
def test_room(test_warehouse):
    return {
        "id": "98765432-5678-4321-8765-432109876543",
        "name": "Test Room",
        "capacity": "100.00",
        "temperature": "20.50",
        "humidity": "50",
        "dimensions": {
            "length": "10.00",
            "width": "8.00",
            "height": "4.00"
        },
        "warehouse_id": test_warehouse["id"],
        "status": RoomStatus.ACTIVE,
        "available_capacity": "100.00",
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
def test_inventory():
    return {
        "id": str(uuid4()),
        "sku": "TEST-SKU-001",
        "name": "Test Item",
        "description": "Test Description",
        "quantity": Decimal("10.00"),
        "unit": "kg",
        "room_id": str(uuid4()),
        "warehouse_id": str(uuid4()),
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
            self.list_items.side_effect = self.list_inventory

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

@pytest.fixture
def sample_room_data(test_warehouse):
    """Create sample room data for testing."""
    return {
        "name": "Sample Room",
        "capacity": "100.00",
        "temperature": "20.00",
        "humidity": "50.00",
        "warehouse_id": test_warehouse["id"],
        "dimensions": {
            "length": "10.00",
            "width": "8.00",
            "height": "4.00"
        },
        "status": "active"
    }

@pytest.fixture
def test_room_with_inventory(test_room, test_inventory):
    """Create a test room with inventory."""
    return {
        **test_room,
        "inventory": [test_inventory],
        "available_capacity": "0.00"  # Room is full due to inventory
    }
