import pytest
from decimal import Decimal
from uuid import uuid4
from app.validation import (
    validate_decimal,
    validate_dimensions,
    validate_phone_number,
    validate_email,
    validate_capacity,
    validate_uuid,
    validate_string_length,
    validate_temperature,
    validate_humidity,
    ValidationError
)

def test_validate_decimal():
    """Test decimal validation"""
    # Test valid cases
    assert validate_decimal("10.50", "test") == Decimal("10.50")
    assert validate_decimal(10.5, "test") == Decimal("10.50")
    assert validate_decimal(Decimal("10.50"), "test") == Decimal("10.50")
    
    # Test invalid cases
    with pytest.raises(ValidationError) as exc:
        validate_decimal("-1", "test")
    assert "must be positive" in str(exc.value)
    
    with pytest.raises(ValidationError) as exc:
        validate_decimal("invalid", "test")
    assert "Invalid decimal value" in str(exc.value)

def test_validate_dimensions():
    """Test dimensions validation"""
    # Test valid case
    validate_dimensions(
        Decimal("10.00"),
        Decimal("10.00"),
        Decimal("10.00")
    )
    
    # Test invalid cases
    with pytest.raises(ValidationError) as exc:
        validate_dimensions(
            Decimal("-1.00"),
            Decimal("10.00"),
            Decimal("10.00")
        )
    assert "length" in str(exc.value)
    assert "must be greater than" in str(exc.value)

def test_validate_phone_number():
    """Test phone number validation"""
    # Test valid cases
    assert validate_phone_number("1234567890") == "1234567890"
    assert validate_phone_number("+1-234-567-8901") == "12345678901"
    
    # Test invalid cases
    with pytest.raises(ValidationError) as exc:
        validate_phone_number("123")
    assert "must be between 10 and 15 digits" in str(exc.value)

def test_validate_email():
    """Test email validation"""
    # Test valid case
    assert validate_email("test@example.com") == "test@example.com"
    
    # Test invalid cases
    with pytest.raises(ValidationError) as exc:
        validate_email("invalid-email")
    assert "Invalid email format" in str(exc.value)

def test_validate_capacity():
    """Test capacity validation"""
    # Test valid case
    validate_capacity(Decimal("10.00"), Decimal("20.00"))
    
    # Test invalid case
    with pytest.raises(ValidationError) as exc:
        validate_capacity(Decimal("20.00"), Decimal("10.00"))
    assert "Cannot reduce capacity below current usage" in str(exc.value)

def test_validate_uuid():
    """Test UUID validation"""
    # Test valid case
    test_uuid = uuid4()
    assert validate_uuid(str(test_uuid)) == test_uuid
    
    # Test invalid case
    with pytest.raises(ValidationError) as exc:
        validate_uuid("invalid-uuid")
    assert "Invalid UUID format" in str(exc.value)

def test_validate_string_length():
    """Test string length validation"""
    # Test valid cases
    assert validate_string_length("test", "field") == "test"
    assert validate_string_length("test", "field", min_length=2, max_length=10) == "test"
    
    # Test invalid cases
    with pytest.raises(ValidationError) as exc:
        validate_string_length("", "field", min_length=1)
    assert "Minimum length" in str(exc.value)
    
    with pytest.raises(ValidationError) as exc:
        validate_string_length("too long", "field", max_length=5)
    assert "Maximum length" in str(exc.value)

def test_validate_temperature():
    """Test temperature validation"""
    # Test valid cases
    assert validate_temperature(Decimal("20.00")) == Decimal("20.00")
    assert validate_temperature(Decimal("-20.50")) == Decimal("-20.50")
    assert validate_temperature(Decimal("0.00")) == Decimal("0.00")
    
    # Test invalid increment
    with pytest.raises(ValidationError) as exc:
        validate_temperature(Decimal("20.23"))
    assert "must be in increments of 0.5 degrees" in str(exc.value)
    
    # Test invalid format
    with pytest.raises(ValidationError) as exc:
        validate_temperature("invalid")
    assert "Invalid temperature value" in str(exc.value)

def test_validate_humidity():
    """Test humidity validation"""
    # Test valid cases
    assert validate_humidity(Decimal("50.00")) == Decimal("50.00")
    assert validate_humidity(Decimal("0.00")) == Decimal("0.00")
    assert validate_humidity(Decimal("100.00")) == Decimal("100.00")
    
    # Test non-whole number
    with pytest.raises(ValidationError) as exc:
        validate_humidity(Decimal("50.50"))
    assert "must be a whole number percentage" in str(exc.value)
    
    # Test invalid format
    with pytest.raises(ValidationError) as exc:
        validate_humidity("invalid")
    assert "Invalid humidity value" in str(exc.value) 