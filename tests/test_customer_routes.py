import pytest
from uuid import uuid4
from fastapi import status
from .conftest import CustomTestClient
from app.database import ItemNotFoundError, ValidationError, DatabaseError, ConflictError

@pytest.mark.asyncio
async def test_create_customer_success(client: CustomTestClient, mock_customer_data, mock_customer_db):
    """Test successful customer creation"""
    response = await client.post("/api/v1/customers", json=mock_customer_data)
    
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["name"] == mock_customer_data["name"]
    assert data["email"] == mock_customer_data["email"]
    assert data["phone_number"] == mock_customer_data["phone_number"]
    assert data["address"] == mock_customer_data["address"]
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data

@pytest.mark.asyncio
async def test_create_customer_invalid_email(client: CustomTestClient, mock_customer_data):
    """Test customer creation with invalid email"""
    mock_customer_data["email"] = "invalid-email"
    response = await client.post("/api/v1/customers", json=mock_customer_data)
    
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    data = response.json()
    assert "email" in str(data["detail"]).lower()

@pytest.mark.asyncio
async def test_create_customer_invalid_phone(client: CustomTestClient, mock_customer_data):
    """Test customer creation with invalid phone number"""
    mock_customer_data["phone_number"] = "123"  # Too short
    response = await client.post("/api/v1/customers", json=mock_customer_data)
    
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    data = response.json()
    assert "phone" in str(data["detail"]).lower()

@pytest.mark.asyncio
async def test_get_customer_success(client: CustomTestClient, mock_customer_db):
    """Test successful customer retrieval"""
    customer_id = uuid4()
    response = await client.get(f"/api/v1/customers/{customer_id}")
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == str(customer_id)
    assert "name" in data
    assert "email" in data
    assert "phone_number" in data
    assert "address" in data

@pytest.mark.asyncio
async def test_get_customer_not_found(client: CustomTestClient, mock_customer_db):
    """Test customer retrieval with non-existent ID"""
    mock_customer_db.get_customer.side_effect = ItemNotFoundError("Customer not found")
    
    response = await client.get(f"/api/v1/customers/{uuid4()}")
    assert response.status_code == status.HTTP_404_NOT_FOUND

@pytest.mark.asyncio
async def test_update_customer_success(client: CustomTestClient, mock_customer_db, mock_customer_data):
    """Test successful customer update"""
    customer_id = uuid4()
    update_data = {
        "name": "Updated Company Name",
        "phone_number": "+9876543210"
    }
    
    response = await client.patch(f"/api/v1/customers/{customer_id}", json=update_data)
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == str(customer_id)
    assert data["name"] == update_data["name"]
    assert data["phone_number"] == update_data["phone_number"]
    assert data["email"] == mock_customer_data["email"]
    assert data["address"] == mock_customer_data["address"]

@pytest.mark.asyncio
async def test_update_customer_not_found(client: CustomTestClient, mock_customer_db):
    """Test customer update with non-existent ID"""
    mock_customer_db.update_customer.side_effect = ItemNotFoundError("Customer not found")
    
    update_data = {"name": "Updated Company Name"}
    response = await client.patch(f"/api/v1/customers/{uuid4()}", json=update_data)
    assert response.status_code == status.HTTP_404_NOT_FOUND

@pytest.mark.asyncio
async def test_delete_customer_success(client: CustomTestClient, mock_customer_db):
    """Test successful customer deletion"""
    customer_id = uuid4()
    response = await client.delete(f"/api/v1/customers/{customer_id}")
    
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not response.content  # Empty response body

@pytest.mark.asyncio
async def test_delete_customer_not_found(client: CustomTestClient, mock_customer_db):
    """Test customer deletion with non-existent ID"""
    mock_customer_db.delete_customer.side_effect = ItemNotFoundError("Customer not found")
    
    response = await client.delete(f"/api/v1/customers/{uuid4()}")
    assert response.status_code == status.HTTP_404_NOT_FOUND

@pytest.mark.asyncio
async def test_create_customer_duplicate_email(client: CustomTestClient, mock_customer_db, mock_customer_data):
    """Test customer creation with duplicate email"""
    mock_customer_db.create_customer.side_effect = ConflictError("Email already exists")
    
    response = await client.post("/api/v1/customers", json=mock_customer_data)
    assert response.status_code == status.HTTP_409_CONFLICT
    data = response.json()
    assert "email already exists" in str(data["detail"]).lower()

