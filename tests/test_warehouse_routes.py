import pytest
from uuid import uuid4
from decimal import Decimal
from fastapi import status
from .conftest import CustomTestClient

@pytest.mark.asyncio
async def test_create_warehouse_success(
    client: CustomTestClient,
    mock_warehouse_db,
    mock_customer_db,
    test_customer
):
    """Test successful warehouse creation"""
    warehouse_data = {
        "name": "Test Warehouse",
        "address": "123 Test St",
        "customer_id": test_customer["id"],
        "total_capacity": "1000.00"
    }
    response = await client.post("/api/v1/warehouses", json=warehouse_data)
    
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["name"] == warehouse_data["name"]
    assert data["address"] == warehouse_data["address"]
    assert Decimal(data["total_capacity"]) == Decimal(warehouse_data["total_capacity"])
    assert data["customer_id"] == str(warehouse_data["customer_id"])
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data
    assert "available_capacity" in data
    assert Decimal(data["available_capacity"]) == Decimal(warehouse_data["total_capacity"])

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
async def test_list_warehouses_by_customer(
    client: CustomTestClient,
    mock_warehouse_db,
    test_customer
):
    """Test listing warehouses for a customer"""
    response = await client.get(f"/api/v1/customers/{test_customer['id']}/warehouses")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert isinstance(data, list)

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
async def test_update_warehouse_capacity_validation(
    client: CustomTestClient,
    mock_warehouse_db
):
    """Test warehouse update with invalid capacity changes"""
    warehouse_id = uuid4()
    mock_warehouse = await mock_warehouse_db.get_warehouse(str(warehouse_id))
    mock_warehouse.available_capacity = Decimal("100.00")
    update_data = {"total_capacity": "50.00"}  # Trying to reduce capacity below current usage
    
    response = await client.patch(f"/api/v1/warehouses/{warehouse_id}", json=update_data)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    data = response.json()
    assert "capacity" in str(data["detail"]).lower()

@pytest.mark.asyncio
async def test_delete_warehouse_success(
    client: CustomTestClient,
    mock_warehouse_db
):
    """Test successful warehouse deletion"""
    warehouse_id = uuid4()
    response = await client.delete(f"/api/v1/warehouses/{warehouse_id}")
    assert response.status_code == status.HTTP_204_NO_CONTENT

@pytest.mark.asyncio
async def test_delete_warehouse_with_inventory(
    client: CustomTestClient,
    mock_warehouse_db
):
    """Test warehouse deletion with existing inventory"""
    warehouse_id = uuid4()
    
    # Mock that we have inventory
    mock_warehouse = await mock_warehouse_db.get_warehouse(str(warehouse_id))
    mock_warehouse.available_capacity = Decimal("900.00")  # Some space is used
    mock_warehouse_db.get_warehouse.return_value = mock_warehouse
    
    response = await client.delete(f"/api/v1/warehouses/{warehouse_id}")
    assert response.status_code == status.HTTP_409_CONFLICT
    data = response.json()
    assert "inventory" in str(data["detail"]).lower()

