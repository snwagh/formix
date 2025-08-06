# src/formix/utils/helpers.py
import json
import random
import string
from datetime import datetime
from typing import Any


def generate_uid(prefix: str = "") -> str:
    """Generate a unique identifier."""
    chars = string.ascii_uppercase + string.digits
    suffix = ''.join(random.choices(chars, k=8))
    return f"{prefix}{suffix}" if prefix else suffix


def validate_json_schema(schema_str: str) -> dict[str, Any]:
    """Validate and parse JSON schema."""
    try:
        schema = json.loads(schema_str)
        # For PoC, ensure it's a single number schema
        if schema.get("type") != "number":
            raise ValueError("Schema must define a single number type")
        return schema
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")


def timestamp_to_datetime(timestamp: str) -> datetime:
    """Convert ISO timestamp to datetime object."""
    return datetime.fromisoformat(timestamp.replace('Z', '+00:00'))


def format_duration(seconds: int) -> str:
    """Format duration in seconds to human-readable string."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}m {secs}s"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"

