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
    Provides direct access to IDF objects without caching.
    """
    def __init__(self):
        self._idf = None
        self._eppy_handler = None
        self._loaded_sections = set()  # Keep track for compatibility
        
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
        
    def get_all_zones(self) -> Dict[str, ZoneData]:
        """
        Get all zones that have HVAC systems.
        Filters out zones without temperature schedules and extracts area IDs.
        """
        if not self._idf:
            return {}

        # Pre-filter temperature schedules for efficiency
        temp_schedules = {}
        for schedule in self._idf.idfobjects['SCHEDULE:COMPACT']:
            schedule_type = str(schedule.Schedule_Type_Limits_Name).lower()
            if schedule_type == "temperature":
                schedule_id = str(schedule.Name).split(' ')[0].lower()
                temp_schedules[schedule_id] = True

        zones = {}
        for zone in self._idf.idfobjects['ZONE']:
            zone_id = str(zone.Name)
            zone_id_lower = zone_id.lower()
            
            # Check for HVAC by looking up in pre-filtered schedules
            zone_base_id = zone_id_lower.split('_')[0] if '_' in zone_id_lower else zone_id_lower
            if zone_base_id not in temp_schedules:
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
        
    def get_all_surfaces(self) -> Dict[str, SurfaceData]:
        """Get all surface data."""
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
                zone_name=str(getattr(surface, "Zone_Name", ""))
            )
        return surfaces
        
    def get_all_constructions(self) -> Dict[str, ConstructionData]:
        """Get all construction data."""
        if not self._idf:
            return {}
            
        constructions = {}
        materials = self.get_all_materials()
        
        for construction in self._idf.idfobjects['CONSTRUCTION']:
            construction_id = str(construction.Name)
            material_layers = []
            total_thickness = 0.0
            
            for i in range(1, len(construction.fieldnames)):
                layer = getattr(construction, f"Layer_{i}", None)
                if layer:
                    layer_id = str(layer)
                    material_layers.append(layer_id)
                    if layer_id in materials:
                        total_thickness += materials[layer_id].thickness
            
            constructions[construction_id] = ConstructionData(
                id=construction_id,
                name=construction_id,
                material_layers=material_layers,
                thickness=total_thickness
            )
        return constructions
        
    def get_all_materials(self) -> Dict[str, MaterialData]:
        """Get all material data."""
        if not self._idf:
            return {}
            
        materials = {}
        for material in self._idf.idfobjects['MATERIAL']:
            material_id = str(material.Name)
            materials[material_id] = MaterialData(
                id=material_id,
                name=material_id,
                conductivity=float(getattr(material, "Conductivity", 0.0)),
                density=float(getattr(material, "Density", 0.0)),
                specific_heat=float(getattr(material, "Specific_Heat", 0.0)),
                thickness=float(getattr(material, "Thickness", 0.0)),
                solar_absorptance=float(getattr(material, "Solar_Absorptance", 0.0))
            )
        return materials
        
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
                # Try to find matching zone to get its type
                for zone in self._idf.idfobjects['ZONE']:
                    if zone_id.lower() in str(zone.Name).lower():
                        zone_type = "core" if any(keyword in str(zone.Name).lower()
                                                for keyword in ['core', 'corridor', 'stair']) else "regular"
                        break
            
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

    def get_surfaces_by_type(self, surface_type: str) -> Dict[str, SurfaceData]:
        """Get all surfaces of a specific type."""
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