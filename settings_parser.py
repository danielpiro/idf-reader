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

def normalize_identifier(identifier):
    """Normalize identifiers by removing extra spaces and handling colons"""
    # For comment identifiers (with spaces around colon)
    if " : " in identifier:
        return identifier.strip()
    # For object identifiers (no spaces around colon)
    return identifier.strip().replace(" ", "")

# Define object types first
SIMPLE_OBJECTS = [
    "Version", "RunPeriod", "Timestep", "ConvergenceLimits", "SimulationControl"
]

# Then define the target keys using the object types
TARGET_COMMENT_KEYS = [
    key for category in SETTINGS_CATEGORIES.values()
    for key in category
    if ":" not in key and key not in SIMPLE_OBJECTS
]

TARGET_OBJECT_KEYWORDS = [
    # Include simple objects
    *SIMPLE_OBJECTS,
    # Include complex objects (with colons)
    *(key.replace(" ", "") for category in SETTINGS_CATEGORIES.values()
      for key in category if ":" in key)
]

for key in sorted(TARGET_COMMENT_KEYS):
    print(f"  - {key}")
print("\nLooking for Object Settings:")
for key in sorted(TARGET_OBJECT_KEYWORDS):
    print(f"  - {key}")
print("----------------------------------------\n")

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
        """Format temperature or reflectance data into a readable table-like format"""
        if not isinstance(data, list) or not data or len(data) > 12:
            return "Not Found"
        
        try:
            # Convert all valid numeric values
            values = []
            for val in data:
                try:
                    values.append(float(val))
                except ValueError:
                    # Skip non-numeric values but don't fail
                    continue
            
            if not values:
                return "Not Found"
            
            # Ensure we have 12 months of data
            while len(values) < 12:
                values.append(values[-1])  # Repeat last value if needed
            
            months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            
            # Format as a three-row table with 4 months per row
            rows = []
            for i in range(0, 12, 4):
                chunk_months = months[i:i+4]
                chunk_values = values[i:i+4]
                month_row = "  ".join(f"{m:^8}" for m in chunk_months)
                value_row = "  ".join(f"{v:^8.2f}" for v in chunk_values)
                rows.extend([month_row, value_row, ""])  # Empty line between rows
            
            return "\n".join(rows).rstrip()
        except Exception:
            # Fallback to simple format if anything goes wrong
            return ", ".join(str(x) for x in data)

    def _get_category_for_key(self, key):
        """Get the category name for a given key"""
        # For object keys, compare without spaces
        if ":" in key:
            clean_key = key.replace(" ", "")
            for category, keys in SETTINGS_CATEGORIES.items():
                clean_keys = [k.replace(" ", "") for k in keys]
                if clean_key in clean_keys:
                    return category
        # For comment keys, compare as-is
        else:
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
        if element_type == 'object':
            orig_identifier = identifier
            identifier = identifier.replace(" ", "")
            if identifier in TARGET_OBJECT_KEYWORDS:
                print(f"\nDEBUG[Settings]: Processing '{identifier}'")
                if data:
                    print(f"  Data: {data}")
                else:
                    print("  Warning: No data received")

        category = self._get_category_for_key(identifier)
        if not category:
            return

        if element_type == 'comment' and identifier in TARGET_COMMENT_KEYS:
            self.extracted_settings[category][identifier] = data
        elif element_type == 'object' and identifier in TARGET_OBJECT_KEYWORDS:
            formatted_value = "Not Found"
            
            if identifier == "Version":
                print(f"Processing Version object with data: {data}")
                formatted_value = self._format_version(data)
            elif identifier == "RunPeriod":
                print(f"Processing RunPeriod object with data: {data}")
                formatted_value = self._format_runperiod(data)
            elif identifier == "Site:Location":
                print(f"Processing Site:Location object with data: {data}")
                formatted_value = self._format_location(data)
            elif identifier == "SimulationControl":
                print(f"Processing SimulationControl object with data: {data}")
                formatted_value = self._format_simulation_control(data)
            elif identifier == "ConvergenceLimits":
                print(f"Processing ConvergenceLimits object with data: {data}")
                formatted_value = self._format_convergence_limits(data)
            elif identifier == "Timestep":
                print(f"Processing Timestep object with data: {data}")
                formatted_value = f"{data[0]} timesteps per hour" if data else "Not Found"
            elif "Temperature" in identifier or "Reflectance" in identifier:
                print(f"Processing Temperature/Reflectance object with data: {data}")
                formatted_value = self._format_temperature_data(data)
            else:
                formatted_value = ", ".join(data) if isinstance(data, list) and data else "Not Found"
            
            print(f"Final formatted value: {formatted_value}")
            self.extracted_settings[category][identifier] = formatted_value

    def get_settings(self):
        """
        Returns the categorized dictionary of extracted settings.
        """
        return self.extracted_settings