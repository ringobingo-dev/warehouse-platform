import pytest
from uuid import uuid4
from decimal import Decimal
from fastapi import status
from .conftest import CustomTestClient
from datetime import datetime, timezone
from app.models import RoomStatus

@pytest.mark.asyncio
async def test_create_room_success(client, mock_room_db, test_warehouse):
    room_data = {
        "name": "Test Room",
        "warehouse_id": str(test_warehouse["id"]),
        "capacity": "200.00",
        "temperature": "20.00",
        "humidity": "50.00",
        "dimensions": {
            "length": "10.00",
            "width": "10.00",
            "height": "10.00"
        }
    }
    mock_room_db.create_room.return_value = {
        "id": str(uuid4()),
        **room_data,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "status": RoomStatus.ACTIVE,
        "available_capacity": room_data["capacity"]
    }
    
    response = await client.post("/api/v1/rooms", json=room_data)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["name"] == room_data["name"]
    assert data["warehouse_id"] == room_data["warehouse_id"]
    assert Decimal(data["capacity"]) == Decimal(room_data["capacity"])
    assert Decimal(data["temperature"]) == Decimal(room_data["temperature"])
    assert Decimal(data["humidity"]) == Decimal(room_data["humidity"])
    assert Decimal(data["dimensions"]["length"]) == Decimal(room_data["dimensions"]["length"])
    assert Decimal(data["dimensions"]["width"]) == Decimal(room_data["dimensions"]["width"])
    assert Decimal(data["dimensions"]["height"]) == Decimal(room_data["dimensions"]["height"])

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
    mock_warehouse_db.get_warehouse.side_effect = KeyError("Warehouse not found")
    
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
    # Mock warehouse with limited available capacity
    mock_warehouse_db.get_warehouse.return_value.available_capacity = Decimal("100.00")
    sample_room_data["capacity"] = Decimal("200.00")
    
    response = await client.post("/api/v1/rooms", json=sample_room_data)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    data = response.json()
    assert "capacity" in str(data["detail"]).lower()
    assert "warehouse" in str(data["detail"]).lower()

@pytest.mark.asyncio
async def test_get_room_success(client, mock_room_db):
    """Test successful room retrieval"""
    room_id = uuid4()
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
async def test_list_rooms_by_warehouse(client, mock_room_db, test_warehouse):
    response = await client.get(f"/api/v1/warehouses/{test_warehouse['id']}/rooms")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert isinstance(data, list)

@pytest.mark.asyncio
async def test_update_room_success(client, mock_room_db):
    """Test successful room update"""
    room_id = uuid4()
    update_data = {
        "temperature": "22.00",
        "humidity": "55.00"
    }
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
    mock_room_db.update_room.return_value = {
        **mock_room_db.get_room.return_value,
        **update_data,
        "updated_at": datetime.now(timezone.utc)
    }
    
    response = await client.patch(f"/api/v1/rooms/{room_id}", json=update_data)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == str(room_id)
    assert Decimal(data["temperature"]) == Decimal(update_data["temperature"])
    assert Decimal(data["humidity"]) == Decimal(update_data["humidity"])

@pytest.mark.asyncio
async def test_update_room_capacity_validation(
    client: CustomTestClient,
    mock_room_db
):
    """Test room update with invalid capacity changes"""
    room_id = uuid4()
    update_data = {
        "capacity": Decimal("50.00")  # Trying to reduce capacity below current usage
    }
    
    # Mock that we have some inventory using capacity
    mock_room_db.get_room.return_value.available_capacity = Decimal("75.00")
    
    response = await client.patch(f"/api/v1/rooms/{room_id}", json=update_data)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    data = response.json()
    assert "capacity" in str(data["detail"]).lower()

@pytest.mark.asyncio
async def test_delete_room_success(client, mock_room_db):
    """Test successful room deletion"""
    room_id = uuid4()
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
    
    response = await client.delete(f"/api/v1/rooms/{room_id}")
    assert response.status_code == status.HTTP_204_NO_CONTENT

@pytest.mark.asyncio
async def test_delete_room_with_inventory(
    client: CustomTestClient,
    mock_room_db
):
    """Test room deletion when inventory exists"""
    room_id = uuid4()
    # Mock that we have inventory
    mock_room_db.get_room.return_value.available_capacity = Decimal("75.00")
    
    response = await client.delete(f"/api/v1/rooms/{room_id}")
    assert response.status_code == status.HTTP_409_CONFLICT
    data = response.json()
    assert "inventory" in str(data["detail"]).lower()

@pytest.mark.asyncio
async def test_monitor_room_conditions(client, mock_room_db, test_room):
    response = await client.get(f"/api/v1/rooms/{test_room['id']}/conditions")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "temperature" in data
    assert "humidity" in data

