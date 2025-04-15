"""
Parser for extracting storage zone information from IDF files.
"""
from typing import Dict, Any

class StorageParser:
    """Parser for extracting storage zone data from IDF files."""
    
    def __init__(self):
        self.storage_zones = {}
        
    def process_idf(self, idf) -> None:
        """
        Process an IDF file to extract storage zone information.
        
        Args:
            idf: An IDF file object from eppy
        """
        for zone in idf.idfobjects['ZONE']:
            # Check if zone name contains storage indicators
            zone_name = str(zone.Name).lower()
            if any(keyword in zone_name for keyword in ['storage', 'store', 'warehouse']):
                zone_data = {
                    "properties": {
                        "floor_area": float(zone.Floor_Area) if hasattr(zone, 'Floor_Area') else 0.0,
                        "volume": float(zone.Volume) if hasattr(zone, 'Volume') else 0.0,
                        "multiplier": int(zone.Multiplier) if hasattr(zone, 'Multiplier') else 1
                    }
                }
                self.storage_zones[zone.Name] = zone_data
                
    def get_storage_zones(self) -> Dict[str, Any]:
        """
        Get the extracted storage zone data.
        
        Returns:
            Dict containing storage zone information
        """
        return self.storage_zones