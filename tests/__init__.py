"""
Test suite initialization for the Warehouse Management Service.

This module sets up the test environment and provides common utilities
for all test modules in the warehouse management service.
"""

import os
import pytest
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import boto3
from moto import mock_dynamodb
from fastapi.testclient import TestClient

# Test Configuration
TEST_CONFIG = {
    "DYNAMODB_ENDPOINT": "http://localhost:8000",
    "AWS_DEFAULT_REGION": "us-east-1",
    "TEST_WAREHOUSE_TABLE": "dev-Warehouses",
    "TEST_CUSTOMER_TABLE": "dev-Customers",
    "TEST_ROOM_TABLE": "dev-Rooms",
    "MAX_TEST_ITEMS": 100,
    "TIMEOUT_SECONDS": 30,
    "MAX_RETRIES": 3
}

# Common Test Data Types
TestData = Dict[str, Any]

# Test Categories
class TestCategory:
    """Enum-like class for test categories."""
    UNIT = "unit"
    INTEGRATION = "integration"
    PERFORMANCE = "performance"
    VALIDATION = "validation"

class TestDataFactory:
    """Factory class for generating test data."""
    
    @staticmethod
    def create_warehouse_data(
        warehouse_id: Optional[str] = None,
        name: Optional[str] = None
    ) -> TestData:
        """Create test warehouse data."""
        return {
            "warehouse_id": warehouse_id or "test-warehouse-123",
            "name": name or "Test Warehouse",
            "status": "ACTIVE",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
    
    @staticmethod
    def create_customer_data(
        customer_id: Optional[str] = None,
        company_name: Optional[str] = None
    ) -> TestData:
        """Create test customer data."""
        return {
            "customer_id": customer_id or "test-customer-123",
            "company_name": company_name or "Test Company Ltd",
            "email": "test@example.com",
            "status": "ACTIVE",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
    
    @staticmethod
    def create_room_data(
        room_id: Optional[str] = None,
        name: Optional[str] = None
    ) -> TestData:
        """Create test room data."""
        return {
            "room_id": room_id or "test-room-123",
            "name": name or "Test Room",
            "temperature_zone": "AMBIENT",
            "status": "ACTIVE",
            "dimensions": {
                "length": 10.0,
                "width": 8.0,
                "height": 4.0
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }

# AWS/DynamoDB Fixtures
@pytest.fixture(scope="function")
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = TEST_CONFIG["AWS_DEFAULT_REGION"]

@pytest.fixture(scope="function")
def dynamodb(aws_credentials):
    """DynamoDB mock fixture."""
    with mock_dynamodb():
        yield boto3.resource("dynamodb", region_name=TEST_CONFIG["AWS_DEFAULT_REGION"])

@pytest.fixture(scope="function")
def setup_test_tables(dynamodb):
    """Setup test tables in mock DynamoDB."""
    # Create Warehouses table
    dynamodb.create_table(
        TableName=TEST_CONFIG["TEST_WAREHOUSE_TABLE"],
        KeySchema=[{"AttributeName": "warehouse_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "warehouse_id", "AttributeType": "S"}],
        ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5}
    )
    
    # Create Customers table
    dynamodb.create_table(
        TableName=TEST_CONFIG["TEST_CUSTOMER_TABLE"],
        KeySchema=[{"AttributeName": "customer_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "customer_id", "AttributeType": "S"}],
        ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5}
    )
    
    # Create Rooms table
    dynamodb.create_table(
        TableName=TEST_CONFIG["TEST_ROOM_TABLE"],
        KeySchema=[{"AttributeName": "room_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "room_id", "AttributeType": "S"}],
        ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5}
    )
    
    yield dynamodb

class TestUtils:
    """Utility functions for tests."""
    
    @staticmethod
    def assert_timestamps(data: TestData) -> None:
        """Assert that created_at and updated_at are valid."""
        assert isinstance(data.get("created_at"), str)
        assert isinstance(data.get("updated_at"), str)
    
    @staticmethod
    def assert_valid_id(id_str: str, prefix: str) -> None:
        """Assert that an ID is valid and has the correct prefix."""
        assert isinstance(id_str, str)
        assert id_str.startswith(prefix)
        assert len(id_str) > len(prefix)
    
    @staticmethod
    def assert_dict_contains_subset(subset: Dict, full_dict: Dict) -> None:
        """Assert that a dictionary contains all key-value pairs from a subset."""
        assert all(full_dict.get(key) == val for key, val in subset.items())
    
    @staticmethod
    def clear_table(table_name: str, dynamodb) -> None:
        """Clear all items from a table."""
        table = dynamodb.Table(table_name)
        response = table.scan()
        key_name = next((k["AttributeName"] for k in table.key_schema if k["KeyType"] == "HASH"), None)
        if key_name:
            for item in response.get("Items", []):
                table.delete_item(Key={key_name: item[key_name]})

# Test Markers
def unit_test(func):
    """Decorator for unit tests."""
    return pytest.mark.unit(func)

def integration_test(func):
    """Decorator for integration tests."""
    return pytest.mark.integration(func)

def performance_test(func):
    """Decorator for performance tests."""
    return pytest.mark.performance(func)

def validation_test(func):
    """Decorator for validation tests."""
    return pytest.mark.validation(func)
