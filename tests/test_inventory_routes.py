import pytest
from uuid import uuid4
from decimal import Decimal
from fastapi import status
from .conftest import CustomTestClient
from datetime import datetime, timezone

@pytest.mark.asyncio
async def test_add_inventory_success(
    client: CustomTestClient,
    mock_inventory_db,
    mock_room_db,
    sample_inventory_data
):
    """Test successful inventory addition"""
    mock_inventory_db.create_inventory.return_value = {
        "id": str(uuid4()),
        **sample_inventory_data,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    
    response = await client.post("/api/v1/inventory", json=sample_inventory_data)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["sku"] == sample_inventory_data["sku"]
    assert data["description"] == sample_inventory_data["description"]
    assert Decimal(data["quantity"]) == sample_inventory_data["quantity"]
    assert data["room_id"] == str(sample_inventory_data["room_id"])
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data

@pytest.mark.asyncio
async def test_add_inventory_exceeds_capacity(
    client: CustomTestClient,
    mock_inventory_db,
    mock_room_db,
    sample_inventory_data
):
    """Test adding inventory that exceeds room capacity"""
    # Mock room with limited available capacity
    mock_room_db.get_room.return_value.available_capacity = Decimal("50.00")
    sample_inventory_data["quantity"] = Decimal("100.00")
    
    response = await client.post("/api/v1/inventory", json=sample_inventory_data)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    data = response.json()
    assert "capacity" in str(data["detail"]).lower()
    assert "room" in str(data["detail"]).lower()

@pytest.mark.asyncio
async def test_get_inventory_success(
    client: CustomTestClient,
    mock_inventory_db
):
    """Test successful inventory retrieval"""
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
    
    response = await client.get(f"/api/v1/inventory/{inventory_id}")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == str(inventory_id)
    assert "sku" in data
    assert "description" in data
    assert "quantity" in data
    assert "room_id" in data

@pytest.mark.asyncio
async def test_list_inventory_by_room(
    client: CustomTestClient,
    mock_inventory_db
):
    """Test listing inventory by room"""
    room_id = uuid4()
    mock_inventory_db.list_inventory.return_value = [{
        "id": str(uuid4()),
        "sku": "TEST-SKU-001",
        "description": "Test Inventory Item",
        "quantity": "100.00",
        "room_id": str(room_id),
        "warehouse_id": str(uuid4()),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }]
    
    response = await client.get(f"/api/v1/rooms/{room_id}/inventory")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert isinstance(data, list)
    if len(data) > 0:
        for item in data:
            assert item["room_id"] == str(room_id)

@pytest.mark.asyncio
async def test_transfer_inventory_success(
    client: CustomTestClient,
    mock_inventory_db,
    mock_room_db
):
    """Test successful inventory transfer between rooms"""
    inventory_id = uuid4()
    transfer_data = {
        "destination_room_id": str(uuid4()),
        "quantity": "10.00"
    }
    
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
    
    mock_inventory_db.update_inventory.return_value = {
        **mock_inventory_db.get_inventory.return_value,
        "room_id": transfer_data["destination_room_id"],
        "quantity": transfer_data["quantity"],
        "updated_at": datetime.now(timezone.utc)
    }
    
    response = await client.post(
        f"/api/v1/inventory/{inventory_id}/transfer",
        json=transfer_data
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == str(inventory_id)
    assert data["room_id"] == transfer_data["destination_room_id"]
    assert Decimal(data["quantity"]) == Decimal(transfer_data["quantity"])

@pytest.mark.asyncio
async def test_transfer_inventory_exceeds_capacity(
    client: CustomTestClient,
    mock_inventory_db,
    mock_room_db
):
    """Test inventory transfer exceeding destination room capacity"""
    inventory_id = uuid4()
    # Mock destination room with limited capacity
    mock_room_db.get_room.return_value.available_capacity = Decimal("5.00")
    
    transfer_data = {
        "destination_room_id": str(uuid4()),
        "quantity": "10.00"
    }
    
    response = await client.post(
        f"/api/v1/inventory/{inventory_id}/transfer",
        json=transfer_data
    )
    
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    data = response.json()
    assert "capacity" in str(data["detail"]).lower()

@pytest.mark.asyncio
async def test_transfer_inventory_insufficient_quantity(
    client: CustomTestClient,
    mock_inventory_db,
    mock_room_db
):
    """Test inventory transfer with insufficient quantity"""
    inventory_id = uuid4()
    # Mock inventory with less quantity than requested
    mock_inventory_db.get_inventory.return_value.quantity = Decimal("5.00")
    
    transfer_data = {
        "destination_room_id": str(uuid4()),
        "quantity": "10.00"
    }
    
    response = await client.post(
        f"/api/v1/inventory/{inventory_id}/transfer",
        json=transfer_data
    )
    
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    data = response.json()
    assert "quantity" in str(data["detail"]).lower()
    assert "insufficient" in str(data["detail"]).lower()

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
async def test_search_inventory(
    client: CustomTestClient,
    mock_inventory_db
):
    """Test inventory search functionality"""
    search_params = {
        "sku": "TEST-SKU",
        "warehouse_id": str(uuid4())
    }
    
    mock_inventory_db.search_inventory.return_value = [{
        "id": str(uuid4()),
        "sku": "TEST-SKU-001",
        "description": "Test Inventory Item",
        "quantity": "100.00",
        "room_id": str(uuid4()),
        "warehouse_id": search_params["warehouse_id"],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }]
    
    response = await client.get(
        "/api/v1/inventory/search",
        params=search_params
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert isinstance(data, list)
    if len(data) > 0:
        for item in data:
            assert search_params["sku"] in item["sku"]

