from decimal import Decimal, InvalidOperation
from typing import Optional, Union
from uuid import UUID
import re
from pydantic import EmailStr

class ValidationError(Exception):
    """Custom validation error with detailed message"""
    def __init__(self, field: str, message: str):
        self.field = field
        self.message = message
        super().__init__(f"{field}: {message}")

def validate_decimal(
    value: Union[str, int, float, Decimal],
    field_name: str,
    min_value: Optional[Union[int, float, Decimal]] = Decimal('0'),
    max_value: Optional[Union[int, float, Decimal]] = None,
    allow_zero: bool = False
) -> Decimal:
    try:
        if isinstance(value, Decimal):
            dec_value = value
        else:
            dec_value = Decimal(str(value)).quantize(Decimal('0.01'))
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationError(field_name, "Invalid decimal value")
    
    if not allow_zero and dec_value == 0:
        raise ValidationError(field_name, "Value must be non-zero")
    if min_value is not None and dec_value < Decimal(str(min_value)):
        if min_value == Decimal('0'):
            raise ValidationError(field_name, "Value must be positive")
        else:
            raise ValidationError(field_name, f"Value must be greater than {min_value}")
    if max_value is not None and dec_value > Decimal(str(max_value)):
        raise ValidationError(field_name, f"Value must be less than {max_value}")
    return dec_value

def validate_dimensions(length: Union[str, int, float, Decimal], width: Union[str, int, float, Decimal], height: Union[str, int, float, Decimal]) -> tuple[Decimal, Decimal, Decimal]:
    try:
        l = validate_decimal(length, "length", min_value=Decimal('0.01'))
        w = validate_decimal(width, "width", min_value=Decimal('0.01'))
        h = validate_decimal(height, "height", min_value=Decimal('0.01'))
        return l, w, h
    except ValidationError as e:
        raise ValidationError(e.field, f"{e.message}")

def validate_phone_number(phone: str) -> str:
    """Validate phone number format"""
    # Remove any non-digit characters for normalization
    normalized = re.sub(r'\D', '', phone)
    if not (10 <= len(normalized) <= 15):
        raise ValidationError("phone_number", "Phone number must be between 10 and 15 digits")
    return normalized

def validate_email(email: str) -> str:
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        raise ValidationError("email", "Invalid email format")
    return email

def validate_capacity(
    current_usage: Decimal,
    requested: Decimal,
    field_name: str = "capacity"
) -> Decimal:
    # First validate that the requested capacity is a valid decimal
    requested = validate_decimal(requested, field_name, min_value=Decimal('0.01'))
    
    # Then check the business rule about current usage
    if current_usage > requested:
        raise ValidationError(field_name, f"Cannot reduce capacity below current usage ({current_usage})")
    return requested

def validate_uuid(value: str, field_name: str = "id") -> UUID:
    try:
        return UUID(value)
    except ValueError:
        raise ValidationError(field_name, "Invalid UUID format")

def validate_string_length(
    value: str,
    field_name: str,
    min_length: Optional[int] = None,
    max_length: Optional[int] = None
) -> str:
    if min_length is not None and len(value) < min_length:
        raise ValidationError(field_name, f"Minimum length is {min_length}")
    if max_length is not None and len(value) > max_length:
        raise ValidationError(field_name, f"Maximum length is {max_length}")
    return value

def validate_temperature(temp: Union[str, int, float, Decimal]) -> Decimal:
    """Validate temperature based on business rules.
    Pydantic handles the basic range validation (-30 to 50).
    This function handles additional business rules."""
    try:
        if isinstance(temp, Decimal):
            value = temp
        else:
            value = Decimal(str(temp)).quantize(Decimal('0.01'))
        
        # Business rule: Temperature must be in increments of 0.5 degrees
        if value % Decimal('0.5') != 0:
            raise ValidationError("temperature", "Temperature must be in increments of 0.5 degrees")
            
        return value
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationError("temperature", "Invalid temperature value")

def validate_humidity(humidity: Union[str, int, float, Decimal]) -> Decimal:
    """Validate humidity based on business rules.
    Pydantic handles the basic range validation (0 to 100).
    This function handles additional business rules."""
    try:
        if isinstance(humidity, Decimal):
            value = humidity
        else:
            value = Decimal(str(humidity)).quantize(Decimal('0.01'))
        
        # Business rule: Humidity must be in whole number percentages
        if value % Decimal('1') != 0:
            raise ValidationError("humidity", "Humidity must be a whole number percentage")
            
        return value
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationError("humidity", "Invalid humidity value") 