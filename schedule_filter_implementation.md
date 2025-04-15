# Schedule Filter Implementation Plan

## Overview

Enhance the schedule parser to filter out basic schedule types and heating/cooling setpoint schedules while maintaining unique rule tuple functionality.

## Implementation Details

### 1. Constants Enhancement

Add new constants for filtering:

```python
# Basic schedule types to filter out
BASIC_TYPES = [
    "on", "off", "work efficiency", "opaque shade",
    "zone comfort control type sched", "design days only",
    "typoperativetempcontrolsch", "onwinterdesignday",
    "onsummerdesignday"
]

# Enhanced setpoint pattern detection
SETPOINT_PATTERNS = {
    "prefixes": ["heating", "cooling"],
    "suffixes": ["sp", "setpoint"]
}
```

### 2. New Helper Methods

Add two new methods to ScheduleExtractor:

```python
def _is_basic_type(self, schedule_type: str) -> bool:
    """
    Check if schedule is a basic type that should be filtered out.

    Args:
        schedule_type: The schedule type to check

    Returns:
        bool: True if schedule should be filtered out
    """
    return any(basic_type.lower() in schedule_type.lower()
              for basic_type in BASIC_TYPES)

def _is_setpoint_schedule(self, schedule_name: str, schedule_type: str) -> bool:
    """
    Enhanced check for setpoint schedules.

    Args:
        schedule_name: Name of the schedule
        schedule_type: Type of the schedule

    Returns:
        bool: True if schedule is a setpoint schedule
    """
    name_type = f"{schedule_name} {schedule_type}".lower()

    # Check for heating/cooling setpoint combinations
    return any(prefix in name_type and suffix in name_type
              for prefix in SETPOINT_PATTERNS["prefixes"]
              for suffix in SETPOINT_PATTERNS["suffixes"])
```

### 3. Process Element Updates

Modify the process_element method to use new filters:

```python
def process_element(self, element_type: str, identifier: str,
                   data: List[str], current_zone_id: Optional[str] = None) -> None:
    """
    Process schedule elements with enhanced filtering.
    """
    if element_type == 'comment':
        return

    elif element_type == 'object' and identifier == 'Schedule:Compact':
        if not data or len(data) < 2:
            return

        try:
            schedule_name = data[0]
            schedule_type = data[1]
            rule_fields = data[2:]
        except IndexError:
            print(f"Warning: Could not parse name/type/rules for Schedule:Compact. Fields: {data}")
            return

        # Apply enhanced filtering
        if (self._is_basic_type(schedule_type) or
            self._is_setpoint_schedule(schedule_name, schedule_type)):
            return

        self._store_schedule(schedule_name, schedule_type, rule_fields)
```

### 4. Testing Plan

Test cases to verify implementation:

1. Basic Type Filtering:

   - Test with each basic type in BASIC_TYPES
   - Verify they are filtered out
   - Test with variations in capitalization

2. Setpoint Schedule Filtering:

   - Test heating/cooling setpoint combinations
   - Test with variations in naming patterns
   - Verify all setpoint schedules are filtered

3. Rule Tuple Uniqueness:
   - Test multiple schedules with same rules
   - Verify only unique rule patterns are kept
   - Check preserved schedule has correct metadata

## Next Steps

1. Switch to Code mode
2. Implement changes in schedule_parser.py
3. Add test cases
4. Verify functionality against example IDF files

## Expected Outcome

The enhanced schedule parser will:

- Filter out all basic schedule types
- Filter out heating/cooling setpoint schedules
- Maintain unique rule tuple functionality
- Preserve existing zone tracking features
