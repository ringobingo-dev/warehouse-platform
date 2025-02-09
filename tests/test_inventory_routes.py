import pytest
from uuid import uuid4, UUID
from decimal import Decimal
from fastapi import status
from .conftest import CustomTestClient
from datetime import datetime, timezone
from app.database import ValidationError
from unittest.mock import AsyncMock
from app.models import RoomStatus

@pytest.fixture
def test_inventory():
    return {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "Test Item",
        "description": "Test Description",
        "sku": "TEST-SKU-001",
        "quantity": 10,
        "unit_weight": Decimal("2.5"),
        "total_weight": Decimal("25.0"),
        "room_id": "550e8400-e29b-41d4-a716-446655440001",
        "warehouse_id": "550e8400-e29b-41d4-a716-446655440002"
    }

@pytest.mark.asyncio
async def test_add_inventory_success(client: CustomTestClient, mock_warehouse_db, test_inventory):
    """Test successful inventory addition"""
    inventory_data = {
        "name": "Test Item",
        "description": "Test Description",
        "sku": "TEST-SKU-001",
        "quantity": "10",
        "unit": "kg",
        "unit_weight": "2.5",
        "room_id": str(test_inventory["room_id"]),
        "warehouse_id": str(test_inventory["warehouse_id"])
    }
    
    mock_warehouse_db.get_room.return_value = {"id": test_inventory["room_id"]}
    mock_warehouse_db.add_inventory.return_value = {
        "id": str(uuid4()),
        **inventory_data,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    
    response = await client.post("/api/v1/inventory", json=inventory_data)
    
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["name"] == inventory_data["name"]
    assert data["quantity"] == inventory_data["quantity"]
    assert data["unit_weight"] == inventory_data["unit_weight"]
    assert "id" in data

@pytest.mark.asyncio
async def test_add_inventory_exceeds_capacity(client: CustomTestClient, mock_inventory_db, test_room):
    """Test inventory addition when it exceeds room capacity"""
    inventory_data = {
        "name": "Large Item",
        "sku": "TEST-SKU-002",
        "description": "Test Large Item",
        "quantity": "1000.00",  # Exceeds capacity
        "unit": "pieces",
        "room_id": test_room["id"]
    }
    
    response = await client.post("/api/v1/inventory", json=inventory_data)
    
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    data = response.json()
    assert "detail" in data

@pytest.mark.asyncio
async def test_get_inventory_success(client: CustomTestClient, mock_inventory_db, test_inventory):
    """Test successful inventory retrieval"""
    response = await client.get(f"/api/v1/inventory/{test_inventory['id']}")
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == test_inventory["id"]
    assert data["name"] == test_inventory["name"]
    assert data["unit"] == test_inventory["unit"]
    assert data["sku"] == test_inventory["sku"]

@pytest.mark.asyncio
async def test_list_inventory_by_room(client: CustomTestClient, mock_warehouse_db):
    room_data = {
        "id": "98765432-5678-4321-8765-432109876543",
        "name": "Test Room",
        "warehouse_id": "87654321-4321-8765-4321-876543210987",
        "dimensions": {
            "length": "10.00",
            "width": "8.00",
            "height": "4.00"
        },
        "capacity": "100.00",
        "temperature": "20.50",
        "humidity": "50",
        "status": RoomStatus.ACTIVE,
        "current_utilization": "0.00",
        "available_capacity": "100.00",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    
    test_inventory = {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "Test Item",
        "description": "Test Description",
        "sku": "TEST-SKU-001",
        "quantity": 10,
        "unit": "kg",
        "unit_weight": Decimal("2.5"),
        "total_weight": Decimal("25.0"),
        "room_id": "550e8400-e29b-41d4-a716-446655440001",
        "warehouse_id": "550e8400-e29b-41d4-a716-446655440002",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    
    # Create new AsyncMock instances for the methods
    mock_warehouse_db.get_room_by_id = AsyncMock(return_value=room_data)
    mock_warehouse_db.list_inventory_by_room = AsyncMock(return_value=[test_inventory])
    
    response = await client.get(f"/api/v1/inventory/room/{test_inventory['room_id']}")
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == test_inventory["id"]

@pytest.mark.asyncio
async def test_transfer_inventory_success(client: CustomTestClient, mock_inventory_db, test_inventory, test_room):
    """Test successful inventory transfer"""
    transfer_data = {
        "quantity": "50.00",
        "source_room_id": test_inventory["room_id"],
        "target_room_id": test_room["id"]
    }
    
    mock_inventory_db.transfer_inventory.return_value = {
        **test_inventory,
        "room_id": test_room["id"],
        "quantity": "50.00"
    }
    
    response = await client.post(f"/api/v1/inventory/{test_inventory['id']}/transfer", json=transfer_data)
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["room_id"] == test_room["id"]
    assert data["quantity"] == transfer_data["quantity"]

@pytest.mark.asyncio
async def test_transfer_inventory_exceeds_capacity(client: CustomTestClient, mock_inventory_db, test_inventory, test_room):
    """Test inventory transfer with insufficient capacity"""
    transfer_data = {
        "quantity": "1000.00",  # Exceeds room capacity
        "source_room_id": test_inventory["room_id"],
        "target_room_id": test_room["id"]
    }
    
    mock_inventory_db.transfer_inventory.side_effect = ValidationError("Transfer exceeds room capacity")
    
    response = await client.post(f"/api/v1/inventory/{test_inventory['id']}/transfer", json=transfer_data)
    
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    data = response.json()
    assert "detail" in data

@pytest.mark.asyncio
async def test_transfer_inventory_insufficient_quantity(client: CustomTestClient, mock_inventory_db, test_inventory, test_room):
    """Test inventory transfer with insufficient quantity"""
    transfer_data = {
        "quantity": "150.00",  # More than available
        "source_room_id": test_inventory["room_id"],
        "target_room_id": test_room["id"]
    }
    
    mock_inventory_db.transfer_inventory.side_effect = ValidationError("Insufficient quantity available")
    
    response = await client.post(f"/api/v1/inventory/{test_inventory['id']}/transfer", json=transfer_data)
    
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    data = response.json()
    assert "detail" in data

@pytest.mark.asyncio
async def test_get_inventory_history(
    client: CustomTestClient,
    mock_inventory_db
):
    """Test retrieving inventory history"""
    inventory_id = uuid4()
    mock_inventory_db.get_inventory_history.return_value = [{
        "timestamp": datetime.now(timezone.utc),
        "action": "TRANSFER",
        "quantity": "10.00",
        "room_id": str(uuid4())
    }]
    
    response = await client.get(f"/api/v1/inventory/{inventory_id}/history")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert isinstance(data, list)
    if len(data) > 0:
        for entry in data:
            assert "timestamp" in entry
            assert "action" in entry
            assert "quantity" in entry
            assert "room_id" in entry

@pytest.mark.asyncio
async def test_update_inventory_success(
    client: CustomTestClient,
    mock_inventory_db,
    mock_room_db,
    sample_inventory_data
):
    """Test successful inventory update"""
    inventory_id = uuid4()
    update_data = {
        "description": "Updated description",
        "quantity": "15.00"
    }
    
    mock_inventory_db.get_inventory.return_value = {
        "id": str(inventory_id),
        **sample_inventory_data,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    
    mock_inventory_db.update_inventory.return_value = {
        **mock_inventory_db.get_inventory.return_value,
        **update_data,
        "updated_at": datetime.now(timezone.utc)
    }
    
    response = await client.patch(
        f"/api/v1/inventory/{inventory_id}",
        json=update_data
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == str(inventory_id)
    assert data["description"] == update_data["description"]
    assert Decimal(data["quantity"]) == Decimal(update_data["quantity"])

@pytest.mark.asyncio
async def test_delete_inventory_success(
    client: CustomTestClient,
    mock_inventory_db
):
    """Test successful inventory deletion"""
    inventory_id = uuid4()
    mock_inventory_db.get_inventory.return_value = {
        "id": str(inventory_id),
        "sku": "TEST-SKU-001",
        "description": "Test Inventory Item",
        "quantity": "100.00",
        "room_id": str(uuid4()),
        "warehouse_id": str(uuid4()),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    
    response = await client.delete(f"/api/v1/inventory/{inventory_id}")
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not response.content

@pytest.mark.asyncio
async def test_create_inventory_success(client: CustomTestClient, mock_warehouse_db, mock_inventory_db, test_room):
    """Test creating inventory successfully."""
    inventory_data = {
        "description": "Test item description",
        "name": "Test Item",
        "sku": "TEST-SKU-001",
        "quantity": "10",
        "unit": "kg",
        "unit_weight": "2.5",
        "room_id": test_room["id"],
        "warehouse_id": test_room["warehouse_id"]
    }
    
    # Create new AsyncMock instances for the methods
    mock_warehouse_db.get_room = AsyncMock(return_value=test_room)
    mock_inventory_db.create_inventory = AsyncMock(return_value={
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": inventory_data["name"],
        "description": inventory_data["description"],
        "quantity": inventory_data["quantity"],
        "unit": inventory_data["unit"],
        "unit_weight": inventory_data["unit_weight"],
        "room_id": inventory_data["room_id"],
        "warehouse_id": inventory_data["warehouse_id"],
        "sku": inventory_data["sku"],
        "created_at": "2025-02-09T18:48:08.469453+00:00",
        "updated_at": "2025-02-09T18:48:08.469455+00:00",
        "transfer_history": []
    })
    
    response = await client.post("/api/v1/inventory", json=inventory_data)
    
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["sku"] == inventory_data["sku"]
    assert data["name"] == inventory_data["name"]
    assert data["quantity"] == inventory_data["quantity"]
    assert data["unit"] == inventory_data["unit"]
    assert data["unit_weight"] == inventory_data["unit_weight"]
    assert data["room_id"] == str(inventory_data["room_id"])
    assert data["warehouse_id"] == str(inventory_data["warehouse_id"])

@pytest.mark.asyncio
async def test_search_inventory(client: CustomTestClient, mock_warehouse_db, mock_inventory_db, test_inventory):
    """Test searching inventory by SKU"""
    # Create new AsyncMock instances for the methods
    mock_inventory_db.search_by_sku = AsyncMock(return_value=[test_inventory])
    mock_warehouse_db.get_warehouse = AsyncMock(return_value={
        "id": test_inventory["warehouse_id"],
        "name": "Test Warehouse",
        "address": "123 Test St",
        "total_capacity": "1000.00",
        "customer_id": str(uuid4()),
        "available_capacity": "900.00",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    })
    
    response = await client.get(f"/api/v1/inventory/search?sku={test_inventory['sku']}")
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == test_inventory["id"]
    assert data[0]["sku"] == test_inventory["sku"]

