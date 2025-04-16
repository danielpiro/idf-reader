"""
Extracts and processes Schedule:Compact objects.
Uses DataLoader for potential future schedule caching.
"""
import re
from typing import Dict, List, Any, Optional, Tuple, TYPE_CHECKING, Union

# --- Helper Functions ---

def time_str_to_minutes(time_str: str) -> int:
    """Converts HH:MM time string to minutes since midnight."""
    try:
        hours, minutes = map(int, time_str.split(':'))
        # Handle 24:00 case specifically
        if hours == 24 and minutes == 0:
            return 24 * 60
        elif 0 <= hours < 24 and 0 <= minutes < 60:
             return hours * 60 + minutes
        else:
             raise ValueError("Time out of range")
    except ValueError:
        print(f"Warning: Could not parse time string: {time_str}. Defaulting to 0.")
        return 0

# --- End Helper Functions ---

# Forward reference for type hints
DataLoader = Union['DataLoader', None]

if TYPE_CHECKING:
    from utils.data_loader import DataLoader

# Basic schedule types to filter out
BASIC_TYPES = [
    "on", "off", "work efficiency", "opaqueshade",
    "zone comfort control type sched", "design days only",
    "typoperativetempcontrolsch", "onwinterdesignday",
    "onsummerdesignday", "sp", "setpoint"
]

class ScheduleExtractor:
    """
    Extracts Schedule:Compact objects, ignoring setpoint schedules 
    and grouping unique schedule patterns by type.
    """
    def __init__(self, data_loader: DataLoader = None):
        """
        Initialize ScheduleExtractor.
        
        Args:
            data_loader: DataLoader instance for accessing cached data
        """
        self.data_loader = data_loader
        # Store schedules by type, with unique value patterns
        self.schedules_by_type: Dict[str, Dict[Tuple, Dict[str, Any]]] = {}
        self.zone_schedules: List[str] = []
        

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

    def process_element(self, element_type: str, identifier: str,
                       data: List[str], current_zone_id: Optional[str] = None) -> None:
        """
        Processes a single element with enhanced filtering for basic types and setpoints.
        
        Args:
            element_type: 'comment' or 'object'
            identifier: The object keyword or eppy object type
            data: List of field values
            current_zone_id: The current zone context (ignored)
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

            # Filter out basic types
            if self._is_basic_type(schedule_type):
                return

            self._store_schedule(schedule_name, schedule_type, rule_fields)

    def process_eppy_schedule(self, schedule_obj) -> None:
        """
        Process a Schedule:Compact object from eppy directly.
        
        Args:
            schedule_obj: An eppy Schedule:Compact object
        """
        # Extract fields from eppy object
        data = [field for field in schedule_obj.fieldvalues]
        # Process using existing logic
        self.process_element('object', 'Schedule:Compact', data)

    def process_idf(self, idf) -> None:
        """
        Process all schedules from the IDF file, using cached data if available.
        
        Args:
            idf: eppy IDF object (kept for compatibility)
        """
        if not self.data_loader:
            return
            
        # Use cached schedules from DataLoader
        schedule_cache = self.data_loader.get_all_schedules_with_names()
        
        # Process each cached schedule
        for schedule_id, schedule_data in schedule_cache.items():
            schedule_type = schedule_data['type']
            
            # Filter out basic types
            if self._is_basic_type(schedule_type):
                continue
                
            # Use raw rules directly from cache
            name = schedule_id
            rule_fields = schedule_data['raw_rules']
            
            # Store using existing logic
            self._store_schedule(name, schedule_type, rule_fields)

    def _normalize_schedule_type(self, type_: str) -> str:
        """
        Normalize schedule type by removing:
        - Numeric parts
        - Time/zone prefixes (e.g. "02:01", "XX:XX")
        - Zone identifiers
        
        Args:
            type_: Original schedule type
            
        Returns:
            str: Normalized schedule type
        """
        # Split on space
        parts = type_.split()
        
        # Remove time/zone prefix patterns (e.g. "02:01", "XX:XX")
        parts = [part for part in parts if not (
            # Skip parts that look like time codes or zone prefixes
            ':' in part or
            part.isdigit() or
            # Skip parts that are all uppercase (likely zone identifiers)
            (part.isupper() and len(part) > 1)
        )]
        
        return ' '.join(parts).strip()

    def _expand_rules_to_hourly(self, time_value_pairs: List[Dict[str, str]]) -> List[Optional[str]]:
        """
        Expands a list of time-value pairs into a list of 24 hourly values.

        Args:
            time_value_pairs: List of {'end_time': 'HH:MM', 'value': str} dicts.

        Returns:
            A list of 24 strings representing the value for each hour (00:00-01:00 is index 0, ..., 23:00-24:00 is index 23).
            Returns list of Nones if input is empty or invalid.
        """
        if not time_value_pairs:
            return [None] * 24

        hourly_values = [None] * 24
        last_minute = 0

        for pair in time_value_pairs:
            end_time_str = pair['end_time']
            value = pair['value']
            current_minute = time_str_to_minutes(end_time_str)

            # Ensure minutes are within a day and handle 24:00 correctly
            current_minute = min(current_minute, 24 * 60)
            if current_minute == 0 and end_time_str != "00:00": # Likely parsing error or wrap-around, treat as 24:00
                 current_minute = 24*60


            if current_minute <= last_minute:
                # Skip zero/negative duration intervals, but log warning
                print(f"Warning: Skipping zero/negative duration interval ending at {end_time_str} (value: {value}). Last minute was {last_minute}.")
                continue # Don't update last_minute here, let the next valid interval handle it

            # Determine the hour indices affected by this interval
            # Start hour index is the ceiling of the last minute divided by 60
            start_hour_index = last_minute // 60
            # End hour index is the ceiling of the current minute divided by 60
            # Special case: 24:00 (1440 minutes) should affect up to index 23
            end_hour_index = (current_minute + 59) // 60 # Ceiling division
            
            # Clamp end_hour_index to be at most 24 (exclusive index for range)
            end_hour_index = min(end_hour_index, 24)


            # Fill the hourly values list
            for h in range(start_hour_index, end_hour_index):
                 if h < 24: # Ensure we don't write past index 23
                    hourly_values[h] = value

            last_minute = current_minute

            # If we reached the end of the day, stop processing further pairs for this block
            if last_minute >= 24 * 60:
                break
                
        # Fill any remaining None values with the value from the last interval if day wasn't completed
        if last_minute < 24 * 60 and time_value_pairs:
             last_value = time_value_pairs[-1]['value']
             start_fill_index = last_minute // 60
             for h in range(start_fill_index, 24):
                 if hourly_values[h] is None:
                     hourly_values[h] = last_value


        # Final check: if the first hour is None, use the last value (handles schedules starting after 00:00)
        if hourly_values[0] is None and time_value_pairs:
             first_val_minute = time_str_to_minutes(time_value_pairs[0]['end_time'])
             # If the first interval ends *after* the first hour, assume the value applies from hour 0
             if first_val_minute > 0:
                 hourly_values[0] = time_value_pairs[0]['value'] # Or potentially the *last* value of the day? Needs clarification. Using first value for now.
                 # Let's refine: Use the value defined for the *last* period of the day (wrap around)
                 # Find the value active at 24:00
                 final_value = None
                 temp_last_minute = 0
                 for pair in time_value_pairs:
                     temp_current_minute = time_str_to_minutes(pair['end_time'])
                     temp_current_minute = min(temp_current_minute, 24 * 60)
                     if temp_current_minute > temp_last_minute:
                         final_value = pair['value']
                         temp_last_minute = temp_current_minute
                     if temp_last_minute >= 24*60: break
                 if final_value is not None:
                     for h in range(first_val_minute // 60):
                         if hourly_values[h] is None:
                             hourly_values[h] = final_value


        # Fill any remaining Nones with a default (e.g., '0' or last known value) - let's use last known value
        last_known_value = '0' # Default fallback
        for i in range(len(hourly_values)):
            if hourly_values[i] is not None:
                last_known_value = hourly_values[i]
            elif hourly_values[i] is None:
                 hourly_values[i] = last_known_value
                 
        # Attempt to round numeric values to 2 decimal places
        formatted_hourly_values = []
        for val in hourly_values:
            try:
                # Try converting to float and rounding
                num_val = float(val)
                # Format to avoid unnecessary '.0' for integers
                if num_val == int(num_val):
                     formatted_hourly_values.append(str(int(num_val)))
                else:
                     formatted_hourly_values.append(f"{num_val:.2f}")
            except (ValueError, TypeError):
                # If conversion fails, keep the original string value
                formatted_hourly_values.append(str(val) if val is not None else '') # Ensure it's a string

        return formatted_hourly_values


    def _parse_compact_rule_blocks(self, rule_fields: List[str]) -> List[Dict[str, Any]]:
        """
        Parses Schedule:Compact rule fields into blocks, expanding time rules
        into hourly values for each block.

        Args:
            rule_fields: List of string values from the Schedule:Compact object.

        Returns:
            List of dictionaries, where each dict represents a rule block:
            {
                'through': str,
                'for_days': str,
                'hourly_values': List[str] (24 values)
            }
        """
        rule_blocks = []
        current_block_rules = []
        current_through = "Until: 31 Dec" # Default if not specified
        current_for = "AllDays"       # Default if not specified
        i = 0

        while i < len(rule_fields):
            field = rule_fields[i].strip()
            field_lower = field.lower()

            if field_lower.startswith("through:"):
                # If we encounter a new 'Through:', process the previous block
                if current_block_rules:
                    hourly_values = self._expand_rules_to_hourly(current_block_rules)
                    rule_blocks.append({
                        'through': current_through,
                        'for_days': current_for,
                        'hourly_values': hourly_values
                    })
                    current_block_rules = [] # Reset for next block

                current_through = field
                i += 1
            elif field_lower.startswith("for:"):
                 # Handle 'For:' similarly, assuming it follows 'Through:'
                 current_for = field
                 i += 1
            elif field_lower.startswith("until:"):
                if i + 1 < len(rule_fields):
                    time_match = re.search(r'(\d{1,2}:\d{2})', field)
                    if time_match:
                        end_time = time_match.group(1)
                        value = rule_fields[i+1].strip()
                        current_block_rules.append({'end_time': end_time, 'value': value})
                        i += 2 # Move past pair
                    else:
                        print(f"Warning: Invalid 'Until:' format found: '{field}'. Skipping field.")
                        i += 1 # Skip this field
                else:
                    # 'Until:' without a value following
                    print(f"Warning: 'Until:' found without a subsequent value: '{field}'. Skipping field.")
                    i += 1
            else:
                # Unknown field, skip it
                # print(f"Info: Skipping unrecognized field in schedule rules: '{field}'")
                i += 1

        # Process the last block after the loop finishes
        if current_block_rules:
            hourly_values = self._expand_rules_to_hourly(current_block_rules)
            rule_blocks.append({
                'through': current_through,
                'for_days': current_for,
                'hourly_values': hourly_values
            })

        return rule_blocks


    def _store_schedule(self, name: str, type_: str, rule_fields: List[str]) -> None:
        """
        Store a schedule with its rules.
        
        Args:
            name: Schedule name
            type_: Schedule type
            rule_fields: List of rule field values
        """
        # Convert rule fields to tuple for hashing/uniqueness check
        rule_tuple = tuple(rule_fields)
        
        # Normalize the schedule type
        normalized_type = self._normalize_schedule_type(type_)

        # Initialize dict for this normalized type if not seen before
        if normalized_type not in self.schedules_by_type:
            self.schedules_by_type[normalized_type] = {}

        # If this rule pattern hasn't been seen for this normalized type, store it
        if rule_tuple not in self.schedules_by_type[normalized_type]:
            schedule_data = {
                'name': name,
                'type': type_,
                'raw_rules': rule_fields, # Keep raw rules for reference if needed
                'rule_blocks': self._parse_compact_rule_blocks(rule_fields) # Add parsed hourly blocks
            }

            # If we have a DataLoader, store additional metadata
            if self.data_loader is not None:
                # Get zone that uses this schedule (if any)
                schedule_name_lower = name.lower()
                zones = self.data_loader.get_all_zones()
                for zone_id, zone_data in zones.items():
                    if zone_id.lower() in schedule_name_lower:
                        # Only store schedule if zone has HVAC
                            schedule_data['zone_id'] = zone_id
                            schedule_data['zone_type'] = zone_data.type
                            break
            
            self.schedules_by_type[normalized_type][rule_tuple] = schedule_data

    def get_parsed_unique_schedules(self) -> List[Dict[str, Any]]:
        """
        Returns unique schedule patterns, organized by type.
        
        Returns:
            list: List of dicts with format:
                {
                    'name': str, 
                    'type': str, 
                    'raw_rules': list,
                    'rule_blocks': list[dict], # Changed: now stores rule blocks with hourly values
                    'zone_id': Optional[str],
                    'zone_type': Optional[str]
                }
        """
        # Flatten the nested dictionaries into a list
        result = []
        for type_dict in self.schedules_by_type.values():
            result.extend(type_dict.values())
        return result
        
    def get_schedules_by_type(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Returns schedules organized by type.
        
        Returns:
            dict: Dictionary of schedules grouped by type
        """
        result = {}
        for type_, schedules in self.schedules_by_type.items():
            result[type_] = list(schedules.values())
        return result
        
    def get_zone_schedules(self, zone_id: str) -> List[Dict[str, Any]]:
        """
        Get all schedules associated with a specific zone.
        
        Args:
            zone_id: The zone identifier to filter by
            
        Returns:
            list: List of schedule data dictionaries
        """
        zone_schedules = []
        for type_dict in self.schedules_by_type.values():
            for schedule in type_dict.values():
                if schedule.get('zone_id') == zone_id:
                    zone_schedules.append(schedule)
        return zone_schedules