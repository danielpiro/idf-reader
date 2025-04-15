"""
DataLoader module for efficient IDF data caching and access.
Provides centralized data management for IDF file parsing and data retrieval.
"""
from typing import Dict, Optional, Set, Any
from dataclasses import dataclass
from pathlib import Path
import re
from eppy.modeleditor import IDF
from utils.eppy_handler import EppyHandler

@dataclass
class ZoneData:
    """Container for zone-related data"""
    id: str
    name: str
    floor_area: float
    volume: float
    multiplier: int
    type: str  # regular or storage
    area_id: Optional[str] = None

@dataclass
class SurfaceData:
    """Container for surface-related data"""
    id: str
    name: str
    surface_type: str
    construction_name: str
    boundary_condition: str
    zone_name: str

@dataclass
class ConstructionData:
    """Container for construction-related data"""
    id: str
    name: str
    material_layers: list[str]
    thickness: float

@dataclass
class MaterialData:
    """Container for material-related data"""
    id: str
    name: str
    conductivity: float
    density: float
    specific_heat: float
    thickness: float
    solar_absorptance: float

class DataLoader:
    """
    Central data management class for IDF file parsing and caching.
    Implements two-tier caching system for efficient data access.
    """
    def __init__(self):
        # Primary cache initialization
        self._zones_cache: Dict[str, ZoneData] = {}
        self._surfaces_cache: Dict[str, SurfaceData] = {}
        self._constructions_cache: Dict[str, ConstructionData] = {}
        self._materials_cache: Dict[str, MaterialData] = {}
        
        # Cache status tracking
        self._loaded_sections: Set[str] = set()
        self._idf = None  # Store IDF reference
        self._eppy_handler = None  # Store EppyHandler reference
        
    def load_file(self, idf_path: str, idd_path: Optional[str] = None) -> None:
        """
        Initial load of IDF file and population of primary cache.
        
        Args:
            idf_path: Path to the IDF file
            idd_path: Optional path to the IDD file
            
        Raises:
            FileNotFoundError: If IDF or IDD file not found
            Exception: Other errors during file loading
        """
        try:
            if not Path(idf_path).exists():
                raise FileNotFoundError(f"IDF file not found at '{idf_path}'")
                
            # Initialize EppyHandler
            self._eppy_handler = EppyHandler(idd_path)
            self._idf = self._eppy_handler.load_idf(idf_path)
            
            # Load primary cache data
            self._load_primary_cache()
            
        except FileNotFoundError as e:
            raise e
        except Exception as e:
            raise Exception(f"Error loading IDF file: {str(e)}")
        
    def _load_primary_cache(self) -> None:
        """
        Load most frequently accessed data during initialization.
        
        Raises:
            Exception: If error occurs during cache loading
        """
        try:
            self._load_core_materials()  # Load materials before constructions
            self._load_common_constructions()
            self._load_zones_basic()
            self._load_surfaces_basic()
            self._loaded_sections.update(['zones', 'surfaces', 'materials', 'constructions'])
        except Exception as e:
            raise Exception(f"Error loading primary cache: {str(e)}")
        
    def _load_zones_basic(self) -> None:
        """
        Load basic zone data into primary cache.
        
        Raises:
            Exception: If error occurs during zone loading
        """
        if not self._idf:
            return
            
        try:
            for zone in self._idf.idfobjects['ZONE']:
                zone_id = str(zone.Name)
                
                # Determine zone type (regular or storage)
                zone_type = "storage" if any(keyword in zone_id.lower() 
                                           for keyword in ['storage', 'store', 'warehouse']) else "regular"
                
                # Extract area ID if present
                area_id = None
                if zone_type == "regular":
                    area_match = re.search(r':(\d{2})', zone_id)
                    if area_match:
                        area_id = area_match.group(1)
                
                # Create zone data object
                zone_data = ZoneData(
                    id=zone_id,
                    name=zone_id,
                    floor_area=float(getattr(zone, "Floor_Area", 0.0)),
                    volume=float(getattr(zone, "Volume", 0.0)),
                    multiplier=int(float(getattr(zone, "Multiplier", 1))),
                    type=zone_type,
                    area_id=area_id
                )
                
                self._zones_cache[zone_id] = zone_data
                
        except Exception as e:
            raise Exception(f"Error loading zones: {str(e)}")
            
    def _load_surfaces_basic(self) -> None:
        """
        Load basic surface data into primary cache.
        
        Raises:
            Exception: If error occurs during surface loading
        """
        if not self._idf:
            return
            
        try:
            for surface in self._idf.idfobjects['BUILDINGSURFACE:DETAILED']:
                surface_id = str(surface.Name)
                
                surface_data = SurfaceData(
                    id=surface_id,
                    name=surface_id,
                    surface_type=str(getattr(surface, "Surface_Type", "")),
                    construction_name=str(getattr(surface, "Construction_Name", "")),
                    boundary_condition=str(getattr(surface, "Outside_Boundary_Condition", "")),
                    zone_name=str(getattr(surface, "Zone_Name", ""))
                )
                
                self._surfaces_cache[surface_id] = surface_data
                
        except Exception as e:
            raise Exception(f"Error loading surfaces: {str(e)}")
            
    def _load_common_constructions(self) -> None:
        """
        Load commonly used construction data into primary cache.
        
        Raises:
            Exception: If error occurs during construction loading
        """
        if not self._idf:
            return
            
        try:
            for construction in self._idf.idfobjects['CONSTRUCTION']:
                construction_id = str(construction.Name)
                construction_name = str(construction.Name)
                
                # Get material layers
                material_layers = []
                total_thickness = 0.0
                
                for i in range(1, len(construction.fieldnames)):
                    layer = getattr(construction, f"Layer_{i}", None)
                    if layer:
                        material_layers.append(str(layer))
                        
                        # Add thickness if material exists in cache
                        if str(layer) in self._materials_cache:
                            total_thickness += self._materials_cache[str(layer)].thickness
                
                construction_data = ConstructionData(
                    id=construction_id,
                    name=construction_name,
                    material_layers=material_layers,
                    thickness=total_thickness
                )
                
                self._constructions_cache[construction_id] = construction_data
                
        except Exception as e:
            raise Exception(f"Error loading constructions: {str(e)}")
            
    def _load_core_materials(self) -> None:
        """
        Load basic material data into primary cache.
        
        Raises:
            Exception: If error occurs during material loading
        """
        if not self._idf:
            return
            
        try:
            for material in self._idf.idfobjects['MATERIAL']:
                material_id = str(material.Name)
                
                material_data = MaterialData(
                    id=material_id,
                    name=material_id,
                    conductivity=float(getattr(material, "Conductivity", 0.0)),
                    density=float(getattr(material, "Density", 0.0)),
                    specific_heat=float(getattr(material, "Specific_Heat", 0.0)),
                    thickness=float(getattr(material, "Thickness", 0.0)),
                    solar_absorptance=float(getattr(material, "Solar_Absorptance", 0.0))
                )
                
                self._materials_cache[material_id] = material_data
                
        except Exception as e:
            raise Exception(f"Error loading materials: {str(e)}")
            
    # Getter methods for cached data
    def get_zone(self, zone_id: str) -> Optional[ZoneData]:
        """Get zone data from cache."""
        return self._zones_cache.get(zone_id)
        
    def get_surface(self, surface_id: str) -> Optional[SurfaceData]:
        """Get surface data from cache."""
        return self._surfaces_cache.get(surface_id)
        
    def get_construction(self, construction_id: str) -> Optional[ConstructionData]:
        """Get construction data from cache."""
        return self._constructions_cache.get(construction_id)
        
    def get_material(self, material_id: str) -> Optional[MaterialData]:
        """Get material data from cache."""
        return self._materials_cache.get(material_id)
        
    # Bulk getter methods
    def get_all_zones(self) -> Dict[str, ZoneData]:
        """Get all cached zone data."""
        return self._zones_cache.copy()
        
    def get_all_surfaces(self) -> Dict[str, SurfaceData]:
        """Get all cached surface data."""
        return self._surfaces_cache.copy()

    def get_all_constructions(self) -> Dict[str, ConstructionData]:
        """Get all cached construction data."""
        return self._constructions_cache.copy()
        
    def get_all_materials(self) -> Dict[str, MaterialData]:
        """Get all cached material data."""
        return self._materials_cache.copy()
        
    def get_surfaces_by_type(self, surface_type: str) -> Dict[str, SurfaceData]:
        """Get all surfaces of a specific type."""
        return {
            surface_id: surface_data
            for surface_id, surface_data in self._surfaces_cache.items()
            if surface_data.surface_type.lower() == surface_type.lower()
        }
        
    def get_zones_by_type(self, zone_type: str) -> Dict[str, ZoneData]:
        """Get all zones of a specific type (regular or storage)."""
        return {
            zone_id: zone_data
            for zone_id, zone_data in self._zones_cache.items()
            if zone_data.type == zone_type
        }

    def get_cache_status(self) -> Dict[str, bool]:
        """Get the loading status of cache sections."""
        return {
            'zones': 'zones' in self._loaded_sections,
            'surfaces': 'surfaces' in self._loaded_sections,
            'materials': 'materials' in self._loaded_sections,
            'constructions': 'constructions' in self._loaded_sections
        }