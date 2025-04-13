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
        if not data or len(data) < 10:
            return "Not Found"
        
        name = data[0].strip() or "Annual simulation"
        start_month, start_day, start_year = data[1:4]
        end_month, end_day, end_year = data[4:7]
        
        result = [
            f"Period: {name}",
            f"Date Range: {start_month}/{start_day}/{start_year} to {end_month}/{end_day}/{end_year}"
        ]
        
        options = []
        if data[7].lower() == "yes": options.append("Use Weather Holidays")
        if data[8].lower() == "yes": options.append("Use Weather DST")
        if data[9].lower() == "yes": options.append("Apply Weekend Rule")
        
        if options:
            result.append(f"Options: {', '.join(options)}")
            
        return "\n".join(result)

    def _format_location(self, data):
        """Format location data"""
        if not data or len(data) < 5:
            return "Not Found"
        
        try:
            return "\n".join([
                f"Location: {data[0]}",
                f"Latitude: {float(data[1])}°",
                f"Longitude: {float(data[2])}°",
                f"Time Zone: GMT{float(data[3])}",
                f"Elevation: {float(data[4])}m"
            ])
        except (ValueError, IndexError):
            return "Not Found"

    def _format_simulation_control(self, data):
        """Format simulation control settings"""
        if not data or len(data) < 5:
            return "Not Found"
        
        controls = [
            "Zone Sizing", "System Sizing", "Plant Sizing",
            "Design Day", "Weather File"
        ]
        return "\n".join(f"{control}: {value}"
                        for control, value in zip(controls, data))

    def _format_convergence_limits(self, data):
        """Format convergence limits"""
        if not data or len(data) < 2:
            return "Not Found"
        
        return "\n".join([
            f"Min System Time Step: {data[0]}",
            f"Max HVAC Iterations: {data[1]}"
        ])

    def _format_temperature_data(self, data):
        """Format temperature or reflectance data"""
        if not data or len(data) < 12:
            return "Not Found"
            
        try:
            values = []
            for val in data:
                try:
                    values.append(float(val))
                except (ValueError, TypeError):
                    continue
            
            if len(values) < 12:
                return "Not Found"
                
            months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            
            rows = []
            for i in range(0, 12, 4):
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
            if identifier in TARGET_COMMENT_KEYS:
                self.extracted_settings["Geometry Settings"][identifier] = data
                return
                
        elif element_type == 'object':
            # Normalize the identifier
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
                    value = f"{data[0]} timesteps per hour" if data else "Not Found"
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