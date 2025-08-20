import re
from typing import Dict, Any
from utils.data_loader import DataLoader
from utils.logging_config import get_logger
from .utils import safe_float

logger = get_logger(__name__)

class EPJSONObjectWrapper:
    """
    Wrapper class to make EPJSON objects behave like eppy objects
    for compatibility with existing settings parsing logic.
    """
    def __init__(self, name: str, data: Dict[str, Any]):
        self.Name = name
        self.name = name
        self._data = data
        
        # Convert all keys to attribute-like access
        for key, value in data.items():
            # Convert EPJSON keys to eppy-style attribute names
            attr_name = key.replace(' ', '_').replace('/', '_').replace('-', '_')
            setattr(self, attr_name, value)
            
            # Also try some common field name variations
            if 'version_identifier' in key.lower():
                setattr(self, 'Version_Identifier', value)
                setattr(self, 'Version', value)
            elif 'north' in key.lower() and 'axis' in key.lower():
                setattr(self, 'North_Axis', value)
            elif 'terrain' in key.lower():
                setattr(self, 'Terrain', value)
    
    def __getattr__(self, name):
        # __getattr__ is only called if the attribute doesn't exist in __dict__
        # So if we reach here, the attribute wasn't set during __init__
        
        # Try exact match in raw data first
        if name in self._data:
            return self._data[name]
        
        # Try case-insensitive match in raw data
        for key, value in self._data.items():
            if key.lower().replace(' ', '_').replace('/', '_').replace('-', '_') == name.lower():
                return value
                
        # Raise AttributeError if not found (so hasattr() works correctly)
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

class SettingsExtractor:
    """
    Extracts settings and simulation parameters from IDF files using a DataLoader instance.
    """
    def __init__(self, data_loader: DataLoader):
        self.data_loader = data_loader
        self.extracted_settings = {}
        self.initialize_settings()
        self._setup_mappings()

    def initialize_settings(self) -> None:
        """
        Initialize the settings dictionary with default values.
        """
        self.extracted_settings = {
            'designbuilder': {
                'version': None,
                'date': None,
                'time': None,
                'geometry_convention': None,
                'zone_geometry_surface_areas': None,
                'zone_volume_calculation': None,
                'zone_floor_area_calculation': None,
                'window_wall_ratio': None
            },
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
            'algorithms': {
                'surface_convection_inside': None,
                'surface_convection_outside': None,
                'heat_balance': None
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
                'weather_file': None,
                'shadow_calculation': {
                    'shading_calculation_method': None,
                    'shading_calculation_update_frequency_method': None,
                    'shading_calculation_update_frequency': None,
                    'maximum_figures_in_shadow_overlap_calculations': None,
                    'polygon_clipping_algorithm': None,
                    'pixel_counting_resolution': None,
                    'sky_diffuse_modeling_algorithm': None
                }
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
            },
            'SHADOWCALCULATION': {
                'Shading_Calculation_Method': ('simulation', 'shadow_calculation', 'shading_calculation_method'),
                'Shading_Calculation_Update_Frequency_Method': ('simulation', 'shadow_calculation', 'shading_calculation_update_frequency_method'),
                'Shading_Calculation_Update_Frequency': ('simulation', 'shadow_calculation', 'shading_calculation_update_frequency'),
                'Maximum_Figures_in_Shadow_Overlap_Calculations': ('simulation', 'shadow_calculation', 'maximum_figures_in_shadow_overlap_calculations'),
                'Polygon_Clipping_Algorithm': ('simulation', 'shadow_calculation', 'polygon_clipping_algorithm'),
                'Pixel_Counting_Resolution': ('simulation', 'shadow_calculation', 'pixel_counting_resolution'),
                'Sky_Diffuse_Modeling_Algorithm': ('simulation', 'shadow_calculation', 'sky_diffuse_modeling_algorithm')
            },
            'SURFACECONVECTIONALGORITHM:INSIDE': {
                'Algorithm': ('algorithms', 'surface_convection_inside')
            },
            'SURFACECONVECTIONALGORITHM:OUTSIDE': {
                'Algorithm': ('algorithms', 'surface_convection_outside')
            },
            'HEATBALANCEALGORITHM': {
                'Algorithm': ('algorithms', 'heat_balance')
            }
        }

    def _parse_designbuilder_comments(self) -> None:
        """
        Parse DesignBuilder metadata comments from the beginning of the IDF file.
        """
        idf_file_path = self.data_loader.get_idf_path()
        if not idf_file_path:
            return

        try:
            with open(idf_file_path, 'r', encoding='utf-8') as f:
                lines_to_check = 20
                lines = [f.readline() for _ in range(lines_to_check)]

            db_settings = self.extracted_settings['designbuilder']

            for line in lines:
                line = line.strip()
                if not line.startswith('!'):
                    if len(line) > 0:
                         break
                    else:
                         continue

                if "File generated by DesignBuilder" in line:
                    match = re.search(r'DesignBuilder - (\S+)\s+(\S+)\s+-\s+(\S+)', line)
                    if match:
                        db_settings['version'] = match.group(1)
                        db_settings['date'] = match.group(2)
                        db_settings['time'] = match.group(3)
                    continue

                parts = line[1:].split(':', 1)
                if len(parts) == 2:
                    key = parts[0].strip().lower().replace(' ', '_').replace('_template', '')
                    value = parts[1].strip()

                    if "geometry_convention" in key:
                        db_settings['geometry_convention'] = value
                    elif "zone_geometry_and_surface_areas" in key:
                        db_settings['zone_geometry_surface_areas'] = value
                    elif "zone_volume_calculation_method" in key:
                        db_settings['zone_volume_calculation'] = value
                    elif "zone_floor_area_calculation_method" in key:
                        db_settings['zone_floor_area_calculation'] = value
                    elif "window_to_wall_ratio_method" in key:
                        db_settings['window_wall_ratio'] = value

        except FileNotFoundError:
            pass
        except Exception as e:
            pass

    def process_idf(self) -> None:
        """
        Process the loaded EPJSON model from DataLoader to extract settings.
        This process will extract settings from various objects in the EPJSON file.
        """
        self._parse_designbuilder_comments()

        epjson_data = self.data_loader.get_idf()
        if not epjson_data:
            return

        try:
            # Process each object type from EPJSON
            object_types_to_process = [
                'Version', 'Building', 'Site:Location', 'SizingPeriod:DesignDay',
                'Site:GroundTemperature:BuildingSurface', 'SimulationControl',
                'RunPeriod', 'Timestep', 'Site:GroundTemperature:Deep',
                'Site:GroundTemperature:Shallow', 'Site:GroundTemperature:FCfactorMethod',
                'Site:GroundReflectance', 'Site:GroundReflectance:SnowModifier',
                'ConvergenceLimits', 'ShadowCalculation',
                'SurfaceConvectionAlgorithm:Inside', 'SurfaceConvectionAlgorithm:Outside',
                'HeatBalanceAlgorithm'
            ]

            for obj_type in object_types_to_process:
                if obj_type in epjson_data:
                    for obj_name, obj_data in epjson_data[obj_type].items():
                        # Create a compatibility wrapper that mimics eppy object behavior
                        obj_wrapper = EPJSONObjectWrapper(obj_name, obj_data)
                        self.process_idf_object(obj_type.upper().replace(':', ':'), obj_wrapper)

        except Exception as e:
            pass

    def _safe_getattr(self, obj, attr_name: str, default=None):
        """Safely get attribute from object with optional type conversion."""
        has_attr = hasattr(obj, attr_name)
        
        if has_attr:
            value = getattr(obj, attr_name, default)
            # Convert to float if it looks numeric
            if isinstance(value, str) and value.replace('.', '').replace('-', '').isdigit():
                return safe_float(value, default)
            return value
        
        # Also check if it's in the raw data
        if hasattr(obj, '_data') and attr_name in obj._data:
            value = obj._data[attr_name]
            return value
            
        return default
    
    def process_idf_object(self, obj_type: str, obj) -> None:
        """
        Process a single IDF object and extract relevant settings.

        Args:
            obj_type: Type of the IDF object (e.g., 'BUILDING', 'SITE:LOCATION')
            obj: The IDF object to process
        """
        if obj_type not in self._settings_map:
            return

        if obj_type == 'VERSION':
            # Try different possible field names for version
            version_identifier = self._safe_getattr(obj, 'Version_Identifier')
            version_identifier_lower = self._safe_getattr(obj, 'version_identifier')
            version = self._safe_getattr(obj, 'Version')
            
            final_version = version_identifier or version_identifier_lower or version or obj.__dict__.get('Version_Identifier')
            
            self.extracted_settings['version']['energyplus'] = final_version
            return

        if obj_type == 'RUNPERIOD':
            run_period = self.extracted_settings['simulation']['run_period']
            run_period['location'] = self._safe_getattr(obj, 'Name')
            run_period['start_month'] = self._safe_getattr(obj, 'Begin_Month')
            run_period['start_day'] = self._safe_getattr(obj, 'Begin_Day_of_Month')
            run_period['end_month'] = self._safe_getattr(obj, 'End_Month')
            run_period['end_day'] = self._safe_getattr(obj, 'End_Day_of_Month')
            run_period['use_weather_file_holidays_and_special_days'] = self._safe_getattr(obj, 'Use_Weather_File_Holidays_and_Special_Days')
            run_period['use_weather_file_rain'] = self._safe_getattr(obj, 'Use_Weather_File_Rain_Indicators')
            run_period['use_weather_file_snow'] = self._safe_getattr(obj, 'Use_Weather_File_Snow_Indicators')
            run_period['treat_weather_as_actual'] = self._safe_getattr(obj, 'Treat_Weather_as_Actual')
            return

        if obj_type == 'SIMULATIONCONTROL':
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

        if obj_type == 'SIZINGPERIOD:DESIGNDAY':
            self._handle_design_day(obj)
            return

        if obj_type in [
            'SITE:GROUNDTEMPERATURE:BUILDINGSURFACE',
            'SITE:GROUNDTEMPERATURE:DEEP',
            'SITE:GROUNDTEMPERATURE:SHALLOW',
            'SITE:GROUNDTEMPERATURE:FCFACTORMETHOD'
        ]:
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

            if obj_type == 'SITE:GROUNDTEMPERATURE:BUILDINGSURFACE':
                self.extracted_settings['site']['ground_temperature'] = temperature_dict
            elif obj_type == 'SITE:GROUNDTEMPERATURE:DEEP':
                self.extracted_settings['site']['ground_temp_deep'] = temperature_dict
            elif obj_type == 'SITE:GROUNDTEMPERATURE:SHALLOW':
                self.extracted_settings['site']['ground_temp_shallow'] = temperature_dict
            elif obj_type == 'SITE:GROUNDTEMPERATURE:FCFACTORMETHOD':
                self.extracted_settings['site']['ground_temp_fcfactor'] = temperature_dict
            return

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
            obj: The SizingPeriod:DesignDay IDF object
        """
        try:
            name = str(obj.Name)
            name_lower = name.lower()

            day_data = {
                'name': name,
                'month': int(obj.Month),
                'day': int(obj.Day_of_Month),
                'temp': float(obj.Maximum_Dry_Bulb_Temperature),
                'humidity': float(obj.Humidity_Condition_Day_Schedule_Name) if hasattr(obj, 'Humidity_Condition_Day_Schedule_Name') else None
            }

            self.extracted_settings['simulation']['design_day'] = day_data

            if 'winter' in name_lower or 'heat' in name_lower:
                self.extracted_settings['simulation']['sizing_zone'] = 'winter'
            elif 'summer' in name_lower or 'cool' in name_lower:
                self.extracted_settings['simulation']['sizing_zone'] = 'summer'
        except Exception as e:
            pass

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
