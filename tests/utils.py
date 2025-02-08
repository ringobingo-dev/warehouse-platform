from decimal import Decimal
import json
from datetime import datetime, timezone
from uuid import UUID
from typing import Any

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, UUID):
            return str(obj)
        return super().default(obj)

def json_dumps(obj: Any) -> str:
    """Serialize object to JSON string with custom encoder."""
    return json.dumps(obj, cls=CustomJSONEncoder)

def serialize_model(obj: Any) -> Any:
    """Convert Pydantic model or dict to JSON-serializable format."""
    if hasattr(obj, 'model_dump'):
        return obj.model_dump()
    if isinstance(obj, dict):
        return {k: serialize_model(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [serialize_model(item) for item in obj]
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (datetime, UUID)):
        return str(obj)
    return obj
