"""
Extracts and processes Schedule:Compact objects.
Uses DataLoader for potential future schedule caching.
"""
from typing import Dict, List, Any, Optional, Tuple
from utils.data_loader import DataLoader

# Substrings that indicate this is a setpoint schedule (to be ignored)
IGNORE_SUBSTRINGS = ["Setpoint", "SP"]

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

    def process_element(self, element_type: str, identifier: str, 
                       data: List[str], current_zone_id: Optional[str] = None) -> None:
        """
        Processes a single element, either from parser format or eppy objects.
        
        Args:
            element_type: 'comment' or 'object'
            identifier: The object keyword or eppy object type
            data: List of field values
            current_zone_id: The current zone context (ignored)
        """
        if element_type == 'comment':
            return  # Ignore comments

        elif element_type == 'object' and identifier == 'Schedule:Compact':
            if not data or len(data) < 2:  # Need at least name and type fields
                return  # Invalid Schedule:Compact object

            try:
                schedule_name = data[0]  # First field is name
                schedule_type = data[1]  # Second field is type
                rule_fields = data[2:]  # The rest are rule fields
            except IndexError:
                print(f"Warning: Could not parse name/type/rules for Schedule:Compact. Fields: {data}")
                return

            # Skip schedules with setpoint-related names
            if any(substring.lower() in schedule_name.lower() 
                  for substring in IGNORE_SUBSTRINGS):
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

        # Initialize dict for this type if not seen before
        if type_ not in self.schedules_by_type:
            self.schedules_by_type[type_] = {}

        # If this rule pattern hasn't been seen for this type, store it
        if rule_tuple not in self.schedules_by_type[type_]:
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
                        schedule_data['zone_id'] = zone_id
                        schedule_data['zone_type'] = zone_data.type
                        break
            
            self.schedules_by_type[type_][rule_tuple] = schedule_data

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