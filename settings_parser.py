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

SIMPLE_OBJECTS = [
    "Version", "RunPeriod", "Timestep", "ConvergenceLimits", "SimulationControl"
]

TARGET_COMMENT_KEYS = [
    key for category in SETTINGS_CATEGORIES.values()
    for key in category
    if ":" not in key and key not in SIMPLE_OBJECTS
]

TARGET_OBJECT_KEYWORDS = [
    *SIMPLE_OBJECTS,
    *(key.replace(" ", "") for category in SETTINGS_CATEGORIES.values()
      for key in category if ":" in key)
]

class SettingsExtractor:
    """Extracts and formats predefined settings data from parsed IDF elements."""
    
    def __init__(self):
        self.extracted_settings = {}
        self.initialize_settings()
        self._setup_formatters()

    def initialize_settings(self):
        """Initialize settings dictionary with categories"""
        self.extracted_settings = {
            category: {key: "Not Found" for key in keys}
            for category, keys in SETTINGS_CATEGORIES.items()
        }

    def _setup_formatters(self):
        """Set up mapping of identifiers to their formatting functions"""
        self.formatters = {
            "Version": lambda data: f"EnergyPlus Version {data[0]}" if data else "Not Found",
            "RunPeriod": self._format_runperiod,
            "Site:Location": self._format_location,
            "SimulationControl": self._format_simulation_control,
            "ConvergenceLimits": self._format_convergence_limits,
            "Timestep": lambda data: f"{data[0]} timesteps per hour" if data else "Not Found"
        }
    
    def _format_tabular_data(self, data, num_columns=4):
        """Generic formatter for tabular data display"""
        if not isinstance(data, list) or not data:
            return "Not Found"
        
        try:
            values = [float(val) for val in data if val.replace('.', '').isdigit()]
            if not values:
                return "Not Found"
            
            # Ensure consistent length
            while len(values) < 12:
                values.append(values[-1])
            
            months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            
            rows = []
            for i in range(0, 12, num_columns):
                month_chunk = months[i:i + num_columns]
                value_chunk = values[i:i + num_columns]
                rows.extend([
                    "  ".join(f"{m:^8}" for m in month_chunk),
                    "  ".join(f"{v:^8.2f}" for v in value_chunk),
                    ""
                ])
            
            return "\n".join(rows).rstrip()
        except Exception:
            return ", ".join(str(x) for x in data)

    def _format_runperiod(self, data):
        """Format RunPeriod data"""
        if not isinstance(data, list) or len(data) < 10:
            return "Not Found"
        
        period_name = data[0] or "Annual simulation"
        start_date = f"{data[1]}/{data[2]}/{data[3]}"
        end_date = f"{data[4]}/{data[5]}/{data[6]}"
        
        options = [opt for flag, opt in zip(data[7:10], 
                  ["Use Weather Holidays", "Use Weather DST", "Apply Weekend Rule"])
                  if flag == "Yes"]
        
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
        
        return "\n".join(f"{control}: {value}"
                        for control, value in zip(controls, data))

    def _format_convergence_limits(self, data):
        """Format convergence limits"""
        if not isinstance(data, list) or len(data) < 2:
            return "Not Found"
        
        return "\n".join([
            f"Min System Time Step: {data[0]}",
            f"Max HVAC Iterations: {data[1]}"
        ])

    def _get_category_for_key(self, key):
        """Get the category name for a given key"""
        normalized_key = key.replace(" ", "") if ":" in key else key
        for category, keys in SETTINGS_CATEGORIES.items():
            normalized_keys = [k.replace(" ", "") if ":" in k else k for k in keys]
            if normalized_key in normalized_keys:
                return category
        return None

    def process_element(self, element_type, identifier, data, current_zone_id=None):
        """Process a single element yielded by the idf_parser."""
        normalized_id = identifier.replace(" ", "") if element_type == 'object' else identifier
        category = self._get_category_for_key(identifier)
        
        if not category:
            return
            
        if element_type == 'comment' and identifier in TARGET_COMMENT_KEYS:
            self.extracted_settings[category][identifier] = data
        elif element_type == 'object' and normalized_id in TARGET_OBJECT_KEYWORDS:
            formatter = self.formatters.get(normalized_id, 
                      self._format_tabular_data if any(x in normalized_id 
                      for x in ["Temperature", "Reflectance"]) else None)
            
            formatted_value = formatter(data) if formatter else (
                ", ".join(data) if isinstance(data, list) and data else "Not Found"
            )
            
            self.extracted_settings[category][identifier] = formatted_value

    def get_settings(self):
        """Returns the categorized dictionary of extracted settings."""
        return self.extracted_settings