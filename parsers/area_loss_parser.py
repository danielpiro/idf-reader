"""
Extracts and processes area loss information for thermal performance analysis.
"""
from typing import Dict, Any, List, Optional
import logging
import re
from parsers.area_parser import AreaParser

logger = logging.getLogger(__name__)

class AreaLossParser:
    """
    Processes area loss information from IDF files, calculating H-values.
    Uses the AreaParser which already has most of the functionality.
    """
    def __init__(self, area_parser: AreaParser):
        self.area_parser = area_parser
        self.processed = False
        self.area_loss_data = []
        
    def parse(self) -> List[Dict[str, Any]]:
        """
        Parse the area loss data and calculate H-values.
        
        Returns:
            List[Dict[str, Any]]: List of dictionaries with area loss data
        """
        if self.processed:
            return self.area_loss_data
            
        try:
            # Use the existing functionality in AreaParser to calculate H-values
            if hasattr(self.area_parser, 'get_area_h_values'):
                self.area_loss_data = self.area_parser.get_area_h_values()
                
                # Get the location for each area from settings or DataLoader
                locations = self._get_area_locations()
                
                # Add the required H-Needed and Compatible fields
                for item in self.area_loss_data:
                    area_id = item.get('area_id', '')
                    
                    # Update the location with actual value from locations dictionary
                    # if available, otherwise keep existing value
                    if area_id in locations and locations[area_id]:
                        item['location'] = locations[area_id]
                    
                    # Set H-Needed to 0 as specified
                    item['h_needed'] = 0
                    
                    # Check compatibility based on h_value < h_needed
                    h_value = item.get('h_value', 0)
                    h_needed = item.get('h_needed', 0)
                    item['compatible'] = "Yes" if h_value < h_needed else "No"
                
                self.processed = True
                return self.area_loss_data
            else:
                logger.error("AreaParser does not have the required get_area_h_values method")
                return []
                
        except Exception as e:
            logger.error(f"Error parsing area loss data: {str(e)}")
            import traceback
            traceback.print_exc()
            return []
    
    def _get_area_locations(self) -> Dict[str, str]:
        """
        Get location information for each area.
        
        Returns:
            Dict[str, str]: A dictionary mapping area_id to location
        """
        locations = {}
        
        # Try to get locations from the DataLoader if available
        try:
            if hasattr(self.area_parser, 'data_loader') and self.area_parser.data_loader:
                # Check for settings data - location might be available there
                if hasattr(self.area_parser.data_loader, 'get_settings'):
                    settings = self.area_parser.data_loader.get_settings()
                    if settings and 'location' in settings:
                        location_name = settings.get('location', {}).get('name', '')
                        # Default all areas to the project location
                        for area_id in self.area_parser.areas_by_zone:
                            if area_id != "unknown":
                                locations[area_id] = location_name
        
        except Exception as e:
            logger.warning(f"Error getting area locations: {e}")
            
        return locations
    
    def get_parsed_area_loss_data(self) -> List[Dict[str, Any]]:
        """
        Get the parsed area loss data.
        
        Returns:
            List[Dict[str, Any]]: List of dictionaries with area loss data
        """
        if not self.processed:
            return self.parse()
        return self.area_loss_data