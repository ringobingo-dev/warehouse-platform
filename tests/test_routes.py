from datetime import datetime, timezone
from fastapi import status
import pytest
from uuid import uuid4
from decimal import Decimal

from app.main import app
from app.utils import json_serialize
from app.models import RoomStatus
from .conftest import CustomTestClient

@pytest.mark.asyncio
async def test_create_customer_success(client, mock_customer_db):
    customer_data = {
        "name": "New Company",
        "email": "new@example.com",
        "phone_number": "+1987654321",
        "address": "789 New St, New City, NS 54321"
    }
    response = await client.post("/api/v1/customers", json=customer_data)
    assert response.status_code == status.HTTP_201_CREATED

@pytest.mark.asyncio
async def test_create_customer_invalid_data(client, mock_customer_db):
    invalid_data = {"name": "Invalid Customer"}  # Missing required fields
    response = await client.post("/api/v1/customers", json=invalid_data)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

@pytest.mark.asyncio
async def test_get_customer_success(client, mock_customer_db, test_customer):
    response = await client.get(f"/api/v1/customers/{test_customer['id']}")
    assert response.status_code == status.HTTP_200_OK

@pytest.mark.asyncio
async def test_get_customer_not_found(client, mock_customer_db):
    response = await client.get(f"/api/v1/customers/{uuid4()}")
    assert response.status_code == status.HTTP_404_NOT_FOUND

@pytest.mark.asyncio
async def test_update_customer_success(client, mock_customer_db, test_customer):
    update_data = {
        "name": "Updated Company",
        "phone_number": "+1987654321"
    }
    response = await client.patch(f"/api/v1/customers/{test_customer['id']}", json=update_data)
    assert response.status_code == status.HTTP_200_OK

@pytest.mark.asyncio
async def test_delete_customer_success(client, mock_customer_db, test_customer):
    response = await client.delete(f"/api/v1/customers/{test_customer['id']}")
    assert response.status_code == status.HTTP_204_NO_CONTENT

@pytest.mark.asyncio
async def test_create_warehouse_success(client, mock_warehouse_db, mock_customer_db, test_customer, mock_warehouse_data):
    warehouse_data = mock_warehouse_data.copy()
    warehouse_data['customer_id'] = test_customer['id']
    response = await client.post('/api/v1/warehouses', json=warehouse_data)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data['name'] == warehouse_data['name']
    assert data['address'] == warehouse_data['address']

@pytest.mark.asyncio
async def test_create_warehouse_invalid_data(client, mock_warehouse_db):
    response = await client.post('/api/v1/warehouses', json={})
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

@pytest.mark.asyncio
async def test_get_warehouse_success(client, mock_warehouse_db, test_warehouse):
    response = await client.get(f'/api/v1/warehouses/{test_warehouse["id"]}')
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data['id'] == test_warehouse['id']
    assert data['name'] == test_warehouse['name']

@pytest.mark.asyncio
async def test_get_warehouse_not_found(client, mock_warehouse_db):
    response = await client.get(f'/api/v1/warehouses/{uuid4()}')
    assert response.status_code == status.HTTP_404_NOT_FOUND

@pytest.mark.asyncio
async def test_list_warehouses_by_customer(client, mock_warehouse_db, test_customer):
    response = await client.get(f'/api/v1/warehouses?customer_id={test_customer["id"]}')
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    for warehouse in data:
        assert warehouse['customer_id'] == test_customer['id']

@pytest.mark.asyncio
async def test_update_warehouse_success(client, mock_warehouse_db, test_warehouse):
    update_data = {
        'name': 'Updated Warehouse',
        'address': '456 New St, New City, NS 54321',
        'total_capacity': Decimal('6000.0')
    }
    response = await client.patch(f'/api/v1/warehouses/{test_warehouse["id"]}', json=update_data)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data['name'] == update_data['name']
    assert data['address'] == update_data['address']

@pytest.mark.asyncio
async def test_update_warehouse_not_found(client, mock_warehouse_db):
    update_data = {'name': 'Updated Warehouse'}
    response = client.patch(f'/api/v1/warehouses/{uuid4()}', json=update_data)
    assert response.status_code == status.HTTP_404_NOT_FOUND

@pytest.mark.asyncio
async def test_delete_warehouse_success(client, mock_warehouse_db, test_warehouse):
    response = await client.delete(f'/api/v1/warehouses/{test_warehouse["id"]}')
    assert response.status_code == status.HTTP_204_NO_CONTENT

@pytest.mark.asyncio
async def test_delete_warehouse_not_found(client, mock_warehouse_db):
    response = await client.delete(f'/api/v1/warehouses/{uuid4()}')
    assert response.status_code == status.HTTP_404_NOT_FOUND

@pytest.mark.asyncio
async def test_invalid_warehouse_id_format(client, mock_warehouse_db):
    response = await client.get('/api/v1/warehouses/invalid-id')
    assert response.status_code == status.HTTP_400_BAD_REQUEST

@pytest.mark.asyncio
async def test_invalid_customer_id_format(client, mock_customer_db):
    response = await client.get('/api/v1/customers/invalid-id')
    assert response.status_code == status.HTTP_400_BAD_REQUEST

