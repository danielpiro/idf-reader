# Settings categories and their associated keys
SETTINGS_CATEGORIES = {
    "General Settings": ["Version", "RunPeriod", "Timestep", "ConvergenceLimits", "SimulationControl"],
    "Geometry Settings": [
        "Geometry convention template",
        "Zone geometry and surface areas",
        "Zone volume calculation method",
        "Zone floor area calculation method",
        "Window to wall ratio method"
    ],
    "Location Settings": ["Site:Location"],
    "Ground Temperature Settings": [
        "Site:GroundTemperature:BuildingSurface",
        "Site:GroundTemperature:Deep",
        "Site:GroundTemperature:Shallow",
        "Site:GroundTemperature:FCfactorMethod"
    ],
    "Ground Reflectance Settings": [
        "Site:GroundReflectance",
        "Site:GroundReflectance:SnowModifier"
    ]
}

# Flatten categories for easy lookup
TARGET_COMMENT_KEYS = [
    key for category in SETTINGS_CATEGORIES.values()
    for key in category
    if ":" not in key
]

TARGET_OBJECT_KEYWORDS = [
    key for category in SETTINGS_CATEGORIES.values()
    for key in category
    if ":" in key
]

class SettingsExtractor:
    """
    Extracts and formats predefined settings data from parsed IDF elements.
    """
    def __init__(self):
        self.extracted_settings = {}
        self.initialize_settings()

    def initialize_settings(self):
        """Initialize settings dictionary with categories"""
        self.extracted_settings = {
            category: {key: "Not Found" for key in keys}
            for category, keys in SETTINGS_CATEGORIES.items()
        }

    def _format_version(self, data):
        """Format version information"""
        if not isinstance(data, list) or not data:
            return "Not Found"
        return f"EnergyPlus Version {data[0]}"

    def _format_temperature_data(self, data):
        """Format temperature data into a readable table-like format"""
        if not isinstance(data, list) or not data:
            return "Not Found"
        
        # For temperature data, typically monthly values
        try:
            values = [float(x) for x in data]
            months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            
            # Format as a two-row table
            rows = []
            for i in range(0, len(values), 4):
                chunk_months = months[i:i+4]
                chunk_values = values[i:i+4]
                month_row = "  ".join(f"{m:^5}" for m in chunk_months)
                value_row = "  ".join(f"{v:^5.1f}" for v in chunk_values)
                rows.extend([month_row, value_row, ""])
            
            return "\n".join(rows).rstrip()
        except (ValueError, IndexError):
            return ", ".join(data)

    def _get_category_for_key(self, key):
        """Get the category name for a given key"""
        for category, keys in SETTINGS_CATEGORIES.items():
            if key in keys:
                return category
        return None

    def _format_runperiod(self, data):
        """Format RunPeriod data"""
        if not isinstance(data, list) or len(data) < 10:
            return "Not Found"
        
        period_name = data[0] if data[0] else "Annual simulation"
        start_date = f"{data[1]}/{data[2]}/{data[3]}"  # MM/DD/YYYY
        end_date = f"{data[4]}/{data[5]}/{data[6]}"    # MM/DD/YYYY
        
        options = []
        if data[7] == "Yes": options.append("Use Weather Holidays")
        if data[8] == "Yes": options.append("Use Weather DST")
        if data[9] == "Yes": options.append("Apply Weekend Rule")
        
        result = [
            f"Period: {period_name}",
            f"Date Range: {start_date} to {end_date}"
        ]
        if options:
            result.append(f"Options: {', '.join(options)}")
        
        return "\n".join(result)

    def _format_location(self, data):
        """Format location data"""
        if not isinstance(data, list) or len(data) < 4:
            return "Not Found"
        
        return "\n".join([
            f"Location: {data[0]}",
            f"Latitude: {data[1]}°",
            f"Longitude: {data[2]}°",
            f"Time Zone: GMT{data[3]}",
            f"Elevation: {data[4]}m"
        ])

    def _format_simulation_control(self, data):
        """Format simulation control settings"""
        if not isinstance(data, list) or len(data) < 5:
            return "Not Found"
        
        controls = [
            "Zone Sizing", "System Sizing", "Plant Sizing",
            "Design Day", "Weather File"
        ]
        
        return "\n".join(
            f"{control}: {value}"
            for control, value in zip(controls, data)
        )

    def _format_convergence_limits(self, data):
        """Format convergence limits"""
        if not isinstance(data, list) or len(data) < 2:
            return "Not Found"
        
        return "\n".join([
            f"Min System Time Step: {data[0]}",
            f"Max HVAC Iterations: {data[1]}"
        ])

    def process_element(self, element_type, identifier, data, current_zone_id=None):
        """
        Processes a single element yielded by the idf_parser.

        Args:
            element_type (str): 'comment' or 'object'.
            identifier (str): The comment key or object keyword.
            data (str or list): Comment value or list of cleaned object fields.
            current_zone_id (str or None): The current zone context (ignored).
        """
        category = self._get_category_for_key(identifier)
        if not category:
            return

        if element_type == 'comment' and identifier in TARGET_COMMENT_KEYS:
            self.extracted_settings[category][identifier] = data
        elif element_type == 'object' and identifier in TARGET_OBJECT_KEYWORDS:
            if identifier == "Version":
                self.extracted_settings[category][identifier] = self._format_version(data)
            elif identifier == "RunPeriod":
                self.extracted_settings[category][identifier] = self._format_runperiod(data)
            elif identifier == "Site:Location":
                self.extracted_settings[category][identifier] = self._format_location(data)
            elif identifier == "SimulationControl":
                self.extracted_settings[category][identifier] = self._format_simulation_control(data)
            elif identifier == "ConvergenceLimits":
                self.extracted_settings[category][identifier] = self._format_convergence_limits(data)
            elif "Temperature" in identifier or "Reflectance" in identifier:
                self.extracted_settings[category][identifier] = self._format_temperature_data(data)
            else:
                self.extracted_settings[category][identifier] = ", ".join(data) if isinstance(data, list) and data else "Not Found"

    def get_settings(self):
        """
        Returns the categorized dictionary of extracted settings.
        """
        return self.extracted_settings

# Example usage (demonstrates how it would be used with the parser)
if __name__ == '__main__':
    from idf_parser import parse_idf # Assuming idf_parser.py is in the same directory

    test_file = 'in.idf'
    print(f"Testing settings extraction with {test_file}")

    extractor = SettingsExtractor()

    try:
        # Update test loop for 4-tuple yield from parse_idf
        target_keys = set(TARGET_COMMENT_KEYS) | set(TARGET_OBJECT_KEYWORDS) # Combine keys for parsing if needed, though parser mainly uses comment keys
        for element_type, identifier, data, zone_id in parse_idf(test_file, settings_keys=set(TARGET_COMMENT_KEYS)):
            # Pass all 4 args, process_element will decide if it needs zone_id
            extractor.process_element(element_type, identifier, data, zone_id)

        settings = extractor.get_settings()

        print("\nExtracted Settings:")
        for key, value in settings.items():
            print(f"  {key}: {value}")

    except FileNotFoundError:
        print(f"Test file '{test_file}' not found. Cannot run example.")
    except Exception as e:
        print(f"Error during test: {e}")