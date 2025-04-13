from idf_parser import strip_inline_comment

class LoadExtractor:
    """
    Extracts unique zone IDs from ZoneControl:Thermostat objects.
    """
    def __init__(self):
        self.unique_zone_ids = set()  # Store unique zone IDs

    def process_element(self, element_type, identifier, data, current_zone_id=None): # Add zone_id
        """
        Processes a single element yielded by the idf_parser.

        Args:
            element_type (str): 'comment' or 'object'.
            identifier (str): The object keyword (should be 'ZoneControl:Thermostat').
            data (list): List of cleaned object fields (if object) or None/str (if comment).
            current_zone_id (str or None): The current zone context (ignored).
        """
        if element_type == 'object' and identifier == 'ZoneControl:Thermostat':
            # Data is now a list of cleaned fields
            if len(data) >= 2:  # Need at least Name and Zone Name fields
                # Zone Name is the second field (index 1)
                zone_id = data[1] # Already cleaned by idf_parser
                # Remove potential "Thermostat" suffix (though unlikely after field split)
                if "Thermostat" in zone_id:
                     zone_id = zone_id.replace("Thermostat", "").strip()
                if zone_id:
                    self.unique_zone_ids.add(zone_id)
            # else: Not enough fields

    def get_unique_zone_ids(self):
        """
        Returns the set of unique zone IDs found.

        Returns:
            set: A set of strings containing unique zone IDs.
        """
        return self.unique_zone_ids