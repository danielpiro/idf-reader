"""
DataLoader module for direct IDF data access.
Provides simplified data loading and retrieval functionality.
Includes support for Hebrew/Unicode characters in file paths.
"""
from typing import Dict, Optional, List, Any
from pathlib import Path
from utils.eppy_handler import EppyHandler
from utils.path_utils import (
    get_data_file_path, contains_non_ascii,
    create_safe_path_for_energyplus
)
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
        FileNotFoundError: If the required model CSV file is not found.        KeyError: If area_location_input or area_definition_input is not found in the CSV.
    """
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
        raise ValueError(f"Invalid ISO type format: {iso_type_input}. Cannot determine year or office type.")    # Validate area_definition_input based on year
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
        return float(value_str)
    except ValueError:
        raise ValueError(f"Invalid data format in CSV. Cannot convert '{value_str}' to float for location '{area_location_input}', definition '{area_definition_input.upper()}' in {file_path}")


logger = get_logger(__name__)

AREA_ID_REGEX = re.compile(r"^\d{2}")

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
    """DataLoader for caching and retrieving IDF data."""
    def __init__(self):
        self._idf = None
        self._eppy_handler = None
        self._idf_path = None
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

    def ensure_output_variables(self, idf_path: str = None, idd_path: Optional[str] = None) -> bool:
        """Ensure required output variables exist in the IDF file before running the simulation.
        Use this method before running the simulation to make sure energy rating variables are present.
        Handles Unicode/Hebrew characters in file paths.

        Args:
            idf_path: Path to the IDF file. If None, uses the previously loaded file.
            idd_path: Optional path to the IDD file

        Returns:
            bool: True if output variables were successfully checked/added, False otherwise
        """
        if idf_path and (not self._idf or self._idf_path != idf_path):
            # Handle Unicode/Hebrew characters in file paths
            safe_file_path = idf_path
            cleanup_func = None
            
            try:
                if contains_non_ascii(idf_path):
                    logger.info(f"IDF file path contains Unicode/Hebrew characters: {idf_path}")
                    safe_file_path, cleanup_func = create_safe_path_for_energyplus(idf_path)
                    logger.info(f"Using ASCII-safe path for eppy: {safe_file_path}")

                if not self._eppy_handler:
                    self._eppy_handler = EppyHandler(idd_path)
                self._idf_path = idf_path  # Store original path
                self._idf = self._eppy_handler.load_idf(safe_file_path)
                
            finally:
                # Clean up temporary file if it was created
                if cleanup_func:
                    cleanup_func()
                    logger.debug("Cleaned up temporary IDF file after loading for output variables")

        if self._idf:
            self._check_output()
            self._idf.save()
            return True
        return False

    def load_file(self, idf_path: str, idd_path: Optional[str] = None) -> None:
        """
        Load IDF file and cache raw data.
        Handles Unicode/Hebrew characters in file paths.

        Args:
            idf_path: Path to the IDF file
            idd_path: Optional path to the IDD file

        Raises:
            FileNotFoundError: If IDF or IDD file not found
        """
        if not Path(idf_path).exists():
            raise FileNotFoundError(f"IDF file not found at '{idf_path}'")

        # Handle Unicode/Hebrew characters in file paths for eppy compatibility
        safe_file_path = idf_path
        cleanup_func = None
        
        try:
            if contains_non_ascii(idf_path):
                logger.info(f"IDF file path contains Unicode/Hebrew characters: {idf_path}")
                safe_file_path, cleanup_func = create_safe_path_for_energyplus(idf_path)
                logger.info(f"Using ASCII-safe path for eppy: {safe_file_path}")

            self._eppy_handler = EppyHandler(idd_path)
            self._idf_path = idf_path  # Store original path
            self._idf = self._eppy_handler.load_idf(safe_file_path)
            self._loaded_sections = {'zones', 'surfaces', 'materials', 'constructions', 'schedules'}

            self._check_output()
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
            
            logger.info(f"Successfully loaded IDF file: {idf_path}")

        except Exception as e:
            logger.error(f"Error loading IDF file '{idf_path}': {str(e)}")
            raise
        finally:
            # Clean up temporary file if it was created
            if cleanup_func:
                cleanup_func()
                logger.debug("Cleaned up temporary IDF file after loading")

    def _check_output(self) -> None:
        """Ensure the required Output:Variable objects are present in the IDF."""
        if not self._idf:
            return

        required_vars_data = [
            {
                'Key_Value': '*',
                'Variable_Name': 'Zone Ideal Loads Supply Air Total Cooling Energy',
                'Reporting_Frequency': 'RunPeriod'
            },
            {
                'Key_Value': '*',
                'Variable_Name': 'Zone Ideal Loads Supply Air Total Heating Energy',
                'Reporting_Frequency': 'RunPeriod'
            },
            {
                'Key_Value': '*',
                'Variable_Name': 'Lights Electricity Energy',
                'Reporting_Frequency': 'RunPeriod'
            }
        ]

        for var_data in required_vars_data:
            output_variable = self._idf.newidfobject('OUTPUT:VARIABLE')
            output_variable.Key_Value = var_data['Key_Value']
            output_variable.Variable_Name = var_data['Variable_Name']
            output_variable.Reporting_Frequency = var_data['Reporting_Frequency']

    def _cache_zones(self) -> None:
        """Cache raw zone data."""
        if not self._idf:
            return
        self._zones_cache.clear()
        for zone in self._idf.idfobjects['ZONE']:
            zone_id = str(zone.Name)
            for schedule_id, schedule_data in self._schedules_cache.items():
                if schedule_data['is_hvac_indicator'] and zone_id in schedule_id:
                    self._hvac_zones_cache.append(zone_id)
                    break
            area_id = self._extract_area_id(zone_id)
            self._zones_cache[zone_id] = {
                'id': zone_id,
                'name': zone_id,
                'area_id': area_id,
                'floor_area': safe_float(getattr(zone, "Floor_Area", 0.0)),
                'volume': safe_float(getattr(zone, "Volume", 0.0)),
                'multiplier': int(safe_float(getattr(zone, "Multiplier", 1))),
                'raw_object': zone,
                'surfaces': zone.zonesurfaces
            }

    def _cache_surfaces(self) -> None:
        """Cache raw surface data"""
        if not self._idf:
            return

        self._surfaces_cache.clear()
        self._windows_cache = {}

        for surface in self._idf.idfobjects['BUILDINGSURFACE:DETAILED']:
            surface_id = str(surface.Name)

            self._surfaces_cache[surface_id] = {
                'id': surface_id,
                'name': surface_id,
                'surface_type': str(getattr(surface, "Surface_Type", "")),
                'construction_name': str(getattr(surface, "Construction_Name", "")),
                'boundary_condition': str(getattr(surface, "Outside_Boundary_Condition", "")),
                'zone_name': str(getattr(surface, "Zone_Name", "")),
                'area': safe_float(getattr(surface, "area", 0.0)),
                'raw_object': surface
            }

        if 'FENESTRATIONSURFACE:DETAILED' in self._idf.idfobjects:
            for window in self._idf.idfobjects['FENESTRATIONSURFACE:DETAILED']:
                window_id = str(window.Name)
                base_surface = str(getattr(window, "Building_Surface_Name", ""))
                zone_name = ""

                if base_surface and base_surface in self._surfaces_cache:
                    zone_name = self._surfaces_cache[base_surface]['zone_name']

                construction_name = str(getattr(window, "Construction_with_Shading_Name", ""))
                if not construction_name:
                    construction_name = str(getattr(window, "Construction_Name", ""))

                window_data = {
                    'id': window_id,
                    'name': window_id,
                    'surface_type': 'Window',
                    'construction_name': construction_name,
                    'base_surface': base_surface,
                    'boundary_condition': 'Outdoors',
                    'zone_name': zone_name,
                    'area': safe_float(getattr(window, "area", 0.0)),
                    'is_glazing': True,
                    'raw_object': window
                }

                self._windows_cache[window_id] = window_data

                self._surfaces_cache[window_id] = window_data

    def _cache_materials(self) -> None:
        """Cache raw material data"""
        if not self._idf:
            return

        self._materials_cache.clear()
        self._window_glazing_cache.clear()
        self._window_gas_cache.clear()
        self._window_shade_cache.clear()
        self._window_simple_glazing_cache.clear()

        for material in self._idf.idfobjects['MATERIAL']:
            material_id = str(material.Name)

            self._materials_cache[material_id] = {
                'id': material_id,
                'name': material_id,
                'conductivity': safe_float(getattr(material, "Conductivity", 0.0)),
                'density': safe_float(getattr(material, "Density", 0.0)),
                'specific_heat': safe_float(getattr(material, "Specific_Heat", 0.0)),
                'thickness': safe_float(getattr(material, "Thickness", 0.0)),
                'solar_absorptance': safe_float(getattr(material, "Solar_Absorptance", 0.0)),
                'raw_object': material
            }

        if 'WINDOWMATERIAL:GLAZING' in self._idf.idfobjects:
            for glazing in self._idf.idfobjects['WINDOWMATERIAL:GLAZING']:
                material_id = str(glazing.Name)

                self._window_glazing_cache[material_id] = {
                    'id': material_id,
                    'name': material_id,
                    'thickness': safe_float(getattr(glazing, "Thickness", 0.0)),
                    'solar_transmittance': safe_float(getattr(glazing, "Solar_Transmittance_at_Normal_Incidence", 0.0)),
                    'visible_transmittance': safe_float(getattr(glazing, "Visible_Transmittance_at_Normal_Incidence", 0.0)),
                    'conductivity': safe_float(getattr(glazing, "Conductivity", 0.0)),
                    'u_factor': safe_float(getattr(glazing, "Conductivity", 0.0)) / safe_float(getattr(glazing, "Thickness", 1.0)),
                    'raw_object': glazing
                }

        if 'WINDOWMATERIAL:GAS' in self._idf.idfobjects:
            for gas in self._idf.idfobjects['WINDOWMATERIAL:GAS']:
                material_id = str(gas.Name)

                self._window_gas_cache[material_id] = {
                    'id': material_id,
                    'name': material_id,
                    'gas_type': str(getattr(gas, "Gas_Type", "")),
                    'thickness': safe_float(getattr(gas, "Thickness", 0.0)),
                    'raw_object': gas
                }

        if 'WINDOWMATERIAL:SHADE' in self._idf.idfobjects:
            for shade in self._idf.idfobjects['WINDOWMATERIAL:SHADE']:
                material_id = str(shade.Name)

                self._window_shade_cache[material_id] = {
                    'id': material_id,
                    'name': material_id,
                    'thickness': safe_float(getattr(shade, "Thickness", 0.0)),
                    'conductivity': safe_float(getattr(shade, "Conductivity", 0.0)),
                    'visible_reflectance': safe_float(getattr(shade, "Visible_Reflectance", 0.0)),
                    'solar_reflectance': safe_float(getattr(shade, "Solar_Reflectance", 0.0)),
                    'solar_transmittance': safe_float(getattr(shade, "Solar_Transmittance", 0.0)),
                    'visible_transmittance': safe_float(getattr(shade, "Visible_Transmittance", 0.0)),
                    'shade_to_glass_distance': safe_float(getattr(shade, "Shade_to_Glass_Distance", 0.0)),
                    'infrared_transmittance': safe_float(getattr(shade, "Infrared_Transmittance", 0.0)),
                    'infrared_hemispheric_emissivity': safe_float(getattr(shade, "Infrared_Hemispherical_Emissivity", 0.0)),
                    'thermal_resistance': safe_float(getattr(shade, "Thermal_Resistance", 0.0)),
                    'raw_object': shade
                }

        if 'WINDOWMATERIAL:SIMPLEGLAZINGSYSTEM' in self._idf.idfobjects:
            for simple_glazing in self._idf.idfobjects['WINDOWMATERIAL:SIMPLEGLAZINGSYSTEM']:
                material_id = str(simple_glazing.Name)

                self._window_simple_glazing_cache[material_id] = {
                    'id': material_id,
                    'name': material_id,
                    'u_factor': safe_float(getattr(simple_glazing, "UFactor", 0.0)),
                    'shgc': safe_float(getattr(simple_glazing, "Solar_Heat_Gain_Coefficient", 0.0)),
                    'visible_transmittance': safe_float(getattr(simple_glazing, "Visible_Transmittance", 0.0)),
                    'raw_object': simple_glazing
                }

    def _cache_constructions(self) -> None:
        """Cache raw construction data"""
        if not self._idf:
            return

        self._constructions_cache.clear()
        self._constructions_glazing_cache.clear()

        for construction in self._idf.idfobjects['CONSTRUCTION']:
            construction_id = str(construction.Name)

            layer_fields = [f for f in construction.fieldnames if f.startswith('Layer_')]
            material_layers = [
                str(getattr(construction, field, ""))
                for field in layer_fields
                if getattr(construction, field, "")
            ]
            outside_layer = str(getattr(construction, "Outside_Layer", ""))
            if outside_layer:
                material_layers.insert(0, outside_layer)

            if construction_id == 'LinearBridgingConstruction' or construction_id == 'IRTSurface':
                continue

            is_glazing_construction = False
            for layer_name in material_layers:
                if (layer_name in self._window_glazing_cache or
                    layer_name in self._window_gas_cache or
                    layer_name in self._window_shade_cache or
                    layer_name in self._window_simple_glazing_cache):
                    is_glazing_construction = True
                    break

            if is_glazing_construction:
                self._constructions_glazing_cache[construction_id] = {
                    'id': construction_id,
                    'name': construction_id,
                    'material_layers': material_layers,
                    'raw_object': construction
                }
                continue
            else:
                self._constructions_cache[construction_id] = {
                    'id': construction_id,
                    'name': construction_id,
                    'material_layers': material_layers,
                    'raw_object': construction
                }

    def _cache_schedules(self) -> None:
        """Cache raw schedule data"""
        if not self._idf:
            return

        self._schedules_cache.clear()
        self._schedule_rules_cache.clear()

        for schedule in self._idf.idfobjects['SCHEDULE:COMPACT']:
            schedule_id = str(schedule.Name)
            schedule_type = str(schedule.Schedule_Type_Limits_Name)

            rule_fields = [str(field) for field in schedule.fieldvalues[2:] if field.strip()]

            is_hvac_indicator = self._is_hvac_indicator(schedule_id, schedule_type)

            self._schedules_cache[schedule_id] = {
                'id': schedule_id,
                'name': schedule_id,
                'type': schedule_type,
                'is_hvac_indicator': is_hvac_indicator,
                'raw_object': schedule
            }

            self._schedule_rules_cache[schedule_id] = rule_fields

    def _cache_loads(self) -> None:
        """Cache raw load data (people, lights, equipment, etc.)"""
        if not self._idf:
            return

        self._people_cache.clear()
        for people in self._idf.idfobjects.get('PEOPLE', []):
            zone_name = str(getattr(people, "Zone_or_ZoneList_Name", ""))
            if not zone_name:
                continue

            if zone_name not in self._people_cache:
                self._people_cache[zone_name] = []

            self._people_cache[zone_name].append({
                'people_per_area': safe_float(getattr(people, "People_per_Zone_Floor_Area", 0.0)),
                'number_of_people': safe_float(getattr(people, "Number_of_People", 0.0)),
                'schedule': str(getattr(people, "Number_of_People_Schedule_Name", "")),
                'activity_schedule': str(getattr(people, "Activity_Level_Schedule_Name", "")),
                'clothing_schedule': str(getattr(people, "Clothing_Insulation_Schedule_Name", "")),
                'raw_object': people
            })

        self._lights_cache.clear()
        for lights in self._idf.idfobjects.get('LIGHTS', []):
            zone_name = str(getattr(lights, "Zone_or_ZoneList_Name", ""))
            if not zone_name:
                continue

            if zone_name not in self._lights_cache:
                self._lights_cache[zone_name] = []

            self._lights_cache[zone_name].append({
                'name': str(getattr(lights, "Name", "")),
                'zone_name': zone_name,
                'watts_per_area': safe_float(getattr(lights, "Watts_per_Zone_Floor_Area", 0.0)),
                'lighting_level': safe_float(getattr(lights, "Lighting_Level", 0.0)),
                'watts_per_person': safe_float(getattr(lights, "Watts_per_Person", 0.0)),
                'design_level_calculation_method': str(getattr(lights, "Design_Level_Calculation_Method", "")),
                'schedule': str(getattr(lights, "Schedule_Name", "")),
                'raw_object': lights
            })

        self._cache_exterior_lights()

        self._equipment_cache.clear()
        for equip_type in ['ELECTRICEQUIPMENT', 'OTHEREQUIPMENT']:
            for equip in self._idf.idfobjects.get(equip_type, []):
                zone_name = str(getattr(equip, "Zone_or_ZoneList_Name", ""))
                if not zone_name:
                    continue

                if zone_name not in self._equipment_cache:
                    self._equipment_cache[zone_name] = []

                equip_name = str(getattr(equip, "Name", ""))
                is_fixed = not ("Miscellaneous" in equip_name)

                self._equipment_cache[zone_name].append({
                    'name': equip_name,
                    'type': "fixed" if is_fixed else "non_fixed",
                    'watts_per_area': safe_float(getattr(equip, "Power_per_Zone_Floor_Area", 0.0)),
                    'schedule': str(getattr(equip, "Schedule_Name", "")),
                    'raw_object': equip
                })

        self._infiltration_cache.clear()
        for infil in self._idf.idfobjects.get('ZONEINFILTRATION:DESIGNFLOWRATE', []):
            zone_name = str(getattr(infil, "Zone_or_ZoneList_Name", ""))
            if not zone_name:
                continue

            if zone_name not in self._infiltration_cache:
                self._infiltration_cache[zone_name] = []

            self._infiltration_cache[zone_name].append({
                'air_changes_per_hour': safe_float(getattr(infil, "Constant_Term_Coefficient", 0.0)),
                'schedule': str(getattr(infil, "Schedule_Name", "")),
                'raw_object': infil
            })

        self._cache_ventilation_loads()

    def _cache_ventilation_loads(self) -> None:
        """Cache raw ventilation data from ZoneVentilation:DesignFlowRate objects."""
        self._ventilation_cache.clear()
        if 'ZONEVENTILATION:DESIGNFLOWRATE' in self._idf.idfobjects:
            for vent in self._idf.idfobjects['ZONEVENTILATION:DESIGNFLOWRATE']:
                zone_name = str(getattr(vent, "Zone_or_ZoneList_Name", ""))
                if not zone_name:
                    continue

                if zone_name not in self._ventilation_cache:
                    self._ventilation_cache[zone_name] = []

                self._ventilation_cache[zone_name].append({
                    'schedule_name': str(getattr(vent, "Schedule_Name", "")),
                    'design_flow_rate': safe_float(getattr(vent, "Design_Flow_Rate", 0.0)),
                    'ventilation_type': str(getattr(vent, "Ventilation_Type", "")),
                    'min_indoor_temp': safe_float(getattr(vent, "Minimum_Indoor_Temperature", 0.0)),
                    'max_indoor_temp': safe_float(getattr(vent, "Maximum_Indoor_Temperature", 0.0)),
                    'max_temp_difference': safe_float(getattr(vent, "Delta_Temperature", 0.0)),
                    'min_outdoor_temp': safe_float(getattr(vent, "Minimum_Outdoor_Temperature", 0.0)),
                    'max_outdoor_temp': safe_float(getattr(vent, "Maximum_Outdoor_Temperature", 0.0)),
                    'max_wind_speed': safe_float(getattr(vent, "Maximum_Wind_Speed", 0.0)),
                    'raw_object': vent
                })

    def _cache_exterior_lights(self) -> None:
        """Cache raw Exterior:Lights data"""
        if not self._idf:
            return

        self._exterior_lights_cache.clear()
        for ext_light in self._idf.idfobjects.get('EXTERIOR:LIGHTS', []):
            self._exterior_lights_cache.append({
                'name': str(getattr(ext_light, "Name", "")),
                'schedule_name': str(getattr(ext_light, "Schedule_Name", "")),
                'design_level': safe_float(getattr(ext_light, "Design_Level", 0.0)),
                'raw_object': ext_light
            })

    def _cache_window_shading_controls(self) -> None:
        """Cache window shading control data"""
        if not self._idf:
            return

        self._window_shading_control_cache.clear()

        window_shading_control_objects = self._idf.idfobjects.get('WINDOWSHADINGCONTROL', [])
        if not window_shading_control_objects:
            return

        first_control = window_shading_control_objects[0]
        fenestration_fields = [f for f in first_control.fieldnames
                               if f.startswith('Fenestration_Surface_') and f.endswith('_Name')]

        for shading_control in window_shading_control_objects:
            control_id = str(shading_control.Name)
            zone_name = str(getattr(shading_control, "Zone_Name", ""))

            window_names = []
            for field in fenestration_fields:
                window_name = str(getattr(shading_control, field, ""))
                if window_name:
                    window_names.append(window_name)

            self._window_shading_control_cache[control_id] = {
                'id': control_id,
                'name': control_id,
                'zone_name': zone_name,
                'shading_type': str(getattr(shading_control, "Shading_Type", "")),
                'construction_with_shading_name': str(getattr(shading_control, "Construction_with_Shading_Name", "")),
                'shading_control_type': str(getattr(shading_control, "Shading_Control_Type", "")),
                'schedule_name': str(getattr(shading_control, "Schedule_Name", "")),
                'is_scheduled': str(getattr(shading_control, "Shading_Control_Is_Scheduled", "")).lower() == "yes",
                'glare_control_is_active': str(getattr(shading_control, "Glare_Control_Is_Active", "")).lower() == "yes",
                'window_names': window_names,
                'raw_object': shading_control
            }

    def _cache_frame_dividers(self) -> None:
        """Cache raw WindowProperty:FrameAndDivider data"""
        if not self._idf:
            return

        self._frame_divider_cache.clear()

        if 'WINDOWPROPERTY:FRAMEANDDIVIDER' in self._idf.idfobjects:
            for frame_divider in self._idf.idfobjects['WINDOWPROPERTY:FRAMEANDDIVIDER']:
                fd_id = str(frame_divider.Name)

                self._frame_divider_cache[fd_id] = {
                    'id': fd_id,
                    'name': fd_id,
                    'frame_width': safe_float(getattr(frame_divider, "Frame_Width", 0.0)),
                    'frame_conductance': safe_float(getattr(frame_divider, "Frame_Conductance", 0.0)),
                    'raw_object': frame_divider
                }
    def _cache_daylighting(self) -> None:
        """Cache raw daylighting data"""
        if not self._idf:
            return

        self._daylighting_controls_cache.clear()
        self._daylighting_reference_point_cache.clear()

        if 'DAYLIGHTING:CONTROLS' in self._idf.idfobjects:
            for control in self._idf.idfobjects['DAYLIGHTING:CONTROLS']:
                control_id = str(control.Name)
                self._daylighting_controls_cache[control_id] = {
                    'id': control_id,
                    'raw_object': control
                }

        if 'DAYLIGHTING:REFERENCEPOINT' in self._idf.idfobjects:
            for ref_point in self._idf.idfobjects['DAYLIGHTING:REFERENCEPOINT']:
                ref_point_id = str(ref_point.Name)
                self._daylighting_reference_point_cache[ref_point_id] = {
                    'id': ref_point_id,
                    'raw_object': ref_point
                }

    def _cache_outdoor_air_specifications(self) -> None:
        """Cache raw DesignSpecification:OutdoorAir data"""
        if not self._idf:
            return

        self._outdoor_air_spec_cache.clear()
        if 'DESIGNSPECIFICATION:OUTDOORAIR' in self._idf.idfobjects:
            for spec in self._idf.idfobjects['DESIGNSPECIFICATION:OUTDOORAIR']:

                spec_name = str(getattr(spec, "Name", ""))
                if not spec_name:
                    continue

                self._outdoor_air_spec_cache[spec_name] = {
                    'id': spec_name,
                    'zone_name': spec_name,
                    'outdoor_air_flow_per_person': safe_float(getattr(spec, "Outdoor_Air_Flow_per_Person", 0.0)),
                    'outdoor_air_flow_rate_fraction_schedule_name': str(getattr(spec, "Outdoor_Air_Schedule_Name", "")),
                    'raw_object': spec
                }

    def _cache_ideal_loads(self) -> None:
        """Cache ZoneHVAC:IdealLoadsAirSystem data linked to zones."""
        if not self._idf:
            return

        self._ideal_loads_cache.clear()
        if 'ZONEHVAC:IDEALLOADSAIRSYSTEM' in self._idf.idfobjects:
            for ideal_load in self._idf.idfobjects['ZONEHVAC:IDEALLOADSAIRSYSTEM']:
                ideal_load_name = str(getattr(ideal_load, "Name", ""))
                if not ideal_load_name:
                    continue

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
                    'max_heating_supply_air_temperature': safe_float(getattr(ideal_load, "Maximum_Heating_Supply_Air_Temperature", 0.0)),
                    'min_cooling_supply_air_temperature': safe_float(getattr(ideal_load, "Minimum_Cooling_Supply_Air_Temperature", 0.0)),
                    'max_heating_supply_air_humidity_ratio': safe_float(getattr(ideal_load, "Maximum_Heating_Supply_Air_Humidity_Ratio", 0.0)),
                    'min_cooling_supply_air_humidity_ratio': safe_float(getattr(ideal_load, "Minimum_Cooling_Supply_Air_Humidity_Ratio", 0.0)),
                    'heating_limit': str(getattr(ideal_load, "Heating_Limit", "")),
                    'cooling_limit': str(getattr(ideal_load, "Cooling_Limit", "")),
                    'dehumidification_control_type': str(getattr(ideal_load, "Dehumidification_Control_Type", "")),
                    'humidification_control_type': str(getattr(ideal_load, "Humidification_Control_Type", "")),
                    'raw_object': ideal_load
                })

    def _get_idfobjects(self, key: str) -> list:
        """Helper to safely get IDF objects by key, returns empty list if not found."""
        return self._idf.idfobjects.get(key, []) if self._idf and hasattr(self._idf, 'idfobjects') else []

    def _get_field(self, obj, field: str, default=None):
        """Helper to safely get a field from an object."""
        return getattr(obj, field, default)

    def _cache_dict(self, idf_key: str, cache: dict, fields: dict, type_name: str = None):
        """Generic cache helper for simple IDF objects."""
        cache.clear()
        for obj in self._get_idfobjects(idf_key):
            obj_id = str(self._get_field(obj, 'Name', ''))
            if not obj_id:
                continue
            entry = {'id': obj_id, 'name': obj_id, 'raw_object': obj}
            for k, v in fields.items():
                entry[k] = v(obj)
            if type_name:
                entry['type'] = type_name
            cache[obj_id] = entry

    def get_zones(self) -> Dict[str, Dict[str, Any]]:
        """Get cached zone data."""
        return self._zones_cache

    def get_hvac_zones(self) -> List[str]:
        """Get cached HVAC zone names."""
        return self._hvac_zones_cache

    def get_surfaces(self) -> Dict[str, Dict[str, Any]]:
        """Get cached surface data."""
        return self._surfaces_cache

    def _build_all_materials_cache(self) -> None:
        """
        Merges all individual material type caches into a single comprehensive cache
        and adds a 'type' field to each material. Called once during load_file.
        """
        if not self._idf:
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

    def get_materials(self) -> Dict[str, Dict[str, Any]]:
        """Get the fully processed and cached material data, merging all material types."""
        return self._all_materials_cache_complete

    def get_constructions(self) -> Dict[str, Dict[str, Any]]:
        """Get cached construction data"""
        return self._constructions_cache

    def get_schedules(self) -> Dict[str, Dict[str, Any]]:
        """Get cached schedule data"""
        return self._schedules_cache

    def get_schedule_rules(self, schedule_id: str) -> List[str]:
        """Get cached rules for a specific schedule"""
        return self._schedule_rules_cache.get(schedule_id, [])

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

    def get_idf(self):
        """
        Get the raw IDF object.
        This is a fallback for parsers that need direct access.
        """
        return self._idf

    def get_idf_path(self) -> Optional[str]:
        """Get the path of the loaded IDF file"""
        return self._idf_path
    def get_daylighting_controls(self) -> Dict[str, Dict[str, Any]]:
        """Return cached raw Daylighting:Controls data"""
        return self._daylighting_controls_cache

    def get_daylighting_reference_points(self) -> Dict[str, Dict[str, Any]]:
        """Return cached raw Daylighting:ReferencePoint data"""
        return self._daylighting_reference_point_cache

    def get_outdoor_air_specifications(self) -> Dict[str, Dict[str, Any]]:
        """Get cached DesignSpecification:OutdoorAir data"""
        return self._outdoor_air_spec_cache

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

    def get_natural_ventilation_data(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get cached natural ventilation data from ZoneVentilation:DesignFlowRate objects"""
        return self._ventilation_cache
