"""
DataLoader module for direct IDF data access.
Provides simplified data loading and retrieval functionality.
"""
from typing import Dict, Optional, List, Any, Union
from pathlib import Path
import re
from utils.eppy_handler import EppyHandler

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
        self._loaded_sections = set()
        
        # Basic caches for raw IDF data
        self._zones_cache = {}
        self._hvac_zones_cache = []
        self._surfaces_cache = {}
        self._materials_cache = {}
        self._constructions_cache = {}
        self._schedules_cache = {}
        self._schedule_rules_cache = {}
        self._people_cache = {}
        self._lights_cache = {}
        self._equipment_cache = {}
        self._infiltration_cache = {}
        self._ventilation_cache = {}
        self._windows_cache = {}
        
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
        self._idf = self._eppy_handler.load_idf(idf_path)
        self._loaded_sections = {'zones', 'surfaces', 'materials', 'constructions', 'schedules'}
        
        # Pre-cache raw data
        print("Pre-caching IDF data...")
        self._cache_schedules()
        self._cache_zones()
        self._cache_surfaces()
        self._cache_materials()
        self._cache_constructions()
        self._cache_loads()
        print("Basic IDF data cached successfully")
    
    def _cache_zones(self) -> None:
        """Cache raw zone data"""
        if not self._idf:
            return
            
        self._zones_cache.clear()
        
        for zone in self._idf.idfobjects['ZONE']:
            zone_id = str(zone.Name)
            
            
            for schedule_id, schedule_data in self._schedules_cache.items():
                if zone_id in schedule_id and 'Temperature' in schedule_data["type"] and ("heating" in schedule_data['name'].lower() or "cooling" in schedule_data['name'].lower()) and "setpoint" not in schedule_data['type'].lower():
                    self._hvac_zones_cache.append(zone_id)
                    break
            # Extract area_id
            area_id = None
            try:
                split = zone_id.split(":", 1)
                if len(split) > 1 and split[1]:
                    if re.match(r"^\d{2}", split[1]):
                        area_id = split[1][:2]  # Take first 2 chars if starts with digits
                    else:
                        area_id = split[1]  # Take whole string after colon
            except Exception as e:
                print(f"Warning: Could not extract area_id for zone '{zone_id}': {e}")
            
            # Cache raw zone data
            self._zones_cache[zone_id] = {
                'id': zone_id,
                'name': zone_id,
                'area_id': area_id,
                'floor_area': safe_float(getattr(zone, "Floor_Area", 0.0)),
                'volume': safe_float(getattr(zone, "Volume", 0.0)),
                'multiplier': int(safe_float(getattr(zone, "Multiplier", 1))),
                'raw_object': zone  # Store the raw object for parsers
            }
    
    def _cache_surfaces(self) -> None:
        """Cache raw surface data"""
        if not self._idf:
            return
            
        self._surfaces_cache.clear()
        
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
    
    def _cache_materials(self) -> None:
        """Cache raw material data"""
        if not self._idf:
            return
            
        self._materials_cache.clear()
        
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
    
    def _cache_constructions(self) -> None:
        """Cache raw construction data"""
        if not self._idf:
            return
            
        self._constructions_cache.clear()
        
        for construction in self._idf.idfobjects['CONSTRUCTION']:
            construction_id = str(construction.Name)
            
            # Get material layers
            layer_fields = [f for f in construction.fieldnames if f.startswith('Layer_')]
            material_layers = [
                str(getattr(construction, field, ""))
                for field in layer_fields
                if getattr(construction, field, "") 
            ]
            
            # Cache raw construction data
            self._constructions_cache[construction_id] = {
                'id': construction_id,
                'name': construction_id,
                'material_layers': material_layers,
                'raw_object': construction  # Store the raw object for parsers
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
            
            # Cache raw schedule data
            self._schedules_cache[schedule_id] = {
                'id': schedule_id,
                'name': schedule_id,
                'type': schedule_type,
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
            if equip_type not in self._idf.idfobjects:
                continue
                
            for equip in self._idf.idfobjects[equip_type]:
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
    
    # Simple getter methods for cached data
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
        """Get cached material data"""
        return self._materials_cache
    
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