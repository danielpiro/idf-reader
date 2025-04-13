import re

from idf_parser import strip_inline_comment

# Substrings that indicate this is a setpoint schedule (to be ignored)
IGNORE_SUBSTRINGS = ["Setpoint", "SP"]

class ScheduleExtractor:
    """
    Extracts Schedule:Compact objects, ignoring setpoint schedules and grouping
    unique schedule patterns by type.
    """
    def __init__(self):
        # Store schedules by type, with unique value patterns
        self.schedules_by_type = {}  # {type: {rule_tuple: schedule_dict}}

    def process_element(self, element_type, identifier, data, current_zone_id=None): # Add zone_id
        """
        Processes a single element yielded by the idf_parser.

        Args:
            element_type (str): 'comment' or 'object'.
            identifier (str): The object keyword (should be 'Schedule:Compact').
            data (list): List of cleaned object fields (if object) or None/str (if comment).
            current_zone_id (str or None): The current zone context (ignored).
        """
        if element_type == 'comment':
            pass  # Ignore comments

        elif element_type == 'object' and identifier == 'Schedule:Compact':
            # Data is now a list of cleaned fields
            if not data or len(data) < 2: # Need at least name and type fields
                return # Invalid Schedule:Compact object

            # Extract name, type, and rules from the cleaned fields list
            # Assumes idf_parser correctly provides these as elements in the list
            try:
                defined_name = data[0] # First field is name
                schedule_type = data[1] # Second field is type
                # The rest are rule fields (already cleaned)
                rule_fields = data[2:]
            except IndexError:
                 print(f"Warning: Could not parse name/type/rules for Schedule:Compact. Cleaned fields: {data}")
                 return

            # Skip schedules with setpoint-related names
            for substring in IGNORE_SUBSTRINGS:
                if substring.lower() in defined_name.lower():
                    return  # Skip this schedule

            # Use the extracted name and type
            schedule_name = defined_name
            # schedule_type already extracted
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
                    'raw_rules': rule_fields # Store the cleaned rule fields
                }

    def get_parsed_unique_schedules(self):
        """
        Returns the list of unique schedule patterns, organized by unique value patterns within each type.
        Format: [{'name': str, 'type': str, 'raw_rules': list_of_strings}]
        """
        # Flatten the nested dictionaries into a list
        result = []
        for type_dict in self.schedules_by_type.values():
            result.extend(type_dict.values())
        return result