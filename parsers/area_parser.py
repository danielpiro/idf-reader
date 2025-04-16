"""
Extracts and processes area information including floor areas and material properties.
"""
from typing import Dict, Any, List, Optional
import numpy as np
import time
import logging
from utils.data_loader import DataLoader

logger = logging.getLogger(__name__)

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
        self._batch_size = 100    # Number of surfaces to process in one batch
        
    def process_idf(self, idf) -> None:
        """
        Process an entire IDF model to extract all area information.
        Uses cached zone data from DataLoader instead of direct file access.
        
        Args:
            idf: eppy IDF object (kept for compatibility)
        """
        start_time = time.time()
        
        try:
            # Process all zones with HVAC systems
            zones = self.data_loader.get_all_zones()
            surface_batch = []
            zone_map = {}  # Map surfaces to their zones for batch processing
            
            # First pass: collect all surfaces
            for zone_id, zone_data in zones.items():
                if not zone_data.area_id:
                    continue
                    
                # Initialize zone data
                self.areas_by_zone[zone_id] = {
                    "area_id": zone_data.area_id,
                    "properties": {
                        "floor_area": zone_data.floor_area,
                        "volume": zone_data.volume,
                        "multiplier": zone_data.multiplier
                    },
                    "element_data": []
                }
                
                # Get pre-cached floor surfaces for this zone
                floor_surfaces = self.data_loader.get_floor_surfaces_by_zone(zone_data.name)
                for surface in floor_surfaces:
                    surface_batch.append(surface)
                    zone_map[surface.id] = zone_id
                    
                    # Process in batches
                    if len(surface_batch) >= self._batch_size:
                        self._process_surface_batch(surface_batch, zone_map)
                        surface_batch = []
                        zone_map = {}
            
            # Process remaining surfaces
            if surface_batch:
                self._process_surface_batch(surface_batch, zone_map)
            
            end_time = time.time()
            logger.info(f"Area processing completed in {end_time - start_time:.2f}s")
            
        except Exception as e:
            logger.error(f"Error during area processing: {str(e)}")
            raise
        
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
        
    def _process_surface_batch(self, surfaces: List[Any], zone_map: Dict[str, str]) -> None:
        """
        Process a batch of surfaces efficiently using cached data.
        
        Args:
            surfaces: List of SurfaceData objects to process
            zone_map: Mapping of surface IDs to zone IDs
        """
        # Get all vertices in one batch
        surface_ids = [s.id for s in surfaces]
        vertices_map = self.data_loader.get_surface_vertices_batch(surface_ids)
        
        # Process each surface using cached data
        for surface in surfaces:
            vertices = vertices_map.get(surface.id)
            if not vertices:
                continue
                
            # Use pre-calculated construction properties
            construction_props = self.data_loader.get_construction_properties(surface.construction_name)
            
            # Calculate area
            area = self._calculate_polygon_area(vertices)
            conductivity = construction_props['conductivity']
            
            zone_id = zone_map[surface.id]
            element_data = {
                "zone": zone_id,
                "element_name": surface.name,
                "element_type": "Floor",
                "area": area,
                "conductivity": conductivity,
                "area_conductivity": area * conductivity
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