import boto3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TypeVar, Generic
from botocore.exceptions import ClientError
from pydantic import BaseModel
from decimal import Decimal
from uuid import UUID, uuid4
from boto3.dynamodb.conditions import Key

from .config import get_settings
from .models import CustomerCreate, CustomerResponse, WarehouseCreate, WarehouseResponse, RoomBase, RoomStatus, RoomCreate, RoomResponse, RoomUpdate, InventoryCreate, InventoryResponse, InventoryUpdate

settings = get_settings()

T = TypeVar('T', bound=BaseModel)
R = TypeVar('R', bound=BaseModel)

class DatabaseError(Exception):
    """Base exception for database operations."""
    pass

class ItemNotFoundError(DatabaseError):
    """Raised when an item is not found in the database."""
    def __init__(self, message: str):
        super().__init__(message)

class ValidationError(DatabaseError):
    """Raised when validation fails for database operations."""
    pass

class ConflictError(DatabaseError):
    """Raised when there's a conflict in database operations."""
    pass

class CapacityError(DatabaseError):
    """Raised when warehouse capacity is exceeded."""
    pass

class BaseDB(Generic[T, R]):
    """Base class for database operations."""
    
    def __init__(self, table_name: str):
        settings = get_settings()
        self.dynamodb = boto3.resource(
            'dynamodb',
            endpoint_url=settings.DYNAMODB_ENDPOINT_URL,
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
        )
        self.table = self.dynamodb.Table(table_name)

    def _format_item(self, item_dict: dict) -> dict:
        """Format item for DynamoDB, converting Pydantic models to dicts and handling Decimals."""
        if hasattr(item_dict, 'model_dump'):
            item_dict = item_dict.model_dump()
        
        # Generate ID if not present
        if 'id' not in item_dict:
            item_dict['id'] = str(uuid4())
        
        # Convert all numeric values to Decimal
        formatted_dict = {}
        for key, value in item_dict.items():
            if isinstance(value, (int, float)):
                formatted_dict[key] = Decimal(str(value))
            elif isinstance(value, dict):
                formatted_dict[key] = self._format_item(value)
            elif isinstance(value, list):
                formatted_dict[key] = [self._format_item(i) if isinstance(i, dict) else i for i in value]
            else:
                formatted_dict[key] = value
        
        return formatted_dict

    def _convert_to_response(self, item: dict) -> R:
        """Convert a DynamoDB item to a response model."""
        converted_item = {}
        for key, value in item.items():
            if isinstance(value, Decimal):
                # Try to convert to int first if it's a whole number
                if value % 1 == 0:
                    converted_item[key] = int(value)
                else:
                    converted_item[key] = float(value)
            elif isinstance(value, dict):
                converted_item[key] = self._convert_decimal_to_number(value)
            elif isinstance(value, list):
                converted_item[key] = [
                    self._convert_decimal_to_number(i) if isinstance(i, dict) else i 
                    for i in value
                ]
            else:
                converted_item[key] = value
        return self.response_model(**converted_item)

    def _convert_decimal_to_number(self, d: dict) -> dict:
        """Helper method to convert Decimal to number in nested dictionaries."""
        result = {}
        for key, value in d.items():
            if isinstance(value, Decimal):
                if value % 1 == 0:
                    result[key] = int(value)
                else:
                    result[key] = float(value)
            elif isinstance(value, dict):
                result[key] = self._convert_decimal_to_number(value)
            elif isinstance(value, list):
                result[key] = [
                    self._convert_decimal_to_number(i) if isinstance(i, dict) else i 
                    for i in value
                ]
            else:
                result[key] = value
        return result

    async def create_item(self, item: T) -> R:
        """Create a new item in the database."""
        try:
            timestamp = datetime.now(timezone.utc).isoformat()
            item_dict = item.model_dump()
            item_dict.update({
                'id': str(uuid4()),
                'created_at': timestamp,
                'updated_at': timestamp
            })
            formatted_item = self._format_item(item_dict)
            
            try:
                self.table.put_item(
                    Item=formatted_item,
                    ConditionExpression='attribute_not_exists(id)'
                )
                return self._convert_to_response(formatted_item)
            except ClientError as e:
                if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                    raise ConflictError("Item already exists")
                raise DatabaseError(f"Failed to create item: {str(e)}")
        except Exception as e:
            if isinstance(e, (ConflictError, ValidationError, ItemNotFoundError, DatabaseError)):
                raise
            raise DatabaseError(f"Failed to create item: {str(e)}")

    async def get_item(self, id: str) -> R:
        """Get an item by its ID."""
        try:
            response = self.table.get_item(Key={'id': id})
            if 'Item' not in response:
                raise ItemNotFoundError(f"Item with id {id} not found")
            return self._convert_to_response(response['Item'])
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                raise ItemNotFoundError(f"Item with id {id} not found")
            raise DatabaseError(f"Failed to get item: {str(e)}")
        except Exception as e:
            if isinstance(e, (ItemNotFoundError, DatabaseError)):
                raise
            raise DatabaseError(f"Failed to get item: {str(e)}")

    async def update_item(self, id: str, item: T) -> R:
        """Update an item in the database."""
        try:
            # First check if item exists
            existing_item = await self.get_item(id)
            
            item_dict = item.model_dump(exclude_unset=True)
            update_expr = []
            expr_attr_values = {}
            expr_attr_names = {}
            
            # Always update updated_at timestamp
            timestamp = datetime.now(timezone.utc).isoformat()
            update_expr.append("#updated_at = :updated_at")
            expr_attr_names["#updated_at"] = "updated_at"
            expr_attr_values[":updated_at"] = timestamp
            
            for key, value in item_dict.items():
                if value is not None:
                    update_expr.append(f"#{key} = :{key}")
                    expr_attr_names[f"#{key}"] = key
                    if isinstance(value, (int, float)):
                        expr_attr_values[f":{key}"] = Decimal(str(value))
                    else:
                        expr_attr_values[f":{key}"] = value
            
            response = self.table.update_item(
                Key={'id': id},
                UpdateExpression="SET " + ", ".join(update_expr),
                ExpressionAttributeNames=expr_attr_names,
                ExpressionAttributeValues=expr_attr_values,
                ReturnValues="ALL_NEW"
            )
            return self._convert_to_response(response['Attributes'])
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                raise ItemNotFoundError(f"Item with id {id} not found")
            elif e.response['Error']['Code'] == 'ValidationException':
                raise ValidationError(str(e))
            raise DatabaseError(f"Failed to update item: {str(e)}")
        except Exception as e:
            if isinstance(e, (ItemNotFoundError, ValidationError, DatabaseError)):
                raise
            raise DatabaseError(f"Failed to update item: {str(e)}")

    async def delete_item(self, id: str) -> None:
        """Delete an item by its ID."""
        try:
            # First check if item exists
            await self.get_item(id)
            
            self.table.delete_item(
                Key={'id': id},
                ConditionExpression='attribute_exists(id)'
            )
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                raise ItemNotFoundError(f"Item with id {id} not found")
            raise DatabaseError(f"Failed to delete item: {str(e)}")
        except Exception as e:
            if isinstance(e, (ItemNotFoundError, DatabaseError)):
                raise
            raise DatabaseError(f"Failed to delete item: {str(e)}")

    async def list_items(self, skip: int = 0, limit: int = 10) -> List[R]:
        """List items with pagination."""
        try:
            response = self.table.scan(
                Limit=limit
            )
            items = response.get('Items', [])
            return [self._convert_to_response(item) for item in items[skip:skip + limit]]
        except ClientError as e:
            raise DatabaseError(f"Failed to list items: {str(e)}")
        except Exception as e:
            if isinstance(e, DatabaseError):
                raise
            raise DatabaseError(f"Failed to list items: {str(e)}")

class CustomerDB(BaseDB[CustomerCreate, CustomerResponse]):
    """Customer-specific database operations."""
    
    def __init__(self):
        settings = get_settings()
        super().__init__(settings.CUSTOMERS_TABLE)
        self.response_model = CustomerResponse
    
    async def get_by_email(self, email: str) -> CustomerResponse:
        """Get a customer by email using GSI."""
        try:
            response = self.table.query(
                IndexName='email-index',
                KeyConditionExpression='email = :email',
                ExpressionAttributeValues={':email': email}
            )
            if not response['Items']:
                raise ItemNotFoundError(f"Customer with email {email} not found")
            return self._convert_to_response(response['Items'][0])
        except ClientError as e:
            raise DatabaseError(f"Failed to get customer by email: {str(e)}")

class WarehouseDB(BaseDB[WarehouseCreate, WarehouseResponse]):
    """DynamoDB service for warehouse management."""
    
    def __init__(self):
        super().__init__(settings.WAREHOUSES_TABLE)
        self.customers_table = self.dynamodb.Table(settings.CUSTOMERS_TABLE)
        self.response_model = WarehouseResponse

    async def create_item(self, warehouse_data: WarehouseCreate) -> WarehouseResponse:
        """Create a new warehouse."""
        try:
            # Verify customer exists
            customer_response = self.customers_table.get_item(
                Key={'id': str(warehouse_data.customer_id)}
            )
            if 'Item' not in customer_response:
                raise ItemNotFoundError("Customer", warehouse_data.customer_id)

            warehouse_id = str(uuid.uuid4())
            warehouse_dict = warehouse_data.model_dump()
            warehouse_dict['id'] = warehouse_id
            warehouse_dict['created_at'] = datetime.now(timezone.utc).isoformat()
            warehouse_dict['updated_at'] = datetime.now(timezone.utc).isoformat()
            warehouse_dict['rooms'] = []
            warehouse_dict['inventory'] = []

            # Create initial rooms if provided
            for room in warehouse_data.rooms:
                room_dict = room.model_dump()
                room_dict['id'] = str(uuid.uuid4())
                room_dict['warehouse_id'] = warehouse_id
                room_dict['created_at'] = warehouse_dict['created_at']
                room_dict['updated_at'] = warehouse_dict['updated_at']
                room_dict['current_utilization'] = 0.0
                room_dict['status'] = RoomStatus.ACTIVE
                warehouse_dict['rooms'].append(room_dict)

            self.table.put_item(
                Item=warehouse_dict,
                ConditionExpression='attribute_not_exists(id)'
            )
            return WarehouseResponse(**warehouse_dict)
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                raise ConflictError("Warehouse", warehouse_id)
            raise DatabaseError(f"Failed to create warehouse: {str(e)}")

    async def list_by_customer(self, customer_id: str) -> List[WarehouseResponse]:
        """List warehouses for a specific customer."""
        try:
            response = self.table.query(
                IndexName='customer-id-index',
                KeyConditionExpression='customer_id = :customer_id',
                ExpressionAttributeValues={':customer_id': customer_id}
            )
            return [WarehouseResponse(**item) for item in response['Items']]
        except ClientError as e:
            raise DatabaseError(f"Failed to list warehouses: {str(e)}")

    async def get_warehouse(self, warehouse_id: str) -> WarehouseResponse:
        """Get a warehouse by ID."""
        try:
            response = self.table.get_item(
                Key={'id': str(warehouse_id)}
            )
            if 'Item' not in response:
                raise ItemNotFoundError("Warehouse", warehouse_id)
            return WarehouseResponse(**response['Item'])
        except ClientError as e:
            raise DatabaseError(f"Failed to get warehouse: {str(e)}")

    async def update_warehouse(self, warehouse_id: str, update_data: Dict[str, Any]) -> WarehouseResponse:
        """Update warehouse details."""
        try:
            if not update_data:
                raise ValidationError("No fields to update")

            update_dict = {k: v for k, v in update_data.items() if v is not None}
            if not update_dict:
                raise ValidationError("No valid fields to update")

            update_dict['updated_at'] = datetime.now(timezone.utc).isoformat()
            
            update_expr = []
            expr_names = {}
            expr_values = {}
            
            for key, value in update_dict.items():
                update_expr.append(f"#{key} = :{key}")
                expr_names[f"#{key}"] = key
                expr_values[f":{key}"] = value

            response = self.table.update_item(
                Key={'id': str(warehouse_id)},
                UpdateExpression=f"SET {', '.join(update_expr)}",
                ExpressionAttributeNames=expr_names,
                ExpressionAttributeValues=expr_values,
                ReturnValues="ALL_NEW",
                ConditionExpression='attribute_exists(id)'
            )
            
            return WarehouseResponse(**response['Attributes'])
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                raise ItemNotFoundError("Warehouse", warehouse_id)
            raise DatabaseError(f"Failed to update warehouse: {str(e)}")

    async def delete_warehouse(self, warehouse_id: str) -> None:
        """Delete a warehouse."""
        try:
            self.table.delete_item(
                Key={'id': str(warehouse_id)},
                ConditionExpression='attribute_exists(id)'
            )
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                raise ItemNotFoundError("Warehouse", warehouse_id)
            raise DatabaseError(f"Failed to delete warehouse: {str(e)}")

    async def list_warehouses(self, customer_id: Optional[str] = None) -> List[WarehouseResponse]:
        """List all warehouses, optionally filtered by customer."""
        try:
            if customer_id:
                response = self.table.query(
                    IndexName='customer-id-index',
                    KeyConditionExpression='customer_id = :customer_id',
                    ExpressionAttributeValues={':customer_id': str(customer_id)}
                )
            else:
                response = self.table.scan()
            
            return [WarehouseResponse(**item) for item in response.get('Items', [])]
        except ClientError as e:
            raise DatabaseError(f"Failed to list warehouses: {str(e)}")

    async def calculate_warehouse_utilization(self, warehouse_id: str) -> Dict[str, Decimal]:
        """Calculate warehouse utilization metrics."""
        try:
            warehouse = await self.get_warehouse(warehouse_id)
            total_capacity = sum(
                Decimal(str(room['max_weight_capacity']))
                for room in warehouse.rooms
                if room['status'] == RoomStatus.ACTIVE
            )
            used_capacity = sum(
                Decimal(str(item['quantity']))
                for item in warehouse.inventory
            )
            utilization = (used_capacity / total_capacity * Decimal('100')) if total_capacity > 0 else Decimal('0')
            
            return {
                'total_capacity': total_capacity,
                'used_capacity': used_capacity,
                'utilization_percentage': utilization,
                'available_capacity': total_capacity - used_capacity
            }
        except ClientError as e:
            raise DatabaseError(f"Failed to calculate utilization: {str(e)}")

    async def get_by_customer(self, customer_id: str) -> List[WarehouseResponse]:
        """Get all warehouses for a customer."""
        try:
            response = self.table.query(
                IndexName='customer-id-index',
                KeyConditionExpression='customer_id = :customer_id',
                ExpressionAttributeValues={':customer_id': str(customer_id)}
            )
            return [WarehouseResponse(**item) for item in response.get('Items', [])]
        except ClientError as e:
            raise DatabaseError(f"Failed to get warehouses by customer: {str(e)}")
    
    async def check_availability(self, warehouse_id: str) -> Dict[str, Any]:
        """Check warehouse availability and capacity."""
        try:
            warehouse = await self.get_warehouse(warehouse_id)
            total_capacity = sum(room.max_weight_capacity for room in warehouse.rooms if room.status == RoomStatus.ACTIVE)
            used_capacity = sum(
                item['quantity']
                for item in warehouse.inventory
            )
            available = total_capacity > used_capacity
            return {
                'available': available,
                'total_capacity': total_capacity,
                'used_capacity': used_capacity,
                'available_capacity': total_capacity - used_capacity
            }
        except ClientError as e:
            raise DatabaseError(f"Failed to check availability: {str(e)}")

    async def create_room(self, warehouse_id: str, room_data: RoomBase) -> dict:
        """Create a new room in a warehouse."""
        try:
            warehouse = await self.get_warehouse(warehouse_id)
            room_dict = room_data.model_dump()
            room_dict['id'] = str(uuid.uuid4())
            room_dict['warehouse_id'] = warehouse_id
            room_dict['created_at'] = datetime.utcnow().isoformat()
            room_dict['updated_at'] = datetime.utcnow().isoformat()
            room_dict['current_utilization'] = 0.0
            room_dict['status'] = RoomStatus.ACTIVE

            rooms = warehouse.rooms
            rooms.append(room_dict)
            await self.update_warehouse(warehouse_id, {'rooms': rooms})
            return room_dict
        except ClientError as e:
            raise DatabaseError(f"Failed to create room: {str(e)}")

    async def get_rooms(self, warehouse_id: str) -> List[dict]:
        """Get all rooms in a warehouse."""
        try:
            warehouse = await self.get_warehouse(warehouse_id)
            return warehouse.rooms
        except ClientError as e:
            raise DatabaseError(f"Failed to get rooms: {str(e)}")

    async def add_inventory(self, warehouse_id: str, inventory_data: dict) -> dict:
        """Add inventory to a warehouse."""
        try:
            warehouse = await self.get_warehouse(warehouse_id)
            availability = await self.check_availability(warehouse_id)
            
            if inventory_data.get('quantity', 0) > availability['available_capacity']:
                raise CapacityError(f"Insufficient capacity. Available: {availability['available_capacity']}, Requested: {inventory_data.get('quantity')}")
            
            inventory_id = str(uuid.uuid4())
            inventory = {
                'id': inventory_id,
                'warehouse_id': warehouse_id,
                'product_id': inventory_data.get('product_id'),
                'quantity': inventory_data.get('quantity'),
                'unit': inventory_data.get('unit'),
                'created_at': datetime.now(timezone.utc).isoformat(),
                'updated_at': datetime.now(timezone.utc).isoformat()
            }

            inventory_items = warehouse.inventory
            inventory_items.append(inventory)
            await self.update_warehouse(warehouse_id, {'inventory': inventory_items})
            return inventory
        except ClientError as e:
            raise DatabaseError(f"Failed to add inventory: {str(e)}")

    async def get_inventory(self, warehouse_id: str) -> List[dict]:
        """Get all inventory in a warehouse."""
        try:
            warehouse = await self.get_warehouse(warehouse_id)
            return warehouse.inventory
        except ClientError as e:
            raise DatabaseError(f"Failed to get inventory: {str(e)}")

    async def create_customer(self, customer_data: CustomerCreate) -> dict:
        """Create a new customer."""
        try:
            customer_dict = customer_data.model_dump()
            customer_dict['id'] = str(uuid.uuid4())
            customer_dict['created_at'] = datetime.utcnow().isoformat()
            customer_dict['updated_at'] = datetime.utcnow().isoformat()
            await self.create_item(customer_dict)
            return customer_dict
        except ClientError as e:
            raise DatabaseError(f"Failed to create customer: {str(e)}")

    async def verify_customer(self, customer_id: str, verification_data: dict) -> dict:
        """Verify a customer."""
        try:
            verification_data['verified_at'] = datetime.utcnow().isoformat()
            return await self.update_item(customer_id, verification_data)
        except ClientError as e:
            raise DatabaseError(f"Failed to verify customer: {str(e)}")

class RoomDB(BaseDB[RoomCreate, RoomResponse]):
    """Room-specific database operations."""
    
    def __init__(self):
        settings = get_settings()
        super().__init__(settings.ROOMS_TABLE)
        self.response_model = RoomResponse
    
    async def create_room(self, room: RoomCreate) -> RoomResponse:
        """Create a new room."""
        try:
            # Add status if not provided
            if not hasattr(room, 'status'):
                room.status = RoomStatus.AVAILABLE
            
            # Add timestamps
            timestamp = datetime.now(timezone.utc).isoformat()
            room_dict = room.model_dump()
            room_dict.update({
                'id': str(uuid4()),
                'created_at': timestamp,
                'updated_at': timestamp
            })
            
            formatted_room = self._format_item(room_dict)
            
            try:
                self.table.put_item(
                    Item=formatted_room,
                    ConditionExpression='attribute_not_exists(id)'
                )
                return self._convert_to_response(formatted_room)
            except ClientError as e:
                if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                    raise ConflictError("Room already exists")
                raise DatabaseError(f"Failed to create room: {str(e)}")
        except Exception as e:
            if isinstance(e, (ConflictError, ValidationError, ItemNotFoundError, DatabaseError)):
                raise
            raise DatabaseError(f"Failed to create room: {str(e)}")

    async def get_room(self, room_id: str) -> RoomResponse:
        """Get a room by its ID."""
        return await self.get_item(room_id)

    async def update_room(self, room_id: str, update_data: RoomUpdate) -> RoomResponse:
        """Update a room."""
        return await self.update_item(room_id, update_data)

    async def delete_room(self, room_id: str) -> None:
        """Delete a room."""
        await self.delete_item(room_id)

    async def list_rooms(self, warehouse_id: Optional[str] = None) -> List[RoomResponse]:
        """List rooms, optionally filtered by warehouse ID."""
        try:
            if warehouse_id:
                response = self.table.query(
                    IndexName='warehouse_id-index',
                    KeyConditionExpression=Key('warehouse_id').eq(warehouse_id)
                )
            else:
                response = self.table.scan()
            
            items = response.get('Items', [])
            return [self._convert_to_response(item) for item in items]
        except ClientError as e:
            raise DatabaseError(f"Failed to list rooms: {str(e)}")
        except Exception as e:
            if isinstance(e, DatabaseError):
                raise
            raise DatabaseError(f"Failed to list rooms: {str(e)}")

    async def get_room_conditions(self, room_id: str) -> Dict[str, Any]:
        """Get current conditions of a room."""
        room = await self.get_room(room_id)
        return {
            "temperature": room.temperature,
            "humidity": room.humidity,
            "status": room.status
        }

class InventoryDB(BaseDB[InventoryCreate, InventoryResponse]):
    """Inventory-specific database operations."""
    
    def __init__(self):
        settings = get_settings()
        super().__init__(settings.INVENTORY_TABLE)
        self.response_model = InventoryResponse
    
    async def create_inventory(self, inventory: InventoryCreate) -> InventoryResponse:
        """Create a new inventory item."""
        try:
            # Add timestamps
            timestamp = datetime.now(timezone.utc).isoformat()
            inventory_dict = inventory.model_dump()
            inventory_dict.update({
                'id': str(uuid4()),
                'created_at': timestamp,
                'updated_at': timestamp
            })
            
            formatted_inventory = self._format_item(inventory_dict)
            
            try:
                self.table.put_item(
                    Item=formatted_inventory,
                    ConditionExpression='attribute_not_exists(id)'
                )
                return self._convert_to_response(formatted_inventory)
            except ClientError as e:
                if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                    raise ConflictError("Inventory item already exists")
                raise DatabaseError(f"Failed to create inventory: {str(e)}")
        except Exception as e:
            if isinstance(e, (ConflictError, ValidationError, ItemNotFoundError, DatabaseError)):
                raise
            raise DatabaseError(f"Failed to create inventory: {str(e)}")

    async def get_inventory(self, inventory_id: str) -> InventoryResponse:
        """Get an inventory item by its ID."""
        return await self.get_item(inventory_id)

    async def update_inventory(self, inventory_id: str, update_data: InventoryUpdate) -> InventoryResponse:
        """Update an inventory item."""
        return await self.update_item(inventory_id, update_data)

    async def delete_inventory(self, inventory_id: str) -> None:
        """Delete an inventory item."""
        await self.delete_item(inventory_id)

    async def transfer_inventory(self, inventory_id: str, transfer_data: dict) -> InventoryResponse:
        """Transfer inventory from one room to another."""
        try:
            inventory = await self.get_inventory(inventory_id)
            
            # Update the room_id and add transfer record
            update_data = InventoryUpdate(
                room_id=transfer_data['target_room_id'],
                transfer_history=[{
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'from_room_id': inventory.room_id,
                    'to_room_id': transfer_data['target_room_id'],
                    'quantity': inventory.quantity
                }]
            )
            
            return await self.update_inventory(inventory_id, update_data)
        except Exception as e:
            if isinstance(e, (ItemNotFoundError, ValidationError, DatabaseError)):
                raise
            raise DatabaseError(f"Failed to transfer inventory: {str(e)}")

    async def get_inventory_history(self, inventory_id: str) -> List[dict]:
        """Get transfer history of an inventory item."""
        inventory = await self.get_inventory(inventory_id)
        return inventory.transfer_history if hasattr(inventory, 'transfer_history') else []

    async def search_inventory(
        self,
        sku: Optional[str] = None,
        warehouse_id: Optional[UUID] = None
    ) -> List[InventoryResponse]:
        """Search inventory items by SKU and/or warehouse ID."""
        try:
            filter_expression = None
            expression_values = {}
            
            if sku:
                filter_expression = Key('sku').eq(sku)
            
            if warehouse_id:
                warehouse_filter = Key('warehouse_id').eq(str(warehouse_id))
                filter_expression = warehouse_filter if not filter_expression else filter_expression & warehouse_filter
            
            if filter_expression:
                response = self.table.query(
                    IndexName='sku-warehouse_id-index',
                    KeyConditionExpression=filter_expression
                )
            else:
                response = self.table.scan()
            
            items = response.get('Items', [])
            return [self._convert_to_response(item) for item in items]
        except ClientError as e:
            raise DatabaseError(f"Failed to search inventory: {str(e)}")
        except Exception as e:
            if isinstance(e, DatabaseError):
                raise
            raise DatabaseError(f"Failed to search inventory: {str(e)}")

