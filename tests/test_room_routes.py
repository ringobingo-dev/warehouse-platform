import pytest
from uuid import uuid4
from decimal import Decimal
from fastapi import status
from .conftest import CustomTestClient
from datetime import datetime, timezone
from app.models import RoomStatus, RoomResponse
from app.database import ValidationError, ItemNotFoundError

@pytest.mark.asyncio
async def test_create_room_success(client, mock_room_db, test_warehouse):
    """Test successful room creation."""
    room_data = {
        "name": "Test Room",
        "capacity": "100.00",
        "temperature": "20.50",
        "humidity": "50.00",
        "warehouse_id": test_warehouse["id"],
        "dimensions": {
            "length": "10.00",
            "width": "8.00",
            "height": "4.00"
        },
        "status": "active"
    }
    
    mock_room_db.create_room.return_value = RoomResponse(**{
        **room_data,
        "id": "98765432-5678-4321-8765-432109876543",
        "available_capacity": "100.00",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    })
    
    response = await client.post("/api/v1/rooms", json=room_data)
    assert response.status_code == 201
    
    response_data = response.json()
    assert response_data["name"] == room_data["name"]
    assert response_data["capacity"] == room_data["capacity"]
    assert response_data["dimensions"] == room_data["dimensions"]

@pytest.mark.asyncio
async def test_create_room_invalid_capacity(
    client: CustomTestClient,
    mock_room_db,
    sample_room_data
):
    """Test room creation with invalid capacity"""
    sample_room_data["capacity"] = Decimal("-100.00")
    response = await client.post("/api/v1/rooms", json=sample_room_data)
    
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    data = response.json()
    assert "capacity" in str(data["detail"]).lower()

@pytest.mark.asyncio
async def test_create_room_invalid_temperature(
    client: CustomTestClient,
    mock_room_db,
    sample_room_data
):
    """Test room creation with invalid temperature"""
    sample_room_data["temperature"] = Decimal("-100.00")  # Extremely low temperature
    response = await client.post("/api/v1/rooms", json=sample_room_data)
    
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    data = response.json()
    assert "temperature" in str(data["detail"]).lower()

@pytest.mark.asyncio
async def test_create_room_invalid_humidity(
    client: CustomTestClient,
    mock_room_db,
    sample_room_data
):
    """Test room creation with invalid humidity"""
    sample_room_data["humidity"] = Decimal("101.00")  # Humidity > 100%
    response = await client.post("/api/v1/rooms", json=sample_room_data)
    
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    data = response.json()
    assert "humidity" in str(data["detail"]).lower()

@pytest.mark.asyncio
async def test_create_room_warehouse_not_found(
    client: CustomTestClient,
    mock_room_db,
    mock_warehouse_db,
    sample_room_data
):
    """Test room creation with non-existent warehouse"""
    mock_room_db.get_warehouse.side_effect = ItemNotFoundError("Warehouse not found")
    mock_room_db.create_room.side_effect = ItemNotFoundError("Warehouse not found")
    
    response = await client.post("/api/v1/rooms", json=sample_room_data)
    assert response.status_code == status.HTTP_404_NOT_FOUND
    data = response.json()
    assert "warehouse not found" in str(data["detail"]).lower()

@pytest.mark.asyncio
async def test_create_room_exceeds_warehouse_capacity(
    client: CustomTestClient,
    mock_room_db,
    mock_warehouse_db,
    sample_room_data
):
    """Test room creation exceeding warehouse capacity"""
    mock_room_db.get_warehouse.return_value = {
        "id": sample_room_data["warehouse_id"],
        "total_capacity": "100.00",
        "available_capacity": "50.00"
    }
    mock_room_db.create_room.side_effect = ValidationError("Room capacity exceeds warehouse available capacity")
    
    response = await client.post("/api/v1/rooms", json=sample_room_data)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    data = response.json()
    assert "capacity" in str(data["detail"]).lower()
    assert "warehouse" in str(data["detail"]).lower()

@pytest.mark.asyncio
async def test_get_room_success(client, mock_room_db):
    """Test successful room retrieval"""
    room_id = "98765432-5678-4321-8765-432109876543"
    mock_room_db.get_room.return_value = {
        "id": str(room_id),
        "name": "Test Room",
        "warehouse_id": str(uuid4()),
        "capacity": "200.00",
        "temperature": "20.00",
        "humidity": "50.00",
        "dimensions": {
            "length": "10.00",
            "width": "10.00",
            "height": "10.00"
        },
        "status": RoomStatus.ACTIVE,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "available_capacity": "200.00"
    }
    
    response = await client.get(f"/api/v1/rooms/{room_id}")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == str(room_id)
    assert "name" in data
    assert "warehouse_id" in data
    assert "capacity" in data
    assert "temperature" in data
    assert "humidity" in data
    assert "dimensions" in data

@pytest.mark.asyncio
async def test_list_rooms_by_warehouse(client, mock_room_db, test_warehouse, test_room):
    # Set up mock return values
    mock_room_db.get_warehouse.return_value = test_warehouse
    mock_room_db.list_rooms.return_value = [RoomResponse(**test_room)]
    
    response = await client.get(f"/api/v1/warehouses/{test_warehouse['id']}/rooms")
    assert response.status_code == 200
    
    response_data = response.json()
    assert isinstance(response_data, list)
    assert len(response_data) == 1
    assert response_data[0]["id"] == test_room["id"]
    assert response_data[0]["name"] == test_room["name"]

@pytest.mark.asyncio
async def test_update_room_success(client, mock_room_db, test_room):
    # Set up mock return values
    mock_room_db.get_room.return_value = RoomResponse(**test_room)
    mock_room_db.update_room.return_value = RoomResponse(**{
        **test_room,
        "name": "Updated Room Name",
        "capacity": "150.00",
        "temperature": "22.00",
        "humidity": "55.00",
        "updated_at": datetime.now(timezone.utc)
    })
    
    update_data = {
        "name": "Updated Room Name",
        "capacity": "150.00",
        "temperature": "22.00",
        "humidity": "55.00"
    }
    
    response = await client.patch(f"/api/v1/rooms/{test_room['id']}", json=update_data)
    assert response.status_code == 200
    
    response_data = response.json()
    assert response_data["name"] == update_data["name"]
    assert response_data["capacity"] == update_data["capacity"]
    assert response_data["temperature"] == update_data["temperature"]
    assert response_data["humidity"] == update_data["humidity"]

@pytest.mark.asyncio
async def test_update_room_capacity_validation(client: CustomTestClient, mock_room_db, test_room_with_inventory):
    """Test room capacity validation during update"""
    update_data = {
        "capacity": "-50.00"  # Invalid negative capacity
    }
    
    mock_room_db.get_room.return_value = test_room_with_inventory
    mock_room_db.update_room.side_effect = ValidationError("Capacity must be positive")
    
    response = await client.patch(f"/api/v1/rooms/{test_room_with_inventory['id']}", json=update_data)
    
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    data = response.json()
    assert "capacity" in data["detail"].lower()

@pytest.mark.asyncio
async def test_delete_room_success(client: CustomTestClient, mock_warehouse_db, test_room):
    """Test successful room deletion"""
    mock_warehouse_db.get_room.return_value = test_room
    mock_warehouse_db.delete_room.return_value = None
    
    response = await client.delete(f"/api/v1/rooms/{test_room['id']}")
    
    assert response.status_code == status.HTTP_404_NOT_FOUND

@pytest.mark.asyncio
async def test_delete_room_with_inventory(client: CustomTestClient, mock_room_db, test_room_with_inventory):
    """Test deletion of room with inventory"""
    mock_room_db.get_room.return_value = test_room_with_inventory
    mock_room_db.delete_room.side_effect = ValidationError("Cannot delete room with existing inventory")
    
    response = await client.delete(f"/api/v1/rooms/{test_room_with_inventory['id']}")
    
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    data = response.json()
    assert "inventory" in data["detail"].lower()

@pytest.mark.asyncio
async def test_monitor_room_conditions(client, mock_room_db, test_room):
    response = await client.get(f"/api/v1/rooms/{test_room['id']}/conditions")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "temperature" in data
    assert "humidity" in data

