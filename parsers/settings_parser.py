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
        "Site:GroundTemperature:FCfactorMethod",
    ],
    "Ground Reflectance Settings": [
        "Site:GroundReflectance",
        "Site:GroundReflectance:SnowModifier"
    ]
}

# Define target comment keys (geometry settings)
TARGET_COMMENT_KEYS = SETTINGS_CATEGORIES["Geometry Settings"]

# Define target object keywords (everything else)
TARGET_OBJECT_KEYWORDS = (
    ["Version", "RunPeriod", "Timestep", "ConvergenceLimits", "SimulationControl"] +
    [key.replace(" ", "") for category, keys in SETTINGS_CATEGORIES.items() 
     if category != "Geometry Settings" 
     for key in keys]
)

class SettingsExtractor:
    """Extracts and formats predefined settings data from parsed IDF elements."""
    
    def __init__(self):
        self.extracted_settings = {}
        self.initialize_settings()
        self._setup_mappings()

    def initialize_settings(self):
        """Initialize settings dictionary with categories"""
        self.extracted_settings = {
            category: {key: "Not Found" for key in keys}
            for category, keys in SETTINGS_CATEGORIES.items()
        }

    def _setup_mappings(self):
        """Set up mappings for object identifiers"""
        # Map for object types (like Version, RunPeriod, etc.)
        self.simple_objects = {
            "version": "Version",
            "runperiod": "RunPeriod",
            "timestep": "Timestep",
            "convergencelimits": "ConvergenceLimits",
            "simulationcontrol": "SimulationControl"
        }
        
        # Map for complex objects (with colons)
        self.complex_objects = {}
        for category in SETTINGS_CATEGORIES.values():
            for key in category:
                if ":" in key:
                    normalized = key.replace(" ", "").lower()
                    self.complex_objects[normalized] = key

    def _format_version(self, data):
        """Format version information"""
        return f"EnergyPlus Version {data[0]}" if data else "Not Found"

    def _format_runperiod(self, data):
        """Format RunPeriod data"""
        if not data or len(data) < 7:
            return "Not Found"
        location = data[1].split('(')[0].strip() if data else "Not Found"
        start_month, start_day, start_year = data[2:5]
        end_month, end_day, end_year = data[5:8]

        if len(data) > 13:
            subjects = []
            if data[8].lower() == "yes":
                subjects.append("Use weather file holidays/special day periods")
            if data[9].lower() == "yes":
                subjects.append("Use WeatherFile DaylightSavingPeriod - will use daylight saving time")
            if data[10].lower() == "yes":
                subjects.append("Apply Weekend Holiday Rule - will reassign weekend holidays to Monday")
            if data[11].lower() == "yes":
                subjects.append("use weather file rain indicators")
            if data[12].lower() == "yes":
                subjects.append("use weather file snow indicators")
            if data[13].lower() == "yes":
                subjects.append("Treat Weather as Actual")
        
        #build the result string
        result = [
            f"Location: {location}",
            f"Start Date: {start_month} {start_day}, {start_year}",
            f"End Date: {end_month} {end_day}, {end_year}"
        ]
        if len(data) > 13:
            result.extend(subjects)
            result.append("")
        return "\n".join(result)

    def _format_location(self, data):
        """Format location data"""
        if not data or len(data) < 6:
            return "Not Found"
        
        try:
            return "\n".join([
                f"Location: {data[1]}",
                f"Latitude: {float(data[2])}°",
                f"Longitude: {float(data[3])}°",
                f"Time Zone: GMT{float(data[4])}",
                f"Elevation: {float(data[5])}m"
            ])
        except (ValueError, IndexError):
            return "Not Found"

    def _format_simulation_control(self, data):
        """Format simulation control settings"""
        #here we need to start from index 1 to skip the first element which is the object name
        if not data or len(data) < 6:
            return "Not Found"
        
        try:
            control = {
                "Do the zone sizing calculation": data[1],
                "Do the system sizing calculation": data[2],
                "Do the plant sizing calculation": data[3],
                "Do the design day calculation": data[4],
                "Do the weather file calculation": data[5]
            }
            
            return "\n".join([f"{key}: {value}" for key, value in control.items()])
        except (ValueError, IndexError):
            return "Not Found"

    def _format_convergence_limits(self, data):
        """Format convergence limits"""
        if not data or len(data) < 3:
            return "Not Found"
        
        return "\n".join([
            f"Min System Time Step: {data[1]}",
            f"Max HVAC Iterations: {data[2]}"
        ])

    def _format_temperature_data(self, data):
        """Format temperature or reflectance data"""
        if not data:
            return "Not Found"
            
        try:
            values = []
            for val in data:
                try:
                    values.append(float(val))
                except (ValueError, TypeError):
                    continue
            
            if not values:
                return "Not Found"
                
            months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            
            # Use only as many months as we have values
            num_values = len(values)
            months = months[:num_values]
            
            rows = []
            # Process in chunks of 4, but only up to the actual data length
            for i in range(0, num_values, 4):
                month_chunk = months[i:i+4]
                value_chunk = values[i:i+4]
                rows.extend([
                    "  ".join(f"{m:^8}" for m in month_chunk),
                    "  ".join(f"{v:^8.2f}" for v in value_chunk),
                    ""
                ])
            
            return "\n".join(rows).rstrip()
        except Exception:
            return "Not Found"

    def _get_category_for_key(self, key):
        """Get the category for a given key"""
        for category, keys in SETTINGS_CATEGORIES.items():
            if key in keys:
                return category
        return None

    def process_element(self, element_type, identifier, data, current_zone_id=None):
        """Process a single element yielded by the idf_parser."""
        if element_type == 'comment':
            # Handle comment elements (geometry settings)
            key = identifier.split(":")[0].strip()
            value = identifier.split(":")[1].strip() if ":" in identifier else "Not Found"
            if key in TARGET_COMMENT_KEYS:
                category = self._get_category_for_key(key)
                if category:
                    self.extracted_settings[category][key] = value
                    return
                
        elif element_type == 'object':
            # Normalize the identifier
            if data and len(data) > 1:
                identifier = data[0].strip()
            norm_id = identifier.replace(" ", "").lower()
            
            # Handle simple objects
            if norm_id in self.simple_objects:
                key = self.simple_objects[norm_id]
                category = "General Settings"
                
                if norm_id == "version":
                    value = self._format_version(data)
                elif norm_id == "runperiod":
                    value = self._format_runperiod(data)
                elif norm_id == "timestep":
                    value = f"{data[1]} timesteps per hour" if data else "Not Found"
                elif norm_id == "convergencelimits":
                    value = self._format_convergence_limits(data)
                elif norm_id == "simulationcontrol":
                    value = self._format_simulation_control(data)
                    
                self.extracted_settings[category][key] = value
                return
                
            # Handle complex objects (with colons)
            if norm_id in self.complex_objects:
                key = self.complex_objects[norm_id]
                category = self._get_category_for_key(key)
                if category:
                    if "Location" in key:
                        value = self._format_location(data)
                    elif "Temperature" in key or "Reflectance" in key:
                        value = self._format_temperature_data(data)
                    else:
                        value = ", ".join(data) if data else "Not Found"
                        
                    self.extracted_settings[category][key] = value

    def get_settings(self):
        """Returns the categorized dictionary of extracted settings."""
        return self.extracted_settings