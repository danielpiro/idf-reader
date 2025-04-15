"""
Extracts and processes area information from zone IDs using eppy.
Areas are extracted from zone IDs following the pattern: XXXXX:YYZZZ where YY is the area identifier.
"""
from typing import Dict, Any
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
        self.areas_by_zone = {}  # {zone_id: {"area_id": str, "properties": {}}}
        
    def _check_zone_hvac(self, zone_name: str) -> bool:
        """
        Check if a zone has HVAC systems by looking for heating/cooling schedules.
        Uses cached zone data.
        
        Args:
            zone_name: Name of the zone to check
            
        Returns:
            bool: True if zone has HVAC systems, False otherwise
        """
        try:
            if not zone_name:
                return False
                
            zone_id = zone_name.split('_')[0] if '_' in zone_name else zone_name
            zone_id = zone_id.lower()
            
            schedules = self.data_loader.get_all_schedules()
            for schedule in schedules.values():
                if schedule.type and schedule.type.lower() != "temperature":
                    continue
                schedule_id = schedule.id.split(' ')[0] if ' ' in schedule.id else schedule.id
                if schedule_id and schedule_id.lower() == zone_id:
                    return True
            
        except Exception as e:
            print(f"Error checking HVAC system for zone {zone_name}: {e}")
            return False
        
        return False
        
    def process_idf(self, idf) -> None:
        """
        Process an entire IDF model to extract all area information.
        Uses cached zone data from DataLoader instead of direct file access.
        
        Args:
            idf: eppy IDF object (kept for compatibility)
        """
        # Process all non-core zones
        zones = self.data_loader.get_zones_by_type("regular")
        for zone_id, zone_data in zones.items():
            if zone_data.area_id and self._check_zone_hvac(zone_id):
                self.areas_by_zone[zone_id] = {
                    "area_id": zone_data.area_id,
                    "properties": {
                        "floor_area": zone_data.floor_area,
                        "volume": zone_data.volume,
                        "multiplier": zone_data.multiplier
                    }
                }
        
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