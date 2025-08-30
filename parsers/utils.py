"""
Shared utilities for parser modules to reduce code duplication and improve maintainability.
"""
from typing import Union, Optional, Dict, Any, List
from functools import wraps
import re
from utils.logging_config import get_logger

logger = get_logger(__name__)

def safe_float(value: Union[str, int, float, None], default: float = 0.0) -> float:
    """
    Safely convert a value to float with a default fallback.
    Consolidates multiple implementations across parsers.
    
    Args:
        value: Value to convert to float
        default: Default value if conversion fails
        
    Returns:
        float: Converted value or default
    """
    try:
        if value is None:
            return default
        return float(value)
    except (ValueError, TypeError):
        return default

def safe_int(value: Union[str, int, float, None], default: int = 0) -> int:
    """
    Safely convert a value to int with a default fallback.
    
    Args:
        value: Value to convert to int
        default: Default value if conversion fails
        
    Returns:
        int: Converted value or default
    """
    try:
        if value is None:
            return default
        return int(float(value))  # Handle string floats like "1.0"
    except (ValueError, TypeError):
        return default

def extract_zone_id_parts(zone_id: str, iso_type: str = None) -> Dict[str, str]:
    """
    Extract standard parts from zone ID using simplified grouping logic.
    
    Simplified rules:
    - For office ISO: no grouping, all fields return zone_id or parts
    - For 2017/2023: only zones with ':' and 'X' or '_' get grouped
    - All other zones remain individual
    
    Args:
        zone_id: Zone identifier string
        iso_type: ISO type to determine grouping behavior
        
    Returns:
        Dict with extracted parts: floor, floor_id, zone_name, base_zone_id, original
    """
    if not zone_id or not isinstance(zone_id, str):
        return {"floor": "-", "floor_id": "-", "zone_name": "-", "base_zone_id": "-", "original": zone_id}
    
    # Check if this is office ISO - if so, no grouping needed
    is_office_iso = iso_type and isinstance(iso_type, str) and 'office' in iso_type.lower()
    if is_office_iso:
        # For office ISO: no grouping, return zone parts without grouping logic
        if ":" in zone_id:
            parts = zone_id.split(":", 1)
            floor = parts[0] if len(parts) >= 2 else zone_id
            zone_part = parts[1] if len(parts) >= 2 else ""
            return {
                "floor": floor,
                "floor_id": zone_id,  # Use full zone_id for office
                "zone_name": zone_part,
                "base_zone_id": zone_id,
                "original": zone_id
            }
        else:
            return {
                "floor": zone_id,
                "floor_id": zone_id,
                "zone_name": "",
                "base_zone_id": zone_id,
                "original": zone_id
            }
    
    # For 2017/2023: apply simplified grouping logic
    if ":" in zone_id:
        parts = zone_id.split(":", 1)
        if len(parts) >= 2:
            floor = parts[0]
            zone_part = parts[1]
            
            # Check if after ':' contains 'X' or '_'
            if 'X' in zone_part:
                separator_index = zone_part.find('X')
                floor_id = zone_part[:separator_index]  # B part
                zone_name = zone_part[separator_index+1:]  # C part
                base_zone_id = f"{floor}:{floor_id}" if floor_id else zone_id
            elif '_' in zone_part:
                separator_index = zone_part.find('_')
                floor_id = zone_part[:separator_index]  # B part
                zone_name = zone_part[separator_index+1:]  # C part
                base_zone_id = f"{floor}:{floor_id}" if floor_id else zone_id
            else:
                # A:B pattern - no grouping
                floor_id = zone_part
                zone_name = ""
                base_zone_id = zone_id
            
            return {
                "floor": floor,
                "floor_id": floor_id,
                "zone_name": zone_name,
                "base_zone_id": base_zone_id,
                "original": zone_id
            }
    
    # A pattern - individual zone
    return {
        "floor": zone_id[:2] if len(zone_id) >= 2 else zone_id,
        "floor_id": zone_id,
        "zone_name": "",
        "base_zone_id": zone_id,
        "original": zone_id
    }

def validate_required_fields(data: Dict[str, Any], required_fields: List[str]) -> List[str]:
    """
    Validate that required fields are present and not None/empty.
    
    Args:
        data: Dictionary to validate
        required_fields: List of required field names
        
    Returns:
        List of missing or invalid field names
    """
    missing_fields = []
    for field in required_fields:
        if field not in data or data[field] is None or data[field] == "":
            missing_fields.append(field)
    return missing_fields

def clean_construction_name(name: str) -> str:
    """
    Clean construction names by removing common suffixes and normalizing.
    Consolidates construction name cleaning logic.
    
    Args:
        name: Construction name to clean
        
    Returns:
        Cleaned construction name
    """
    if not name:
        return name
    
    # Remove common suffixes
    suffixes_to_remove = ["_rev", "_reverse", "_R"]
    cleaned = name
    for suffix in suffixes_to_remove:
        if cleaned.endswith(suffix):
            cleaned = cleaned[:-len(suffix)]
            break
    
    return cleaned.strip()

def parse_numeric_field(obj, field_name: str, default: float = 0.0) -> float:
    """
    Extract numeric field from object with safe conversion.
    Common pattern across many parsers.
    
    Args:
        obj: Object to extract field from
        field_name: Name of field to extract
        default: Default value if extraction fails
        
    Returns:
        Extracted numeric value or default
    """
    try:
        if hasattr(obj, field_name):
            value = getattr(obj, field_name, default)
            return safe_float(value, default)
        return default
    except (AttributeError, TypeError):
        return default

def log_processing_stats(parser_name: str, processed_count: int, total_count: int, errors: int = 0):
    """
    Standard logging format for parser processing statistics.
    
    Args:
        parser_name: Name of the parser
        processed_count: Number of items successfully processed
        total_count: Total number of items attempted
        errors: Number of errors encountered
    """
    success_rate = (processed_count / total_count * 100) if total_count > 0 else 0
    logger.info(f"{parser_name}: Processed {processed_count}/{total_count} items "
                f"({success_rate:.1f}% success rate)" + 
                (f", {errors} errors" if errors > 0 else ""))

def handle_parser_errors(parser_name: str):
    """
    Decorator to standardize error handling across parsers.
    
    Args:
        parser_name: Name of parser for logging context
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except FileNotFoundError as e:
                logger.error(f"{parser_name}: File not found - {e}")
                return None
            except (ValueError, TypeError) as e:
                logger.error(f"{parser_name}: Data validation error - {e}")
                return None
            except Exception as e:
                logger.error(f"{parser_name}: Unexpected error - {e}", exc_info=True)
                return None
        return wrapper
    return decorator


def normalize_surface_type(surface_type: str) -> str:
    """
    Normalize surface type strings to consistent format.
    
    Args:
        surface_type: Raw surface type string
        
    Returns:
        Normalized surface type
    """
    if not surface_type:
        return "-"
    
    surface_type_lower = surface_type.lower().strip()
    
    # Common normalizations
    type_mappings = {
        "wall": "Wall",
        "floor": "Floor", 
        "ceiling": "Ceiling",
        "roof": "Roof",
        "window": "Window",
        "door": "Door"
    }
    
    for key, normalized in type_mappings.items():
        if key in surface_type_lower:
            return normalized
    
    # Capitalize first letter as fallback
    return surface_type.capitalize()

def extract_field_by_pattern(obj, pattern: str, field_prefix: str = "") -> Dict[str, Any]:
    """
    Extract fields from object using regex pattern.
    Common pattern for extracting numbered fields.
    
    Args:
        obj: Object to extract fields from
        pattern: Regex pattern to match field names
        field_prefix: Optional prefix for extracted field names
        
    Returns:
        Dictionary of extracted fields
    """
    extracted = {}
    if not hasattr(obj, '__dict__'):
        return extracted
    
    pattern_re = re.compile(pattern)
    for attr_name in dir(obj):
        if pattern_re.match(attr_name):
            try:
                value = getattr(obj, attr_name)
                key = f"{field_prefix}{attr_name}" if field_prefix else attr_name
                extracted[key] = value
            except AttributeError:
                continue
    
    return extracted