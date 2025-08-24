"""
DataLoader module for direct EPJSON data access.
Provides simplified data loading and retrieval functionality using EPJSON format.
Includes support for Hebrew/Unicode characters in file paths.
Replaces the eppy-based implementation with native JSON handling.
"""
from typing import Dict, Optional, List, Any
from pathlib import Path
from utils.epjson_handler import EPJSONHandler
from utils.path_utils import (
    get_data_file_path, contains_non_ascii,
    create_safe_path_for_energyplus
)
import os
import sys
import re
from utils.logging_config import get_logger
import pandas as pd

def get_energy_consumption(iso_type_input: str, area_location_input: str, area_definition_input: str) -> float:
    """
    Retrieves the energy consumption value based on ISO type, area location, and area definition.

    Args:
        iso_type_input: User's selection for ISO type (e.g., "ISO_TYPE_2017_A", "ISO_TYPE_2023_B").
        area_location_input: The descriptive string for the area type (e.g., "Ground Floor & Intermediate ceiling").
        area_definition_input: For 2017/office: 'A', 'B', 'C', 'D' (climate zones).
                              For 2023: '1', '2', '3', '4', '5', '6', '7', '8' (climate codes).

    Returns:
        The energy consumption value as a float.

    Raises:
        ValueError: If iso_type_input is invalid, area_definition_input is invalid,
                    or if data in CSV cannot be converted to float.
        FileNotFoundError: If the required model CSV file is not found.
        KeyError: If area_location_input or area_definition_input is not found in the CSV.
    """
    logger = get_logger(__name__)
    year = None
    file_name = None
    
    if "2017" in iso_type_input:
        year = 2017
        file_name = f"{year}_model.csv"
    elif "2023" in iso_type_input:
        year = 2023
        file_name = f"{year}_model.csv"
    elif "office" in iso_type_input.lower():
        file_name = "office_model.csv"
    else:
        raise ValueError(f"Invalid ISO type format: {iso_type_input}. Cannot determine year or office type.")
    
    # Validate area_definition_input based on year
    if year == 2023:
        # For 2023, expect climate codes 1-8
        if not area_definition_input or area_definition_input not in ['1', '2', '3', '4', '5', '6', '7', '8']:
            raise ValueError(f"Invalid area definition for 2023: '{area_definition_input}'. Must be 1, 2, 3, 4, 5, 6, 7, or 8.")
    else:
        # For 2017 and office, expect climate zones A-D
        if not area_definition_input or area_definition_input.upper() not in ['A', 'B', 'C', 'D']:
            raise ValueError(f"Invalid area definition: '{area_definition_input}'. Must be A, B, C, or D.")

    # Use robust path utility for model CSV files
    file_path = get_data_file_path(file_name)

    try:
        df = pd.read_csv(file_path)
        if df.empty:
            raise ValueError(f"CSV file {file_path} is empty.")

        if 'area_location' in df.columns:
            df = df.set_index('area_location')
        elif df.columns[0]:
            df = df.set_index(df.columns[0])
        else:
            raise ValueError(f"CSV file {file_path} has no columns to set as index.")

    except FileNotFoundError:
        raise
    except pd.errors.EmptyDataError:
       raise ValueError(f"CSV file {file_path} is empty or not valid CSV.")
    except Exception as e:
        raise ValueError(f"Error reading or parsing CSV file {file_path}: {e}")

    if area_location_input not in df.index:
        available_indices = list(df.index)
        if len(available_indices) > 20: available_indices = available_indices[:20] + ['...']
        raise KeyError(f"Area location '{area_location_input}' not found in index of {file_path}. Available index values (sample): {available_indices}")

    # Set target column based on year
    if year == 2023:
        target_column = area_definition_input  # Use climate code directly (1, 2, 3, etc.)
    else:
        target_column = area_definition_input.upper()  # Use climate zone letter (A, B, C, D)
    
    if target_column not in df.columns:
        raise KeyError(f"Area definition column '{target_column}' not found in columns of {file_path}. Available columns: {list(df.columns)}")

    try:
        value_str = df.loc[area_location_input, target_column]
    except KeyError as e:
        raise KeyError(f"Data not found for location '{area_location_input}' and definition '{target_column}' in {file_path}. Original error: {e}")
    except Exception as e:
        raise RuntimeError(f"Unexpected error during data lookup in {file_path} for loc='{area_location_input}', col='{target_column}'. Error: {e}")

    try:
        result = float(value_str)
        # Energy consumption data retrieved
        return result
    except ValueError:
        raise ValueError(f"Invalid data format in CSV. Cannot convert '{value_str}' to float for location '{area_location_input}', definition '{area_definition_input.upper()}' in {file_path}")


logger = get_logger(__name__)


class IDFObjectCompatibilityWrapper:
    """
    General compatibility wrapper to make EPJSON data compatible with eppy-based parsers.
    Provides the .Name and other attributes expected by existing parsers.
    """
    
    def __init__(self, object_id: str, object_data: Dict[str, Any]):
        self.Name = object_id
        self.name = object_id
        self.object_id = object_id
        self.object_data = object_data
        
        # Add all object data as attributes
        for key, value in object_data.items():
            setattr(self, key, value)
            
        # Add specific eppy-style field name mappings for compatibility
        self._add_eppy_field_mappings()
    
    def _add_eppy_field_mappings(self):
        """Add eppy-style field names for compatibility with existing parsers."""
        # Map EPJSON snake_case to eppy PascalCase field names
        field_mappings = {
            # Surface fields
            'outside_boundary_condition_object': 'Outside_Boundary_Condition_Object',
            'outside_boundary_condition': 'Outside_Boundary_Condition',
            'construction_name': 'Construction_Name',
            'surface_type': 'Surface_Type',
            'zone_name': 'Zone_Name',
            'building_surface_name': 'Building_Surface_Name',
            
            # Window/Frame fields  
            'frame_and_divider_name': 'Frame_and_Divider_Name',
            
            # Schedule fields
            'schedule_name': 'Schedule_Name',
            'availability_schedule_name': 'Availability_Schedule_Name',
            
            # Lighting fields
            'zone_or_space_name': 'Zone_Name',
            'lighting_control_type': 'Lighting_Control_Type',
            'number_of_stepped_control_steps': 'Number_of_Stepped_Control_Steps',
            'minimum_input_power_fraction_for_continuous_or_continuousoff_dimming_control': 'Minimum_Input_Power_Fraction_for_Continuous_or_ContinuousOff_Dimming_Control',
            'minimum_light_output_fraction_for_continuous_or_continuousoff_dimming_control': 'Minimum_Light_Output_Fraction_for_Continuous_or_ContinuousOff_Dimming_Control',
            'x_coordinate_of_reference_point': 'XCoordinate_of_Reference_Point',
            'y_coordinate_of_reference_point': 'YCoordinate_of_Reference_Point',
            'z_coordinate_of_reference_point': 'ZCoordinate_of_Reference_Point',
            'xcoordinate_of_reference_point': 'XCoordinate_of_Reference_Point',
            'ycoordinate_of_reference_point': 'YCoordinate_of_Reference_Point',
            'zcoordinate_of_reference_point': 'ZCoordinate_of_Reference_Point',
            
            # Load fields
            'design_flow_rate': 'Design_Flow_Rate',
            
            # Settings/Version fields
            'version_identifier': 'Version_Identifier',
            'begin_month': 'Begin_Month',
            'begin_day_of_month': 'Begin_Day_of_Month',
            'end_month': 'End_Month',
            'end_day_of_month': 'End_Day_of_Month',
            'use_weather_file_holidays_and_special_days': 'Use_Weather_File_Holidays_and_Special_Days',
            'use_weather_file_rain_indicators': 'Use_Weather_File_Rain_Indicators',
            'use_weather_file_snow_indicators': 'Use_Weather_File_Snow_Indicators',
            'treat_weather_as_actual': 'Treat_Weather_as_Actual',
            'do_zone_sizing_calculation': 'Do_Zone_Sizing_Calculation',
            'do_system_sizing_calculation': 'Do_System_Sizing_Calculation',
            'do_plant_sizing_calculation': 'Do_Plant_Sizing_Calculation',
            'run_simulation_for_sizing_periods': 'Run_Simulation_for_Sizing_Periods',
            'run_simulation_for_weather_file_run_periods': 'Run_Simulation_for_Weather_File_Run_Periods',
            'ground_reflected_solar_modifier': 'Ground_Reflected_Solar_Modifier',
            'daylighting_ground_reflected_solar_modifier': 'Daylighting_Ground_Reflected_Solar_Modifier',
            'minimum_system_timestep': 'Minimum_System_Timestep',
            'maximum_hvac_iterations': 'Maximum_HVAC_Iterations',
            'month': 'Month',
            'day_of_month': 'Day_of_Month',
            'maximum_dry_bulb_temperature': 'Maximum_Dry_Bulb_Temperature',
            'humidity_condition_day_schedule_name': 'Humidity_Condition_Day_Schedule_Name'
        }
        
        for epjson_field, eppy_field in field_mappings.items():
            if hasattr(self, epjson_field):
                setattr(self, eppy_field, getattr(self, epjson_field))


class ScheduleCompatibilityWrapper(IDFObjectCompatibilityWrapper):
    """
    Compatibility wrapper to make EPJSON schedule data compatible with eppy-based parsers.
    Provides the .fieldvalues attribute expected by existing schedule parsers.
    """
    
    def __init__(self, schedule_id: str, schedule_data: Dict[str, Any]):
        super().__init__(schedule_id, schedule_data)
        self.schedule_id = schedule_id
        
        # Create fieldvalues list from schedule data
        self.fieldvalues = self._build_fieldvalues()
    
    def _build_fieldvalues(self) -> List[str]:
        """Build fieldvalues list from EPJSON schedule data for parser compatibility."""
        fieldvalues = []
        
        # Add basic schedule information
        fieldvalues.append(self.name)  # Schedule name
        fieldvalues.append(self.object_data.get('schedule_type_limits_name', ''))  # Schedule type
        
        # Extract field values from EPJSON data format
        field_count = 0
        
        # EPJSON format stores rules in data array with field property
        if 'data' in self.object_data and isinstance(self.object_data['data'], list):
            for data_item in self.object_data['data']:
                if isinstance(data_item, dict) and 'field' in data_item:
                    field_value = data_item['field']
                    # Include all field values, even 0 and empty strings (they are meaningful in schedules)
                    if field_value is not None:
                        fieldvalues.append(str(field_value))
                        field_count += 1
        else:
            # Fallback to old field_1, field_2 format for compatibility
            field_index = 1
            while f"field_{field_index}" in self.object_data:
                field_value = self.object_data[f"field_{field_index}"]
                if field_value and str(field_value).strip():
                    fieldvalues.append(str(field_value))
                    field_count += 1
                field_index += 1
        
        
        return fieldvalues


AREA_ID_REGEX = re.compile(r"^\d{2}")

SETTINGS_OBJECT_TYPES = [
    "Version",
    "RunPeriod",
    "Timestep",
    "ConvergenceLimits",
    "SimulationControl",
    "Site:Location",
    "Site:GroundTemperature:BuildingSurface",
    "Site:GroundTemperature:Deep",
    "Site:GroundTemperature:Shallow",
    "Site:GroundTemperature:FCfactorMethod",
    "Site:GroundReflectance",
    "Site:GroundReflectance:SnowModifier"
]

def safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert a value to float, returning a default if conversion fails."""
    if value is None or value == '':
        return default
    try:
        if hasattr(value, 'item'):
            return float(value.item())
        return float(value)
    except (ValueError, TypeError, AttributeError):
        return default

class DataLoader:
    """DataLoader for caching and retrieving EPJSON data."""
    def __init__(self, energyplus_path: Optional[str] = None):
        self._epjson_data = None
        self._epjson_handler = None
        self._file_path = None
        self._energyplus_path = energyplus_path
        self._loaded_sections = set()
        self._zones_cache = {}
        self._hvac_zones_cache = []
        self._surfaces_cache = {}
        self._materials_cache = {}
        self._constructions_cache = {}
        self._constructions_glazing_cache = {}
        self._schedules_cache = {}
        self._schedule_rules_cache = {}
        self._people_cache = {}
        self._lights_cache = {}
        self._exterior_lights_cache = []
        self._equipment_cache = {}
        self._infiltration_cache = {}
        self._ventilation_cache = {}
        self._outdoor_air_spec_cache = {}
        self._windows_cache = {}
        self._window_glazing_cache = {}
        self._window_gas_cache = {}
        self._window_shade_cache = {}
        self._window_simple_glazing_cache = {}
        self._all_materials_cache_complete = {}
        self._window_shading_control_cache = {}
        self._frame_divider_cache = {}
        self._daylighting_controls_cache = {}
        self._daylighting_reference_point_cache = {}
        self._ideal_loads_cache = {}
        # Track when detailed logs were last shown to prevent spam
        self._last_detailed_log = {}
        import time
        self._log_cooldown = 30  # seconds between detailed logs

    def _should_log_details(self, method_name: str) -> bool:
        """Check if detailed logging should be shown for a method to prevent spam."""
        # Disable verbose logging to reduce log noise
        return False

    def _convert_individual_vertices_to_array(self, surface_data) -> list:
        """
        Convert individual vertex coordinate fields to vertices array format.
        EPJSON fenestration surfaces store vertices as individual fields like:
        vertex_1_x_coordinate, vertex_1_y_coordinate, vertex_1_z_coordinate, etc.
        
        Args:
            surface_data: Surface data dictionary with individual vertex fields
            
        Returns:
            list: Array of vertex dictionaries compatible with _calculate_surface_area_from_vertices
        """
        vertices = []
        try:
            vertex_num = 1
            while f"vertex_{vertex_num}_x_coordinate" in surface_data:
                vertex = {
                    "vertex_x_coordinate": safe_float(surface_data.get(f"vertex_{vertex_num}_x_coordinate", 0.0)),
                    "vertex_y_coordinate": safe_float(surface_data.get(f"vertex_{vertex_num}_y_coordinate", 0.0)),
                    "vertex_z_coordinate": safe_float(surface_data.get(f"vertex_{vertex_num}_z_coordinate", 0.0))
                }
                vertices.append(vertex)
                vertex_num += 1
            return vertices
        except Exception as e:
            return []

    def _calculate_surface_area_from_vertices(self, vertices) -> float:
        """
        Calculate the area of a surface from its vertices using the shoelace formula.
        Assumes vertices form a simple polygon in 3D space.
        
        Args:
            vertices: List of vertex dictionaries with x, y, z coordinates
            
        Returns:
            float: Calculated area in square meters
        """
        try:
            if not vertices or len(vertices) < 3:
                return 0.0
            
            # Extract coordinates
            points = []
            for vertex in vertices:
                x = safe_float(vertex.get("vertex_x_coordinate", 0.0))
                y = safe_float(vertex.get("vertex_y_coordinate", 0.0))
                z = safe_float(vertex.get("vertex_z_coordinate", 0.0))
                points.append((x, y, z))
            
            # For simple rectangular surfaces, use cross product method
            if len(points) == 4:
                # Vector from point 0 to point 1
                v1 = (points[1][0] - points[0][0], 
                      points[1][1] - points[0][1], 
                      points[1][2] - points[0][2])
                
                # Vector from point 0 to point 3 (or point 2, depending on vertex order)
                v2 = (points[3][0] - points[0][0], 
                      points[3][1] - points[0][1], 
                      points[3][2] - points[0][2])
                
                # Cross product gives area vector
                cross_x = v1[1] * v2[2] - v1[2] * v2[1]
                cross_y = v1[2] * v2[0] - v1[0] * v2[2]
                cross_z = v1[0] * v2[1] - v1[1] * v2[0]
                
                # Magnitude of cross product is area
                area = 0.5 * (cross_x**2 + cross_y**2 + cross_z**2)**0.5
                return area
            
            # For non-rectangular surfaces, use shoelace formula (2D projection)
            # Project to XY plane for simplicity
            xy_points = [(p[0], p[1]) for p in points]
            
            # Shoelace formula
            n = len(xy_points)
            area = 0.0
            for i in range(n):
                j = (i + 1) % n
                area += xy_points[i][0] * xy_points[j][1]
                area -= xy_points[j][0] * xy_points[i][1]
            
            return abs(area) / 2.0
            
        except Exception as e:
            # Return 0 if calculation fails
            return 0.0

    def ensure_output_variables(self, file_path: str = None, energyplus_path: Optional[str] = None) -> bool:
        """Ensure required output variables exist in the EPJSON file before running the simulation.
        Use this method before running the simulation to make sure energy rating variables are present.
        Handles Unicode/Hebrew characters in file paths.

        Args:
            file_path: Path to the file (IDF or EPJSON). If None, uses the previously loaded file.
            energyplus_path: Optional path to EnergyPlus installation

        Returns:
            bool: True if output variables were successfully checked/added, False otherwise
        """
        if file_path and (not self._epjson_data or self._file_path != file_path):
            self.load_file(file_path, energyplus_path)

        if self._epjson_data:
            self._epjson_handler.ensure_output_variables(self._epjson_data)
            # Save the updated EPJSON
            if self._file_path.endswith('.epJSON'):
                self._epjson_handler.save_epjson(self._epjson_data, self._file_path)
            return True
        return False

    def load_file(self, file_path: str, energyplus_path: Optional[str] = None) -> None:
        """
        Load file (IDF or EPJSON) and cache raw data.
        Handles Unicode/Hebrew characters in file paths.

        Args:
            file_path: Path to the file (can be .idf or .epJSON)
            energyplus_path: Optional path to EnergyPlus installation

        Raises:
            FileNotFoundError: If file not found
        """
        if not Path(file_path).exists():
            raise FileNotFoundError(f"File not found at '{file_path}'")

        try:
            # Initialize EPJSON handler
            if not self._epjson_handler:
                self._epjson_handler = EPJSONHandler(energyplus_path or self._energyplus_path)
            
            # Load or convert file to EPJSON
            self._epjson_data, actual_path = self._epjson_handler.load_or_convert_file(file_path)
            self._file_path = actual_path
            self._loaded_sections = {'zones', 'surfaces', 'materials', 'constructions', 'schedules'}

            # Ensure output variables
            self._epjson_handler.ensure_output_variables(self._epjson_data)
            
            # Cache all data
            self._cache_schedules()
            self._cache_zones()
            self._cache_surfaces()
            self._cache_materials()
            self._build_all_materials_cache()
            self._cache_constructions()
            self._cache_loads()
            self._cache_window_shading_controls()
            self._cache_frame_dividers()
            self._cache_daylighting()
            self._cache_outdoor_air_specifications()
            self._cache_ideal_loads()
            
            # Successfully loaded file

        except Exception as e:
            logger.error(f"Error loading file '{file_path}': {str(e)}")
            # Try to provide more helpful error messages
            if "EnergyPlus conversion failed" in str(e):
                logger.error(f"The IDF file '{file_path}' contains errors that prevent conversion to EPJSON.")
                logger.error("Please check the IDF file for:")
                logger.error("- Version compatibility (file may be too old/new)")
                logger.error("- Missing required properties or invalid values")
                logger.error("- Malformed surface definitions or coordinates")
                logger.error("Check the EnergyPlus error file (eplusout.err) for detailed error information.")
            raise

    def _cache_zones(self) -> None:
        """Cache raw zone data from EPJSON."""
        if not self._epjson_data:
            return
        
        self._zones_cache.clear()
        self._hvac_zones_cache.clear()
        
        zones = self._epjson_data.get('Zone', {})
        
        for zone_id, zone_data in zones.items():
            # Check if this is an HVAC zone
            for schedule_id, schedule_data in self._schedules_cache.items():
                if schedule_data['is_hvac_indicator'] and zone_id in schedule_id:
                    self._hvac_zones_cache.append(zone_id)
                    break
            
            area_id = self._extract_area_id(zone_id)
            self._zones_cache[zone_id] = {
                'id': zone_id,
                'name': zone_id,
                'area_id': area_id,
                'floor_area': safe_float(zone_data.get("floor_area", 0.0)),
                'volume': safe_float(zone_data.get("volume", 0.0)),
                'multiplier': int(safe_float(zone_data.get("multiplier", 1))),
                'raw_object': IDFObjectCompatibilityWrapper(zone_id, zone_data)
            }

    def _cache_surfaces(self) -> None:
        """Cache raw surface data from EPJSON"""
        if not self._epjson_data:
            return

        self._surfaces_cache.clear()
        self._windows_cache = {}

        # Cache building surfaces
        building_surfaces = self._epjson_data.get('BuildingSurface:Detailed', {})
        for surface_id, surface_data in building_surfaces.items():
            # Calculate area from vertices since EPJSON doesn't store area directly
            calculated_area = self._calculate_surface_area_from_vertices(surface_data.get("vertices", []))
            
            self._surfaces_cache[surface_id] = {
                'id': surface_id,
                'name': surface_id,
                'surface_type': surface_data.get("surface_type", ""),
                'construction_name': surface_data.get("construction_name", ""),
                'boundary_condition': surface_data.get("outside_boundary_condition", ""),
                'zone_name': surface_data.get("zone_name", ""),
                'area': calculated_area,
                'raw_object': IDFObjectCompatibilityWrapper(surface_id, surface_data)
            }

        # Cache fenestration surfaces (windows)
        fenestration_surfaces = self._epjson_data.get('FenestrationSurface:Detailed', {})
        for window_id, window_data in fenestration_surfaces.items():
            base_surface = window_data.get("building_surface_name", "")
            zone_name = ""

            # Get zone name from base surface
            if base_surface and base_surface in self._surfaces_cache:
                zone_name = self._surfaces_cache[base_surface]['zone_name']

            construction_name = window_data.get("construction_name", "")
            
            # Calculate window area from vertices since EPJSON doesn't store area directly
            # Convert individual vertex coordinates to vertices array for calculation
            vertices = self._convert_individual_vertices_to_array(window_data)
            window_area = self._calculate_surface_area_from_vertices(vertices)

            window_cache_data = {
                'id': window_id,
                'name': window_id,
                'surface_type': 'Window',
                'construction_name': construction_name,
                'base_surface': base_surface,
                'boundary_condition': 'Outdoors',
                'zone_name': zone_name,
                'area': window_area,
                'is_glazing': True,
                'raw_object': IDFObjectCompatibilityWrapper(window_id, window_data)
            }

            self._windows_cache[window_id] = window_cache_data
            self._surfaces_cache[window_id] = window_cache_data

    def _cache_materials(self) -> None:
        """Cache raw material data from EPJSON"""
        if not self._epjson_data:
            return

        self._materials_cache.clear()
        self._window_glazing_cache.clear()
        self._window_gas_cache.clear()
        self._window_shade_cache.clear()
        self._window_simple_glazing_cache.clear()

        # Cache regular materials
        materials = self._epjson_data.get('Material', {})
        for material_id, material_data in materials.items():
            self._materials_cache[material_id] = {
                'id': material_id,
                'name': material_id,
                'conductivity': safe_float(material_data.get("conductivity", 0.0)),
                'density': safe_float(material_data.get("density", 0.0)),
                'specific_heat': safe_float(material_data.get("specific_heat", 0.0)),
                'thickness': safe_float(material_data.get("thickness", 0.0)),
                'solar_absorptance': safe_float(material_data.get("solar_absorptance", 0.0)),
                'raw_object': IDFObjectCompatibilityWrapper(material_id, material_data)
            }

        # Cache no-mass materials
        no_mass_materials = self._epjson_data.get('Material:NoMass', {})
        for material_id, material_data in no_mass_materials.items():
            self._materials_cache[material_id] = {
                'id': material_id,
                'name': material_id,
                'conductivity': 0.0,  # No-mass materials don't have conductivity
                'density': 0.0,  # No-mass materials don't have density
                'specific_heat': 0.0,  # No-mass materials don't have specific heat
                'thickness': 0.0,  # No-mass materials don't have thickness
                'thermal_resistance': safe_float(material_data.get("thermal_resistance", 0.0)),
                'solar_absorptance': safe_float(material_data.get("solar_absorptance", 0.0)),
                'raw_object': IDFObjectCompatibilityWrapper(material_id, material_data)
            }

        # Cache infrared transparent materials
        infrared_materials = self._epjson_data.get('Material:InfraredTransparent', {})
        for material_id, material_data in infrared_materials.items():
            self._materials_cache[material_id] = {
                'id': material_id,
                'name': material_id,
                'conductivity': 0.0,  # Infrared transparent materials don't have standard thermal properties
                'density': 0.0,
                'specific_heat': 0.0,
                'thickness': 0.0,
                'solar_absorptance': 0.0,
                'raw_object': IDFObjectCompatibilityWrapper(material_id, material_data)
            }

        # Cache window glazing materials
        window_glazing = self._epjson_data.get('WindowMaterial:Glazing', {})
        for material_id, glazing_data in window_glazing.items():
            self._window_glazing_cache[material_id] = {
                'id': material_id,
                'name': material_id,
                'thickness': safe_float(glazing_data.get("thickness", 0.0)),
                'solar_transmittance': safe_float(glazing_data.get("solar_transmittance_at_normal_incidence", 0.0)),
                'visible_transmittance': safe_float(glazing_data.get("visible_transmittance_at_normal_incidence", 0.0)),
                'conductivity': safe_float(glazing_data.get("conductivity", 0.0)),
                'u_factor': safe_float(glazing_data.get("conductivity", 0.0)) / safe_float(glazing_data.get("thickness", 1.0)),
                'raw_object': IDFObjectCompatibilityWrapper(material_id, glazing_data)
            }

        # Cache window gas materials
        window_gas = self._epjson_data.get('WindowMaterial:Gas', {})
        for material_id, gas_data in window_gas.items():
            self._window_gas_cache[material_id] = {
                'id': material_id,
                'name': material_id,
                'gas_type': gas_data.get("gas_type", ""),
                'thickness': safe_float(gas_data.get("thickness", 0.0)),
                'raw_object': IDFObjectCompatibilityWrapper(material_id, gas_data)
            }

        # Cache window shade materials
        window_shade = self._epjson_data.get('WindowMaterial:Shade', {})
        for material_id, shade_data in window_shade.items():
            self._window_shade_cache[material_id] = {
                'id': material_id,
                'name': material_id,
                'thickness': safe_float(shade_data.get("thickness", 0.0)),
                'conductivity': safe_float(shade_data.get("conductivity", 0.0)),
                'visible_reflectance': safe_float(shade_data.get("visible_reflectance", 0.0)),
                'solar_reflectance': safe_float(shade_data.get("solar_reflectance", 0.0)),
                'solar_transmittance': safe_float(shade_data.get("solar_transmittance", 0.0)),
                'visible_transmittance': safe_float(shade_data.get("visible_transmittance", 0.0)),
                'raw_object': IDFObjectCompatibilityWrapper(material_id, shade_data)
            }

        # Cache simple glazing systems
        simple_glazing = self._epjson_data.get('WindowMaterial:SimpleGlazingSystem', {})
        for material_id, simple_data in simple_glazing.items():
            self._window_simple_glazing_cache[material_id] = {
                'id': material_id,
                'name': material_id,
                'u_factor': safe_float(simple_data.get("u_factor", 0.0)),
                'shgc': safe_float(simple_data.get("solar_heat_gain_coefficient", 0.0)),
                'visible_transmittance': safe_float(simple_data.get("visible_transmittance", 0.0)),
                'raw_object': IDFObjectCompatibilityWrapper(material_id, simple_data)
            }

    def _cache_constructions(self) -> None:
        """Cache raw construction data from EPJSON"""
        if not self._epjson_data:
            return

        self._constructions_cache.clear()
        self._constructions_glazing_cache.clear()

        constructions = self._epjson_data.get('Construction', {})
        for construction_id, construction_data in constructions.items():
            if construction_id in ['LinearBridgingConstruction', 'IRTSurface']:
                continue

            # Extract material layers
            material_layers = []
            outside_layer = construction_data.get("outside_layer", "")
            if outside_layer:
                material_layers.append(outside_layer)
            
            # Add additional layers
            layer_index = 2
            while f"layer_{layer_index}" in construction_data:
                layer = construction_data[f"layer_{layer_index}"]
                if layer:
                    material_layers.append(layer)
                layer_index += 1

            # Check if this is a glazing construction
            is_glazing_construction = any(
                layer_name in self._window_glazing_cache or
                layer_name in self._window_gas_cache or
                layer_name in self._window_shade_cache or
                layer_name in self._window_simple_glazing_cache
                for layer_name in material_layers
            )

            construction_cache_data = {
                'id': construction_id,
                'name': construction_id,
                'material_layers': material_layers,
                'raw_object': IDFObjectCompatibilityWrapper(construction_id, construction_data)
            }

            if is_glazing_construction:
                self._constructions_glazing_cache[construction_id] = construction_cache_data
            else:
                self._constructions_cache[construction_id] = construction_cache_data

    def _cache_schedules(self) -> None:
        """Cache raw schedule data from EPJSON"""
        if not self._epjson_data:
            return

        self._schedules_cache.clear()
        self._schedule_rules_cache.clear()

        schedules = self._epjson_data.get('Schedule:Compact', {})
        for schedule_id, schedule_data in schedules.items():
            schedule_type = schedule_data.get('schedule_type_limits_name', '')
            
            # Extract schedule rules (field values)
            rule_fields = []
            
            # EPJSON format stores rules in data array with field property
            if 'data' in schedule_data and isinstance(schedule_data['data'], list):
                for data_item in schedule_data['data']:
                    if isinstance(data_item, dict) and 'field' in data_item:
                        field_value = data_item['field']
                        # Include all field values, even 0 and empty strings (they are meaningful in schedules)
                        if field_value is not None:
                            rule_fields.append(str(field_value))
            else:
                # Fallback to old field_1, field_2 format for compatibility
                field_index = 1
                while f"field_{field_index}" in schedule_data:
                    field_value = schedule_data[f"field_{field_index}"]
                    if field_value and str(field_value).strip():
                        rule_fields.append(str(field_value))
                    field_index += 1

            is_hvac_indicator = self._is_hvac_indicator(schedule_id, schedule_type)

            self._schedules_cache[schedule_id] = {
                'id': schedule_id,
                'name': schedule_id,
                'type': schedule_type,
                'is_hvac_indicator': is_hvac_indicator,
                'raw_object': IDFObjectCompatibilityWrapper(schedule_id, schedule_data)
            }

            self._schedule_rules_cache[schedule_id] = rule_fields

    def _cache_loads(self) -> None:
        """Cache raw load data (people, lights, equipment, etc.) from EPJSON"""
        if not self._epjson_data:
            return

        # Cache people loads
        self._people_cache.clear()
        people_objects = self._epjson_data.get('People', {})
        for people_id, people_data in people_objects.items():
            zone_name = people_data.get("zone_or_zonelist_name", "")
            if not zone_name:
                continue

            if zone_name not in self._people_cache:
                self._people_cache[zone_name] = []

            self._people_cache[zone_name].append({
                'people_per_area': safe_float(people_data.get("people_per_zone_floor_area", 0.0)),
                'number_of_people': safe_float(people_data.get("number_of_people", 0.0)),
                'schedule': people_data.get("number_of_people_schedule_name", ""),
                'activity_schedule': people_data.get("activity_level_schedule_name", ""),
                'clothing_schedule': people_data.get("clothing_insulation_schedule_name", ""),
                'raw_object': IDFObjectCompatibilityWrapper(people_id, people_data)
            })

        # Cache lights loads
        self._lights_cache.clear()
        lights_objects = self._epjson_data.get('Lights', {})
        for lights_id, lights_data in lights_objects.items():
            # EPJSON uses zone_or_zonelist_or_space_or_spacelist_name
            zone_name = lights_data.get("zone_or_zonelist_or_space_or_spacelist_name", "")
            if not zone_name:
                # Fallback to older field names
                zone_name = lights_data.get("zone_or_zonelist_name", "")
            if not zone_name:
                continue

            if zone_name not in self._lights_cache:
                self._lights_cache[zone_name] = []

            # EPJSON uses watts_per_floor_area instead of watts_per_zone_floor_area
            watts_per_area = safe_float(lights_data.get("watts_per_floor_area", 0.0))
            if watts_per_area == 0.0:
                # Fallback to older field name
                watts_per_area = safe_float(lights_data.get("watts_per_zone_floor_area", 0.0))

            self._lights_cache[zone_name].append({
                'name': lights_id,
                'zone_name': zone_name,
                'watts_per_area': watts_per_area,
                'lighting_level': safe_float(lights_data.get("lighting_level", 0.0)),
                'watts_per_person': safe_float(lights_data.get("watts_per_person", 0.0)),
                'design_level_calculation_method': lights_data.get("design_level_calculation_method", ""),
                'schedule': lights_data.get("schedule_name", ""),
                'raw_object': IDFObjectCompatibilityWrapper(lights_id, lights_data)
            })

        # Cache exterior lights
        self._cache_exterior_lights()

        # Cache equipment loads
        self._equipment_cache.clear()
        for equip_type in ['ElectricEquipment', 'OtherEquipment']:
            equipment_objects = self._epjson_data.get(equip_type, {})
            for equip_id, equip_data in equipment_objects.items():
                zone_name = equip_data.get("zone_or_zonelist_name", "")
                if not zone_name:
                    continue

                if zone_name not in self._equipment_cache:
                    self._equipment_cache[zone_name] = []

                is_fixed = not ("Miscellaneous" in equip_id)

                self._equipment_cache[zone_name].append({
                    'name': equip_id,
                    'type': "fixed" if is_fixed else "non_fixed",
                    'watts_per_area': safe_float(equip_data.get("power_per_zone_floor_area", 0.0)),
                    'schedule': equip_data.get("schedule_name", ""),
                    'raw_object': IDFObjectCompatibilityWrapper(equip_id, equip_data)
                })

        # Cache infiltration loads
        self._infiltration_cache.clear()
        infiltration_objects = self._epjson_data.get('ZoneInfiltration:DesignFlowRate', {})
        for infil_id, infil_data in infiltration_objects.items():
            zone_name = infil_data.get("zone_or_zonelist_name", "")
            if not zone_name:
                continue

            if zone_name not in self._infiltration_cache:
                self._infiltration_cache[zone_name] = []

            self._infiltration_cache[zone_name].append({
                'air_changes_per_hour': safe_float(infil_data.get("constant_term_coefficient", 0.0)),
                'schedule': infil_data.get("schedule_name", ""),
                'raw_object': IDFObjectCompatibilityWrapper(infil_id, infil_data)
            })

        # Cache ventilation loads
        self._cache_ventilation_loads()

    def _cache_ventilation_loads(self) -> None:
        """Cache raw ventilation data from ZoneVentilation:DesignFlowRate objects."""
        self._ventilation_cache.clear()
        ventilation_objects = self._epjson_data.get('ZoneVentilation:DesignFlowRate', {})
        
        for vent_id, vent_data in ventilation_objects.items():
            zone_name = vent_data.get("zone_or_zonelist_name", "")
            if not zone_name:
                continue

            if zone_name not in self._ventilation_cache:
                self._ventilation_cache[zone_name] = []

            self._ventilation_cache[zone_name].append({
                'schedule_name': vent_data.get("schedule_name", ""),
                'design_flow_rate': safe_float(vent_data.get("design_flow_rate", 0.0)),
                'ventilation_type': vent_data.get("ventilation_type", ""),
                'min_indoor_temp': safe_float(vent_data.get("minimum_indoor_temperature", 0.0)),
                'max_indoor_temp': safe_float(vent_data.get("maximum_indoor_temperature", 0.0)),
                'max_temp_difference': safe_float(vent_data.get("delta_temperature", 0.0)),
                'min_outdoor_temp': safe_float(vent_data.get("minimum_outdoor_temperature", 0.0)),
                'max_outdoor_temp': safe_float(vent_data.get("maximum_outdoor_temperature", 0.0)),
                'max_wind_speed': safe_float(vent_data.get("maximum_wind_speed", 0.0)),
                'raw_object': IDFObjectCompatibilityWrapper(vent_id, vent_data)
            })

    def _cache_exterior_lights(self) -> None:
        """Cache raw Exterior:Lights data from EPJSON"""
        if not self._epjson_data:
            return

        self._exterior_lights_cache.clear()
        exterior_lights = self._epjson_data.get('Exterior:Lights', {})
        
        for ext_light_id, ext_light_data in exterior_lights.items():
            self._exterior_lights_cache.append({
                'name': ext_light_id,
                'schedule_name': ext_light_data.get("schedule_name", ""),
                'design_level': safe_float(ext_light_data.get("design_level", 0.0)),
                'raw_object': IDFObjectCompatibilityWrapper(ext_light_id, ext_light_data)
            })

    def _cache_window_shading_controls(self) -> None:
        """Cache window shading control data from EPJSON"""
        if not self._epjson_data:
            return

        self._window_shading_control_cache.clear()
        shading_controls = self._epjson_data.get('WindowShadingControl', {})

        for control_id, control_data in shading_controls.items():
            zone_name = control_data.get("zone_name", "")

            # Extract window names from fenestration surface fields
            window_names = []
            
            # First try the EPJSON array format
            fenestration_surfaces = control_data.get("fenestration_surfaces", [])
            if fenestration_surfaces:
                for surface_obj in fenestration_surfaces:
                    if isinstance(surface_obj, dict):
                        window_name = surface_obj.get("fenestration_surface_name")
                        if window_name:
                            window_names.append(window_name)
            else:
                # Fallback to the IDF-style field format
                field_index = 1
                while f"fenestration_surface_{field_index}_name" in control_data:
                    window_name = control_data[f"fenestration_surface_{field_index}_name"]
                    if window_name:
                        window_names.append(window_name)
                    field_index += 1

            self._window_shading_control_cache[control_id] = {
                'id': control_id,
                'name': control_id,
                'zone_name': zone_name,
                'shading_type': control_data.get("shading_type", ""),
                'construction_with_shading_name': control_data.get("construction_with_shading_name", ""),
                'shading_control_type': control_data.get("shading_control_type", ""),
                'schedule_name': control_data.get("schedule_name", ""),
                'is_scheduled': control_data.get("shading_control_is_scheduled", "").lower() == "yes",
                'glare_control_is_active': control_data.get("glare_control_is_active", "").lower() == "yes",
                'window_names': window_names,
                'raw_object': IDFObjectCompatibilityWrapper(control_id, control_data)
            }

    def _cache_frame_dividers(self) -> None:
        """Cache raw WindowProperty:FrameAndDivider data from EPJSON"""
        if not self._epjson_data:
            return

        self._frame_divider_cache.clear()
        frame_dividers = self._epjson_data.get('WindowProperty:FrameAndDivider', {})

        for fd_id, fd_data in frame_dividers.items():
            self._frame_divider_cache[fd_id] = {
                'id': fd_id,
                'name': fd_id,
                'frame_width': safe_float(fd_data.get("frame_width", 0.0)),
                'frame_conductance': safe_float(fd_data.get("frame_conductance", 0.0)),
                'raw_object': IDFObjectCompatibilityWrapper(fd_id, fd_data)
            }

    def _cache_daylighting(self) -> None:
        """Cache raw daylighting data from EPJSON"""
        if not self._epjson_data:
            return

        self._daylighting_controls_cache.clear()
        self._daylighting_reference_point_cache.clear()

        # Cache daylighting controls
        daylighting_controls = self._epjson_data.get('Daylighting:Controls', {})
        for control_id, control_data in daylighting_controls.items():
            self._daylighting_controls_cache[control_id] = {
                'id': control_id,
                'raw_object': IDFObjectCompatibilityWrapper(control_id, control_data)
            }

        # Cache daylighting reference points
        reference_points = self._epjson_data.get('Daylighting:ReferencePoint', {})
        for ref_point_id, ref_point_data in reference_points.items():
            self._daylighting_reference_point_cache[ref_point_id] = {
                'id': ref_point_id,
                'raw_object': IDFObjectCompatibilityWrapper(ref_point_id, ref_point_data)
            }

    def _cache_outdoor_air_specifications(self) -> None:
        """Cache raw DesignSpecification:OutdoorAir data from EPJSON"""
        if not self._epjson_data:
            return

        self._outdoor_air_spec_cache.clear()
        outdoor_air_specs = self._epjson_data.get('DesignSpecification:OutdoorAir', {})

        for spec_name, spec_data in outdoor_air_specs.items():
            self._outdoor_air_spec_cache[spec_name] = {
                'id': spec_name,
                'zone_name': spec_name,
                'outdoor_air_flow_per_person': safe_float(spec_data.get("outdoor_air_flow_per_person", 0.0)),
                'outdoor_air_flow_rate_fraction_schedule_name': spec_data.get("outdoor_air_schedule_name", ""),
                'raw_object': IDFObjectCompatibilityWrapper(spec_name, spec_data)
            }

    def _cache_ideal_loads(self) -> None:
        """Cache ZoneHVAC:IdealLoadsAirSystem data linked to zones from EPJSON."""
        if not self._epjson_data:
            return

        self._ideal_loads_cache.clear()
        ideal_loads = self._epjson_data.get('ZoneHVAC:IdealLoadsAirSystem', {})

        for ideal_load_name, ideal_load_data in ideal_loads.items():
            # Extract zone name from ideal load name
            # Pattern: "00:01XLIVING Ideal Loads Air" -> "00:01XLIVING"
            zone_name = ""
            if "Ideal Loads Air" in ideal_load_name:
                zone_name = ideal_load_name.replace(" Ideal Loads Air", "").strip()
            
            if not zone_name:
                continue

            if zone_name not in self._ideal_loads_cache:
                self._ideal_loads_cache[zone_name] = []

            self._ideal_loads_cache[zone_name].append({
                'id': ideal_load_name,
                'name': ideal_load_name,
                'zone_name': zone_name,
                'max_heating_supply_air_temperature': safe_float(ideal_load_data.get("maximum_heating_supply_air_temperature", 0.0)),
                'min_cooling_supply_air_temperature': safe_float(ideal_load_data.get("minimum_cooling_supply_air_temperature", 0.0)),
                'max_heating_supply_air_humidity_ratio': safe_float(ideal_load_data.get("maximum_heating_supply_air_humidity_ratio", 0.0)),
                'min_cooling_supply_air_humidity_ratio': safe_float(ideal_load_data.get("minimum_cooling_supply_air_humidity_ratio", 0.0)),
                'heating_limit': ideal_load_data.get("heating_limit", ""),
                'cooling_limit': ideal_load_data.get("cooling_limit", ""),
                'dehumidification_control_type': ideal_load_data.get("dehumidification_control_type", ""),
                'humidification_control_type': ideal_load_data.get("humidification_control_type", ""),
                'raw_object': IDFObjectCompatibilityWrapper(ideal_load_name, ideal_load_data)
            })

    def _build_all_materials_cache(self) -> None:
        """
        Merges all individual material type caches into a single comprehensive cache
        and adds a 'type' field to each material. Called once during load_file.
        """
        if not self._epjson_data:
            return
        self._all_materials_cache_complete.clear()

        temp_merged_materials = {
            **self._materials_cache,
            **self._window_glazing_cache,
            **self._window_gas_cache,
            **self._window_shade_cache,
            **self._window_simple_glazing_cache
        }

        for mat_id, mat_data_original in temp_merged_materials.items():
            mat_data = mat_data_original.copy()

            if mat_id in self._materials_cache:
                # Check original EPJSON source to determine specific type
                if mat_id in self._epjson_data.get('Material', {}):
                    mat_data['type'] = 'Material'
                elif mat_id in self._epjson_data.get('Material:NoMass', {}):
                    mat_data['type'] = 'Material:NoMass'
                elif mat_id in self._epjson_data.get('Material:InfraredTransparent', {}):
                    mat_data['type'] = 'Material:InfraredTransparent'
                else:
                    mat_data['type'] = 'Material'
            elif mat_id in self._window_glazing_cache:
                mat_data['type'] = 'WindowMaterial:Glazing'
            elif mat_id in self._window_gas_cache:
                mat_data['type'] = 'WindowMaterial:Gas'
            elif mat_id in self._window_shade_cache:
                mat_data['type'] = 'WindowMaterial:Shade'
            elif mat_id in self._window_simple_glazing_cache:
                mat_data['type'] = 'WindowMaterial:SimpleGlazingSystem'
            else:
                mat_data['type'] = 'UnknownMaterialType'

            self._all_materials_cache_complete[mat_id] = mat_data

    # Getter methods (same as original, maintaining API compatibility)
    def get_zones(self) -> Dict[str, Dict[str, Any]]:
        """Get cached zone data."""
        if self._should_log_details('get_zones'):
            logger.info(f"Retrieved zones data: {len(self._zones_cache)} zones found")
            # Log sample of first few zones
            sample_count = min(3, len(self._zones_cache))
            for i, (zone_id, zone_data) in enumerate(self._zones_cache.items()):
                if i >= sample_count:
                    break
                logger.info(f"Zone sample {i+1}: {zone_id} - Floor Area: {zone_data.get('floor_area', 0)}, Volume: {zone_data.get('volume', 0)}, Area ID: {zone_data.get('area_id', 'N/A')}")
        return self._zones_cache

    def get_hvac_zones(self) -> List[str]:
        """Get cached HVAC zone names."""
        if self._should_log_details('get_hvac_zones'):
            logger.info(f"Retrieved HVAC zones: {len(self._hvac_zones_cache)} HVAC zones found")
            logger.info(f"HVAC zones list: {self._hvac_zones_cache}")
        return self._hvac_zones_cache

    def get_surfaces(self) -> Dict[str, Dict[str, Any]]:
        """Get cached surface data."""
        if self._should_log_details('get_surfaces'):
            logger.info(f"Retrieved surfaces data: {len(self._surfaces_cache)} surfaces found")
            # Log sample of first few surfaces
            sample_count = min(3, len(self._surfaces_cache))
            for i, (surface_id, surface_data) in enumerate(self._surfaces_cache.items()):
                if i >= sample_count:
                    break
                logger.info(f"Surface sample {i+1}: {surface_id} - Type: {surface_data.get('surface_type', 'N/A')}, Area: {surface_data.get('area', 0)}, Zone: {surface_data.get('zone_name', 'N/A')}")
        return self._surfaces_cache

    def get_materials(self) -> Dict[str, Dict[str, Any]]:
        """Get the fully processed and cached material data, merging all material types."""
        if self._should_log_details('get_materials'):
            logger.info(f"Retrieved materials data: {len(self._all_materials_cache_complete)} materials found")
            # Log sample of first few materials
            sample_count = min(3, len(self._all_materials_cache_complete))
            for i, (material_id, material_data) in enumerate(self._all_materials_cache_complete.items()):
                if i >= sample_count:
                    break
                logger.info(f"Material sample {i+1}: {material_id} - Type: {material_data.get('type', 'N/A')}, Conductivity: {material_data.get('conductivity', 'N/A')}, Thickness: {material_data.get('thickness', 'N/A')}")
        return self._all_materials_cache_complete

    def get_constructions(self) -> Dict[str, Dict[str, Any]]:
        """Get cached construction data"""
        if self._should_log_details('get_constructions'):
            logger.info(f"Retrieved constructions data: {len(self._constructions_cache)} constructions found")
            # Log sample of first few constructions
            sample_count = min(3, len(self._constructions_cache))
            for i, (construction_id, construction_data) in enumerate(self._constructions_cache.items()):
                if i >= sample_count:
                    break
                layers = construction_data.get('material_layers', [])
                logger.info(f"Construction sample {i+1}: {construction_id} - Layers: {len(layers)} ({', '.join(layers[:2])}{'...' if len(layers) > 2 else ''})")
        return self._constructions_cache

    def get_schedules(self) -> Dict[str, Dict[str, Any]]:
        """Get cached schedule data"""
        if self._should_log_details('get_schedules'):
            logger.info(f"Retrieved schedules data: {len(self._schedules_cache)} schedules found")
            # Log sample of first few schedules
            sample_count = min(3, len(self._schedules_cache))
            for i, (schedule_id, schedule_data) in enumerate(self._schedules_cache.items()):
                if i >= sample_count:
                    break
                logger.info(f"Schedule sample {i+1}: {schedule_id} - Type: {schedule_data.get('type', 'N/A')}, HVAC Indicator: {schedule_data.get('is_hvac_indicator', False)}")
        return self._schedules_cache

    def get_schedule_rules(self, schedule_id: str) -> List[str]:
        """Get cached rules for a specific schedule"""
        return self._schedule_rules_cache.get(schedule_id, [])
    
    def get_schedule_objects(self) -> List[Any]:
        """
        Get schedule objects as a list for compatibility with processing manager.
        Creates eppy-compatible objects for existing parsers.
        
        Returns:
            List of schedule objects with eppy-compatible interface
        """
        if not self._schedules_cache:
            logger.warning("No schedule data available. Load a file first.")
            return []
        
        # Create eppy-compatible schedule objects
        schedule_objects = []
        schedules_epjson = self._epjson_data.get('Schedule:Compact', {})
        
        for schedule_id, schedule_data in self._schedules_cache.items():
            # Use original EPJSON data for the wrapper so it can access the 'data' array
            original_epjson_data = schedules_epjson.get(schedule_id, {})
            schedule_obj = ScheduleCompatibilityWrapper(schedule_id, original_epjson_data)
            schedule_objects.append(schedule_obj)
        
        return schedule_objects

    def get_people_loads(self, zone_name: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
        """Get cached people loads, optionally filtered by zone"""
        if zone_name:
            return {zone_name: self._people_cache.get(zone_name, [])} if zone_name in self._people_cache else {}
        return self._people_cache

    def get_lights_loads(self, zone_name: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
        """Get cached lights loads, optionally filtered by zone"""
        if zone_name:
            return {zone_name: self._lights_cache.get(zone_name, [])} if zone_name in self._lights_cache else {}
        return self._lights_cache

    def get_exterior_lights_loads(self) -> List[Dict[str, Any]]:
        """Get cached exterior lights loads"""
        return self._exterior_lights_cache

    def get_equipment_loads(self, zone_name: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
        """Get cached equipment loads, optionally filtered by zone"""
        if zone_name:
            return {zone_name: self._equipment_cache.get(zone_name, [])} if zone_name in self._equipment_cache else {}
        return self._equipment_cache

    def get_infiltration_loads(self, zone_name: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
        """Get cached infiltration loads, optionally filtered by zone"""
        if zone_name:
            return {zone_name: self._infiltration_cache.get(zone_name, [])} if zone_name in self._infiltration_cache else {}
        return self._infiltration_cache

    def get_ventilation_loads(self, zone_name: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
        """Get cached ventilation loads, optionally filtered by zone"""
        if zone_name:
            return {zone_name: self._ventilation_cache.get(zone_name, [])} if zone_name in self._ventilation_cache else {}
        return self._ventilation_cache

    def get_ideal_loads(self, zone_name: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
        """Get cached ideal loads air systems, optionally filtered by zone"""
        if zone_name:
            return {zone_name: self._ideal_loads_cache.get(zone_name, [])} if zone_name in self._ideal_loads_cache else {}
        return self._ideal_loads_cache

    def get_windows(self) -> Dict[str, Dict[str, Any]]:
        """Get cached window data"""
        return self._windows_cache

    def get_raw_windows_cache(self) -> Dict[str, Dict[str, Any]]:
        """Get the raw windows cache (FenestrationSurface:Detailed objects)."""
        return self._windows_cache

    def get_window_glazing_materials(self) -> Dict[str, Dict[str, Any]]:
        """Get cached window glazing materials"""
        return self._window_glazing_cache

    def get_window_gas_materials(self) -> Dict[str, Dict[str, Any]]:
        """Get cached window gas materials"""
        return self._window_gas_cache

    def get_window_shade_materials(self) -> Dict[str, Dict[str, Any]]:
        """Get cached window shade materials"""
        return self._window_shade_cache

    def get_window_simple_glazing_materials(self) -> Dict[str, Dict[str, Any]]:
        """Get cached window simple glazing systems"""
        return self._window_simple_glazing_cache

    def get_window_shading_controls(self) -> Dict[str, Dict[str, Any]]:
        """Get cached window shading controls"""
        return self._window_shading_control_cache

    def get_frame_dividers(self) -> Dict[str, Dict[str, Any]]:
        """Get cached WindowProperty:FrameAndDivider data"""
        return self._frame_divider_cache

    def get_constructions_glazing(self) -> Dict[str, Dict[str, Any]]:
        """Get cached construction glazing data"""
        return self._constructions_glazing_cache

    def get_cache_status(self) -> Dict[str, bool]:
        """Get the loading status of cache sections (maintained for compatibility)"""
        return {
            'zones': bool(self._zones_cache),
            'surfaces': bool(self._surfaces_cache),
            'materials': bool(self._materials_cache),
            'constructions': bool(self._constructions_cache),
            'schedules': bool(self._schedules_cache)
        }

    def get_epjson_data(self):
        """
        Get the raw EPJSON data.
        This replaces the get_idf() method for EPJSON compatibility.
        """
        return self._epjson_data

    def get_idf(self):
        """
        Legacy method for compatibility.
        Returns the EPJSON data instead of IDF object.
        """
        return self._epjson_data

    def get_file_path(self) -> Optional[str]:
        """Get the path of the loaded file"""
        return self._file_path

    def get_idf_path(self) -> Optional[str]:
        """Legacy method for compatibility. Returns the file path."""
        return self._file_path

    def get_daylighting_controls(self) -> Dict[str, Dict[str, Any]]:
        """Return cached raw Daylighting:Controls data"""
        return self._daylighting_controls_cache

    def get_daylighting_reference_points(self) -> Dict[str, Dict[str, Any]]:
        """Return cached raw Daylighting:ReferencePoint data"""
        return self._daylighting_reference_point_cache

    def get_outdoor_air_specifications(self) -> Dict[str, Dict[str, Any]]:
        """Get cached DesignSpecification:OutdoorAir data"""
        return self._outdoor_air_spec_cache

    def get_natural_ventilation_data(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get cached natural ventilation data from ZoneVentilation:DesignFlowRate objects"""
        return self._ventilation_cache

    def get_settings_objects(self) -> dict:
        """Return a dictionary of common settings objects from the EPJSON data by type."""
        if not self._epjson_data:
            logger.warning("No EPJSON data loaded, returning empty settings")
            return {}
        
        settings = {}
        if self._should_log_details('get_settings_objects'):
            for object_type in SETTINGS_OBJECT_TYPES:
                try:
                    objects = self._epjson_data.get(object_type, {})
                    settings[object_type] = objects
                    # Log details for each settings category
                    if objects:
                        logger.info(f"Settings {object_type}: {len(objects)} objects found")
                        # Log first object details
                        first_obj_name = next(iter(objects.keys()), None)
                        if first_obj_name:
                            logger.info(f"  Sample: {first_obj_name}")
                except Exception as e:
                    logger.error(f"Error retrieving objects of type '{object_type}': {e}")
                    settings[object_type] = {}
            
            total_settings = sum(len(objects) for objects in settings.values())
            logger.info(f"Retrieved settings objects: {total_settings} total settings across {len(SETTINGS_OBJECT_TYPES)} categories")
        else:
            # Just collect the data without detailed logging
            for object_type in SETTINGS_OBJECT_TYPES:
                try:
                    settings[object_type] = self._epjson_data.get(object_type, {})
                except Exception as e:
                    logger.error(f"Error retrieving objects of type '{object_type}': {e}")
                    settings[object_type] = {}
        
        return settings

    def _extract_area_id(self, zone_id: str) -> Optional[str]:
        """Extract area_id from a zone_id string."""
        split = zone_id.split(":", 1)
        if len(split) > 1 and split[1]:
            if AREA_ID_REGEX.match(split[1]):
                return split[1][:2]
            return split[1]
        return None

    def _is_hvac_indicator(self, schedule_id: str, schedule_type: str) -> bool:
        """Determine if a schedule indicates an HVAC zone."""
        schedule_name_lower = schedule_id.lower()
        schedule_type_lower = schedule_type.lower()
        return (
            'temperature' in schedule_type_lower and
            ('heating' in schedule_name_lower or 'cooling' in schedule_name_lower) and
            'setpoint' not in schedule_type_lower
        )