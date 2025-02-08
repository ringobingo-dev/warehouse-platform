from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, field_validator, ValidationInfo
from decimal import Decimal
import json
from enum import Enum
from .validation import (
    validate_decimal,
    validate_dimensions,
    validate_phone_number,
    validate_email,
    validate_capacity,
    validate_string_length,
    validate_temperature,
    validate_humidity,
    ValidationError
)

class RoomStatus(str, Enum):
    ACTIVE = "active"
    MAINTENANCE = "maintenance"
    DECOMMISSIONED = "decommissioned"

class VerificationStatus(str, Enum):
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"

class BaseDBModel(BaseModel):
    class Config:
        from_orm = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
            Decimal: lambda v: str(v)
        }

class RoomDimensions(BaseModel):
    length: Decimal
    width: Decimal
    height: Decimal

    @field_validator('length', 'width', 'height')
    @classmethod
    def validate_dimensions(cls, v: Decimal, info: ValidationInfo) -> Decimal:
        try:
            return validate_decimal(v, info.field_name, min_value=Decimal('0.01'))
        except ValidationError as e:
            raise ValueError(str(e))

class RoomBase(BaseDBModel):
    name: str = Field(..., min_length=1, max_length=100)
    capacity: Decimal = Field(..., gt=0)
    temperature: Decimal = Field(..., ge=-30, le=50)
    humidity: Decimal = Field(..., ge=0, le=100)
    dimensions: RoomDimensions
    warehouse_id: UUID

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str, info: ValidationInfo) -> str:
        try:
            return validate_string_length(v, "name", max_length=100)
        except ValidationError as e:
            raise ValueError(str(e))

    @field_validator('capacity')
    @classmethod
    def validate_room_capacity(cls, v: Decimal, info: ValidationInfo) -> Decimal:
        try:
            return validate_decimal(v, "capacity", min_value=Decimal('0.01'))
        except ValidationError as e:
            raise ValueError(str(e))

    @field_validator('temperature')
    @classmethod
    def validate_room_temperature(cls, v: Decimal, info: ValidationInfo) -> Decimal:
        try:
            return validate_temperature(v)
        except ValidationError as e:
            raise ValueError(str(e))

    @field_validator('humidity')
    @classmethod
    def validate_room_humidity(cls, v: Decimal, info: ValidationInfo) -> Decimal:
        try:
            return validate_humidity(v)
        except ValidationError as e:
            raise ValueError(str(e))

class RoomCreate(RoomBase):
    status: RoomStatus = Field(default=RoomStatus.ACTIVE)

class RoomResponse(RoomBase):
    id: UUID
    status: RoomStatus
    available_capacity: Decimal = Field(..., ge=0)
    created_at: datetime
    updated_at: datetime

    @property
    def room_id(self) -> UUID:
        return self.id

    @field_validator('available_capacity')
    @classmethod
    def validate_available_capacity(cls, v: Decimal, info: ValidationInfo) -> Decimal:
        try:
            return validate_decimal(v, "available_capacity", min_value=Decimal('0'))
        except ValidationError as e:
            raise ValueError(str(e))

class RoomUpdate(BaseDBModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    capacity: Optional[Decimal] = Field(None, gt=0)
    temperature: Optional[Decimal] = Field(None, ge=-30, le=50)
    humidity: Optional[Decimal] = Field(None, ge=0, le=100)
    dimensions: Optional[RoomDimensions] = None

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: Optional[str], info: ValidationInfo) -> Optional[str]:
        if v is not None:
            try:
                return validate_string_length(v, "name", max_length=100)
            except ValidationError as e:
                raise ValueError(str(e))
        return v

    @field_validator('capacity', 'temperature', 'humidity')
    @classmethod
    def validate_decimal_fields(cls, v: Optional[Decimal], info: ValidationInfo) -> Optional[Decimal]:
        if v is not None:
            try:
                if info.field_name == 'capacity':
                    return validate_decimal(v, info.field_name, min_value=Decimal('0.01'))
                elif info.field_name == 'temperature':
                    return validate_temperature(v)
                elif info.field_name == 'humidity':
                    return validate_humidity(v)
            except ValidationError as e:
                raise ValueError(str(e))
        return v

class WarehouseBase(BaseDBModel):
    name: str = Field(..., min_length=1, max_length=100)
    address: str = Field(..., min_length=1, max_length=200)
    total_capacity: Decimal = Field(..., gt=0)
    customer_id: UUID

    @field_validator('name', 'address')
    @classmethod
    def validate_string_fields(cls, v: str, info: ValidationInfo) -> str:
        try:
            max_length = 200 if info.field_name == 'address' else 100
            return validate_string_length(v, info.field_name, max_length=max_length)
        except ValidationError as e:
            raise ValueError(str(e))

    @field_validator('total_capacity')
    @classmethod
    def validate_warehouse_capacity(cls, v: Decimal, info: ValidationInfo) -> Decimal:
        try:
            return validate_decimal(v, "total_capacity", min_value=Decimal('0.01'))
        except ValidationError as e:
            raise ValueError(str(e))

class WarehouseCreate(WarehouseBase):
    rooms: List[RoomCreate] = Field(default_factory=list)

class WarehouseResponse(WarehouseBase):
    id: UUID
    rooms: List[RoomResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    available_capacity: Decimal

    @property
    def warehouse_id(self) -> UUID:
        return self.id

class WarehouseUpdate(BaseDBModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    address: Optional[str] = Field(None, min_length=1, max_length=200)
    total_capacity: Optional[Decimal] = Field(None, gt=0)

    @field_validator('name', 'address')
    @classmethod
    def validate_string_fields(cls, v: Optional[str], info: ValidationInfo) -> Optional[str]:
        if v is not None:
            try:
                max_length = 200 if info.field_name == 'address' else 100
                return validate_string_length(v, info.field_name, max_length=max_length)
            except ValidationError as e:
                raise ValueError(str(e))
        return v

    @field_validator('total_capacity')
    @classmethod
    def validate_warehouse_capacity(cls, v: Optional[Decimal], info: ValidationInfo) -> Optional[Decimal]:
        if v is not None:
            try:
                return validate_decimal(v, "total_capacity", min_value=Decimal('0.01'))
            except ValidationError as e:
                raise ValueError(str(e))
        return v

# Customer Models
class CustomerBase(BaseDBModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    phone_number: str = Field(..., min_length=10, max_length=15)
    address: str = Field(..., min_length=5, max_length=200)

    @field_validator('name', 'address')
    @classmethod
    def validate_string_fields(cls, v: str, info: ValidationInfo) -> str:
        try:
            min_length = 5 if info.field_name == 'address' else 1
            max_length = 200 if info.field_name == 'address' else 100
            return validate_string_length(v, info.field_name, min_length=min_length, max_length=max_length)
        except ValidationError as e:
            raise ValueError(str(e))

    @field_validator('email')
    @classmethod
    def validate_customer_email(cls, v: str, info: ValidationInfo) -> str:
        try:
            return validate_email(v)
        except ValidationError as e:
            raise ValueError(str(e))

    @field_validator('phone_number')
    @classmethod
    def validate_customer_phone(cls, v: str, info: ValidationInfo) -> str:
        try:
            return validate_phone_number(v)
        except ValidationError as e:
            raise ValueError(str(e))

class CustomerCreate(CustomerBase):
    pass

class CustomerUpdate(BaseDBModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = Field(None, min_length=10, max_length=15)
    address: Optional[str] = Field(None, min_length=5, max_length=200)

    @field_validator('name', 'address')
    @classmethod
    def validate_string_fields(cls, v: Optional[str], info: ValidationInfo) -> Optional[str]:
        if v is not None:
            try:
                min_length = 5 if info.field_name == 'address' else 1
                max_length = 200 if info.field_name == 'address' else 100
                return validate_string_length(v, info.field_name, min_length=min_length, max_length=max_length)
            except ValidationError as e:
                raise ValueError(str(e))
        return v

    @field_validator('email')
    @classmethod
    def validate_customer_email(cls, v: Optional[str], info: ValidationInfo) -> Optional[str]:
        if v is not None:
            try:
                return validate_email(v)
            except ValidationError as e:
                raise ValueError(str(e))
        return v

    @field_validator('phone_number')
    @classmethod
    def validate_customer_phone(cls, v: Optional[str], info: ValidationInfo) -> Optional[str]:
        if v is not None:
            try:
                return validate_phone_number(v)
            except ValidationError as e:
                raise ValueError(str(e))
        return v

class CustomerResponse(CustomerBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    verification_status: VerificationStatus = Field(default=VerificationStatus.PENDING)

    @property
    def customer_id(self) -> UUID:
        return self.id

# Inventory Models
class InventoryBase(BaseDBModel):
    sku: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    quantity: Decimal = Field(..., ge=0)
    unit: str = Field(..., min_length=1, max_length=20)
    room_id: UUID
    warehouse_id: UUID

    @field_validator('sku', 'name', 'unit')
    @classmethod
    def validate_string_fields(cls, v: str, info: ValidationInfo) -> str:
        try:
            max_length = 50 if info.field_name == 'sku' else 100 if info.field_name == 'name' else 20
            return validate_string_length(v, info.field_name, max_length=max_length)
        except ValidationError as e:
            raise ValueError(str(e))

    @field_validator('description')
    @classmethod
    def validate_description(cls, v: Optional[str], info: ValidationInfo) -> Optional[str]:
        if v is not None:
            try:
                return validate_string_length(v, "description", max_length=500)
            except ValidationError as e:
                raise ValueError(str(e))
        return v

    @field_validator('quantity')
    @classmethod
    def validate_quantity(cls, v: Decimal, info: ValidationInfo) -> Decimal:
        try:
            return validate_decimal(v, "quantity", min_value=Decimal('0'))
        except ValidationError as e:
            raise ValueError(str(e))

class InventoryCreate(InventoryBase):
    pass

class InventoryResponse(InventoryBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    transfer_history: Optional[List[dict]] = Field(default_factory=list)

    @property
    def inventory_id(self) -> UUID:
        return self.id

class InventoryUpdate(BaseDBModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    quantity: Optional[Decimal] = Field(None, ge=0)
    unit: Optional[str] = Field(None, min_length=1, max_length=20)
    room_id: Optional[UUID] = None
    transfer_history: Optional[List[dict]] = None

    @field_validator('name', 'unit')
    @classmethod
    def validate_string_fields(cls, v: Optional[str], info: ValidationInfo) -> Optional[str]:
        if v is not None:
            try:
                max_length = 100 if info.field_name == 'name' else 20
                return validate_string_length(v, info.field_name, max_length=max_length)
            except ValidationError as e:
                raise ValueError(str(e))
        return v

    @field_validator('description')
    @classmethod
    def validate_description(cls, v: Optional[str], info: ValidationInfo) -> Optional[str]:
        if v is not None:
            try:
                return validate_string_length(v, "description", max_length=500)
            except ValidationError as e:
                raise ValueError(str(e))
        return v

    @field_validator('quantity')
    @classmethod
    def validate_quantity(cls, v: Optional[Decimal], info: ValidationInfo) -> Optional[Decimal]:
        if v is not None:
            try:
                return validate_decimal(v, "quantity", min_value=Decimal('0'))
            except ValidationError as e:
                raise ValueError(str(e))
        return v

# Common Response Models
class ErrorResponse(BaseModel):
    detail: str

class SuccessResponse(BaseModel):
    message: str

class PaginatedResponse(BaseModel):
    items: List[BaseDBModel]
    total: int
    page: int
    size: int
    pages: int

    @field_validator('items')
    @classmethod
    def validate_items(cls, v: List[BaseDBModel], info: ValidationInfo) -> List[BaseDBModel]:
        if not v:
            return []
        return v
