"""
Extracts and processes Schedule:Compact objects.
Uses DataLoader for cached access to IDF data.
"""
import re
from typing import Dict, List, Any, Optional, Tuple
from utils.data_loader import DataLoader
from utils.data_models import ScheduleData

def time_str_to_minutes(time_str: str) -> int:
    """Convert HH:MM time string to minutes since midnight."""
    try:
        hours, minutes = map(int, time_str.split(':'))
        if hours == 24 and minutes == 0:
            return 24 * 60
        if 0 <= hours < 24 and 0 <= minutes < 60:
            return hours * 60 + minutes
        raise ValueError(f"Time out of range: {time_str}")
    except Exception:
        return 0

BASIC_TYPES = [
    "on", "off", "work efficiency", "opaqueshade",
    "zone comfort control type sched", "design days only",
    "typoperativetempcontrolsch", "onwinterdesignday",
    "onsummerdesignday", "heating setpoint schedule", "cooling sp sch"
]

def _is_basic_type(schedule_type: str) -> bool:
    """
    Check if schedule is a basic type that should be filtered out.
    Handles schedule types that may have a zone prefix (e.g., "00:01XLIVING Heating Setpoint Schedule").

    Args:
        schedule_type: The schedule type to check

    Returns:
        bool: True if schedule should be filtered out
    """
    zone_prefix_pattern = r'^\d{2}:\d{2}[A-Z\d]*\s+'
    actual_schedule_type_name = re.sub(zone_prefix_pattern, '', schedule_type, count=1)
    return any(basic_type.lower() == actual_schedule_type_name.lower() for basic_type in BASIC_TYPES)

def _standardize_date_format(date_string: str) -> str:
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
    date_string = date_string.strip()
    if date_string.lower().startswith("through:"):
        date_string = date_string[8:].strip().lower()

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

    pattern1 = re.search(r'(\d{1,2})\s+([a-zA-Z]+)', date_string, re.IGNORECASE)
    if pattern1:
        day = int(pattern1.group(1))
        month_name = pattern1.group(2).lower()
        for name, num in month_names.items():
            if month_name.startswith(name):
                return f"{day:02d}/{num:02d}"

    pattern2 = re.search(r'(\d{1,2})/(\d{1,2})', date_string)
    if pattern2:
        first, second = int(pattern2.group(1)), int(pattern2.group(2))
        if 1 <= first <= 12 and second > 12:
            return f"{second:02d}/{first:02d}"
        elif 1 <= second <= 12 and first > 12:
            return f"{first:02d}/{second:02d}"
        elif 1 <= first <= 12 and 1 <= second <= 12:
            return f"{second:02d}/{first:02d}"

    if date_string.isdigit():
        return f"{int(date_string):02d}/12"

    return f"{date_string} -> ??/??"

def _extract_zone_id_from_schedule(schedule_id: str) -> Optional[str]:
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
        parts = schedule_id.split()
        if parts:
            return parts[0]
    return None

def _expand_rules_to_hourly(time_value_pairs: List[Dict[str, str]]) -> List[Optional[str]]:
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

        current_minute = min(current_minute, 24 * 60)
        if current_minute == 0 and end_time_str != "00:00":
             current_minute = 24*60

        if current_minute <= last_minute:
            continue

        start_hour_index = last_minute // 60
        end_hour_index = (current_minute + 59) // 60

        end_hour_index = min(end_hour_index, 24)

        for h in range(start_hour_index, end_hour_index):
             if h < 24:
                hourly_values[h] = value

        last_minute = current_minute

        if last_minute >= 24 * 60:
            break

    if last_minute < 24 * 60 and time_value_pairs:
         last_value = time_value_pairs[-1]['value']
         start_fill_index = last_minute // 60
         for h in range(start_fill_index, 24):
             if hourly_values[h] is None:
                 hourly_values[h] = last_value

    if hourly_values[0] is None and time_value_pairs:
         first_val_minute = time_str_to_minutes(time_value_pairs[0]['end_time'])
         if first_val_minute > 0:
             hourly_values[0] = time_value_pairs[0]['value']
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

    last_known_value = '0'
    for i in range(len(hourly_values)):
        if hourly_values[i] is not None:
            last_known_value = hourly_values[i]
        elif hourly_values[i] is None:
             hourly_values[i] = last_known_value

    processed_values = list(hourly_values)
    for h in range(1, 24):
        if hourly_values[h] != hourly_values[h-1]:
            processed_values[h-1] = hourly_values[h]

    if hourly_values[0] != hourly_values[23]:
         processed_values[23] = hourly_values[0]

    formatted_hourly_values = []
    for val in processed_values:
        try:
            num_val = float(val)
            if num_val == int(num_val):
                 formatted_hourly_values.append(str(int(num_val)))
            else:
                 formatted_hourly_values.append(f"{num_val:.2f}")
        except (ValueError, TypeError):
            formatted_hourly_values.append(str(val) if val is not None else '')

    return formatted_hourly_values

def _parse_compact_rule_blocks(rule_fields: List[str]) -> List[Dict[str, Any]]:
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
    current_through = "31/12"
    current_for = "AllDays"
    i = 0

    while i < len(rule_fields):
        field = rule_fields[i].strip()
        field_lower = field.lower()

        if field_lower.startswith("through:"):
            if current_block_rules:
                hourly_values = _expand_rules_to_hourly(current_block_rules)
                rule_blocks.append({
                    'through': current_through,
                    'for_days': current_for,
                    'hourly_values': hourly_values
                })
                current_block_rules = []

            current_through = _standardize_date_format(field)
            i += 1

        elif field_lower.startswith("for:"):
             current_for = field
             i += 1
        elif field_lower.startswith("until:"):
            if i + 1 < len(rule_fields):
                time_match = re.search(r'(\d{1,2}:\d{2})', field)
                if time_match:
                    end_time = time_match.group(1)
                    value = rule_fields[i+1].strip()
                    current_block_rules.append({'end_time': end_time, 'value': value})
                    i += 2
                else:
                    i += 1
            else:
                i += 1
        else:
            i += 1

    if current_block_rules:
        hourly_values = _expand_rules_to_hourly(current_block_rules)
        rule_blocks.append({
            'through': current_through,
            'for_days': current_for,
            'hourly_values': hourly_values
        })

    return rule_blocks

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
        self.schedules_by_type: Dict[str, Dict[Tuple, Dict[str, Any]]] = {}
        self.processed_schedules: Dict[str, ScheduleData] = {}

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
        if element_type == 'object' and identifier == 'Schedule:Compact':
            if not data or len(data) < 2:
                return

            schedule_name, schedule_type, *rule_fields = data

            if _is_basic_type(schedule_type):
                return

            self._store_schedule(schedule_name, schedule_type, rule_fields)

    def process_eppy_schedule(self, schedule_obj) -> None:
        """
        Process a Schedule:Compact object from eppy directly.

        Args:
            schedule_obj: An eppy Schedule:Compact object
        """
        data = [field for field in schedule_obj.fieldvalues]
        self.process_element('object', 'Schedule:Compact', data)

    def process_idf(self, idf) -> None:
        """
        Process all schedules from the IDF file, using cached data.
        Implementation details moved from DataLoader.

        Args:
            idf: eppy IDF object (kept for compatibility)
        """
        if not self.data_loader:
            raise RuntimeError("ScheduleExtractor requires a DataLoader instance.")

        schedule_cache = self.data_loader.get_schedules()

        for schedule_id, schedule_data in schedule_cache.items():
            schedule_type = schedule_data['type']

            rule_fields = self.data_loader.get_schedule_rules(schedule_id)

            self._store_schedule(schedule_id, schedule_type, rule_fields)

            self._create_schedule_data(schedule_id, schedule_type, rule_fields)

    def _create_schedule_data(self, name: str, type_: str, rule_fields: List[str]) -> None:
        """
        Create ScheduleData object for use by other parsers.
        Implementation moved from DataLoader.

        Args:
            name: Schedule name
            type_: Schedule type
            rule_fields: List of rule field values
        """
        zone_id = _extract_zone_id_from_schedule(name)
        zone_type = None

        if zone_id and self.data_loader:
            zones = self.data_loader.get_zones()
            for zone_name in zones:
                if zone_id.lower() in zone_name.lower():
                    # zone_type is not implemented in DataLoader, using None for now
                    zone_type = None  # Could be enhanced later if zone type detection is needed
                    break

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
        rule_tuple = tuple(rule_fields)

        normalized_type = ' '.join(part for part in type_.split() if not (
            ':' in part or
            part.isdigit() or
            (part.isupper() and len(part) > 1)
        )).strip()

        if normalized_type not in self.schedules_by_type:
            self.schedules_by_type[normalized_type] = {}

        if rule_tuple not in self.schedules_by_type[normalized_type]:
            zone_id = _extract_zone_id_from_schedule(name)
            zone_type = None

            if zone_id and self.data_loader:
                zones = self.data_loader.get_zones()
                for zone_name in zones:
                    if zone_id.lower() in zone_name.lower():
                        # zone_type is not implemented in DataLoader, using None for now
                        zone_type = None  # Could be enhanced later if zone type detection is needed
                        break

            schedule_data = {
                'name': name,
                'type': type_,
                'raw_rules': rule_fields,
                'rule_blocks': _parse_compact_rule_blocks(rule_fields),
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
        return [schedule for type_dict in self.schedules_by_type.values() for schedule in type_dict.values()]

    def get_schedules_by_type(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Returns schedules organized by type.

        Returns:
            dict: Dictionary of schedules grouped by type
        """
        return {type_: list(schedules.values()) for type_, schedules in self.schedules_by_type.items()}

    def get_zone_schedules(self, zone_id: str) -> List[Dict[str, Any]]:
        """
        Get all schedules associated with a specific zone.

        Args:
            zone_id: The zone identifier to filter by

        Returns:
            list: List of schedule data dictionaries
        """
        return [schedule for type_dict in self.schedules_by_type.values() for schedule in type_dict.values() if schedule.get('zone_id') == zone_id]

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
        name = schedule_id

        for suffix in [' Schedule', ' Sch', '_schedule', '_sch']:
            if name.lower().endswith(suffix.lower()):
                name = name[:-len(suffix)]

        zone_pattern = re.search(r'(\d{2}:\d{2}[A-Z]?)', name)
        if zone_pattern:
            remaining = name[zone_pattern.end():].strip()
            if remaining:
                name = remaining

        name = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)
        name = name.replace('_', ' ')

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
        all_schedules = self.get_parsed_unique_schedules()
        formatted_name_map = {self.format_schedule_name(s['name']).lower(): s for s in all_schedules}
        for schedule in all_schedules:
            if schedule['name'] == schedule_name:
                return schedule
        schedule_name_lower = schedule_name.lower()
        if schedule_name_lower in formatted_name_map:
            return formatted_name_map[schedule_name_lower]
        for schedule in all_schedules:
            if (schedule_name_lower in schedule['name'].lower() or 
                schedule_name_lower in self.format_schedule_name(schedule['name']).lower()):
                return schedule
        return None
