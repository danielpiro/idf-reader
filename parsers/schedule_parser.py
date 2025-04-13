"""
Extracts and processes Schedule:Compact objects using eppy.
"""

# Substrings that indicate this is a setpoint schedule (to be ignored)
IGNORE_SUBSTRINGS = ["Setpoint", "SP"]

class ScheduleExtractor:
    """
    Extracts Schedule:Compact objects using eppy, ignoring setpoint schedules 
    and grouping unique schedule patterns by type.
    """
    def __init__(self):
        # Store schedules by type, with unique value patterns
        self.schedules_by_type = {}  # {type: {rule_tuple: schedule_dict}}

    def process_element(self, element_type, identifier, data, current_zone_id=None):
        """
        Processes a single element, either from the old parser format or from eppy objects.
        Maintains backwards compatibility while supporting eppy objects.

        Args:
            element_type (str): 'comment' or 'object'
            identifier (str): The object keyword or eppy object type
            data (list): List of field values
            current_zone_id (str or None): The current zone context (ignored)
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
            if any(substring.lower() in schedule_name.lower() for substring in IGNORE_SUBSTRINGS):
                return

            # Convert rule fields to tuple for hashing/uniqueness check
            rule_tuple = tuple(rule_fields)

            # Initialize dict for this type if not seen before
            if schedule_type not in self.schedules_by_type:
                self.schedules_by_type[schedule_type] = {}

            # If this rule pattern hasn't been seen for this type, store it
            if rule_tuple not in self.schedules_by_type[schedule_type]:
                self.schedules_by_type[schedule_type][rule_tuple] = {
                    'name': schedule_name,
                    'type': schedule_type,
                    'raw_rules': rule_fields
                }

    def process_eppy_schedule(self, schedule_obj):
        """
        Process a Schedule:Compact object from eppy directly.
        
        Args:
            schedule_obj: An eppy Schedule:Compact object
        """
        # Extract fields from eppy object
        data = [field for field in schedule_obj.fieldvalues]
        # Process using existing logic
        self.process_element('object', 'Schedule:Compact', data)

    def get_parsed_unique_schedules(self):
        """
        Returns the list of unique schedule patterns, organized by unique value patterns within each type.
        
        Returns:
            list: List of dicts with format {'name': str, 'type': str, 'raw_rules': list}
        """
        # Flatten the nested dictionaries into a list
        result = []
        for type_dict in self.schedules_by_type.values():
            result.extend(type_dict.values())
        return result