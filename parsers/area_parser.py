"""
Extracts and processes area information including floor areas and material properties.
"""
from typing import Dict, Any, List, Optional
import numpy as np
from utils.data_loader import DataLoader

class AreaParser:
    """
    Extracts and processes area information from zone IDs.
    Uses DataLoader for efficient data access and caching.
    """
    def __init__(self, data_loader: DataLoader):
        """
        Initialize AreaParser with DataLoader instance.
        
        Args:
            data_loader: DataLoader instance for accessing cached IDF data
        """
        self.data_loader = data_loader
        self.areas_by_zone = {}  # {zone_id: {"area_id": str, "properties": {}, "element_data": []}}
        
    def process_idf(self, idf) -> None:
        """
        Process an entire IDF model to extract all area information.
        Uses cached zone data from DataLoader instead of direct file access.
        
        Args:
            idf: eppy IDF object (kept for compatibility)
        """
        # Process all zones with HVAC systems
        zones = self.data_loader.get_all_zones()
        for zone_id, zone_data in zones.items():
            if zone_data.area_id:  # HVAC check is now done in get_all_zones
                # Process basic zone properties
                self.areas_by_zone[zone_id] = {
                    "area_id": zone_data.area_id,
                    "properties": {
                        "floor_area": zone_data.floor_area,
                        "volume": zone_data.volume,
                        "multiplier": zone_data.multiplier
                    },
                    "element_data": []
                }
                
                # Process floor surfaces for this zone
                self._process_zone_surfaces(zone_id, zone_data)
        
    def get_parsed_areas(self) -> Dict[str, Any]:
        """
        Returns the dictionary of parsed area information.
        Does not include storage zones.
        
        Returns:
            dict: Dictionary of area information by zone
        """
        return self.areas_by_zone
        
    def get_zones_by_area(self, area_id: str) -> Dict[str, Any]:
        """
        Get all zones belonging to a specific area.
        
        Args:
            area_id: The area identifier to filter by
            
        Returns:
            dict: Dictionary of zones in the specified area
        """
        return {
            zone_id: zone_data
            for zone_id, zone_data in self.areas_by_zone.items()
            if zone_data["area_id"] == area_id
        }
        
    def get_area_totals(self, area_id: str) -> Dict[str, float]:
        """
        Calculate total properties for an area.
        
        Args:
            area_id: The area identifier to calculate totals for
            
        Returns:
            dict: Dictionary with total floor area, volume, etc.
        """
        area_zones = self.get_zones_by_area(area_id)
        
        total_floor_area = 0.0
        total_volume = 0.0
        
        for zone_data in area_zones.values():
            multiplier = zone_data["properties"]["multiplier"]
            total_floor_area += zone_data["properties"]["floor_area"] * multiplier
            total_volume += zone_data["properties"]["volume"] * multiplier
            
        return {
            "total_floor_area": total_floor_area,
            "total_volume": total_volume,
            "zone_count": len(area_zones)
        }
        
    def _calculate_polygon_area(self, vertices: List[tuple]) -> float:
        """
        Calculate area of polygon defined by vertices.
        
        Args:
            vertices: List of (x,y,z) coordinate tuples
            
        Returns:
            float: Calculated area of the polygon
        """
        points_2d = np.array([(x, y) for x, y, z in vertices])
        x = points_2d[:, 0]
        y = points_2d[:, 1]
        return 0.5 * np.abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))
        
    def _get_zone_floor_surfaces(self, zone_name: str) -> List[Dict[str, Any]]:
        """
        Get all floor surfaces for a given zone.
        
        Args:
            zone_name: Name of the zone to get surfaces for
            
        Returns:
            list: List of floor surface data dictionaries
        """
        surfaces = self.data_loader.get_all_surfaces()
        return [
            surface for surface in surfaces.values()
            if surface.zone_name == zone_name
            and surface.surface_type.lower() == "floor"
        ]
        
    def _get_construction_properties(self, construction_id: str) -> Dict[str, float]:
        """
        Get material properties for a construction.
        
        Args:
            construction_id: ID of the construction
            
        Returns:
            dict: Dictionary of construction properties
        """
        construction = self.data_loader.get_construction(construction_id)
        if not construction:
            return {"conductivity": 0.0}
            
        total_resistance = 0.0
        for material_id in construction.material_layers:
            material = self.data_loader.get_material(material_id)
            if material and material.conductivity > 0:
                total_resistance += material.thickness / material.conductivity
                
        # Calculate effective conductivity
        if total_resistance > 0:
            total_thickness = construction.thickness
            return {"conductivity": total_thickness / total_resistance}
        return {"conductivity": 0.0}
        
    def _process_zone_surfaces(self, zone_id: str, zone_data) -> None:
        """
        Process all surfaces for a zone, calculating areas and material properties.
        
        Args:
            zone_id: ID of zone to process
            zone_data: ZoneData object for the zone
        """
        floor_surfaces = self._get_zone_floor_surfaces(zone_data.name)
        
        for surface in floor_surfaces:
            # Get surface vertices
            vertices = self.data_loader.get_surface_vertices(surface.id)
            if not vertices:
                continue
                
            area = self._calculate_polygon_area(vertices)
            construction_props = self._get_construction_properties(surface.construction_name)
            
            element_data = {
                "zone": zone_id,
                "element_name": surface.name,
                "element_type": "Floor",
                "area": area,
                "conductivity": construction_props["conductivity"],
                "area_conductivity": area * construction_props["conductivity"]
            }
            
            # Add element data to zone
            self.areas_by_zone[zone_id]["element_data"].append(element_data)
            
    def get_element_data(self, zone_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get list of processed elements with areas and properties.
        
        Args:
            zone_id: Optional zone ID to filter elements by
            
        Returns:
            list: List of dictionaries containing element data
        """
        if zone_id:
            return self.areas_by_zone.get(zone_id, {}).get("element_data", [])
        
        # Return all element data if no zone specified
        all_elements = []
        for zone_data in self.areas_by_zone.values():
            all_elements.extend(zone_data.get("element_data", []))
        return all_elements