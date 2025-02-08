class WarehouseServiceError(Exception):
    """Base exception for warehouse service errors."""
    pass

class ItemNotFoundError(WarehouseServiceError):
    """Exception raised when an item is not found in the database."""
    def __init__(self, item_type: str, item_id: str):
        self.item_type = item_type
        self.item_id = item_id
        super().__init__(f"{item_type} {item_id} not found")

class ValidationError(WarehouseServiceError):
    """Exception raised when validation fails."""
    pass

class DatabaseError(WarehouseServiceError):
    """Exception raised when a database operation fails."""
    pass

class CapacityError(WarehouseServiceError):
    """Exception raised when warehouse or room capacity is exceeded."""
    pass

class StatusTransitionError(WarehouseServiceError):
    """Exception raised when an invalid status transition is attempted."""
    pass 