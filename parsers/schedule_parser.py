"""
Extracts and processes Schedule:Compact objects.
Uses DataLoader for cached access to IDF data.
"""
import re
from typing import Dict, List, Any, Optional, Tuple
from utils.data_loader import DataLoader
from utils.data_models import ScheduleData

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

# Basic schedule types to filter out
BASIC_TYPES = [
    "on", "off", "work efficiency", "opaqueshade",
    "zone comfort control type sched", "design days only",
    "typoperativetempcontrolsch", "onwinterdesignday",
    "onsummerdesignday", "heating setpoint schedule", "cooling sp sch"
]

class ScheduleExtractor:
    """
    Extracts Schedule:Compact objects, ignoring setpoint schedules 
    and grouping unique schedule patterns by type.
    """
    def __init__(self, data_loader: Optional[DataLoader] = None):
        """
        Initialize ScheduleExtractor.
        
        Args:
            data_loader: DataLoader instance for accessing cached data
        """
        self.data_loader = data_loader
        # Store schedules by type, with unique value patterns
        self.schedules_by_type: Dict[str, Dict[Tuple, Dict[str, Any]]] = {}
        self.zone_schedules: List[str] = []
        self.processed_schedules: Dict[str, ScheduleData] = {}
        

    def _is_basic_type(self, schedule_type: str) -> bool:
        """
        Check if schedule is a basic type that should be filtered out.
        Handles schedule types that may have a zone prefix (e.g., "00:01XLIVING Heating Setpoint Schedule").
        
        Args:
            schedule_type: The schedule type to check
            
        Returns:
            bool: True if schedule should be filtered out
        """
        # Regex to match potential zone prefixes like "00:01X " or "00:00LIVING ".
        # It looks for "HH:MM" possibly followed by one or more capital letters/digits (for zone name part), then a space.
        # Example Prefixes: "00:01X ", "PERIMETER_ZN_1 "
        # More general approach: split by space, if first part matches a zone-like pattern, remove it.
        # However, a direct regex substitution is cleaner if the prefix pattern is consistent.
        
        # Attempt to remove a zone-like prefix.
        # This pattern matches "XX:XX" followed by any non-whitespace characters and a space.
        # Or common words like "OFFICE", "LIVING" etc. followed by a space.
        # A more robust way is to check if the first word is a zone identifier.
        # The existing _extract_zone_id_from_schedule uses `schedule_id.split()` and checks the first part.
        # Let's adapt a similar logic or a regex.
        
        # Regex to find a prefix like "word " where word does not contain "schedule" or "type" or "sched"
        # and is typically a zone identifier.
        # A simpler regex for common prefixes: "HH:MM[OptionalLetter(s)] "
        zone_prefix_pattern = r'^\d{2}:\d{2}[A-Z\d]*\s+' # Matches "00:00XLIVING " or "01:23Z1 "
        
        # Remove the prefix if it exists to get the actual schedule type name
        actual_schedule_type_name = re.sub(zone_prefix_pattern, '', schedule_type, count=1)

        # If the above didn't strip (e.g. "LIVING Cooling SP Sch"), try another common pattern
        # This is tricky because "Work Efficiency" is a basic type.
        # For now, we rely on the HH:MMX pattern. If other prefixes are common, this might need adjustment.

        # Perform case-insensitive exact match on the (potentially stripped) schedule type name
        return any(basic_type.lower() == actual_schedule_type_name.lower()
                  for basic_type in BASIC_TYPES)

    def _standardize_date_format(self, date_string: str) -> str:
        """
        Parse various date formats and standardize to DD/MM format.
        Handles formats like:
        - 31 Dec, 31 December -> 31/12
        - 31 March -> 31/03
        - 12/31 -> 31/12
        - 4/1 -> 01/04
        - 30 November -> 30/11

        Args:
            date_string: Original date string

        Returns:
            Standardized date string in DD/MM format
        """
        # Clean the input string - remove "Through:" prefix if present
        date_string = date_string.strip()
        if date_string.lower().startswith("through:"):
            date_string = date_string[8:].strip().lower()
            
        # Month name to number mapping (both full and abbreviated)
        month_names = {
            "jan": 1, "january": 1,
            "feb": 2, "february": 2,
            "mar": 3, "march": 3,
            "apr": 4, "april": 4,
            "may": 5,
            "jun": 6, "june": 6,
            "jul": 7, "july": 7,
            "aug": 8, "august": 8,
            "sep": 9, "september": 9,
            "oct": 10, "october": 10,
            "nov": 11, "november": 11,
            "dec": 12, "december": 12
        }
        
        # Try to match "DD Month" pattern (like "31 Dec" or "31 March")
        pattern1 = re.search(r'(\d{1,2})\s+([a-zA-Z]+)', date_string, re.IGNORECASE)
        if pattern1:
            day = int(pattern1.group(1))
            month_name = pattern1.group(2).lower()
            # Try to match the month name
            for name, num in month_names.items():
                if month_name.startswith(name):
                    return f"{day:02d}/{num:02d}"  # Format as DD/MM
        
        # Try to match "MM/DD" or "DD/MM" pattern
        pattern2 = re.search(r'(\d{1,2})/(\d{1,2})', date_string)
        if pattern2:
            first = int(pattern2.group(1))
            second = int(pattern2.group(2))
            
            # If first number is clearly a month (1-12) and second is >12, it's MM/DD
            if 1 <= first <= 12 and second > 12:
                return f"{second:02d}/{first:02d}"  # Convert MM/DD to DD/MM
            
            # If second number is clearly a month (1-12) and first is >12, it's DD/MM
            elif 1 <= second <= 12 and first > 12:
                return f"{first:02d}/{second:02d}"  # Already DD/MM format
            
            # If both could be either day or month, assume MM/DD format as it's more common in IDF files
            elif 1 <= first <= 12 and 1 <= second <= 12:
                return f"{second:02d}/{first:02d}"  # Convert MM/DD to DD/MM
        
        # If we couldn't parse it, try to make it look like DD/MM format
        # This is a fallback to at least make it look consistent
        if date_string.isdigit():
            # If it's just a number (like "31"), assume it's a day and add "/12" (December)
            return f"{int(date_string):02d}/12"
            
        # Last resort - return original with a consistent format marker
        return f"{date_string} -> ??/??"  # Add marker to show it couldn't be parsed

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
        Process all schedules from the IDF file, using cached data.
        Implementation details moved from DataLoader.
        
        Args:
            idf: eppy IDF object (kept for compatibility)
        """
        if not self.data_loader:
            print("Warning: ScheduleExtractor requires a DataLoader instance for efficient processing")
            return
            
        # Get cached schedule data
        schedule_cache = self.data_loader.get_schedules()
        
        # Process each cached schedule
        for schedule_id, schedule_data in schedule_cache.items():
            schedule_type = schedule_data['type']
            
                
            # Get schedule rules from cache
            rule_fields = self.data_loader.get_schedule_rules(schedule_id)
            
            # Process schedule
            self._store_schedule(schedule_id, schedule_type, rule_fields)
            
            # Create ScheduleData objects for other parsers to use
            self._create_schedule_data(schedule_id, schedule_type, rule_fields)

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

        # Post-processing: Adjust for "one hour before" rule
        # Iterate from the second hour onwards (index 1)
        processed_values = list(hourly_values) # Create a copy to modify
        for h in range(1, 24):
            # If the value at hour 'h' is different from the previous hour 'h-1'
            if hourly_values[h] != hourly_values[h-1]:
                # Apply the value of hour 'h' to the previous hour 'h-1'
                processed_values[h-1] = hourly_values[h]

        # Handle wrap-around change from hour 23 to hour 0
        if hourly_values[0] != hourly_values[23]:
             processed_values[23] = hourly_values[0] # Apply hour 0's value to hour 23

        # Attempt to round numeric values to 2 decimal places using the processed values
        formatted_hourly_values = []
        for val in processed_values: # Use the adjusted list
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
                'through': str, # Date in standardized DD/MM format
                'for_days': str,
                'hourly_values': List[str] (24 values)
            }
        """
        rule_blocks = []
        current_block_rules = []
        current_through = "31/12"  # Default if not specified, standardized format
        current_for = "AllDays"   # Default if not specified
        i = 0

        while i < len(rule_fields):
            field = rule_fields[i].strip()
            field_lower = field.lower()

            if field_lower.startswith("through:"):
                # If we encounter a new 'Through:', process the previous block
                if current_block_rules:
                    hourly_values = self._expand_rules_to_hourly(current_block_rules)
                    rule_blocks.append({
                        'through': current_through, # Standardized date format
                        'for_days': current_for,
                        'hourly_values': hourly_values
                    })
                    current_block_rules = [] # Reset for next block

                # Extract the date part from the Through field and standardize it
                current_through = self._standardize_date_format(field)
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
                # Info: Skipping unrecognized field in schedule rules: '{field}'
                i += 1

        # Process the last block after the loop finishes
        if current_block_rules:
            hourly_values = self._expand_rules_to_hourly(current_block_rules)
            rule_blocks.append({
                'through': current_through, # Standardized date format
                'for_days': current_for,
                'hourly_values': hourly_values
            })

        return rule_blocks

    def _extract_zone_id_from_schedule(self, schedule_id: str) -> Optional[str]:
        """
        Extract zone ID from schedule identifier for HVAC schedules.
        Implementation moved from DataLoader.
        
        Args:
            schedule_id: Schedule identifier
            
        Returns:
            Optional[str]: Zone ID if found, None otherwise
        """
        schedule_lower = schedule_id.lower()
        if 'heating' in schedule_lower or 'cooling' in schedule_lower:
            # Split on spaces and take first part as zone ID
            parts = schedule_id.split()
            if parts:
                return parts[0]  # Returns e.g. '00:01XLIVING' from '00:01XLIVING Heating Setpoint Schedule'
        return None

    def _create_schedule_data(self, name: str, type_: str, rule_fields: List[str]) -> None:
        """
        Create ScheduleData object for use by other parsers.
        Implementation moved from DataLoader.
        
        Args:
            name: Schedule name
            type_: Schedule type
            rule_fields: List of rule field values
        """
        # Extract zone ID for HVAC schedules
        zone_id = self._extract_zone_id_from_schedule(name)
        zone_type = None
        
        # Get zone type if zone ID is found
        if zone_id and self.data_loader:
            zones = self.data_loader.get_zones()
            # Find matching zone
            for zone_name in zones:
                if zone_id.lower() in zone_name.lower():
                    zone_type = self.data_loader.get_zone_type(zone_name)
                    break
        
        # Create and store ScheduleData
        self.processed_schedules[name] = ScheduleData(
            id=name,
            name=name,
            type=type_,
            raw_rules=rule_fields,
            zone_id=zone_id,
            zone_type=zone_type
        )

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
        normalized_type = ' '.join(part for part in type_.split() if not (
            ':' in part or
            part.isdigit() or
            (part.isupper() and len(part) > 1)
        )).strip()

        # Initialize dict for this normalized type if not seen before
        if normalized_type not in self.schedules_by_type:
            self.schedules_by_type[normalized_type] = {}

        # If this rule pattern hasn't been seen for this normalized type, store it
        if rule_tuple not in self.schedules_by_type[normalized_type]:
            # Extract zone ID if possible
            zone_id = self._extract_zone_id_from_schedule(name)
            zone_type = None
            
            # Get zone type if zone ID is found
            if zone_id and self.data_loader:
                zones = self.data_loader.get_zones()
                # Find matching zone
                for zone_name in zones:
                    if zone_id.lower() in zone_name.lower():
                        zone_type = self.data_loader.get_zone_type(zone_name)
                        break
            
            schedule_data = {
                'name': name,
                'type': type_,
                'raw_rules': rule_fields,
                'rule_blocks': self._parse_compact_rule_blocks(rule_fields),
                'zone_id': zone_id,
                'zone_type': zone_type
            }
            
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
                    'rule_blocks': list[dict],
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
    
    def get_all_schedules(self) -> Dict[str, ScheduleData]:
        """
        Get all processed schedules.
        Implementation moved from DataLoader.
        
        Returns:
            Dict[str, ScheduleData]: Dictionary of all processed schedules
        """
        return self.processed_schedules
    
    def get_schedule_by_id(self, schedule_id: str) -> Optional[ScheduleData]:
        """
        Get a specific schedule by ID.
        Implementation moved from DataLoader.
        
        Args:
            schedule_id: ID of the schedule to retrieve
            
        Returns:
            Optional[ScheduleData]: Schedule data if found, None otherwise
        """
        return self.processed_schedules.get(schedule_id)
    
    def format_schedule_name(self, schedule_id: str) -> str:
        """
        Format schedule name for better readability.
        Implementation moved from DataLoader.
        
        Args:
            schedule_id: The original schedule identifier
            
        Returns:
            str: Formatted schedule name
        """
        # Convert IDs like "00:01XLIVING Heating Setpoint Schedule" to "Living Heating Setpoint"
        name = schedule_id
        
        # Remove common suffixes
        for suffix in [' Schedule', ' Sch', '_schedule', '_sch']:
            if name.lower().endswith(suffix.lower()):
                name = name[:-len(suffix)]
                
        # Handle zone identifier formats (e.g., "00:01X")
        zone_pattern = re.search(r'(\d{2}:\d{2}[A-Z]?)', name)
        if zone_pattern:
            # Extract the rest of the name after the zone pattern
            remaining = name[zone_pattern.end():].strip()
            if remaining:
                name = remaining
                
        # Convert camelCase or snake_case to Title Case with spaces
        name = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)  # camelCase to spaces
        name = name.replace('_', ' ')  # snake_case to spaces
        
        # Title case the result
        name = ' '.join(word.capitalize() for word in name.split())
        
        return name
    
    def get_schedule_by_name(self, schedule_name: str) -> Optional[Dict[str, Any]]:
        """
        Get schedule data by providing a schedule name (either original ID or formatted name).
        Implementation moved from DataLoader.
        
        Args:
            schedule_name: The name of the schedule to find
            
        Returns:
            Optional[Dict[str, Any]]: Schedule data if found, None otherwise
        """
        # First try exact match on original ID
        all_schedules = self.get_parsed_unique_schedules()
        
        # Create a lookup by formatted name
        formatted_name_map = {}
        for schedule in all_schedules:
            formatted_name = self.format_schedule_name(schedule['name'])
            formatted_name_map[formatted_name.lower()] = schedule
        
        # Try exact match on ID
        for schedule in all_schedules:
            if schedule['name'] == schedule_name:
                return schedule
                
        # Try case-insensitive match on formatted names
        schedule_name_lower = schedule_name.lower()
        if schedule_name_lower in formatted_name_map:
            return formatted_name_map[schedule_name_lower]
            
        # Finally try partial match
        for schedule in all_schedules:
            if (schedule_name_lower in schedule['name'].lower() or 
                schedule_name_lower in self.format_schedule_name(schedule['name']).lower()):
                return schedule
                
        return None
