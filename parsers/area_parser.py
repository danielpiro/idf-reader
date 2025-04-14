"""
Extracts and processes area information from zone IDs using eppy.
Areas are extracted from zone IDs following the pattern: XXXXX:YYZZZ where YY is the area identifier.
"""
import re
from typing import Dict, Any
from eppy.modeleditor import IDF

class AreaParser:
    """
    Extracts and processes area information from zone IDs.
    Tracks areas, their associated zones, and properties.
    """
    def __init__(self):
        # Store area data by zone
        self.areas_by_zone = {}  # {zone_id: {"area_id": str, "properties": {}}}
        
    def extract_area_from_zone_id(self, zone_id: str) -> str:
        """
        Extract area identifier from zone ID.
        Expected format: XXXXX:YYZZZ where YY is the area identifier.
        
        Args:
            zone_id: The zone identifier to parse
            
        Returns:
            str: The extracted area identifier, or None if no match found
        """
        # Match pattern: anything followed by colon, then capture 2 digits
        area_pattern = r':(\d{2})'
        match = re.search(area_pattern, zone_id)
        
        if match:
            return match.group(1)
        return None

    def process_idf(self, idf: IDF) -> None:
        """
        Process an entire IDF model to extract all area information.
        
        Args:
            idf: eppy IDF object
        """
        # Process each zone to extract area information
        for zone in idf.idfobjects['ZONE']:
            zone_id = str(zone.Name)
            area_id = self.extract_area_from_zone_id(zone_id)
            
            if area_id:
                self.areas_by_zone[zone_id] = {
                    "area_id": area_id,
                    "properties": {
                        "floor_area": float(getattr(zone, "Floor_Area", 0.0)),
                        "volume": float(getattr(zone, "Volume", 0.0)),
                        "multiplier": int(float(getattr(zone, "Multiplier", 1)))
                    }
                }

    def get_parsed_areas(self) -> Dict[str, Any]:
        """
        Returns the dictionary of parsed area information.
        
        Returns:
            dict: Dictionary of area information by zone
        """
        return self.areas_by_zone