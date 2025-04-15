"""
Extracts and processes Schedule:Compact objects.
Uses DataLoader for potential future schedule caching.
"""
from typing import Dict, List, Any, Optional, Tuple, TYPE_CHECKING, Union

# Forward reference for type hints
DataLoader = Union['DataLoader', None]

if TYPE_CHECKING:
    from utils.data_loader import DataLoader

# Substrings that indicate this is a setpoint schedule (to be ignored)
# Basic schedule types to filter out
BASIC_TYPES = [
    "on", "off", "work efficiency", "opaqueshade",
    "zone comfort control type sched", "design days only",
    "typoperativetempcontrolsch", "onwinterdesignday",
    "onsummerdesignday"
]

# Enhanced setpoint pattern detection
SETPOINT_PATTERNS = {
    "prefixes": ["heating", "cooling"],
    "suffixes": ["sp", "setpoint"]
}

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
        
    def _check_zone_hvac(self, zone_name: str) -> bool:
        """
        Check if a zone has HVAC systems by looking for heating/cooling schedules.
        Uses cached zone data.
        
        Args:
            zone_name: Name of the zone to check
            
        Returns:
            bool: True if zone has HVAC systems, False otherwise
        """
        try:
            if not zone_name:
                return False
                
            zone_id = zone_name.split('_')[0] if '_' in zone_name else zone_name
            zone_id = zone_id.lower()
            
            schedules = self.data_loader.get_all_schedules()
            for schedule in schedules.values():
                if schedule.zone_id and schedule.zone_id.lower() == zone_id:
                    # Check if the schedule is for heating or cooling
                    if "heating" in schedule.type.lower() or "cooling" in schedule.type.lower():
                        return True
            
        except Exception as e:
            print(f"Error checking HVAC system for zone {zone_name}: {e}")
            return False
            
        return False

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

            # Enhanced filtering: check both basic types and setpoint schedules
            if (self._is_basic_type(schedule_type) or
                self._is_setpoint_schedule(schedule_name, schedule_type)):
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
                'raw_rules': rule_fields
            }
            
            # If we have a DataLoader, store additional metadata
            if self.data_loader is not None:
                # Get zone that uses this schedule (if any)
                schedule_name_lower = name.lower()
                zones = self.data_loader.get_all_zones()
                for zone_id, zone_data in zones.items():
                    if zone_id.lower() in schedule_name_lower:
                        # Only store schedule if zone has HVAC
                        if self._check_zone_hvac(zone_id):
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