"""
Extracts settings and simulation parameters from IDF files.
Uses DataLoader for cached access to IDF data.
"""
from typing import Dict, Any, Optional
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
        
    def initialize_settings(self) -> None:
        """
        Initialize the settings dictionary with default values.
        Remove sizing section and focus on IDF settings specifically mentioned.
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
            'site': {
                'terrain': None,
                'ground_temperature': {},
                'ground_temp_deep': {},
                'ground_temp_shallow': {},
                'ground_temp_fcfactor': {},
                'ground_reflectance': {},
                'ground_reflectance_snow_modifier': {}
            },
            'simulation': {
                'north': None,
                'time_step': None,
                'run_period': {
                    'location': None,
                    'start_month': None,
                    'start_day': None,
                    'end_month': None,
                    'end_day': None,
                    'use_weather_file_holidays': None,
                    'use_weather_file_rain': None,
                    'use_weather_file_snow': None,
                    'treat_weather_as_actual': None
                },
                'convergence_min_timestep': None,
                'convergence_max_hvac_iterations': None,
                'sizing_zone': None,
                'sizing_system': None,
                'sizing_plant': None,
                'design_day': None,
                'weather_file': None
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
                'January_Ground_Temperature': ('site', 'ground_temperature')
            },
            'SITE:GROUNDTEMPERATURE:DEEP': {
                'January_Ground_Temperature': ('site', 'ground_temp_deep'),
                'February_Ground_Temperature': ('site', 'ground_temp_deep'),
                'March_Ground_Temperature': ('site', 'ground_temp_deep'),
                'April_Ground_Temperature': ('site', 'ground_temp_deep'),
                'May_Ground_Temperature': ('site', 'ground_temp_deep'),
                'June_Ground_Temperature': ('site', 'ground_temp_deep'),
                'July_Ground_Temperature': ('site', 'ground_temp_deep'),
                'August_Ground_Temperature': ('site', 'ground_temp_deep'),
                'September_Ground_Temperature': ('site', 'ground_temp_deep'),
                'October_Ground_Temperature': ('site', 'ground_temp_deep'),
                'November_Ground_Temperature': ('site', 'ground_temp_deep'),
                'December_Ground_Temperature': ('site', 'ground_temp_deep')
            },
            'SITE:GROUNDTEMPERATURE:SHALLOW': {
                'January_Ground_Temperature': ('site', 'ground_temp_shallow'),
                'February_Ground_Temperature': ('site', 'ground_temp_shallow'),
                'March_Ground_Temperature': ('site', 'ground_temp_shallow'),
                'April_Ground_Temperature': ('site', 'ground_temp_shallow'),
                'May_Ground_Temperature': ('site', 'ground_temp_shallow'),
                'June_Ground_Temperature': ('site', 'ground_temp_shallow'),
                'July_Ground_Temperature': ('site', 'ground_temp_shallow'),
                'August_Ground_Temperature': ('site', 'ground_temp_shallow'),
                'September_Ground_Temperature': ('site', 'ground_temp_shallow'),
                'October_Ground_Temperature': ('site', 'ground_temp_shallow'),
                'November_Ground_Temperature': ('site', 'ground_temp_shallow'),
                'December_Ground_Temperature': ('site', 'ground_temp_shallow')
            },
            'SITE:GROUNDTEMPERATURE:FCFACTORMETHOD': {
                'January_Ground_Temperature': ('site', 'ground_temp_fcfactor'),
                'February_Ground_Temperature': ('site', 'ground_temp_fcfactor'),
                'March_Ground_Temperature': ('site', 'ground_temp_fcfactor'),
                'April_Ground_Temperature': ('site', 'ground_temp_fcfactor'),
                'May_Ground_Temperature': ('site', 'ground_temp_fcfactor'),
                'June_Ground_Temperature': ('site', 'ground_temp_fcfactor'),
                'July_Ground_Temperature': ('site', 'ground_temp_fcfactor'),
                'August_Ground_Temperature': ('site', 'ground_temp_fcfactor'),
                'September_Ground_Temperature': ('site', 'ground_temp_fcfactor'),
                'October_Ground_Temperature': ('site', 'ground_temp_fcfactor'),
                'November_Ground_Temperature': ('site', 'ground_temp_fcfactor'),
                'December_Ground_Temperature': ('site', 'ground_temp_fcfactor')
            },
            'SITE:GROUNDREFLECTANCE': {
                'January_Ground_Reflectance': ('site', 'ground_reflectance'),
                'February_Ground_Reflectance': ('site', 'ground_reflectance'),
                'March_Ground_Reflectance': ('site', 'ground_reflectance'),
                'April_Ground_Reflectance': ('site', 'ground_reflectance'),
                'May_Ground_Reflectance': ('site', 'ground_reflectance'),
                'June_Ground_Reflectance': ('site', 'ground_reflectance'),
                'July_Ground_Reflectance': ('site', 'ground_reflectance'),
                'August_Ground_Reflectance': ('site', 'ground_reflectance'),
                'September_Ground_Reflectance': ('site', 'ground_reflectance'),
                'October_Ground_Reflectance': ('site', 'ground_reflectance'),
                'November_Ground_Reflectance': ('site', 'ground_reflectance'),
                'December_Ground_Reflectance': ('site', 'ground_reflectance')
            },
            'SITE:GROUNDREFLECTANCE:SNOWMODIFIER': {
                'Ground_Reflected_Solar_Modifier': ('site', 'ground_reflectance_snow_modifier'),
                'Daylighting_Ground_Reflected_Solar_Modifier': ('site', 'ground_reflectance_snow_modifier')
            },
            'SIMULATIONCONTROL': {
                'Run_Simulation_for_Sizing_Periods': ('simulation', 'sizing_zone'),
                'Run_Simulation_for_Weather_File_Run_Periods': ('simulation', 'weather_file')
            },
            'RUNPERIOD': {
                'Begin_Month': ('simulation', 'run_period', 'start_month'),
                'Begin_Day_of_Month': ('simulation', 'run_period', 'start_day'),
                'End_Month': ('simulation', 'run_period', 'end_month'),
                'End_Day_of_Month': ('simulation', 'run_period', 'end_day'),
                'Use_Weather_File_Holidays/Special_Days': ('simulation', 'run_period', 'use_weather_file_holidays'),
                'Use_Weather_File_Rain_Indicators': ('simulation', 'run_period', 'use_weather_file_rain'),
                'Use_Weather_File_Snow_Indicators': ('simulation', 'run_period', 'use_weather_file_snow'),
                'Treat_Weather_as_Actual': ('simulation', 'run_period', 'treat_weather_as_actual')
            },
            'TIMESTEP': {
                'Number_of_Timesteps_per_Hour': ('simulation', 'time_step')
            },
            'CONVERGENCELIMITS': {
                'Minimum_System_Time_Step': ('simulation', 'convergence_min_timestep'),
                'Maximum_HVAC_Iterations': ('simulation', 'convergence_max_hvac_iterations')
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
                    
            # Add new objects for extraction
            if 'SITE:GROUNDTEMPERATURE:DEEP' in idf.idfobjects:
                for obj in idf.idfobjects['SITE:GROUNDTEMPERATURE:DEEP']:
                    self.process_eppy_object('SITE:GROUNDTEMPERATURE:DEEP', obj)
            if 'SITE:GROUNDTEMPERATURE:SHALLOW' in idf.idfobjects:
                for obj in idf.idfobjects['SITE:GROUNDTEMPERATURE:SHALLOW']:
                    self.process_eppy_object('SITE:GROUNDTEMPERATURE:SHALLOW', obj)
            if 'SITE:GROUNDTEMPERATURE:FCFACTORMETHOD' in idf.idfobjects:
                for obj in idf.idfobjects['SITE:GROUNDTEMPERATURE:FCFACTORMETHOD']:
                    self.process_eppy_object('SITE:GROUNDTEMPERATURE:FCFACTORMETHOD', obj)
            if 'SITE:GROUNDREFLECTANCE' in idf.idfobjects:
                for obj in idf.idfobjects['SITE:GROUNDREFLECTANCE']:
                    self.process_eppy_object('SITE:GROUNDREFLECTANCE', obj)
            if 'SITE:GROUNDREFLECTANCE:SNOWMODIFIER' in idf.idfobjects:
                for obj in idf.idfobjects['SITE:GROUNDREFLECTANCE:SNOWMODIFIER']:
                    self.process_eppy_object('SITE:GROUNDREFLECTANCE:SNOWMODIFIER', obj)
            if 'CONVERGENCELIMITS' in idf.idfobjects:
                for obj in idf.idfobjects['CONVERGENCELIMITS']:
                    self.process_eppy_object('CONVERGENCELIMITS', obj)
                    
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
            
        # Special handling for specific object types
        if obj_type == 'VERSION':
            if hasattr(obj, 'Version_Identifier'):
                self.extracted_settings['version']['energyplus'] = getattr(obj, 'Version_Identifier')
            return
            
        if obj_type == 'RUNPERIOD':
            # Extract all RunPeriod fields
            self.extracted_settings['simulation']['run_period']['location'] = getattr(obj, 'Name', None) if hasattr(obj, 'Name') else None
            self.extracted_settings['simulation']['run_period']['start_month'] = getattr(obj, 'Begin_Month', None) if hasattr(obj, 'Begin_Month') else None
            self.extracted_settings['simulation']['run_period']['start_day'] = getattr(obj, 'Begin_Day_of_Month', None) if hasattr(obj, 'Begin_Day_of_Month') else None
            self.extracted_settings['simulation']['run_period']['end_month'] = getattr(obj, 'End_Month', None) if hasattr(obj, 'End_Month') else None
            self.extracted_settings['simulation']['run_period']['end_day'] = getattr(obj, 'End_Day_of_Month', None) if hasattr(obj, 'End_Day_of_Month') else None
            
            # Weather options
            self.extracted_settings['simulation']['run_period']['use_weather_file_holidays_and_special_days'] = getattr(obj, 'Use_Weather_File_Holidays_and_Special_Days', None) if hasattr(obj, 'Use_Weather_File_Holidays_and_Special_Days') else None
            self.extracted_settings['simulation']['run_period']['use_weather_file_rain'] = getattr(obj, 'Use_Weather_File_Rain_Indicators', None) if hasattr(obj, 'Use_Weather_File_Rain_Indicators') else None
            self.extracted_settings['simulation']['run_period']['use_weather_file_snow'] = getattr(obj, 'Use_Weather_File_Snow_Indicators', None) if hasattr(obj, 'Use_Weather_File_Snow_Indicators') else None
            self.extracted_settings['simulation']['run_period']['treat_weather_as_actual'] = getattr(obj, 'Treat_Weather_as_Actual', None) if hasattr(obj, 'Treat_Weather_as_Actual') else None
            return
        
        if obj_type == 'SIMULATIONCONTROL':
            # Extract SimulationControl fields directly
            if hasattr(obj, 'Do_Zone_Sizing_Calculation'):
                self.extracted_settings['simulation']['sizing_zone'] = getattr(obj, 'Do_Zone_Sizing_Calculation')
            if hasattr(obj, 'Do_System_Sizing_Calculation'):
                self.extracted_settings['simulation']['sizing_system'] = getattr(obj, 'Do_System_Sizing_Calculation')
            if hasattr(obj, 'Do_Plant_Sizing_Calculation'):
                self.extracted_settings['simulation']['sizing_plant'] = getattr(obj, 'Do_Plant_Sizing_Calculation')
            if hasattr(obj, 'Run_Simulation_for_Sizing_Periods'):
                self.extracted_settings['simulation']['design_day'] = getattr(obj, 'Run_Simulation_for_Sizing_Periods')
            if hasattr(obj, 'Run_Simulation_for_Weather_File_Run_Periods'):
                self.extracted_settings['simulation']['weather_file'] = getattr(obj, 'Run_Simulation_for_Weather_File_Run_Periods')
            return
            
        # Special handling for SIZINGPERIOD:DESIGNDAY
        if obj_type == 'SIZINGPERIOD:DESIGNDAY':
            self._handle_design_day(obj)
            return
            
        # For ground temperature objects, store monthly values as a dictionary
        if obj_type in [
            'SITE:GROUNDTEMPERATURE:BUILDINGSURFACE',
            'SITE:GROUNDTEMPERATURE:DEEP',
            'SITE:GROUNDTEMPERATURE:SHALLOW',
            'SITE:GROUNDTEMPERATURE:FCFACTORMETHOD'
        ]:
            # Process month by month
            months = [
                'January', 'February', 'March', 'April', 'May', 'June',
                'July', 'August', 'September', 'October', 'November', 'December'
            ]
            temperature_dict = {}
            for month in months:
                if "shallow" in obj_type.lower():
                    field = f'{month}_Surface_Ground_Temperature'
                elif "deep" in obj_type.lower():
                    field = f'{month}_Deep_Ground_Temperature'
                else:
                    field = f'{month}_Ground_Temperature'
                if hasattr(obj, field):
                    temperature_dict[month] = getattr(obj, field)
            
            # Determine which ground temperature dictionary to update
            if obj_type == 'SITE:GROUNDTEMPERATURE:BUILDINGSURFACE':
                self.extracted_settings['site']['ground_temperature'] = temperature_dict
            elif obj_type == 'SITE:GROUNDTEMPERATURE:DEEP':
                self.extracted_settings['site']['ground_temp_deep'] = temperature_dict
            elif obj_type == 'SITE:GROUNDTEMPERATURE:SHALLOW':
                self.extracted_settings['site']['ground_temp_shallow'] = temperature_dict
            elif obj_type == 'SITE:GROUNDTEMPERATURE:FCFACTORMETHOD':
                self.extracted_settings['site']['ground_temp_fcfactor'] = temperature_dict
            return
            
        # Handle ground reflectance similarly
        if obj_type == 'SITE:GROUNDREFLECTANCE':
            months = [
                'January', 'February', 'March', 'April', 'May', 'June',
                'July', 'August', 'September', 'October', 'November', 'December'
            ]
            reflectance_dict = {}
            for month in months:
                field = f'{month}_Ground_Reflectance'
                if hasattr(obj, field):
                    reflectance_dict[month] = getattr(obj, field)
            self.extracted_settings['site']['ground_reflectance'] = reflectance_dict
            return
            
        if obj_type == 'SITE:GROUNDREFLECTANCE:SNOWMODIFIER':
            snow_dict = {}
            if hasattr(obj, 'Ground_Reflected_Solar_Modifier'):
                snow_dict['ground'] = getattr(obj, 'Ground_Reflected_Solar_Modifier')
            if hasattr(obj, 'Daylighting_Ground_Reflected_Solar_Modifier'):
                snow_dict['daylighting'] = getattr(obj, 'Daylighting_Ground_Reflected_Solar_Modifier')
            self.extracted_settings['site']['ground_reflectance_snow_modifier'] = snow_dict
            return
            
        if obj_type == 'CONVERGENCELIMITS':
            if hasattr(obj, 'Minimum_System_Timestep'):
                self.extracted_settings['simulation']['convergence_min_timestep'] = getattr(obj, 'Minimum_System_Timestep')
            if hasattr(obj, 'Maximum_HVAC_Iterations'):
                self.extracted_settings['simulation']['convergence_max_hvac_iterations'] = getattr(obj, 'Maximum_HVAC_Iterations')
            return
            
        if obj_type == 'TIMESTEP':
            if hasattr(obj, 'Number_of_Timesteps_per_Hour'):
                self.extracted_settings['simulation']['time_step'] = getattr(obj, 'Number_of_Timesteps_per_Hour')
            return
            
        # Process regular objects using the mapping
        field_map = self._settings_map[obj_type]
        for field_name, setting_path in field_map.items():
            if hasattr(obj, field_name):
                section, key = setting_path[:2]
                if len(setting_path) == 3:
                    sub_key = setting_path[2]
                    if section not in self.extracted_settings:
                        self.extracted_settings[section] = {}
                    if key not in self.extracted_settings[section]:
                        self.extracted_settings[section][key] = {}
                    self.extracted_settings[section][key][sub_key] = getattr(obj, field_name)
                else:
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
            self.extracted_settings['simulation']['design_day'] = day_data
            
            # Determine if this is a winter or summer design day
            if 'winter' in name_lower or 'heat' in name_lower:
                self.extracted_settings['simulation']['sizing_zone'] = 'winter'
            elif 'summer' in name_lower or 'cool' in name_lower:
                self.extracted_settings['simulation']['sizing_zone'] = 'summer'
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
        
    def get_design_days(self) -> Dict[str, Any]:
        """
        Get design day data.
        
        Returns:
            Dict[str, Any]: Design day data dictionary
        """
        return self.extracted_settings.get('simulation', {}).get('design_day', {})