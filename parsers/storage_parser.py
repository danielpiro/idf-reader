"""
Parser for extracting storage zone information from IDF files.
"""
from typing import Dict, Any
from utils.data_loader import DataLoader

class StorageParser:
    """Parser for extracting storage zone data from IDF files."""
    
    def __init__(self, data_loader: DataLoader):
        """
        Initialize the StorageParser with a DataLoader instance.
        
        Args:
            data_loader: DataLoader instance for accessing cached IDF data
        """
        self.data_loader = data_loader
        self.storage_zones = {}
        
    def process_idf(self, idf) -> None:
        """
        Process an IDF file to extract storage zone information.
        Uses cached data from DataLoader instead of direct file access.
        
        Args:
            idf: An IDF file object from eppy (kept for compatibility)
        """
        # Get all storage zones from DataLoader
        storage_zones = self.data_loader.get_zones_by_type("storage")
        
        # Process each storage zone
        for zone_id, zone_data in storage_zones.items():
            self.storage_zones[zone_id] = {
                "properties": {
                    "floor_area": zone_data.floor_area,
                    "volume": zone_data.volume,
                    "multiplier": zone_data.multiplier
                }
            }
                
    def get_storage_zones(self) -> Dict[str, Any]:
        """
        Get the extracted storage zone data.
        
        Returns:
            Dict containing storage zone information
        """
        return self.storage_zones