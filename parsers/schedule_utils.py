"""
Utility functions for schedule parsing to simplify complex time handling.
Extracted from schedule_parser.py to improve maintainability.
"""
from typing import List, Dict, Any, Optional
from utils.logging_config import get_logger

logger = get_logger(__name__)

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
            return 24 * 60
        
        # Clamp to valid range
        hours = max(0, min(23, hours))
        minutes = max(0, min(59, minutes))
        
        return hours * 60 + minutes
        
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
        return ['0'] * 24
    
    hourly_values = [None] * 24
    
    # Sort pairs by end time to ensure proper ordering
    sorted_pairs = sorted(time_value_pairs, key=lambda x: time_str_to_minutes(x['end_time']))
    
    current_minute = 0
    
    for pair in sorted_pairs:
        end_time_str = pair['end_time']
        value = pair['value']
        end_minute = time_str_to_minutes(end_time_str)
        
        # Handle 24:00 as end of day
        if end_minute == 0 and end_time_str == "24:00":
            end_minute = 24 * 60
        
        # Skip if end time is before current time (invalid sequence)
        if end_minute <= current_minute:
            continue
        
        # Fill hours from current time to end time
        start_hour = current_minute // 60
        end_hour = min(end_minute // 60, 24)
        
        for hour in range(start_hour, end_hour):
            if hour < 24:
                hourly_values[hour] = value
        
        current_minute = end_minute
        
        if current_minute >= 24 * 60:
            break
    
    # Fill any remaining None values with last known value or default
    fill_value = '0'
    if time_value_pairs:
        fill_value = time_value_pairs[-1]['value']
    
    for i in range(24):
        if hourly_values[i] is None:
            hourly_values[i] = fill_value
    
    # Format values consistently
    formatted_values = []
    for val in hourly_values:
        try:
            num_val = float(val)
            if num_val == int(num_val):
                formatted_values.append(str(int(num_val)))
            else:
                formatted_values.append(f"{num_val:.2f}")
        except (ValueError, TypeError):
            formatted_values.append(str(val) if val is not None else '0')
    
    return formatted_values

def parse_date_range(date_str: str) -> Dict[str, Any]:
    """
    Parse date range strings like "Through: 31 Dec" or "For: Weekdays".
    
    Args:
        date_str: Date range string
        
    Returns:
        Dictionary with parsed date information
    """
    date_str = date_str.strip().lower()
    
    # Month name mapping
    month_map = {
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
                if month_name in month_map:
                    result.update({
                        'type': 'through_date',
                        'end_month': month_map[month_name],
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
        'date_range': 'All Days',
        'day_types': ['All Days'],
        'hourly_values': ['0'] * 24,
        'time_value_pairs': []
    }

def normalize_schedule_value(value: Any) -> str:
    """Normalize schedule values to consistent string format."""
    if value is None:
        return '0'
    
    try:
        num_val = float(value)
        if num_val == int(num_val):
            return str(int(num_val))
        else:
            return f"{num_val:.2f}"
    except (ValueError, TypeError):
        return str(value)