"""
DataLoader module for direct IDF data access.
Provides simplified data loading and retrieval functionality.
"""
from typing import Dict, Optional, List
from pathlib import Path
import re
from parsers.schedule_parser import ScheduleExtractor
from utils.eppy_handler import EppyHandler
from utils.data_models import (
    ZoneData, SurfaceData, ConstructionData,
    ScheduleData, MaterialData
)

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
        
    def load_file(self, idf_path: str, idd_path: Optional[str] = None) -> None:
        """
        Load IDF file for data access.
        
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
        
        # Pre-cache frequently accessed data
        self._cache_temp_schedules()
        self._cache_zone_types()
        self._cache_floor_surfaces()
        self._cache_construction_properties()
        
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
                floor_area=float(getattr(zone, "Floor_Area", 0.0)),
                volume=float(getattr(zone, "Volume", 0.0)),
                multiplier=int(float(getattr(zone, "Multiplier", 1))),
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
                    float(getattr(surface, f'{prefix}{coord}coordinate', 0.0))
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
                conductivity=float(getattr(material, "Conductivity", 0.0)),
                density=float(getattr(material, "Density", 0.0)),
                specific_heat=float(getattr(material, "Specific_Heat", 0.0)),
                thickness=float(getattr(material, "Thickness", 0.0)),
                solar_absorptance=float(getattr(material, "Solar_Absorptance", 0.0))
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