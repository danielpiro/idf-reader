"""
DataLoader module for direct IDF data access.
Provides simplified data loading and retrieval functionality.
"""
from typing import Dict, Optional, List, Any, Union
from pathlib import Path
import re
from parsers.schedule_parser import ScheduleExtractor
from utils.eppy_handler import EppyHandler
from utils.data_models import (
    ZoneData, SurfaceData, ConstructionData,
    ScheduleData, MaterialData
)


def safe_float(value: Any, default: float = 0.0) -> float:
    """
    Safely convert a value to float, returning a default if conversion fails.
    
    Args:
        value: Value to convert to float
        default: Default value to return if conversion fails
        
    Returns:
        float: Converted value or default
    """
    if value is None or value == '':
        return default
        
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


class DataLoader:
    """
    Data loading class for IDF file parsing and object retrieval.
    Implements efficient data access with caching of frequently used lookups.
    """
    def __init__(self):
        self._idf = None
        self._eppy_handler = None
        self._loaded_sections = set()  # Keep track for compatibility
        
        # Cache for frequent lookups
        self._temp_schedules = {}      # Cache for temperature schedules
        self._zone_types = {}          # Cache for zone types
        self._materials = None         # Cache for materials
        self._floor_surfaces = {}      # Cache for floor surfaces by zone
        self._construction_props = {}  # Cache for construction properties
        self._surface_vertices = {}    # Cache for surface vertices
        self._schedules_cache = {}     # Cache for schedules with formatted names
        self._schedules_name_map = {}  # Cache for schedule name lookups
        
        # Additional caches for comprehensive data storage
        self._zones = None             # Cache for all zones
        self._surfaces = None          # Cache for all surfaces
        self._constructions = None     # Cache for all constructions
        self._loads = {}               # Cache for all loads by zone
        self._infiltration = {}        # Cache for infiltration by zone
        self._ventilation = {}         # Cache for ventilation by zone
        self._people = {}              # Cache for people loads by zone
        self._lights = {}              # Cache for lighting loads by zone
        self._equipment = {}           # Cache for equipment loads by zone
        self._windows = {}             # Cache for windows by surface
        
    def load_file(self, idf_path: str, idd_path: Optional[str] = None) -> None:
        """
        Load IDF file for data access and cache all data in memory.
        
        Args:
            idf_path: Path to the IDF file
            idd_path: Optional path to the IDD file
            
        Raises:
            FileNotFoundError: If IDF or IDD file not found
            Exception: Other errors during file loading
        """
        if not Path(idf_path).exists():
            raise FileNotFoundError(f"IDF file not found at '{idf_path}'")
            
        self._eppy_handler = EppyHandler(idd_path)
        self._idf = self._eppy_handler.load_idf(idf_path)
        self._loaded_sections = {'zones', 'surfaces', 'materials', 'constructions', 'schedules'}
        
        # Pre-cache all data at once so we don't need to read the file again
        print("Pre-caching all IDF data...")
        
        # Cache base data required by other functions
        self._cache_temp_schedules()
        self._cache_zone_types()
        
        # Cache all major data types
        self._materials = self._load_all_materials()
        self._zones = self._load_all_zones()
        self._surfaces = self._load_all_surfaces()
        self._constructions = self._load_all_constructions()
        
        # Cache derived data that depends on other caches
        self._cache_floor_surfaces()
        self._cache_construction_properties()
        self._cache_schedules()
        self._cache_loads_data()
        
        print("All IDF data cached successfully")
        
    def _cache_temp_schedules(self):
        """Pre-cache temperature schedules for efficient zone filtering."""
        self._temp_schedules.clear()
        for schedule in self._idf.idfobjects['SCHEDULE:COMPACT']:
            schedule_type = str(schedule.Schedule_Type_Limits_Name).lower()
            if schedule_type == "temperature":
                schedule_id = str(schedule.Name).split(' ')[0].lower()
                self._temp_schedules[schedule_id] = True
                
    def _cache_zone_types(self):
        """Pre-cache zone types for efficient schedule processing."""
        self._zone_types.clear()
        for zone in self._idf.idfobjects['ZONE']:
            zone_id = str(zone.Name)
            self._zone_types[zone_id] = "core" if any(
                keyword in zone_id.lower() for keyword in ['core', 'corridor', 'stair']
            ) else "regular"
                
    def get_all_zones(self) -> Dict[str, ZoneData]:
        """
        Get all zones that have HVAC systems.
        Filters out zones without temperature schedules and extracts area IDs.
        """
        if not self._idf:
            return {}

        zones = {}
        for zone in self._idf.idfobjects['ZONE']:
            zone_id = str(zone.Name)
            zone_id_lower = zone_id.lower()
            
            # Use cached temperature schedules lookup
            zone_base_id = zone_id_lower.split('_')[0] if '_' in zone_id_lower else zone_id_lower
            if zone_base_id not in self._temp_schedules:
                continue
            
            # Determine zone type and extract area ID
            zone_type = "regular"  # No core zone filtering needed
            
            # Extract area ID from zone ID
            area_id = None
            area_match = re.search(r':(\d{2})', zone_id)
            if area_match:
                area_id = area_match.group(1)
            
            zones[zone_id] = ZoneData(
                id=zone_id,
                name=zone_id,
                floor_area=safe_float(getattr(zone, "Floor_Area", 0.0)),
                volume=safe_float(getattr(zone, "Volume", 0.0)),
                multiplier=int(safe_float(getattr(zone, "Multiplier", 1))),
                type=zone_type,
                area_id=area_id
            )
        return zones
        
    def _extract_vertices(self, surface) -> List[tuple]:
        """
        Extract vertex coordinates from a surface object efficiently.
        
        Args:
            surface: The surface object to extract vertices from
            
        Returns:
            List[tuple]: List of (x,y,z) vertex coordinate tuples
        """
        vertices = []
        for i in range(1, 5):
            prefix = f'Vertex_{i}_'
            try:
                coords = [
                    safe_float(getattr(surface, f'{prefix}{coord}coordinate', 0.0))
                    for coord in ('X', 'Y', 'Z')
                ]
                if any(coords):  # Only add if we have non-zero coordinates
                    vertices.append(tuple(coords))
            except (AttributeError, ValueError):
                break
        return vertices

    def get_surface_vertices(self, surface_id: str) -> Optional[List[tuple]]:
        """
        Get vertex coordinates for a specific surface.
        
        Args:
            surface_id: ID of the surface
            
        Returns:
            Optional[List[tuple]]: List of (x,y,z) vertex coordinate tuples if found, None otherwise
        """
        if not self._idf:
            return None
            
        for surface in self._idf.idfobjects['BUILDINGSURFACE:DETAILED']:
            if str(surface.Name) == surface_id:
                vertices = self._extract_vertices(surface)
                return vertices if vertices else None
        return None

    def _cache_floor_surfaces(self):
        """Pre-cache floor surfaces organized by zone for efficient access."""
        if not self._idf:
            return

        self._floor_surfaces.clear()
        for surface in self._idf.idfobjects['BUILDINGSURFACE:DETAILED']:
            if str(surface.Surface_Type).lower() == "floor":
                zone_name = str(surface.Zone_Name)
                surface_data = SurfaceData(
                    id=str(surface.Name),
                    name=str(surface.Name),
                    surface_type="Floor",
                    construction_name=str(surface.Construction_Name),
                    boundary_condition=str(surface.Outside_Boundary_Condition),
                    zone_name=zone_name,
                    vertices=self._extract_vertices(surface)
                )
                
                if zone_name not in self._floor_surfaces:
                    self._floor_surfaces[zone_name] = []
                self._floor_surfaces[zone_name].append(surface_data)

    def _cache_construction_properties(self):
        """Pre-calculate and cache construction properties for efficient access."""
        if not self._idf:
            return

        materials = self.get_all_materials()  # Uses existing materials cache
        self._construction_props.clear()

        for construction in self._idf.idfobjects['CONSTRUCTION']:
            construction_id = str(construction.Name)
            total_resistance = 0.0
            total_thickness = 0.0

            # Get material layers
            layer_fields = [f for f in construction.fieldnames if f.startswith('Layer_')]
            for field in layer_fields:
                material_id = str(getattr(construction, field, ""))
                if not material_id:
                    continue
                    
                material = materials.get(material_id)
                if material and material.conductivity > 0:
                    total_resistance += material.thickness / material.conductivity
                    total_thickness += material.thickness

            self._construction_props[construction_id] = {
                'thickness': total_thickness,
                'conductivity': total_thickness / total_resistance if total_resistance > 0 else 0.0
            }

    def _cache_schedules(self):
        """Pre-cache schedules with formatted names for efficient access."""
        if not self._idf:
            return
            
        self._schedules_cache.clear()
        self._schedules_name_map.clear()
        
        for schedule in self._idf.idfobjects['SCHEDULE:COMPACT']:
            schedule_id = str(schedule.Name)
            schedule_type = str(schedule.Schedule_Type_Limits_Name)
            
            # Format schedule name for better display
            display_name = self._format_schedule_name(schedule_id)
            
            # Extract zone ID for HVAC schedules
            zone_id = self._extract_zone_id_from_schedule(schedule_id)
            zone_type = None
            if zone_id:
                # Use cached zone types
                matching_zone = next(
                    (zone_name for zone_name in self._zone_types
                     if zone_id.lower() in zone_name.lower()),
                    None
                )
                if matching_zone:
                    zone_type = self._zone_types[matching_zone]
            
            # Get all non-empty fields after Name and Type
            rule_fields = []
            for field in schedule.fieldvalues[2:]:  # Skip Name and Type
                if field.strip():
                    rule_fields.append(str(field))
            
            # Create schedule data
            schedule_data = {
                'id': schedule_id,
                'name': display_name,  # Use formatted name
                'original_name': schedule_id,  # Keep original ID
                'type': schedule_type,
                'raw_rules': rule_fields,
                'zone_id': zone_id,
                'zone_type': zone_type
            }
            
            # Cache by ID
            self._schedules_cache[schedule_id] = schedule_data
            
            # Create lookup by display name (lowercase for case-insensitivity)
            self._schedules_name_map[display_name.lower()] = schedule_id

    def get_all_surfaces(self) -> Dict[str, SurfaceData]:
        """Get all surface data including vertex coordinates efficiently."""
        if not self._idf:
            return {}
            
        surfaces = {}
        for surface in self._idf.idfobjects['BUILDINGSURFACE:DETAILED']:
            surface_id = str(surface.Name)
            
            # Get all required attributes in one pass
            attrs = {
                "Surface_Type": "",
                "Construction_Name": "",
                "Outside_Boundary_Condition": "",
                "Zone_Name": ""
            }
            for attr in attrs:
                attrs[attr] = str(getattr(surface, attr, attrs[attr]))
            
            surfaces[surface_id] = SurfaceData(
                id=surface_id,
                name=surface_id,
                surface_type=attrs["Surface_Type"],
                construction_name=attrs["Construction_Name"],
                boundary_condition=attrs["Outside_Boundary_Condition"],
                zone_name=attrs["Zone_Name"],
                vertices=self._extract_vertices(surface)
            )
        return surfaces
        
    def get_all_constructions(self) -> Dict[str, ConstructionData]:
        """Get all construction data with optimized material layer processing."""
        if not self._idf:
            return {}
            
        constructions = {}
        materials = self.get_all_materials()  # Uses cached materials
        
        # Get field indices for Layer_* fields once
        layer_fields = [f for f in self._idf.idfobjects['CONSTRUCTION'][0].fieldnames
                       if f.startswith('Layer_')]
        
        for construction in self._idf.idfobjects['CONSTRUCTION']:
            construction_id = str(construction.Name)
            
            # Process all layers in one go using list comprehension
            material_layers = [
                str(getattr(construction, field))
                for field in layer_fields
                if getattr(construction, field, None)
            ]
            
            # Calculate total thickness using sum with generator
            total_thickness = sum(
                materials[layer_id].thickness
                for layer_id in material_layers
                if layer_id in materials
            )
            
            constructions[construction_id] = ConstructionData(
                id=construction_id,
                name=construction_id,
                material_layers=material_layers,
                thickness=total_thickness
            )
        return constructions
        
    def get_all_materials(self) -> Dict[str, MaterialData]:
        """Get all material data with caching."""
        if not self._idf:
            return {}
            
        # Return cached materials if available
        if self._materials is not None:
            return self._materials
            
        # Build materials cache
        self._materials = {}
        for material in self._idf.idfobjects['MATERIAL']:
            material_id = str(material.Name)
            self._materials[material_id] = MaterialData(
                id=material_id,
                name=material_id,
                conductivity=safe_float(getattr(material, "Conductivity", 0.0)),
                density=safe_float(getattr(material, "Density", 0.0)),
                specific_heat=safe_float(getattr(material, "Specific_Heat", 0.0)),
                thickness=safe_float(getattr(material, "Thickness", 0.0)),
                solar_absorptance=safe_float(getattr(material, "Solar_Absorptance", 0.0))
            )
        return self._materials
        
    def _extract_zone_id_from_schedule(self, schedule_id: str) -> Optional[str]:
        """Extract zone ID from schedule identifier for HVAC schedules."""
        schedule_lower = schedule_id.lower()
        if 'heating' in schedule_lower or 'cooling' in schedule_lower:
            # Split on spaces and take first part as zone ID
            parts = schedule_id.split()
            if parts:
                return parts[0]  # Returns e.g. '00:01XLIVING' from '00:01XLIVING Heating Setpoint Schedule'
        return None

    def get_all_schedules(self) -> Dict[str, ScheduleData]:
        """Get all schedule data with enhanced zone ID extraction for HVAC schedules."""
        if not self._idf:
            return {}
            
        schedules = {}
        for schedule in self._idf.idfobjects['SCHEDULE:COMPACT']:
            schedule_id = str(schedule.Name)
            schedule_type = str(schedule.Schedule_Type_Limits_Name)
            
            # Extract zone ID for HVAC schedules
            zone_id = self._extract_zone_id_from_schedule(schedule_id)
            zone_type = None
            if zone_id:
                # Use cached zone types
                matching_zone = next(
                    (zone_name for zone_name in self._zone_types
                     if zone_id.lower() in zone_name.lower()),
                    None
                )
                if matching_zone:
                    zone_type = self._zone_types[matching_zone]
            
            # Get all non-empty fields after Name and Type
            rule_fields = []
            for field in schedule.fieldvalues[2:]:  # Skip Name and Type
                if field.strip():
                    rule_fields.append(str(field))
            
            schedules[schedule_id] = ScheduleData(
                id=schedule_id,
                name=schedule_id,
                type=schedule_type,
                raw_rules=rule_fields,
                zone_id=zone_id,
                zone_type=zone_type
            )
        return schedules

    def get_floor_surfaces_by_zone(self, zone_name: str) -> List[SurfaceData]:
        """Get pre-cached floor surfaces for a specific zone."""
        return self._floor_surfaces.get(zone_name, [])

    def get_construction_properties(self, construction_id: str) -> Dict[str, float]:
        """Get pre-calculated properties for a specific construction."""
        return self._construction_props.get(construction_id, {'thickness': 0.0, 'conductivity': 0.0})

    def get_surface_vertices_batch(self, surface_ids: List[str]) -> Dict[str, List[tuple]]:
        """Get vertex coordinates for multiple surfaces efficiently."""
        result = {}
        for surface_id in surface_ids:
            # Check cache first
            if surface_id in self._surface_vertices:
                result[surface_id] = self._surface_vertices[surface_id]
                continue

            # Load and cache if not found
            for surface in self._idf.idfobjects['BUILDINGSURFACE:DETAILED']:
                if str(surface.Name) == surface_id:
                    vertices = self._extract_vertices(surface)
                    self._surface_vertices[surface_id] = vertices
                    result[surface_id] = vertices
                    break
        return result

    def get_surfaces_by_type(self, surface_type: str) -> Dict[str, SurfaceData]:
        """Get all surfaces of a specific type."""
        if surface_type.lower() == "floor":
            # Use pre-cached floor surfaces
            all_floors = {}
            for floors in self._floor_surfaces.values():
                for floor in floors:
                    all_floors[floor.id] = floor
            return all_floors
        else:
            # Fall back to regular surface filtering
            return {
                surface_id: surface_data
                for surface_id, surface_data in self.get_all_surfaces().items()
                if surface_data.surface_type.lower() == surface_type.lower()
            }
        
    def get_zones_by_type(self, zone_type: str) -> Dict[str, ZoneData]:
        """Get all zones of a specific type (regular or storage)."""
        return {
            zone_id: zone_data
            for zone_id, zone_data in self.get_all_zones().items()
            if zone_data.type == zone_type
        }
        
    def get_schedules_by_type(self, schedule_type: str) -> Dict[str, ScheduleData]:
        """Get all schedules of a specific type."""
        return {
            schedule_id: schedule_data
            for schedule_id, schedule_data in self.get_all_schedules().items()
            if schedule_data.type.lower() == schedule_type.lower()
        }
        
    def get_zone_schedules(self, zone_id: str) -> Dict[str, ScheduleData]:
        """Get all schedules associated with a specific zone."""
        return {
            schedule_id: schedule_data
            for schedule_id, schedule_data in self.get_all_schedules().items()
            if schedule_data.zone_id == zone_id
        }

    def get_all_schedules_with_names(self) -> Dict[str, Dict[str, any]]:
        """
        Get all schedules with parsed display names for better readability.
        
        Returns:
            Dict[str, Dict[str, any]]: Dictionary of schedule data with enhanced naming
        """
        if not self._idf:
            return {}
            
        # Return the cached schedules if available
        if self._schedules_cache:
            return self._schedules_cache
            
        # If cache is empty, rebuild it
        self._cache_schedules()
        return self._schedules_cache
        
    def _format_schedule_name(self, schedule_id: str) -> str:
        """
        Format schedule name for better readability.
        
        Args:
            schedule_id: The original schedule identifier
            
        Returns:
            str: Formatted schedule name
        """
        # Convert IDs like "00:01XLIVING Heating Setpoint Schedule" to "Living Heating Setpoint"
        name = schedule_id
        
        # Remove common suffixes
        for suffix in [' Schedule', ' Sch', '_schedule', '_sch']:
            if name.lower().endswith(suffix.lower()):
                name = name[:-len(suffix)]
                
        # Handle zone identifier formats (e.g., "00:01X")
        zone_pattern = re.search(r'(\d{2}:\d{2}[A-Z]?)', name)
        if zone_pattern:
            # Extract the rest of the name after the zone pattern
            remaining = name[zone_pattern.end():].strip()
            if remaining:
                name = remaining
                
        # Convert camelCase or snake_case to Title Case with spaces
        name = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)  # camelCase to spaces
        name = name.replace('_', ' ')  # snake_case to spaces
        
        # Title case the result
        name = ' '.join(word.capitalize() for word in name.split())
        
        return name
        
    def get_schedule_by_name(self, schedule_name: str) -> Optional[Dict[str, any]]:
        """
        Get schedule data by providing a schedule name (either original ID or formatted name).
        
        Args:
            schedule_name: The name of the schedule to find
            
        Returns:
            Optional[Dict[str, any]]: Schedule data if found, None otherwise
        """
        if not self._idf:
            return None
            
        # Make sure cache is initialized
        if not self._schedules_cache:
            self._cache_schedules()
            
        # First try exact match on original ID
        if schedule_name in self._schedules_cache:
            return self._schedules_cache[schedule_name]
            
        # Then try case-insensitive match on formatted names using the name map
        schedule_name_lower = schedule_name.lower()
        if schedule_name_lower in self._schedules_name_map:
            return self._schedules_cache[self._schedules_name_map[schedule_name_lower]]
            
        # Finally try partial match on both IDs and formatted names
        for schedule_id, schedule_data in self._schedules_cache.items():
            if (schedule_name_lower in schedule_data['name'].lower() or 
                schedule_name_lower in schedule_id.lower()):
                return schedule_data
                
        return None

    # Individual getters for compatibility
    def get_zone(self, zone_id: str) -> Optional[ZoneData]:
        """Get zone data by ID."""
        return self.get_all_zones().get(zone_id)
        
    def get_surface(self, surface_id: str) -> Optional[SurfaceData]:
        """Get surface data by ID."""
        return self.get_all_surfaces().get(surface_id)
        
    def get_construction(self, construction_id: str) -> Optional[ConstructionData]:
        """Get construction data by ID."""
        return self.get_all_constructions().get(construction_id)
        
    def get_material(self, material_id: str) -> Optional[MaterialData]:
        """Get material data by ID."""
        return self.get_all_materials().get(material_id)
        
    def get_cache_status(self) -> Dict[str, bool]:
        """Get the loading status of cache sections (maintained for compatibility)."""
        return {
            'zones': 'zones' in self._loaded_sections,
            'surfaces': 'surfaces' in self._loaded_sections,
            'materials': 'materials' in self._loaded_sections,
            'constructions': 'constructions' in self._loaded_sections,
            'schedules': 'schedules' in self._loaded_sections
        }
        
    def _load_all_zones(self) -> Dict[str, ZoneData]:
        """
        Load all zones from IDF into memory.
        This is a more comprehensive version of get_all_zones that doesn't filter out non-HVAC zones.
        
        Returns:
            Dict[str, ZoneData]: Dictionary of all zones
        """
        if not self._idf:
            return {}
            
        zones = {}
        for zone in self._idf.idfobjects['ZONE']:
            zone_id = str(zone.Name)
            
            # Extract area ID from zone ID
            area_id = None
            area_match = re.search(r':(\d{2})', zone_id)
            if area_match:
                area_id = area_match.group(1)
            
            # Determine zone type
            zone_type = self._zone_types.get(zone_id, "regular")
            
            zones[zone_id] = ZoneData(
                id=zone_id,
                name=zone_id,
                floor_area=safe_float(getattr(zone, "Floor_Area", 0.0)),
                volume=safe_float(getattr(zone, "Volume", 0.0)),
                multiplier=int(safe_float(getattr(zone, "Multiplier", 1))),
                type=zone_type,
                area_id=area_id
            )
        return zones
        
    def _load_all_surfaces(self) -> Dict[str, SurfaceData]:
        """
        Load all surfaces from IDF into memory.
        
        Returns:
            Dict[str, SurfaceData]: Dictionary of all surfaces
        """
        if not self._idf:
            return {}
            
        surfaces = {}
        for surface in self._idf.idfobjects['BUILDINGSURFACE:DETAILED']:
            surface_id = str(surface.Name)
            
            surfaces[surface_id] = SurfaceData(
                id=surface_id,
                name=surface_id,
                surface_type=str(getattr(surface, "Surface_Type", "")),
                construction_name=str(getattr(surface, "Construction_Name", "")),
                boundary_condition=str(getattr(surface, "Outside_Boundary_Condition", "")),
                zone_name=str(getattr(surface, "Zone_Name", "")),
                vertices=self._extract_vertices(surface)
            )
            
            # Cache the vertices for quick lookup
            self._surface_vertices[surface_id] = surfaces[surface_id].vertices
            
        return surfaces
        
    def _load_all_materials(self) -> Dict[str, MaterialData]:
        """
        Load all materials from IDF into memory.
        
        Returns:
            Dict[str, MaterialData]: Dictionary of all materials
        """
        if not self._idf:
            return {}
            
        materials = {}
        for material in self._idf.idfobjects['MATERIAL']:
            material_id = str(material.Name)
            materials[material_id] = MaterialData(
                id=material_id,
                name=material_id,
                conductivity=safe_float(getattr(material, "Conductivity", 0.0)),
                density=safe_float(getattr(material, "Density", 0.0)),
                specific_heat=safe_float(getattr(material, "Specific_Heat", 0.0)),
                thickness=safe_float(getattr(material, "Thickness", 0.0)),
                solar_absorptance=safe_float(getattr(material, "Solar_Absorptance", 0.0))
            )
        return materials
        
    def _load_all_constructions(self) -> Dict[str, ConstructionData]:
        """
        Load all constructions from IDF into memory.
        
        Returns:
            Dict[str, ConstructionData]: Dictionary of all constructions
        """
        if not self._idf:
            return {}
            
        constructions = {}
        materials = self._materials or self._load_all_materials()
        
        for construction in self._idf.idfobjects['CONSTRUCTION']:
            construction_id = str(construction.Name)
            
            # Get material layers
            layer_fields = [f for f in construction.fieldnames if f.startswith('Layer_')]
            material_layers = [
                str(getattr(construction, field, ""))
                for field in layer_fields
                if getattr(construction, field, "") 
            ]
            
            # Calculate total thickness
            total_thickness = 0.0
            for layer_id in material_layers:
                if layer_id in materials:
                    total_thickness += materials[layer_id].thickness
            
            constructions[construction_id] = ConstructionData(
                id=construction_id,
                name=construction_id,
                material_layers=material_layers,
                thickness=total_thickness
            )
        return constructions
    
    def _cache_loads_data(self) -> None:
        """
        Cache all loads data (people, lights, equipment, infiltration, ventilation).
        This allows parsers to access load data without direct IDF access.
        """
        if not self._idf:
            return
            
        # Cache people loads
        self._cache_people_loads()
        
        # Cache lights loads
        self._cache_lights_loads()
        
        # Cache equipment loads
        self._cache_equipment_loads()
        
        # Cache infiltration loads
        self._cache_infiltration_loads()
        
        # Cache ventilation loads
        self._cache_ventilation_loads()
        
        # Cache windows by surface
        self._cache_windows()
    
    def _cache_people_loads(self) -> None:
        """Cache people loads for all zones."""
        if not self._idf:
            return
            
        self._people.clear()
        for people in self._idf.idfobjects['PEOPLE']:
            zone_name = str(getattr(people, "Zone_or_ZoneList_Name", ""))
            if not zone_name:
                continue
                
            if zone_name not in self._people:
                self._people[zone_name] = []
                
            self._people[zone_name].append({
                "people_per_area": safe_float(getattr(people, "People_per_Zone_Floor_Area", 0.0)),
                "number_of_people": safe_float(getattr(people, "Number_of_People", 0.0)),
                "schedule": str(getattr(people, "Number_of_People_Schedule_Name", "")),
                "activity_schedule": str(getattr(people, "Activity_Level_Schedule_Name", ""))
            })
    
    def _cache_lights_loads(self) -> None:
        """Cache lighting loads for all zones."""
        if not self._idf:
            return
            
        self._lights.clear()
        for lights in self._idf.idfobjects['LIGHTS']:
            zone_name = str(getattr(lights, "Zone_or_ZoneList_Name", ""))
            if not zone_name:
                continue
                
            if zone_name not in self._lights:
                self._lights[zone_name] = []
                
            self._lights[zone_name].append({
                "watts_per_area": safe_float(getattr(lights, "Watts_per_Zone_Floor_Area", 0.0)),
                "schedule": str(getattr(lights, "Schedule_Name", ""))
            })
    
    def _cache_equipment_loads(self) -> None:
        """Cache equipment loads for all zones."""
        if not self._idf:
            return
            
        self._equipment.clear()
        for equip_type in ['ELECTRICEQUIPMENT', 'OTHEREQUIPMENT']:
            if equip_type in self._idf.idfobjects:
                for equip in self._idf.idfobjects[equip_type]:
                    zone_name = str(getattr(equip, "Zone_or_ZoneList_Name", ""))
                    if not zone_name:
                        continue
                        
                    if zone_name not in self._equipment:
                        self._equipment[zone_name] = []
                        
                    equip_name = str(getattr(equip, "Name", ""))
                    is_fixed = not ("Miscellaneous" in equip_name)
                        
                    self._equipment[zone_name].append({
                        "name": equip_name,
                        "type": "fixed" if is_fixed else "non_fixed",
                        "watts_per_area": safe_float(getattr(equip, "Watts_per_Zone_Floor_Area", 0.0)),
                        "schedule": str(getattr(equip, "Schedule_Name", ""))
                    })
    
    def _cache_infiltration_loads(self) -> None:
        """Cache infiltration loads for all zones."""
        if not self._idf:
            return
            
        self._infiltration.clear()
        for infil in self._idf.idfobjects['ZONEINFILTRATION:DESIGNFLOWRATE']:
            zone_name = str(getattr(infil, "Zone_or_ZoneList_Name", ""))
            if not zone_name:
                continue
                
            if zone_name not in self._infiltration:
                self._infiltration[zone_name] = []
                
            self._infiltration[zone_name].append({
                "air_changes_per_hour": safe_float(getattr(infil, "Air_Changes_Per_Hour", 0.0)),
                "schedule": str(getattr(infil, "Schedule_Name", ""))
            })
    
    def _cache_ventilation_loads(self) -> None:
        """Cache ventilation loads for all zones."""
        if not self._idf:
            return
            
        self._ventilation.clear()
        if 'ZONEVENTILATION:DESIGNFLOWRATE' in self._idf.idfobjects:
            for vent in self._idf.idfobjects['ZONEVENTILATION:DESIGNFLOWRATE']:
                zone_name = str(getattr(vent, "Zone_or_ZoneList_Name", ""))
                if not zone_name:
                    continue
                    
                if zone_name not in self._ventilation:
                    self._ventilation[zone_name] = []
                    
                self._ventilation[zone_name].append({
                    "air_changes_per_hour": safe_float(getattr(vent, "Air_Changes_Per_Hour", 0.0)),
                    "schedule": str(getattr(vent, "Schedule_Name", ""))
                })
    
    def _cache_windows(self) -> None:
        """Cache windows by surface."""
        if not self._idf:
            return
            
        self._windows.clear()
        if 'FENESTRATIONSURFACE:DETAILED' in self._idf.idfobjects:
            for window in self._idf.idfobjects['FENESTRATIONSURFACE:DETAILED']:
                surface_name = str(getattr(window, "Building_Surface_Name", ""))
                if not surface_name:
                    continue
                    
                if surface_name not in self._windows:
                    self._windows[surface_name] = []
                    
                self._windows[surface_name].append({
                    "id": str(getattr(window, "Name", "")),
                    "construction_name": str(getattr(window, "Construction_Name", "")),
                    "vertices": self._extract_vertices(window)
                })
    
    def get_people_loads(self, zone_name: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get people loads from cache.
        
        Args:
            zone_name: Optional zone name to filter by
            
        Returns:
            Dict[str, List[Dict[str, Any]]]: Dictionary of people loads by zone
        """
        if not self._people:
            self._cache_people_loads()
            
        if zone_name:
            return {zone_name: self._people.get(zone_name, [])} if zone_name in self._people else {}
        return self._people
        
    def get_lights_loads(self, zone_name: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get lighting loads from cache.
        
        Args:
            zone_name: Optional zone name to filter by
            
        Returns:
            Dict[str, List[Dict[str, Any]]]: Dictionary of lighting loads by zone
        """
        if not self._lights:
            self._cache_lights_loads()
            
        if zone_name:
            return {zone_name: self._lights.get(zone_name, [])} if zone_name in self._lights else {}
        return self._lights
        
    def get_equipment_loads(self, zone_name: Optional[str] = None, equipment_type: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get equipment loads from cache.
        
        Args:
            zone_name: Optional zone name to filter by
            equipment_type: Optional equipment type to filter by ('fixed' or 'non_fixed')
            
        Returns:
            Dict[str, List[Dict[str, Any]]]: Dictionary of equipment loads by zone
        """
        if not self._equipment:
            self._cache_equipment_loads()
            
        result = {}
        
        if zone_name:
            # Filter by zone
            equipment_list = self._equipment.get(zone_name, [])
            if equipment_type:
                # Also filter by equipment type
                equipment_list = [equip for equip in equipment_list if equip["type"] == equipment_type]
            result = {zone_name: equipment_list} if equipment_list else {}
        else:
            # No zone filter, but potentially filter by equipment type
            for zone, equipment_list in self._equipment.items():
                if equipment_type:
                    filtered_list = [equip for equip in equipment_list if equip["type"] == equipment_type]
                    if filtered_list:
                        result[zone] = filtered_list
                else:
                    result[zone] = equipment_list
                    
        return result
        
    def get_infiltration_loads(self, zone_name: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get infiltration loads from cache.
        
        Args:
            zone_name: Optional zone name to filter by
            
        Returns:
            Dict[str, List[Dict[str, Any]]]: Dictionary of infiltration loads by zone
        """
        if not self._infiltration:
            self._cache_infiltration_loads()
            
        if zone_name:
            return {zone_name: self._infiltration.get(zone_name, [])} if zone_name in self._infiltration else {}
        return self._infiltration
        
    def get_ventilation_loads(self, zone_name: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get ventilation loads from cache.
        
        Args:
            zone_name: Optional zone name to filter by
            
        Returns:
            Dict[str, List[Dict[str, Any]]]: Dictionary of ventilation loads by zone
        """
        if not self._ventilation:
            self._cache_ventilation_loads()
            
        if zone_name:
            return {zone_name: self._ventilation.get(zone_name, [])} if zone_name in self._ventilation else {}
        return self._ventilation
        
    def get_windows(self, surface_name: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get windows from cache.
        
        Args:
            surface_name: Optional surface name to filter by
            
        Returns:
            Dict[str, List[Dict[str, Any]]]: Dictionary of windows by surface
        """
        if not self._windows:
            self._cache_windows()
            
        if surface_name:
            return {surface_name: self._windows.get(surface_name, [])} if surface_name in self._windows else {}
        return self._windows
        
    def get_all_load_data(self, zone_name: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """
        Get comprehensive load data for one or all zones.
        Combines people, lights, equipment, infiltration and ventilation data.
        
        Args:
            zone_name: Optional zone name to filter by
            
        Returns:
            Dict[str, Dict[str, Any]]: Dictionary of aggregated load data by zone
        """
        # Initialize result
        result = {}
        
        # Get zone list to process
        zone_list = [zone_name] if zone_name else self.get_all_zones().keys()
        
        for zone in zone_list:
            # Skip if zone doesn't exist
            if not zone or zone not in self.get_all_zones():
                continue
                
            zone_data = self.get_all_zones()[zone]
            
            # Get load data for this zone
            people_data = self.get_people_loads(zone).get(zone, [])
            lights_data = self.get_lights_loads(zone).get(zone, [])
            equip_data = self.get_equipment_loads(zone).get(zone, [])
            infiltration_data = self.get_infiltration_loads(zone).get(zone, [])
            ventilation_data = self.get_ventilation_loads(zone).get(zone, [])
            
            # Calculate aggregated values
            people_per_area = sum(item["people_per_area"] for item in people_data) if people_data else 0.0
            lights_watts_per_area = sum(item["watts_per_area"] for item in lights_data) if lights_data else 0.0
            
            # Split equipment by type
            non_fixed_equipment = [item for item in equip_data if item["type"] == "non_fixed"]
            fixed_equipment = [item for item in equip_data if item["type"] == "fixed"]
            
            non_fixed_watts = sum(item["watts_per_area"] for item in non_fixed_equipment) if non_fixed_equipment else 0.0
            fixed_watts = sum(item["watts_per_area"] for item in fixed_equipment) if fixed_equipment else 0.0
            
            infiltration_ach = sum(item["air_changes_per_hour"] for item in infiltration_data) if infiltration_data else 0.0
            ventilation_ach = sum(item["air_changes_per_hour"] for item in ventilation_data) if ventilation_data else 0.0
            
            # Initialize load structure
            result[zone] = {
                "properties": {
                    "area": zone_data.floor_area,
                    "volume": zone_data.volume,
                    "multiplier": zone_data.multiplier
                },
                "loads": {
                    "people": {
                        "people_per_area": people_per_area,
                        "activity_schedule": people_data[0]["activity_schedule"] if people_data else None,
                        "schedule": people_data[0]["schedule"] if people_data else None
                    },
                    "lights": {
                        "watts_per_area": lights_watts_per_area,
                        "schedule": lights_data[0]["schedule"] if lights_data else None
                    },
                    "non_fixed_equipment": {
                        "watts_per_area": non_fixed_watts,
                        "schedule": non_fixed_equipment[0]["schedule"] if non_fixed_equipment else None
                    },
                    "fixed_equipment": {
                        "watts_per_area": fixed_watts,
                        "schedule": fixed_equipment[0]["schedule"] if fixed_equipment else None
                    },
                    "infiltration": {
                        "rate_ach": infiltration_ach,
                        "schedule": infiltration_data[0]["schedule"] if infiltration_data else None
                    },
                    "ventilation": {
                        "rate_ach": ventilation_ach,
                        "schedule": ventilation_data[0]["schedule"] if ventilation_data else None
                    }
                },
                "schedules": self._get_temperature_schedules_for_zone(zone)
            }
            
        return result
        
    def _get_temperature_schedules_for_zone(self, zone_name: str) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Get temperature schedules for a zone.
        
        Args:
            zone_name: Zone name to get schedules for
            
        Returns:
            Dict[str, Optional[Dict[str, Any]]]: Dictionary with heating and cooling schedules
        """
        result = {
            "heating": None,
            "cooling": None
        }
        
        # Look for schedules matching the zone name
        for schedule_id, schedule_data in self._schedules_cache.items():
            schedule_id_lower = schedule_id.lower()
            zone_name_lower = zone_name.lower()
            
            if zone_name_lower in schedule_id_lower:
                if "heating" in schedule_id_lower:
                    result["heating"] = schedule_data
                elif "cooling" in schedule_id_lower:
                    result["cooling"] = schedule_data
                    
        return result