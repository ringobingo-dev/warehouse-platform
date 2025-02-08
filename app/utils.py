from typing import Dict, List, Optional, Union, Any
from datetime import datetime
from decimal import Decimal
import logging
import json
from pydantic import ValidationError
from uuid import UUID
from fastapi.encoders import jsonable_encoder

class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for handling Decimal types and other custom objects."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, UUID):
            return str(obj)
        elif hasattr(obj, 'dict'):
            return obj.dict()
        return super().default(obj)

def json_serialize(obj: Any) -> str:
    """
    Serialize object to JSON string with custom encoder.
    
    Args:
        obj: Any Python object to serialize
        
    Returns:
        JSON string representation of the object
    """
    return json.dumps(jsonable_encoder(obj), cls=CustomJSONEncoder)

def json_dumps(obj):
    """Convert object to JSON string with custom encoder."""
    return json.dumps(obj, cls=CustomJSONEncoder)

# Configure logging
logger = logging.getLogger(__name__)

# Validation Utilities
def validate_warehouse_dimensions(length: float, width: float, height: float) -> bool:
    """
    Validates if warehouse dimensions are within acceptable ranges.
    Raises ValueError if dimensions are invalid.
    """
    try:
        if any(dim <= 0 for dim in [length, width, height]):
            raise ValueError("Dimensions must be positive values")
        if any(dim > 1000 for dim in [length, width, height]):  # Example maximum
            raise ValueError("Dimensions exceed maximum allowed values")
        return True
    except Exception as e:
        logger.error(f"Dimension validation error: {str(e)}")
        raise

def validate_weight_capacity(capacity: float, room_dimensions: Dict[str, float]) -> bool:
    """
    Validates if weight capacity is appropriate for room dimensions.
    Takes into account floor strength and building codes.
    """
    try:
        floor_area = room_dimensions['length'] * room_dimensions['width']
        max_capacity_per_sqm = 2000  # Example: 2000 kg/m²
        max_allowed_capacity = floor_area * max_capacity_per_sqm
        
        if capacity <= 0:
            raise ValueError("Capacity must be positive")
        if capacity > max_allowed_capacity:
            raise ValueError(f"Capacity exceeds maximum allowed {max_allowed_capacity}kg for given dimensions")
        return True
    except Exception as e:
        logger.error(f"Weight capacity validation error: {str(e)}")
        raise

def validate_temperature_range(min_temp: float, max_temp: float, zone_type: str) -> bool:
    """
    Validates temperature range for different storage zone types.
    """
    ZONE_RANGES = {
        'frozen': (-30, -18),
        'refrigerated': (2, 8),
        'ambient': (15, 25)
    }
    
    try:
        if zone_type not in ZONE_RANGES:
            raise ValueError(f"Invalid zone type. Must be one of {list(ZONE_RANGES.keys())}")
        
        zone_min, zone_max = ZONE_RANGES[zone_type]
        if not (zone_min <= min_temp <= max_temp <= zone_max):
            raise ValueError(f"Temperature range {min_temp} to {max_temp} outside valid range for {zone_type}")
        return True
    except Exception as e:
        logger.error(f"Temperature validation error: {str(e)}")
        raise

def validate_inventory_placement(room_id: UUID, item_dimensions: Dict[str, float], 
                            weight: float, temperature_req: Optional[Dict[str, float]] = None) -> bool:
    """
    Validates if inventory can be placed in specified room.
    Checks dimensions, weight limits, and temperature requirements.
    """
    try:
        # Implementation will need room details from database
        # This is a placeholder for the validation logic
        return True
    except Exception as e:
        logger.error(f"Inventory placement validation error: {str(e)}")
        raise

# Authentication and Authorization
def verify_customer_access(customer_id: UUID, warehouse_id: UUID) -> bool:
    """
    Verifies if customer has access to specified warehouse.
    """
    try:
        # Implementation will need to check customer-warehouse relationships
        # This is a placeholder for the verification logic
        return True
    except Exception as e:
        logger.error(f"Customer access verification error: {str(e)}")
        raise

def verify_warehouse_access(user_id: UUID, warehouse_id: UUID, required_permission: str) -> bool:
    """
    Verifies if user has required permissions for warehouse operations.
    """
    try:
        # Implementation will need to check user permissions
        # This is a placeholder for the verification logic
        return True
    except Exception as e:
        logger.error(f"Warehouse access verification error: {str(e)}")
        raise

# Data Formatting
def format_warehouse_response(warehouse_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Formats warehouse data for API response.
    """
    try:
        return {
            "id": str(warehouse_data.get("warehouse_id")),
            "name": warehouse_data.get("name"),
            "location": warehouse_data.get("location"),
            "rooms": [format_room_response(room) for room in warehouse_data.get("rooms", [])],
            "total_capacity": format_decimal(warehouse_data.get("total_capacity")),
            "current_utilization": format_decimal(warehouse_data.get("current_utilization")),
            "status": warehouse_data.get("status"),
            "created_at": format_datetime(warehouse_data.get("created_at")),
            "updated_at": format_datetime(warehouse_data.get("updated_at"))
        }
    except Exception as e:
        logger.error(f"Warehouse response formatting error: {str(e)}")
        raise

def format_room_response(room_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Formats room data for API response.
    """
    try:
        return {
            "id": str(room_data.get("room_id")),
            "name": room_data.get("name"),
            "dimensions": {
                "length": format_decimal(room_data.get("length")),
                "width": format_decimal(room_data.get("width")),
                "height": format_decimal(room_data.get("height"))
            },
            "capacity": format_decimal(room_data.get("capacity")),
            "utilization": format_decimal(room_data.get("utilization")),
            "temperature_zone": room_data.get("temperature_zone"),
            "status": room_data.get("status")
        }
    except Exception as e:
        logger.error(f"Room response formatting error: {str(e)}")
        raise

# Error Handling
def handle_database_error(error: Exception) -> Dict[str, str]:
    """
    Handles database-related errors and returns appropriate error response.
    """
    logger.error(f"Database error: {str(error)}")
    return {"error": "Database operation failed", "details": str(error)}

def handle_validation_error(error: ValidationError) -> Dict[str, Any]:
    """
    Handles validation errors and returns formatted error response.
    """
    logger.error(f"Validation error: {str(error)}")
    return {
        "error": "Validation failed",
        "details": [{"field": e["loc"][0], "message": e["msg"]} for e in error.errors()]
    }

# Conversion Utilities
def convert_dimensions(value: float, from_unit: str, to_unit: str) -> float:
    """
    Converts dimensions between different units (m, ft, cm, etc.).
    """
    CONVERSION_RATES = {
        "m_to_ft": 3.28084,
        "ft_to_m": 0.3048,
        "m_to_cm": 100,
        "cm_to_m": 0.01
    }
    
    conversion_key = f"{from_unit}_to_{to_unit}"
    if conversion_key not in CONVERSION_RATES:
        raise ValueError(f"Unsupported conversion: {from_unit} to {to_unit}")
    
    return value * CONVERSION_RATES[conversion_key]

def convert_weight(value: float, from_unit: str, to_unit: str) -> float:
    """
    Converts weight between different units (kg, lbs, etc.).
    """
    CONVERSION_RATES = {
        "kg_to_lbs": 2.20462,
        "lbs_to_kg": 0.453592
    }
    
    conversion_key = f"{from_unit}_to_{to_unit}"
    if conversion_key not in CONVERSION_RATES:
        raise ValueError(f"Unsupported conversion: {from_unit} to {to_unit}")
    
    return value * CONVERSION_RATES[conversion_key]

def convert_temperature(value: float, from_unit: str, to_unit: str) -> float:
    """
    Converts temperature between different units (C, F, K).
    """
    if from_unit == "C" and to_unit == "F":
        return (value * 9/5) + 32
    elif from_unit == "F" and to_unit == "C":
        return (value - 32) * 5/9
    elif from_unit == "C" and to_unit == "K":
        return value + 273.15
    elif from_unit == "K" and to_unit == "C":
        return value - 273.15
    else:
        raise ValueError(f"Unsupported conversion: {from_unit} to {to_unit}")

# Helper Functions
def format_decimal(value: Union[float, Decimal, None]) -> Optional[float]:
    """
    Formats decimal values for API responses.
    """
    if value is None:
        return None
    return float(value)

def format_datetime(dt: Optional[datetime]) -> Optional[str]:
    """
    Formats datetime objects for API responses.
    """
    if dt is None:
        return None
    return dt.isoformat()

