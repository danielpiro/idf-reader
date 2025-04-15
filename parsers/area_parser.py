"""
Extracts and processes area information from zone IDs using eppy.
Areas are extracted from zone IDs following the pattern: XXXXX:YYZZZ where YY is the area identifier.
Special handling for STORAGE zones with pattern: XXXXX:STORAGE
"""
import re
import json
import os
from pathlib import Path
from typing import Dict, Any
from eppy.modeleditor import IDF
from generators.storage_report_generator import generate_storage_report_pdf

class AreaParser:
    """
    Extracts and processes area information from zone IDs.
    Tracks areas, their associated zones, and properties.
    """
    def __init__(self):
        # Store area data by zone
        self.areas_by_zone = {}  # {zone_id: {"area_id": str, "properties": {}}}
        # Store storage zone data separately
        self.storage_zones = {}  # {zone_id: {"properties": {}}}
        
    def is_storage_zone(self, zone_id: str) -> bool:
        """
        Check if the zone ID matches the STORAGE pattern.
        
        Args:
            zone_id: The zone identifier to check
            
        Returns:
            bool: True if this is a storage zone, False otherwise
        """
        return bool(re.search(r':STORAGE$', zone_id))
        
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
        Handles both regular zones and storage zones.
        
        Args:
            idf: eppy IDF object
        """
        # Process each zone to extract area information
        for zone in idf.idfobjects['ZONE']:
            zone_id = str(zone.Name)
            
            # Extract common zone properties
            zone_properties = {
                "floor_area": float(getattr(zone, "Floor_Area", 0.0)),
                "volume": float(getattr(zone, "Volume", 0.0)),
                "multiplier": int(float(getattr(zone, "Multiplier", 1)))
            }
            
            if self.is_storage_zone(zone_id):
                # Handle storage zones separately
                self.storage_zones[zone_id] = {
                    "properties": zone_properties
                }
            else:
                # Process regular zones as before
                area_id = self.extract_area_from_zone_id(zone_id)
                if area_id:
                    self.areas_by_zone[zone_id] = {
                        "area_id": area_id,
                        "properties": zone_properties
                    }

    def get_parsed_areas(self) -> Dict[str, Any]:
        """
        Returns the dictionary of parsed area information.
        Does not include storage zones.
        
        Returns:
            dict: Dictionary of area information by zone
        """
        return self.areas_by_zone
        
    def get_storage_zones(self) -> Dict[str, Any]:
        """
        Returns the dictionary of storage zone information.
        
        Returns:
            dict: Dictionary of storage zone information
        """
        return self.storage_zones
        
    def save_storage_zones(self, output_dir: str = "output/zones") -> bool:
        """
        Save storage zones to a PDF report.
        Creates output directory if it doesn't exist.
        
        Args:
            output_dir: Directory where to save the PDF report
            
        Returns:
            bool: True if saving was successful, False otherwise
        """
        try:
            # Create output directory if it doesn't exist
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            # Generate storage zones PDF report
            return generate_storage_report_pdf(
                self.storage_zones,
                str(output_path / "storage_zones.pdf")
            )
            
        except Exception as e:
            print(f"Error saving storage zones: {e}")
            return False