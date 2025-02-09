import pytest
from uuid import uuid4
from decimal import Decimal
from fastapi import status
from .conftest import CustomTestClient
from datetime import datetime, timezone

@pytest.mark.asyncio
async def test_create_warehouse_success(client: CustomTestClient, mock_warehouse_db, test_customer):
    """Test successful warehouse creation"""
    warehouse_data = {
        "name": "Test Warehouse",
        "address": "123 Test Street, Warehouse City, WH 12345",
        "total_capacity": "1000.00",
        "customer_id": test_customer["id"]
    }
    
    mock_warehouse_db.get_customer.return_value = test_customer
    mock_warehouse_db.create_warehouse.return_value = {
        "id": str(uuid4()),
        **warehouse_data,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    
    response = await client.post("/api/v1/warehouses", json=warehouse_data)
    
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["name"] == warehouse_data["name"]
    assert data["address"] == warehouse_data["address"]
    assert data["total_capacity"] == warehouse_data["total_capacity"]
    assert data["customer_id"] == warehouse_data["customer_id"]

@pytest.mark.asyncio
async def test_create_warehouse_invalid_capacity(
    client: CustomTestClient,
    mock_warehouse_db,
    mock_customer_db,
    test_customer
):
    """Test warehouse creation with invalid capacity"""
    warehouse_data = {
        "name": "Test Warehouse",
        "address": "123 Test St",
        "customer_id": test_customer["id"],
        "total_capacity": "-1000.00"  # Invalid negative capacity
    }
    response = await client.post("/api/v1/warehouses", json=warehouse_data)
    
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    data = response.json()
    assert "capacity" in str(data["detail"]).lower()

@pytest.mark.asyncio
async def test_create_warehouse_customer_not_found(
    client: CustomTestClient,
    mock_warehouse_db,
    mock_customer_db,
    sample_warehouse_data
):
    """Test warehouse creation with non-existent customer"""
    mock_customer_db.get_customer.side_effect = KeyError("Customer not found")
    
    response = await client.post("/api/v1/warehouses", json=sample_warehouse_data)
    assert response.status_code == status.HTTP_404_NOT_FOUND
    data = response.json()
    assert "customer not found" in str(data["detail"]).lower()

@pytest.mark.asyncio
async def test_get_warehouse_success(
    client: CustomTestClient,
    mock_warehouse_db,
    test_warehouse
):
    """Test successful warehouse retrieval"""
    response = await client.get(f"/api/v1/warehouses/{test_warehouse['id']}")
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == str(test_warehouse['id'])

@pytest.mark.asyncio
async def test_get_warehouse_not_found(
    client: CustomTestClient,
    mock_warehouse_db
):
    """Test warehouse retrieval with non-existent ID"""
    response = await client.get(f"/api/v1/warehouses/{uuid4()}")
    assert response.status_code == status.HTTP_404_NOT_FOUND

@pytest.mark.asyncio
async def test_list_warehouses_by_customer(client: CustomTestClient, mock_warehouse_db, test_customer, test_warehouse):
    """Test listing warehouses by customer"""
    mock_warehouse_db.get_customer.return_value = test_customer
    mock_warehouse_db.list_warehouses.return_value = [{
        "id": str(test_warehouse["id"]),
        "name": test_warehouse["name"],
        "address": test_warehouse["address"],
        "total_capacity": test_warehouse["total_capacity"],
        "customer_id": str(test_customer["id"]),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }]
    
    response = await client.get(f"/api/v1/warehouses?customer_id={test_customer['id']}")
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    warehouse = data[0]
    assert warehouse["customer_id"] == str(test_customer["id"])

@pytest.mark.asyncio
async def test_update_warehouse_success(
    client: CustomTestClient,
    mock_warehouse_db,
    sample_warehouse_data
):
    """Test successful warehouse update"""
    warehouse_id = uuid4()
    update_data = {
        "name": "Updated Warehouse Name",
        "address": "789 New Address"
    }
    
    response = await client.patch(f"/api/v1/warehouses/{warehouse_id}", json=update_data)
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == str(warehouse_id)
    assert data["name"] == update_data["name"]
    assert data["address"] == update_data["address"]
    # Original data should remain unchanged
    assert Decimal(data["total_capacity"]) == sample_warehouse_data["total_capacity"]
    assert data["customer_id"] == str(sample_warehouse_data["customer_id"])

@pytest.mark.asyncio
async def test_update_warehouse_capacity_validation(client: CustomTestClient, mock_warehouse_db, test_warehouse):
    """Test warehouse capacity validation during update"""
    mock_warehouse_db.get_warehouse.return_value = test_warehouse
    
    update_data = {
        "total_capacity": "-50.00"  # Invalid negative capacity
    }
    
    response = await client.patch(f"/api/v1/warehouses/{test_warehouse['id']}", json=update_data)
    
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    data = response.json()
    assert "detail" in data

@pytest.mark.asyncio
async def test_delete_warehouse_success(client: CustomTestClient, mock_warehouse_db, test_warehouse):
    """Test successful warehouse deletion"""
    response = await client.delete(f"/api/v1/warehouses/{test_warehouse['id']}")
    
    assert response.status_code == status.HTTP_204_NO_CONTENT

@pytest.mark.asyncio
async def test_delete_warehouse_with_inventory(client: CustomTestClient, mock_warehouse_db, test_warehouse_with_inventory):
    """Test deletion of warehouse with inventory"""
    response = await client.delete(f"/api/v1/warehouses/{test_warehouse_with_inventory['id']}")
    
    assert response.status_code == status.HTTP_409_CONFLICT
    data = response.json()
    assert "detail" in data

