"""
Extracts settings and simulation parameters from IDF files.
Uses DataLoader for cached access to IDF data.
"""
from typing import Dict, Any, List, Optional
from utils.data_loader import DataLoader

class SettingsExtractor:
    """
    Extracts settings and simulation parameters from IDF files.
    Implementation details moved from DataLoader.
    """
    def __init__(self, data_loader: Optional[DataLoader] = None):
        """
        Initialize the SettingsExtractor.
        
        Args:
            data_loader: Optional DataLoader instance for accessing cached data
        """
        self.data_loader = data_loader
        self.extracted_settings = {}
        self.initialize_settings()
        self._setup_mappings()
        self._cached_settings = {}  # Cache for settings data
        
    def initialize_settings(self) -> None:
        """
        Initialize the settings dictionary with default values.
        """
        self.extracted_settings = {
            'version': {
                'energyplus': None,
                'file': None
            },
            'location': {
                'name': None,
                'latitude': None,
                'longitude': None,
                'timezone': None,
                'elevation': None
            },
            'sizing': {
                'winter_design_day': None,
                'summer_design_day': None,
                'cooling_design_temp': None,
                'heating_design_temp': None,
                'cooling_design_humidity': None,
                'heating_design_humidity': None,
                'design_days': []
            },
            'site': {
                'terrain': None,
                'gnd_temperature': None
            },
            'simulation': {
                'north': None,
                'algorithm': None,
                'time_step': None,
                'run_period': None,
                'begin_month': None,
                'begin_day': None,
                'end_month': None,
                'end_day': None
            }
        }
    
    def _setup_mappings(self) -> None:
        """
        Setup field mappings between IDF object fields and settings dictionary.
        Implementation details moved from DataLoader.
        """
        self._settings_map = {
            'VERSION': {
                'Version': ('version', 'energyplus')
            },
            'BUILDING': {
                'Name': ('version', 'file'),
                'North_Axis': ('simulation', 'north'),
                'Terrain': ('site', 'terrain')
            },
            'SITE:LOCATION': {
                'Name': ('location', 'name'),
                'Latitude': ('location', 'latitude'),
                'Longitude': ('location', 'longitude'),
                'Time_Zone': ('location', 'timezone'),
                'Elevation': ('location', 'elevation')
            },
            'SIZINGPERIOD:DESIGNDAY': {
                # Handled separately due to multiple instances
            },
            'SITE:GROUNDTEMPERATURE:BUILDINGSURFACE': {
                'January_Ground_Temperature': ('site', 'gnd_temperature')
            },
            'SIMULATIONCONTROL': {
                'Run_Simulation_for_Sizing_Periods': ('simulation', 'run_for_sizing'),
                'Run_Simulation_for_Weather_File_Run_Periods': ('simulation', 'run_for_weather')
            },
            'RUNPERIOD': {
                'Begin_Month': ('simulation', 'begin_month'),
                'Begin_Day_of_Month': ('simulation', 'begin_day'),
                'End_Month': ('simulation', 'end_month'),
                'End_Day_of_Month': ('simulation', 'end_day')
            },
            'TIMESTEP': {
                'Number_of_Timesteps_per_Hour': ('simulation', 'time_step')
            }
        }
        
    def process_idf(self, idf) -> None:
        """
        Process an entire IDF model to extract settings.
        This process will extract settings from various objects in the IDF file.
        
        Args:
            idf: eppy IDF object (kept for compatibility)
        """
        if not idf:
            print("Warning: No IDF object provided to process settings")
            return
            
        try:
            # Process VERSION objects
            if 'VERSION' in idf.idfobjects:
                for obj in idf.idfobjects['VERSION']:
                    self.process_eppy_object('VERSION', obj)
                    
            # Process BUILDING objects
            if 'BUILDING' in idf.idfobjects:
                for obj in idf.idfobjects['BUILDING']:
                    self.process_eppy_object('BUILDING', obj)
                    
            # Process SITE:LOCATION objects
            if 'SITE:LOCATION' in idf.idfobjects:
                for obj in idf.idfobjects['SITE:LOCATION']:
                    self.process_eppy_object('SITE:LOCATION', obj)
                    
            # Process SIZINGPERIOD:DESIGNDAY objects
            if 'SIZINGPERIOD:DESIGNDAY' in idf.idfobjects:
                for obj in idf.idfobjects['SIZINGPERIOD:DESIGNDAY']:
                    self.process_eppy_object('SIZINGPERIOD:DESIGNDAY', obj)
                    
            # Process SITE:GROUNDTEMPERATURE:BUILDINGSURFACE objects
            if 'SITE:GROUNDTEMPERATURE:BUILDINGSURFACE' in idf.idfobjects:
                for obj in idf.idfobjects['SITE:GROUNDTEMPERATURE:BUILDINGSURFACE']:
                    self.process_eppy_object('SITE:GROUNDTEMPERATURE:BUILDINGSURFACE', obj)
                    
            # Process SIMULATIONCONTROL objects
            if 'SIMULATIONCONTROL' in idf.idfobjects:
                for obj in idf.idfobjects['SIMULATIONCONTROL']:
                    self.process_eppy_object('SIMULATIONCONTROL', obj)
                    
            # Process RUNPERIOD objects
            if 'RUNPERIOD' in idf.idfobjects:
                for obj in idf.idfobjects['RUNPERIOD']:
                    self.process_eppy_object('RUNPERIOD', obj)
                    
            # Process TIMESTEP objects
            if 'TIMESTEP' in idf.idfobjects:
                for obj in idf.idfobjects['TIMESTEP']:
                    self.process_eppy_object('TIMESTEP', obj)
                    
            print("Settings extraction complete")
            
        except Exception as e:
            print(f"Error extracting settings: {str(e)}")
        
    def process_eppy_object(self, obj_type: str, obj) -> None:
        """
        Process a single eppy object and extract relevant settings.
        
        Args:
            obj_type: Type of the eppy object (e.g., 'BUILDING', 'SITE:LOCATION')
            obj: The eppy object to process
        """
        # Skip if object type not in mappings
        if obj_type not in self._settings_map:
            return
            
        # Special handling for SIZINGPERIOD:DESIGNDAY
        if obj_type == 'SIZINGPERIOD:DESIGNDAY':
            self._handle_design_day(obj)
            return
            
        # Process regular objects
        field_map = self._settings_map[obj_type]
        for field_name, setting_path in field_map.items():
            if hasattr(obj, field_name):
                section, key = setting_path
                self.extracted_settings[section][key] = getattr(obj, field_name)
                
    def _handle_design_day(self, obj) -> None:
        """
        Handle SizingPeriod:DesignDay objects, which need special handling.
        Implementation details moved from DataLoader.
        
        Args:
            obj: The SizingPeriod:DesignDay eppy object
        """
        try:
            # Get design day name and determine if winter or summer
            name = str(obj.Name)
            name_lower = name.lower()
            
            day_data = {
                'name': name,
                'month': int(obj.Month),
                'day': int(obj.Day_of_Month),
                'temp': float(obj.Maximum_Dry_Bulb_Temperature),
                'humidity': float(obj.Humidity_Condition_Day_Schedule_Name) if hasattr(obj, 'Humidity_Condition_Day_Schedule_Name') else None
            }
            
            # Store design day data
            self.extracted_settings['sizing']['design_days'].append(day_data)
            
            # Determine if this is a winter or summer design day
            if 'winter' in name_lower or 'heat' in name_lower:
                self.extracted_settings['sizing']['winter_design_day'] = name
                self.extracted_settings['sizing']['heating_design_temp'] = day_data['temp']
                self.extracted_settings['sizing']['heating_design_humidity'] = day_data['humidity']
            elif 'summer' in name_lower or 'cool' in name_lower:
                self.extracted_settings['sizing']['summer_design_day'] = name
                self.extracted_settings['sizing']['cooling_design_temp'] = day_data['temp']
                self.extracted_settings['sizing']['cooling_design_humidity'] = day_data['humidity']
        except Exception as e:
            print(f"Error processing design day {getattr(obj, 'Name', 'unknown')}: {str(e)}")
    
    def get_settings(self) -> Dict[str, Any]:
        """
        Get the extracted settings.
        
        Returns:
            Dict[str, Any]: The settings dictionary
        """
        return self.extracted_settings
        
    def get_setting(self, section: str, key: str) -> Any:
        """
        Get a specific setting value.
        
        Args:
            section: The settings section (e.g., 'location', 'simulation')
            key: The key within the section
            
        Returns:
            Any: The setting value, or None if not found
        """
        if section in self.extracted_settings and key in self.extracted_settings[section]:
            return self.extracted_settings[section][key]
        return None
        
    def get_location_settings(self) -> Dict[str, Any]:
        """
        Get location settings.
        
        Returns:
            Dict[str, Any]: The location settings
        """
        return self.extracted_settings.get('location', {})
        
    def get_simulation_settings(self) -> Dict[str, Any]:
        """
        Get simulation settings.
        
        Returns:
            Dict[str, Any]: The simulation settings
        """
        return self.extracted_settings.get('simulation', {})
        
    def get_design_days(self) -> List[Dict[str, Any]]:
        """
        Get all design days.
        
        Returns:
            List[Dict[str, Any]]: List of design day data
        """
        return self.extracted_settings.get('sizing', {}).get('design_days', [])