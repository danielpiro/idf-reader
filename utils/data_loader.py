"""
DataLoader module for direct IDF data access.
Provides simplified data loading and retrieval functionality.
"""
from typing import Dict, Optional, List, Any
from pathlib import Path
import re
from utils.eppy_handler import EppyHandler

# Pre-compile regex for area_id extraction
AREA_ID_REGEX = re.compile(r"^\d{2}")

def safe_float(value: Any, default: float = 0.0) -> float:
    """
    Safely convert a value to float, returning a default if conversion fails.
    Handles numpy float types by converting them to Python floats.
    
    Args:
        value: Value to convert to float
        default: Default value to return if conversion fails
        
    Returns:
        float: Converted value or default
    """
    if value is None or value == '':
        return default
        
    try:
        # Handle numpy float types by converting to Python float
        if hasattr(value, 'item'):  # Check if it's a numpy type
            return float(value.item())
        return float(value)
    except (ValueError, TypeError, AttributeError):
        return default


class DataLoader:
    """
    Simplified DataLoader class focused on caching raw IDF data.
    Implementation details for processing have been moved to the respective parsers.
    """
    def __init__(self):
        self._idf = None
        self._eppy_handler = None
        self._idf_path = None # Store the path
        self._loaded_sections = set()
        
        # Basic caches for raw IDF data
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
        self._equipment_cache = {}
        self._infiltration_cache = {}
        self._ventilation_cache = {}
        self._windows_cache = {}
        
        # Window-related material caches
        self._window_glazing_cache = {}
        self._window_gas_cache = {}
        self._window_shade_cache = {}
        self._window_simple_glazing_cache = {}
        self._window_shading_control_cache = {}
        self._frame_divider_cache = {} # Added cache for FrameAndDivider
        self._daylighting_controls_cache = {}
        self._daylighting_reference_point_cache = {}
        
    def load_file(self, idf_path: str, idd_path: Optional[str] = None) -> None:
        """
        Load IDF file and cache raw data.
        
        Args:
            idf_path: Path to the IDF file
            idd_path: Optional path to the IDD file
            
        Raises:
            FileNotFoundError: If IDF or IDD file not found
        """
        if not Path(idf_path).exists():
            raise FileNotFoundError(f"IDF file not found at '{idf_path}'")
            
        self._eppy_handler = EppyHandler(idd_path)
        self._idf_path = idf_path # Store the path
        self._idf = self._eppy_handler.load_idf(idf_path)
        self._loaded_sections = {'zones', 'surfaces', 'materials', 'constructions', 'schedules'}
        
        # Pre-cache raw data
        self._check_output()
        self._cache_schedules()
        self._cache_zones()
        self._cache_surfaces()
        self._cache_materials()
        self._cache_constructions()
        self._cache_loads()
        self._cache_window_shading_controls()
        self._cache_frame_dividers()
        self._cache_daylighting()
        # self._filter_constructions_glazing() # Moved to glazing_parser

    def _check_output(self) -> None:
        """Check if the IDF file is loaded and output is available"""
        if not self._idf:
            return
            
        # Check if output is available
        if 'OUTPUT:VARIABLE' not in self._idf.idfobjects:
            output_variable = self._idf.newidfobject('OUTPUT:VARIABLE')
            output_variable.Key_Value = '*'
            output_variable.Variable_Name = 'Zone Ideal Loads Supply Air Total Cooling Energy'
            output_variable.Reporting_Frequency = 'RunPeriod'
            output_variable = self._idf.newidfobject('OUTPUT:VARIABLE')
            output_variable.Key_Value = '*'
            output_variable.Variable_Name = 'Zone Ideal Loads Supply Air Total Heating Energy'
            output_variable.Reporting_Frequency = 'RunPeriod'
        else:
            pass
    
    def _cache_zones(self) -> None:
        """Cache raw zone data"""
        if not self._idf:
            return
            
        self._zones_cache.clear()
        
        for zone in self._idf.idfobjects['ZONE']:
            zone_id = str(zone.Name)
            
            # Check against pre-calculated flags in schedules
            for schedule_id, schedule_data in self._schedules_cache.items():
                if schedule_data['is_hvac_indicator'] and zone_id in schedule_id:
                    self._hvac_zones_cache.append(zone_id)
                    break # Found one, no need to check other schedules for this zone
                    
            # Extract area_id
            area_id = None
            try:
                split = zone_id.split(":", 1)
                if len(split) > 1 and split[1]:
                    if AREA_ID_REGEX.match(split[1]):
                        area_id = split[1][:2]  # Take first 2 chars if starts with digits
                    else:
                        area_id = split[1]  # Take whole string after colon
            except:
                pass # Silently ignore if area_id extraction fails
            
            # Cache raw zone data
            self._zones_cache[zone_id] = {
                'id': zone_id,
                'name': zone_id,
                'area_id': area_id,
                'floor_area': safe_float(getattr(zone, "Floor_Area", 0.0)),
                'volume': safe_float(getattr(zone, "Volume", 0.0)),
                'multiplier': int(safe_float(getattr(zone, "Multiplier", 1))),
                'raw_object': zone,  # Store the raw object for parsers
                'surfaces': zone.zonesurfaces  # Updated to include surfaces
            }
    
    def _cache_surfaces(self) -> None:
        """Cache raw surface data"""
        if not self._idf:
            return
            
        self._surfaces_cache.clear()
        self._windows_cache = {}  # Initialize windows cache
        
        # Process regular surfaces
        for surface in self._idf.idfobjects['BUILDINGSURFACE:DETAILED']:
            surface_id = str(surface.Name)
            
            # Cache raw surface data
            self._surfaces_cache[surface_id] = {
                'id': surface_id,
                'name': surface_id,
                'surface_type': str(getattr(surface, "Surface_Type", "")),
                'construction_name': str(getattr(surface, "Construction_Name", "")),
                'boundary_condition': str(getattr(surface, "Outside_Boundary_Condition", "")),
                'zone_name': str(getattr(surface, "Zone_Name", "")),
                'area': safe_float(getattr(surface, "area", 0.0)),  # Get area directly from the object
                'raw_object': surface  # Store the raw object for parsers
            }
        
        # Process windows (fenestration surfaces)
        if 'FENESTRATIONSURFACE:DETAILED' in self._idf.idfobjects:
            for window in self._idf.idfobjects['FENESTRATIONSURFACE:DETAILED']:
                window_id = str(window.Name)
                base_surface = str(getattr(window, "Building_Surface_Name", ""))
                zone_name = ""
                
                # Get the zone name from the base surface
                if base_surface and base_surface in self._surfaces_cache:
                    zone_name = self._surfaces_cache[base_surface]['zone_name']
                
                # Get construction name, preferring the shading version if available
                construction_name = str(getattr(window, "Construction_with_Shading_Name", ""))
                if not construction_name:
                    construction_name = str(getattr(window, "Construction_Name", ""))
                
                # Cache window data
                window_data = {
                    'id': window_id,
                    'name': window_id,
                    'surface_type': 'Window',  # Windows are always of type "Window"
                    'construction_name': construction_name,
                    'base_surface': base_surface,
                    'boundary_condition': 'Outdoors',  # Windows typically have outdoors boundary
                    'zone_name': zone_name,
                    'area': safe_float(getattr(window, "area", 0.0)),
                    'is_glazing': True,
                    'raw_object': window
                }
                
                # Add to windows cache
                self._windows_cache[window_id] = window_data
                
                # Also add to the general surfaces cache to handle it the same way as other surfaces
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
        
        # Cache standard materials
        for material in self._idf.idfobjects['MATERIAL']:
            material_id = str(material.Name)
            
            # Cache raw material data
            self._materials_cache[material_id] = {
                'id': material_id,
                'name': material_id,
                'conductivity': safe_float(getattr(material, "Conductivity", 0.0)),
                'density': safe_float(getattr(material, "Density", 0.0)),
                'specific_heat': safe_float(getattr(material, "Specific_Heat", 0.0)),
                'thickness': safe_float(getattr(material, "Thickness", 0.0)),
                'solar_absorptance': safe_float(getattr(material, "Solar_Absorptance", 0.0)),
                'raw_object': material  # Store the raw object for parsers
            }
        
        # Cache WindowMaterial:Glazing
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
        
        # Cache WindowMaterial:Gas
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
        
        # Cache WindowMaterial:Shade
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
        
        # Cache WindowMaterial:SimpleGlazingSystem
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
        self._constructions_glazing_cache.clear() # Clear glazing cache too

        for construction in self._idf.idfobjects['CONSTRUCTION']:
            construction_id = str(construction.Name)

            # Get material layers
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

            # Check if the construction uses any window-specific materials
            is_glazing_construction = False
            for layer_name in material_layers:
                if (layer_name in self._window_glazing_cache or
                    layer_name in self._window_gas_cache or
                    layer_name in self._window_shade_cache or
                    layer_name in self._window_simple_glazing_cache):
                    is_glazing_construction = True
                    break

            if is_glazing_construction:
                 # Add to glazing cache; type will be determined by the GlazingParser
                self._constructions_glazing_cache[construction_id] = {
                    'id': construction_id,
                    'name': construction_id,
                    'material_layers': material_layers,
                    'raw_object': construction
                    # 'type' key removed
                }
                # Continue to ensure it's only in the glazing cache, not the general one
                continue
            else:
                # Cache raw non-glazing construction data
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
            
            # Get all non-empty fields after Name and Type
            rule_fields = []
            for field in schedule.fieldvalues[2:]:  # Skip Name and Type
                if field.strip():
                    rule_fields.append(str(field))
            
            # Determine if schedule indicates HVAC zone (based on type/name)
            schedule_name_lower = schedule_id.lower()
            schedule_type_lower = schedule_type.lower()
            is_hvac_indicator = (
                'temperature' in schedule_type_lower and
                ('heating' in schedule_name_lower or 'cooling' in schedule_name_lower) and
                'setpoint' not in schedule_type_lower
            )

            # Cache raw schedule data
            self._schedules_cache[schedule_id] = {
                'id': schedule_id,
                'name': schedule_id,
                'type': schedule_type,
                'is_hvac_indicator': is_hvac_indicator, # Add the pre-calculated flag
                'raw_object': schedule  # Store the raw object for parsers
            }

            # Cache rules separately
            self._schedule_rules_cache[schedule_id] = rule_fields
    
    def _cache_loads(self) -> None:
        """Cache raw load data (people, lights, equipment, etc.)"""
        if not self._idf:
            return
            
        # Cache people loads
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
                'raw_object': people  # Store the raw object for parsers
            })
        
        # Cache lights loads
        self._lights_cache.clear()
        for lights in self._idf.idfobjects.get('LIGHTS', []):
            zone_name = str(getattr(lights, "Zone_or_ZoneList_Name", ""))
            if not zone_name:
                continue
                
            if zone_name not in self._lights_cache:
                self._lights_cache[zone_name] = []
                
            self._lights_cache[zone_name].append({
                'watts_per_area': safe_float(getattr(lights, "Watts_per_Zone_Floor_Area", 0.0)),
                'schedule': str(getattr(lights, "Schedule_Name", "")),
                'raw_object': lights  # Store the raw object for parsers
            })
        
        # Cache equipment loads
        self._equipment_cache.clear()
        for equip_type in ['ELECTRICEQUIPMENT', 'OTHEREQUIPMENT']:
            # Use .get() to safely iterate over equipment types, defaulting to empty list if type doesn't exist
            for equip in self._idf.idfobjects.get(equip_type, []):
                zone_name = str(getattr(equip, "Zone_or_ZoneList_Name", ""))
                if not zone_name:
                    continue # Skip if zone name is missing
                    
                if zone_name not in self._equipment_cache:
                    self._equipment_cache[zone_name] = []
                    
                equip_name = str(getattr(equip, "Name", ""))
                is_fixed = not ("Miscellaneous" in equip_name)
                    
                self._equipment_cache[zone_name].append({
                    'name': equip_name,
                    'type': "fixed" if is_fixed else "non_fixed",
                    'watts_per_area': safe_float(getattr(equip, "Power_per_Zone_Floor_Area", 0.0)),
                    'schedule': str(getattr(equip, "Schedule_Name", "")),
                    'raw_object': equip  # Store the raw object for parsers
                })
        
        # Cache infiltration loads
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
                'raw_object': infil  # Store the raw object for parsers
            })
        
        # Cache ventilation loads
        self._ventilation_cache.clear()
        if 'ZONEVENTILATION:DESIGNFLOWRATE' in self._idf.idfobjects:
            for vent in self._idf.idfobjects['ZONEVENTILATION:DESIGNFLOWRATE']:
                zone_name = str(getattr(vent, "Zone_or_ZoneList_Name", ""))
                if not zone_name:
                    continue
                    
                if zone_name not in self._ventilation_cache:
                    self._ventilation_cache[zone_name] = []
                    
                self._ventilation_cache[zone_name].append({
                    'air_changes_per_hour': safe_float(getattr(vent, "Delta_Temperature", 0.0)),
                    'schedule': str(getattr(vent, "Schedule_Name", "")),
                    'raw_object': vent  # Store the raw object for parsers
                })
    
    def _cache_window_shading_controls(self) -> None:
        """Cache window shading control data"""
        if not self._idf:
            return
            
        self._window_shading_control_cache.clear()
        
        # Cache WindowShadingControl objects
        if 'WINDOWSHADINGCONTROL' in self._idf.idfobjects:
            for shading_control in self._idf.idfobjects['WINDOWSHADINGCONTROL']:
                control_id = str(shading_control.Name)
                zone_name = str(getattr(shading_control, "Zone_Name", ""))
                
                # Get the list of fenestration surfaces controlled by this shading control
                window_names = []
                fenestration_fields = [f for f in shading_control.fieldnames 
                                     if f.startswith('Fenestration_Surface_') and f.endswith('_Name')]
                
                for field in fenestration_fields:
                    window_name = str(getattr(shading_control, field, ""))
                    if window_name:
                        window_names.append(window_name)
                
                # Cache shading control data with all relevant fields
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

        # Cache Daylighting:Controls
        if 'DAYLIGHTING:CONTROLS' in self._idf.idfobjects:
            for control in self._idf.idfobjects['DAYLIGHTING:CONTROLS']:
                control_id = str(control.Name)
                self._daylighting_controls_cache[control_id] = {
                    'id': control_id,
                    'raw_object': control
                }

        # Cache Daylighting:ReferencePoint
        if 'DAYLIGHTING:REFERENCEPOINT' in self._idf.idfobjects:
            for ref_point in self._idf.idfobjects['DAYLIGHTING:REFERENCEPOINT']:
                ref_point_id = str(ref_point.Name)
                self._daylighting_reference_point_cache[ref_point_id] = {
                    'id': ref_point_id,
                    'raw_object': ref_point # Ensure no extra characters here
                }

    # _filter_constructions_glazing moved to parsers/glazing_parser.py


    # Getter methods for cached data
    def get_zones(self) -> Dict[str, Dict[str, Any]]:
        """Get cached zone data"""
        return self._zones_cache
    
    def get_hvac_zones(self) -> List[str]:
        """Get cached HVAC zone names"""
        return self._hvac_zones_cache
    
    def get_surfaces(self) -> Dict[str, Dict[str, Any]]:
        """Get cached surface data"""
        return self._surfaces_cache
    
    def get_materials(self) -> Dict[str, Dict[str, Any]]:
        """Get cached material data, merging all material types."""
        # Merge all relevant material caches into one dictionary
        merged_materials = {
            **self._materials_cache,
            **self._window_glazing_cache,
            **self._window_gas_cache,
            **self._window_shade_cache,
            **self._window_simple_glazing_cache
            # Add other window material caches if they exist and are needed
        }
        # Add type information to each material for easier identification in parsers
        for mat_id, mat_data in merged_materials.items():
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
            # Add elif for other types if necessary

        return merged_materials
    
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
    
    def get_windows(self) -> Dict[str, Dict[str, Any]]:
        """Get cached window data"""
        return self._windows_cache

    def get_raw_windows_cache(self) -> Dict[str, Dict[str, Any]]:
        """Get the raw windows cache (FenestrationSurface:Detailed objects)."""
        # This is the same as get_windows() currently, but provides a clearer name
        # for accessing the raw window objects if needed separately later.
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