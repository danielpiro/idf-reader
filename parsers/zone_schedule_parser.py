class ZoneScheduleParser:
    """
    Parses IDF objects to map schedule names to the zone they are used within.
    """
    def __init__(self):
        self.schedules_by_zone = {} # {zone_id: set(schedule_names)}

    def process_element(self, element_type, identifier, data, current_zone_id):
        """
        Processes a single element yielded by the idf_parser.

        Args:
            element_type (str): 'comment' or 'object'.
            identifier (str): The object keyword or comment identifier.
            data (list or str or None): List of cleaned object fields, comment value, or None.
            current_zone_id (str or None): The ID of the current zone context.
        """
        if element_type == 'object' and current_zone_id is not None and isinstance(data, list):
            # Initialize the set for this zone if it's the first time seeing it
            if current_zone_id not in self.schedules_by_zone:
                self.schedules_by_zone[current_zone_id] = set()

            # Iterate through the cleaned fields of the object
            for field_value in data:
                # Simple check: if 'schedule' is in the field value (case-insensitive)
                # This is a basic heuristic and might need refinement based on IDF structure
                # or by checking specific field indices for known objects.
                if isinstance(field_value, str) and 'schedule' in field_value.lower():
                    # Assume the field value *is* the schedule name (already cleaned)
                    cleaned_schedule_name = field_value # Already cleaned by idf_parser
                    if cleaned_schedule_name: # Avoid adding empty strings
                        self.schedules_by_zone[current_zone_id].add(cleaned_schedule_name)

    def get_schedules_by_zone(self):
        """
        Returns the dictionary mapping zone IDs to sets of associated schedule names.

        Returns:
            dict: {zone_id (str): set(schedule_name (str))}
        """
        return self.schedules_by_zone