"""
Utility functions for schedule parsing to simplify complex time handling.
Extracted from schedule_parser.py to improve maintainability.
"""
from typing import List, Dict, Any, Optional
from utils.logging_config import get_logger

logger = get_logger(__name__)

# Constants
MINUTES_PER_HOUR = 60
HOURS_PER_DAY = 24
MINUTES_PER_DAY = HOURS_PER_DAY * MINUTES_PER_HOUR
MAX_HOUR = 23
MAX_MINUTE = 59

# Month name mapping - shared with schedule_parser.py
MONTH_MAP = {
    'jan': 1, 'january': 1,
    'feb': 2, 'february': 2, 
    'mar': 3, 'march': 3,
    'apr': 4, 'april': 4,
    'may': 5,
    'jun': 6, 'june': 6,
    'jul': 7, 'july': 7,
    'aug': 8, 'august': 8,
    'sep': 9, 'september': 9, 'sept': 9,
    'oct': 10, 'october': 10,
    'nov': 11, 'november': 11,
    'dec': 12, 'december': 12
}

# Default schedule values
DEFAULT_SCHEDULE_VALUE = '0'
DEFAULT_DATE_RANGE = 'All Days'

def time_str_to_minutes(time_str: str) -> int:
    """
    Convert time string (HH:MM) to minutes since midnight.
    
    Args:
        time_str: Time in format "HH:MM" or "H:MM"
        
    Returns:
        Minutes since midnight (0-1440)
    """
    try:
        if ':' not in time_str:
            return 0
        
        parts = time_str.split(':')
        if len(parts) != 2:
            return 0
        
        hours = int(parts[0])
        minutes = int(parts[1])
        
        # Handle 24:00 as end of day
        if hours == 24 and minutes == 0:
            return MINUTES_PER_DAY
        
        # Clamp to valid range
        hours = max(0, min(MAX_HOUR, hours))
        minutes = max(0, min(MAX_MINUTE, minutes))
        
        return hours * MINUTES_PER_HOUR + minutes
        
    except (ValueError, TypeError):
        logger.warning(f"Invalid time format: {time_str}")
        return 0

def expand_time_value_pairs_to_hourly(time_value_pairs: List[Dict[str, str]]) -> List[str]:
    """
    Simplified version of time expansion logic.
    Converts time-value pairs to 24-hour array.
    
    Args:
        time_value_pairs: List of {'end_time': 'HH:MM', 'value': str} dicts
        
    Returns:
        List of 24 hourly values
    """
    if not time_value_pairs:
        return [DEFAULT_SCHEDULE_VALUE] * HOURS_PER_DAY
    
    hourly_values = [None] * HOURS_PER_DAY
    
    # Sort pairs by end time to ensure proper ordering
    sorted_pairs = sorted(time_value_pairs, key=lambda x: time_str_to_minutes(x['end_time']))
    
    current_minute = 0
    
    for pair in sorted_pairs:
        end_time_str = pair['end_time']
        value = pair['value']
        end_minute = time_str_to_minutes(end_time_str)
        
        # Handle 24:00 as end of day
        if end_minute == 0 and end_time_str == "24:00":
            end_minute = MINUTES_PER_DAY
        
        # Skip if end time is before current time (invalid sequence)
        if end_minute <= current_minute:
            continue
        
        # Fill hours from current time to end time
        start_hour, end_hour = _calculate_hour_range(current_minute, end_minute)
        
        for hour in range(start_hour, end_hour):
            if hour < HOURS_PER_DAY:
                hourly_values[hour] = value
        
        current_minute = end_minute
        
        if current_minute >= MINUTES_PER_DAY:
            break
    
    # Fill any remaining None values and format consistently
    fill_value = _get_fill_value(time_value_pairs)
    return _format_hourly_values(hourly_values, fill_value)

def parse_date_range(date_str: str) -> Dict[str, Any]:
    """
    Parse date range strings like "Through: 31 Dec" or "For: Weekdays".
    
    Args:
        date_str: Date range string
        
    Returns:
        Dictionary with parsed date information
    """
    date_str = date_str.strip().lower()
    
    # Use global constant for month mapping
    
    # Default result
    result = {
        'type': 'unknown',
        'start_month': 1,
        'start_day': 1,
        'end_month': 12,
        'end_day': 31,
        'days_of_week': 'all'
    }
    
    if 'through:' in date_str:
        # Handle "Through: 31 Dec" format
        date_part = date_str.replace('through:', '').strip()
        parts = date_part.split()
        
        if len(parts) >= 2:
            try:
                day = int(parts[0])
                month_name = parts[1].lower()
                if month_name in MONTH_MAP:
                    result.update({
                        'type': 'through_date',
                        'end_month': MONTH_MAP[month_name],
                        'end_day': day
                    })
            except (ValueError, IndexError):
                pass
    
    elif 'for:' in date_str:
        # Handle "For: Weekdays" format
        day_part = date_str.replace('for:', '').strip()
        result.update({
            'type': 'day_type',
            'days_of_week': day_part
        })
    
    return result

def create_default_schedule_block() -> Dict[str, Any]:
    """Create a default schedule block with standard structure."""
    return {
        'date_range': DEFAULT_DATE_RANGE,
        'day_types': [DEFAULT_DATE_RANGE],
        'hourly_values': [DEFAULT_SCHEDULE_VALUE] * HOURS_PER_DAY,
        'time_value_pairs': []
    }

def normalize_schedule_value(value: Any) -> str:
    """Normalize schedule values to consistent string format."""
    if value is None:
        return DEFAULT_SCHEDULE_VALUE
    
    try:
        num_val = float(value)
        if num_val == int(num_val):
            return str(int(num_val))
        else:
            return f"{num_val:.2f}"
    except (ValueError, TypeError):
        return str(value)

def _calculate_hour_range(current_minute: int, end_minute: int) -> tuple[int, int]:
    """
    Calculate start and end hour range for time period.
    
    Args:
        current_minute: Starting minute of day
        end_minute: Ending minute of day
        
    Returns:
        Tuple of (start_hour, end_hour)
    """
    start_hour = current_minute // MINUTES_PER_HOUR
    end_hour = min(end_minute // MINUTES_PER_HOUR, HOURS_PER_DAY)
    return start_hour, end_hour

def _get_fill_value(time_value_pairs: List[Dict[str, str]]) -> str:
    """
    Get appropriate fill value for missing schedule hours.
    
    Args:
        time_value_pairs: List of time-value pair dictionaries
        
    Returns:
        Fill value to use for empty slots
    """
    if time_value_pairs:
        return time_value_pairs[-1]['value']
    return DEFAULT_SCHEDULE_VALUE

def _format_hourly_values(hourly_values: List[Optional[str]], fill_value: str) -> List[str]:
    """
    Format hourly values with consistent numeric formatting.
    
    Args:
        hourly_values: List of hourly values (may contain None)
        fill_value: Value to use for None entries
        
    Returns:
        List of formatted hourly values
    """
    formatted_values = []
    
    for i in range(HOURS_PER_DAY):
        val = hourly_values[i] if i < len(hourly_values) else None
        if val is None:
            val = fill_value
        
        formatted_val = normalize_schedule_value(val)
        formatted_values.append(formatted_val)
    
    return formatted_values

def validate_time_format(time_str: str) -> bool:
    """
    Validate that time string is in correct HH:MM format.
    
    Args:
        time_str: Time string to validate
        
    Returns:
        True if valid format, False otherwise
    """
    if not time_str or ':' not in time_str:
        return False
    
    parts = time_str.split(':')
    if len(parts) != 2:
        return False
    
    try:
        hours = int(parts[0])
        minutes = int(parts[1])
        return (0 <= hours <= 24) and (0 <= minutes <= MAX_MINUTE)
    except ValueError:
        return False