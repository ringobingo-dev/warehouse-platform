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
    RoomUpdate,
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
def mock_warehouse_db(test_warehouse, test_room, test_inventory):
    """Mock warehouse database with proper timestamps and model validation."""
    class MockWarehouseDB:
        def __init__(self):
            self.warehouses = {}
            self.customers = {}
            self.inventory = {}
            self.rooms = {}
            
            # Add test warehouse
            self.warehouses[test_warehouse["id"]] = test_warehouse
            
            # Add test room
            self.rooms[test_room["id"]] = test_room
            
            # Mock methods with correct names
            self.get_warehouse = AsyncMock(side_effect=self.handle_get_warehouse)
            self.create_warehouse = AsyncMock(side_effect=self.handle_create_warehouse)
            self.update_warehouse = AsyncMock(side_effect=self.handle_update_warehouse)
            self.delete_warehouse = AsyncMock(side_effect=self.handle_delete_warehouse)
            self.list_warehouses = AsyncMock(return_value=[test_warehouse])
            self.get_customer = AsyncMock(side_effect=self.handle_get_customer)
            self.get_inventory_levels = AsyncMock(side_effect=self.handle_get_inventory_levels)
            self.list_by_customer = AsyncMock(side_effect=self.handle_list_by_customer)
            
            # Add missing methods
            self.get_room = AsyncMock(side_effect=self.handle_get_room)
            self.create_room = AsyncMock(side_effect=self.handle_create_room)
            self.update_room = AsyncMock(side_effect=self.handle_update_room)
            self.delete_room = AsyncMock(side_effect=self.handle_delete_room)
            self.list_rooms = AsyncMock(return_value=[test_room])
            self.get_rooms = AsyncMock(side_effect=self.handle_get_rooms)
            self.add_inventory = AsyncMock(side_effect=self.handle_add_inventory)
            self.get_inventory = AsyncMock(side_effect=self.handle_get_inventory)
            self.list_inventory_by_room = AsyncMock(side_effect=self.handle_list_inventory_by_room)
            self.create_inventory = AsyncMock(side_effect=self.handle_create_inventory)
            self.search_inventory = AsyncMock(side_effect=self.handle_search_inventory)

        async def handle_get_customer(self, customer_id: UUID) -> Dict[str, Any]:
            """Handle get customer requests."""
            # If get_customer has a side effect that's an exception, raise it
            if hasattr(self, 'get_customer') and hasattr(self.get_customer, '_mock_side_effect'):
                side_effect = self.get_customer._mock_side_effect
                if isinstance(side_effect, Exception):
                    raise side_effect
                if callable(side_effect):
                    return side_effect(customer_id)

            test_customer_id = UUID("12345678-1234-5678-1234-567812345678")
            
            # Check if customer exists
            if customer_id != test_customer_id:
                raise ItemNotFoundError(f"Customer {customer_id} not found")
            
            # Return test customer data
            return {
                "id": str(test_customer_id),
                "name": "Test Customer",
                "email": "test@example.com",
                "phone_number": "1234567890",
                "address": "123 Test St",
                "verification_status": "VERIFIED",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z"
            }

        async def handle_get_warehouse(self, warehouse_id: UUID) -> Dict[str, Any]:
            """Handle get warehouse requests."""
            warehouse_id_str = str(warehouse_id)
            if warehouse_id_str in self.warehouses:
                return self.warehouses[warehouse_id_str]
            raise ItemNotFoundError(f"Warehouse {warehouse_id} not found")

        async def handle_create_warehouse(self, warehouse_data: Dict[str, Any]) -> Dict[str, Any]:
            """Handle create warehouse requests."""
            # Check if customer exists
            customer_id = warehouse_data.customer_id if hasattr(warehouse_data, 'customer_id') else warehouse_data.get('customer_id')
            
            # If get_customer has a side effect that's an exception, let it propagate
            if hasattr(self.get_customer, '_mock_side_effect'):
                side_effect = self.get_customer._mock_side_effect
                if isinstance(side_effect, Exception):
                    raise side_effect
            
            # Otherwise check if customer exists
            try:
                await self.get_customer(customer_id)
            except ItemNotFoundError:
                raise ItemNotFoundError(f"Customer {customer_id} not found")

            # Create warehouse with a new UUID
            warehouse_id = str(uuid4())
            warehouse = {
                'id': warehouse_id,
                'name': warehouse_data.name if hasattr(warehouse_data, 'name') else warehouse_data['name'],
                'address': warehouse_data.address if hasattr(warehouse_data, 'address') else warehouse_data['address'],
                'total_capacity': warehouse_data.total_capacity if hasattr(warehouse_data, 'total_capacity') else warehouse_data['total_capacity'],
                'available_capacity': warehouse_data.total_capacity if hasattr(warehouse_data, 'total_capacity') else warehouse_data['total_capacity'],
                'customer_id': str(customer_id),
                'created_at': datetime.now(timezone.utc),
                'updated_at': datetime.now(timezone.utc),
                'rooms': []
            }
            self.warehouses[warehouse_id] = warehouse
            return warehouse

        async def handle_update_warehouse(self, warehouse_id_str: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
            warehouse_id = str(warehouse_id_str)
            if warehouse_id not in self.warehouses:
                raise ItemNotFoundError(f"Warehouse {warehouse_id} not found")
            
            warehouse = self.warehouses[warehouse_id]
            
            # Handle Pydantic models or dicts
            if hasattr(update_data, "model_dump"):
                update_dict = update_data.model_dump(exclude_unset=True)
            elif hasattr(update_data, "dict"):
                update_dict = update_data.dict(exclude_unset=True)
            else:
                update_dict = update_data
            
            # Filter out None values
            update_dict = {k: v for k, v in update_dict.items() if v is not None}
            
            # Update the warehouse
            updated_warehouse = {**warehouse, **update_dict}
            updated_warehouse["updated_at"] = datetime.now(timezone.utc)
            
            self.warehouses[warehouse_id] = updated_warehouse
            return updated_warehouse

        async def handle_delete_warehouse(self, warehouse_id: UUID) -> None:
            """Delete a warehouse."""
            warehouse_id_str = str(warehouse_id)
            
            warehouse = await self.handle_get_warehouse(warehouse_id)
            if not warehouse:
                raise ItemNotFoundError(f"Warehouse {warehouse_id} not found")
            
            # Check for inventory in the warehouse's rooms
            for room in warehouse.get('rooms', []):
                if room.get('inventory', []):
                    raise ValidationError(f"Cannot delete warehouse {warehouse_id} with existing inventory")
            
            # Delete the warehouse if it exists
            if warehouse_id_str in self.warehouses:
                del self.warehouses[warehouse_id_str]

        async def handle_get_inventory_levels(self, warehouse_id: UUID) -> Dict[str, Any]:
            """Handle get inventory levels requests."""
            warehouse_id_str = str(warehouse_id)
            if warehouse_id_str in self.warehouses:
                return {
                    'total_capacity': self.warehouses[warehouse_id_str]['total_capacity'],
                    'available_capacity': self.warehouses[warehouse_id_str]['available_capacity'],
                    'utilized_capacity': Decimal(self.warehouses[warehouse_id_str]['total_capacity']) - Decimal(self.warehouses[warehouse_id_str]['available_capacity'])
                }
            raise ItemNotFoundError(f"Warehouse {warehouse_id} not found")

        async def handle_list_by_customer(self, customer_id: UUID) -> List[Dict[str, Any]]:
            """Handle list warehouses by customer requests."""
            customer_id_str = str(customer_id)
            warehouses = []
            for warehouse in self.warehouses.values():
                if str(warehouse['customer_id']) == customer_id_str:
                    warehouses.append(warehouse)
            return warehouses

        async def handle_get_room(self, warehouse_id: str, room_id: str) -> Dict[str, Any]:
            """Handle get room requests."""
            # Check if warehouse exists
            if str(warehouse_id) not in self.warehouses:
                raise ItemNotFoundError(f"Warehouse {warehouse_id} not found")
            
            # Check if room exists
            if str(room_id) not in self.rooms:
                raise ItemNotFoundError(f"Room {room_id} not found")
            
            # Check if room belongs to warehouse
            room = self.rooms[str(room_id)]
            if room["warehouse_id"] != str(warehouse_id):
                raise ItemNotFoundError(f"Room {room_id} not found in warehouse {warehouse_id}")
            
            return room

        async def handle_create_room(self, warehouse_id: str, room_data: RoomCreate) -> Dict[str, Any]:
            room_dict = {
                "id": str(uuid.uuid4()),
                "name": room_data.name,
                "capacity": room_data.capacity,
                "temperature": room_data.temperature,
                "humidity": room_data.humidity,
                "dimensions": room_data.dimensions.model_dump(),
                "warehouse_id": warehouse_id,
                "status": RoomStatus.ACTIVE,
                "available_capacity": room_data.capacity,
                "current_utilization": Decimal('0.00'),
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
            return room_dict

        async def handle_update_room(self, warehouse_id: str, room_id: str, update_data: dict) -> dict:
            """Handle room update operation."""
            room = await self.get_room(warehouse_id, room_id)
            if not room:
                raise ItemNotFoundError(f"Room {room_id} not found")
            
            # Update room data
            updated_room = {**room, **update_data}
            self.rooms[room_id] = updated_room
            return updated_room

        async def handle_delete_room(self, room_id: UUID) -> None:
            """Handle delete room requests."""
            if str(room_id) not in self.rooms:
                raise ItemNotFoundError(f"Room {room_id} not found")
            
            # Check if room has inventory
            for inventory in self.inventory.values():
                if inventory["room_id"] == str(room_id):
                    raise ValueError("Cannot delete room with existing inventory")
            
            del self.rooms[str(room_id)]

        async def handle_get_rooms(self, warehouse_id: UUID) -> List[Dict[str, Any]]:
            rooms = []
            for room in self.rooms.values():
                if room["warehouse_id"] == str(warehouse_id):
                    rooms.append(room)
            return rooms

        async def handle_add_inventory(self, warehouse_id: str, inventory_data: Dict[str, Any]) -> Dict[str, Any]:
            """Handle add inventory requests."""
            # Check if warehouse exists
            warehouse_id_str = str(warehouse_id)
            if warehouse_id_str not in self.warehouses:
                raise ItemNotFoundError(f"Warehouse {warehouse_id} not found")
            
            # Check room exists
            room_id = str(inventory_data["room_id"])
            if room_id not in self.rooms:
                raise ItemNotFoundError(f"Room {room_id} not found")
            
            # Check capacity
            room = self.rooms[room_id]
            if Decimal(inventory_data["quantity"]) > Decimal(room["available_capacity"]):
                raise ValidationError("Insufficient room capacity")
            
            # Create inventory
            inventory_id = str(uuid4())
            inventory = {
                "id": inventory_id,
                "sku": inventory_data["sku"],
                "name": inventory_data["name"],
                "description": inventory_data.get("description"),
                "quantity": inventory_data["quantity"],
                "unit": inventory_data["unit"],
                "unit_weight": inventory_data["unit_weight"],
                "room_id": room_id,
                "warehouse_id": warehouse_id_str,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
            
            # Update room's available capacity
            room["available_capacity"] = str(Decimal(room["available_capacity"]) - Decimal(inventory_data["quantity"]))
            self.rooms[room_id] = room
            
            # Store inventory
            self.inventory[inventory_id] = inventory
            return inventory

        async def handle_get_inventory(self, warehouse_id: str) -> List[Dict[str, Any]]:
            """Handle get inventory requests."""
            test_warehouse_id = "87654321-4321-8765-4321-876543210987"
            
            # Return empty list for test warehouse
            if warehouse_id == test_warehouse_id:
                return []
            
            # Return test inventory for other warehouses
            return [{
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "sku": "TEST-SKU-001",
                "name": "Test Item",
                "description": "Test Description",
                "quantity": "10.00",
                "unit": "kg",
                "unit_weight": "1.00",
                "total_weight": "10.00",
                "room_id": "550e8400-e29b-41d4-a716-446655440001",
                "warehouse_id": warehouse_id,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z"
            }]

        async def handle_list_inventory_by_room(self, room_id: UUID) -> List[Dict[str, Any]]:
            """Handle list inventory by room requests."""
            room_id_str = str(room_id)
            if room_id_str not in self.rooms:
                raise ItemNotFoundError(f"Room {room_id} not found")
            
            # Return all inventory items for this room
            inventory_items = []
            for inventory in self.inventory.values():
                if inventory["room_id"] == room_id_str:
                    inventory_items.append(inventory)
            return inventory_items

        async def handle_create_inventory(self, inventory_data: Dict[str, Any]) -> Dict[str, Any]:
            """Handle create inventory requests."""
            inventory_id = str(uuid4())
            inventory = {
                "id": inventory_id,
                "sku": inventory_data.sku,
                "name": inventory_data.name,
                "description": inventory_data.description,
                "quantity": str(inventory_data.quantity),
                "unit": inventory_data.unit,
                "unit_weight": str(inventory_data.unit_weight),
                "room_id": str(inventory_data.room_id),
                "warehouse_id": str(inventory_data.warehouse_id),
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
            self.inventory[inventory_id] = inventory
            return inventory

        async def handle_search_inventory(self, query: str) -> List[Dict[str, Any]]:
            """Handle search inventory requests."""
            results = []
            for inventory in self.inventory.values():
                if (query.lower() in inventory["name"].lower() or 
                    query.lower() in inventory["sku"].lower() or 
                    (inventory["description"] and query.lower() in inventory["description"].lower())):
                    results.append(inventory)
            return results

        async def handle_get_room_by_id(self, room_id: str) -> Dict[str, Any]:
            """Handle get room by ID requests."""
            if str(room_id) not in self.rooms:
                raise ItemNotFoundError(f"Room {room_id} not found")
            return self.rooms[str(room_id)]

        async def get_room_by_id(self, room_id: str) -> Dict[str, Any]:
            """Get room by ID."""
            return await self.handle_get_room_by_id(room_id)

    return MockWarehouseDB()

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
                            "current_utilization": Decimal(test_room["current_utilization"]),
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
        "current_utilization": "0.00",
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
        available_capacity=format_decimal(Decimal("100.00")),
        current_utilization=format_decimal(Decimal("0.00"))
    )

@pytest.fixture
def sample_inventory_data():
    return {
        'sku': 'TEST-SKU-001',
        'name': 'Test Inventory Item',
        'description': 'Test Inventory Item Description',
        'quantity': format_decimal(Decimal('100.00')),
        'unit': 'kg',
        'unit_weight': format_decimal(Decimal('1.00')),
        'room_id': str(uuid4()),
        'warehouse_id': str(uuid4())
    }

@pytest.fixture
def test_inventory():
    """Test inventory fixture with proper timestamps."""
    return {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "sku": "TEST-SKU-001",
        "name": "Test Item",
        "description": "Test Description",
        "quantity": "100.00",
        "unit": "kg",
        "unit_weight": "1.00",
        "total_weight": "100.00",
        "room_id": "98765432-5678-4321-8765-432109876543",
        "warehouse_id": "87654321-4321-8765-4321-876543210987",
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
        unit_weight=Decimal("1.00"),
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

            # Set up list_by_warehouse to return empty list for all warehouses
            async def handle_list_by_warehouse(warehouse_id: str) -> List[Dict[str, Any]]:
                return []  # Return empty list for all warehouses
            
            self.list_by_warehouse.side_effect = handle_list_by_warehouse

    mock_db = MockInventoryDB()
    
    # Set up default behaviors using the helper method
    mock_db.get_inventory.return_value = mock_db.create_inventory_response(test_inventory)
    mock_db.create_inventory.return_value = mock_db.create_inventory_response(test_inventory)
    mock_db.update_inventory.return_value = mock_db.create_inventory_response(test_inventory)
    mock_db.transfer_inventory.return_value = mock_db.create_inventory_response(test_inventory)
    
    # Set up default behaviors for listing operations
    mock_db.list_inventory.return_value = [mock_db.create_inventory_response(test_inventory)]
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

@pytest.fixture
def sample_warehouse_data(test_customer):
    """Create sample warehouse data for testing."""
    return {
        "name": "Test Warehouse",
        "address": "123 Test Street, Warehouse City, WH 12345",
        "total_capacity": format_decimal(Decimal("1000.00")),
        "customer_id": test_customer["id"],
        "rooms": []
    }

@pytest.fixture
def test_warehouse_with_inventory(test_warehouse, test_room, test_inventory):
    """Create a test warehouse with inventory for testing."""
    warehouse = test_warehouse.copy()
    room = test_room.copy()
    room["inventory"] = [test_inventory]
    warehouse["rooms"] = [room]
    warehouse["available_capacity"] = format_decimal(Decimal("900.00"))  # Reduced by inventory
    return warehouse
