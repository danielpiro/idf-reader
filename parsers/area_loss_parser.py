"""
Extracts and processes area loss information for thermal performance analysis.
"""
from typing import Dict, Any, List, Optional
import logging
import re
from parsers.area_parser import AreaParser
from collections import defaultdict  # Added for counting apartments per level

logger = logging.getLogger(__name__)

class AreaLossParser:
    """
    Processes area loss information from IDF files, calculating H-values.
    Uses the AreaParser which already has most of the functionality.
    """
    def __init__(self, area_parser: AreaParser, city_area_name: str = "א"):
        self.area_parser = area_parser
        self.processed = False
        self.area_loss_data = []
        self.city_area_name = city_area_name
        self.apartments_per_level = {}  # Added to store count of apartments per level
        
    def parse(self) -> List[Dict[str, Any]]:
        """
        Parse the area loss data and calculate H-values.
        
        Returns:
            List[Dict[str, Any]]: List of dictionaries with area loss data
        """
        if self.processed:
            return self.area_loss_data
            
        try:
            # Calculate apartments per level before processing H-values
            self._calculate_apartments_per_level()
            
            # Use the existing functionality in AreaParser to calculate H-values
            if hasattr(self.area_parser, 'get_area_h_values'):
                self.area_loss_data = self.area_parser.get_area_h_values()
                
                # Get the locations and wall mass per area for each area
                wall_mass_data = self._get_wall_mass_per_area()
                
                # Add the required H-Needed and Compatible fields
                for item in self.area_loss_data:
                    area_id = item.get('area_id', '')
                    location = item.get('location', 'Unknown')
                    total_floor_area = item.get('total_floor_area', 0)
                    wall_mass_per_area = wall_mass_data.get(area_id, 0)
                    
                    # Calculate h_needed based on the tables and conditions
                    h_needed = self._calculate_h_needed(location, total_floor_area, wall_mass_per_area, area_id)
                    item['h_needed'] = h_needed
                    
                    # Check compatibility based on h_value < h_needed
                    h_value = item.get('h_value', 0)
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
    
    def _calculate_apartments_per_level(self) -> None:
        """
        Analyze zone names to determine the number of apartments per level.
        Zone names follow the format: "01:02XLIVING" where:
        - First two digits (01) represent the level/floor number
        - Digits after the colon (02) represent the apartment number
        """
        try:
            # Get all zones from the area parser
            zones_by_area = self.area_parser.areas_by_zone
            
            # Dictionary to track unique apartment numbers per level
            apartments_by_level = defaultdict(set)
            
            # Parse zone names
            for zone_id in zones_by_area.keys():
                # Extract level and apartment number using regex
                match = re.match(r'(\d{2}):(\d{2})', zone_id)
                if match:
                    level = match.group(1)
                    apartment = match.group(2)
                    apartments_by_level[level].add(apartment)
            
            # Count apartments per level
            self.apartments_per_level = {level: len(apartments) for level, apartments in apartments_by_level.items()}
            
            logger.debug(f"Calculated apartments per level: {self.apartments_per_level}")
        
        except Exception as e:
            logger.error(f"Error calculating apartments per level: {str(e)}")
            # Default to empty dictionary if there's an error
            self.apartments_per_level = {}
    
    def _get_wall_mass_per_area(self) -> Dict[str, float]:
        """
        Calculate the wall mass per area for each area ID.
        
        Returns:
            Dict[str, float]: A dictionary mapping area_id to wall mass per area
        """
        wall_mass_data = {}
        
        try:
            # Use MaterialsParser to get construction information for external walls
            materials_parser = self.area_parser.materials_parser
            if materials_parser and hasattr(materials_parser, 'get_element_data'):
                element_data = materials_parser.get_element_data()
                
                # Group elements by area and calculate wall mass
                for element in element_data:
                    if element.get('element_type', '').lower() == 'wall' and 'external' in element.get('boundary_condition', '').lower():
                        area_id = element.get('area_id', '')
                        if not area_id:
                            continue
                            
                        mass = element.get('mass_per_area', 0.0)
                        area = element.get('area', 0.0)
                        
                        if area_id not in wall_mass_data:
                            wall_mass_data[area_id] = mass
                        else:
                            # Keep the largest mass per area
                            wall_mass_data[area_id] = max(wall_mass_data[area_id], mass)
            
            else:
                logger.warning("MaterialsParser instance not available or missing get_element_data method")
                
        except Exception as e:
            logger.error(f"Error calculating wall mass per area: {str(e)}")
        
        return wall_mass_data
    
    def _calculate_h_needed(self, location: str, total_floor_area: float, wall_mass_per_area: float, area_id: str) -> float:
        """
        Calculate h_needed based on the tables provided.
        
        Args:
            location (str): The location type (Ground Floor, Intermediate Floor, etc.)
            total_floor_area (float): The total floor area for this area
            wall_mass_per_area (float): The wall mass per area for this area
            area_id (str): The area ID to determine level and apartments per floor
            
        Returns:
            float: The calculated h_needed value
        """
        # Map location to number
        location_map = {
            "Ground Floor": 1,
            "Intermediate Floor": 1,
            "Over Close Space": 2,
            "Below Open Space": 3,
            "Over Open Space": 4
        }
        
        # Default to location type 1 if not found
        location_num = location_map.get(location, 1)
        
        # Map city area name to column index (0-based)
        area_col = {
            "א": 0,
            "ב": 1,
            "ג": 2,
            "ד": 3
        }
        
        # Default to area "א" if city_area_name not found
        col_idx = area_col.get(self.city_area_name, 0)
        
        # Special case for location 3 (Below Open Space)
        if location_num == 3:
            # Extract level from area_id to determine apartments per level
            level = area_id[:2] if len(area_id) >= 2 and area_id[:2].isdigit() else None
            apts_per_level = self.apartments_per_level.get(level, 0) if level else 0
            
            # Determine if it's one apartment per level or multiple
            is_single_apt = apts_per_level <= 1
            
            # Choose the appropriate table based on wall mass
            if wall_mass_per_area > 100:
                # Table Z: wall_mass_per_area > 100
                table_z = [
                    [4.6, 4.2, 3.8, 3.7],  # Row 1: 1 apartment per floor
                    [4.4, 4.0, 3.7, 3.6]   # Row 2: 2+ apartments per floor
                ]
                row_idx = 0 if is_single_apt else 1
                h_needed = table_z[row_idx][col_idx]
            else:
                # Table X: wall_mass_per_area <= 100
                table_x = [
                    [3.9, 3.6, 3.3, 3.3],  # Row 1: 1 apartment per floor
                    [3.8, 3.5, 3.2, 3.2]   # Row 2: 2+ apartments per floor
                ]
                row_idx = 0 if is_single_apt else 1
                h_needed = table_x[row_idx][col_idx]
                
            logger.debug(f"Special case for Below Open Space: Level={level}, Apts={apts_per_level}, "
                         f"Is Single Apt={is_single_apt}, Wall Mass={wall_mass_per_area}, h_needed={h_needed}")
                
            return h_needed
        
        # For other locations, use the standard tables
        # Define the tables
        # Table 1: total_floor_area <= 100 and wall_mass_per_area >= 100
        table1 = [
            [2.3, 2.2, 2.1, 2.0],  # Location 1
            [3.0, 2.6, 2.5, 2.5],  # Location 2
            [2.9, 2.8, 2.7, 2.6],  # Location 3 - No longer used for location 3
            [3.6, 3.2, 2.9, 2.9]   # Location 4
        ]
        
        # Table 2: total_floor_area <= 100 and wall_mass_per_area < 100
        table2 = [
            [1.8, 1.7, 1.7, 1.7],  # Location 1
            [2.5, 2.3, 2.1, 2.1],  # Location 2
            [2.4, 2.3, 2.3, 2.3],  # Location 3 - No longer used for location 3
            [3.1, 2.8, 2.5, 2.5]   # Location 4
        ]
        
        # Table 3: total_floor_area > 100 and wall_mass_per_area >= 100
        table3 = [
            [2.1, 2.0, 1.9, 1.8],  # Location 1
            [2.7, 2.5, 2.4, 2.3],  # Location 2
            [2.7, 2.6, 2.5, 2.4],  # Location 3 - No longer used for location 3
            [3.3, 3.0, 2.7, 2.7]   # Location 4
        ]
        
        # Table 4: total_floor_area > 100 and wall_mass_per_area < 100
        table4 = [
            [1.7, 1.6, 1.6, 1.6],  # Location 1
            [2.3, 2.1, 2.0, 2.0],  # Location 2
            [2.3, 2.2, 2.2, 2.2],  # Location 3 - No longer used for location 3
            [2.9, 2.6, 2.4, 2.4]   # Location 4
        ]
        
        # Select the appropriate table based on conditions
        if total_floor_area <= 100:
            if wall_mass_per_area >= 100:
                table = table1
            else:
                table = table2
        else:
            if wall_mass_per_area >= 100:
                table = table3
            else:
                table = table4
        
        # Ensure location_num is within range (1-4 maps to 0-3 for array index)
        row_idx = min(max(location_num - 1, 0), 3)
        
        # Get h_needed from the selected table
        h_needed = table[row_idx][col_idx]
        
        logger.debug(f"Calculated h_needed: {h_needed} - Location: {location} (map: {location_num}), "
                    f"Floor Area: {total_floor_area}, Wall Mass: {wall_mass_per_area}, "
                    f"City Area: {self.city_area_name} (col: {col_idx})")
        
        return h_needed
    
    def get_parsed_area_loss_data(self) -> List[Dict[str, Any]]:
        """
        Get the parsed area loss data.
        
        Returns:
            List[Dict[str, Any]]: List of dictionaries with area loss data
        """
        if not self.processed:
            return self.parse()
        return self.area_loss_data