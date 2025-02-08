from typing import Any, Dict, List, Optional
from decimal import Decimal
from uuid import UUID, uuid4
from datetime import datetime, timezone
from fastapi import Response
from pydantic import BaseModel

def assert_decimal_equal(value1: Any, value2: Any, places: int = 2) -> bool:
    """Compare two values that might be Decimal for equality"""
    if isinstance(value1, Decimal) and isinstance(value2, (Decimal, float, int)):
        return round(value1, places) == round(Decimal(str(value2)), places)
    if isinstance(value2, Decimal) and isinstance(value1, (float, int)):
        return round(Decimal(str(value1)), places) == round(value2, places)
    return value1 == value2

def assert_response_data(
    response_data: Dict,
    expected_data: Dict,
    exclude_keys: Optional[List[str]] = None
) -> None:
    """Assert that response data matches expected data, handling Decimal comparisons"""
    exclude_keys = exclude_keys or []
    for key, expected_value in expected_data.items():
        if key in exclude_keys:
            continue
        assert key in response_data, f"Missing key in response: {key}"
        if isinstance(expected_value, dict):
            assert_response_data(response_data[key], expected_value)
        elif isinstance(expected_value, (Decimal, float, int)):
            assert assert_decimal_equal(response_data[key], expected_value)
        else:
            assert response_data[key] == expected_value

def create_mock_data(
    base_data: Dict[str, Any],
    include_id: bool = True,
    include_timestamps: bool = True
) -> Dict[str, Any]:
    """Create mock data with optional ID and timestamps"""
    data = base_data.copy()
    if include_id:
        data["id"] = str(uuid4())
    if include_timestamps:
        now = datetime.now(timezone.utc)
        data["created_at"] = now.isoformat()
        data["updated_at"] = now.isoformat()
    return data

def create_paginated_response(
    items: List[Dict],
    page: int = 1,
    size: int = 10,
    total: Optional[int] = None
) -> Dict:
    """Create a paginated response object"""
    total = total or len(items)
    return {
        "items": items,
        "page": page,
        "size": size,
        "total": total,
        "pages": (total + size - 1) // size
    }

class ResponseValidator:
    """Utility class for validating API responses"""
    @staticmethod
    def has_valid_id(data: Dict) -> bool:
        """Check if data has a valid UUID id"""
        try:
            UUID(data.get("id", ""))
            return True
        except (ValueError, AttributeError, TypeError):
            return False

    @staticmethod
    def has_valid_timestamps(data: Dict) -> bool:
        """Check if data has valid created_at and updated_at timestamps"""
        try:
            datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))
            datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00"))
            return True
        except (ValueError, KeyError, AttributeError):
            return False

    @staticmethod
    def is_valid_decimal(value: Any, min_value: Optional[Decimal] = None, max_value: Optional[Decimal] = None) -> bool:
        """Check if value is a valid decimal within optional range"""
        try:
            dec_value = Decimal(str(value))
            if min_value is not None and dec_value < min_value:
                return False
            if max_value is not None and dec_value > max_value:
                return False
            return True
        except (TypeError, ValueError, DecimalException):
            return False

def create_test_model(model_class: type[BaseModel], **kwargs) -> Dict:
    """Create a test model instance with default values"""
    model = model_class(**kwargs)
    return model.model_dump()

def assert_successful_response(
    response: Response,
    expected_status_code: int = 200,
    expected_data: Optional[Dict] = None
) -> Dict:
    """Assert that response is successful and matches expected data"""
    assert response.status_code == expected_status_code
    if expected_data is not None:
        response_data = response.json()
        assert_response_data(response_data, expected_data)
        return response_data
    return response.json() if response.content else {}

def mock_exception_response(
    status_code: int,
    detail: str
) -> Dict:
    """Create a mock exception response"""
    return {
        "detail": detail,
        "status_code": status_code,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

def create_error_response(
    message: str,
    error_type: str = "ValidationError",
    status_code: int = 400
) -> Dict:
    """Create a standardized error response"""
    return {
        "detail": {
            "message": message,
            "error_type": error_type
        },
        "status_code": status_code,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

