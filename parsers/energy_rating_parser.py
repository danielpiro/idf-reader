"""
Extracts and processes energy consumption and rating information from EnergyPlus output files.
"""
from typing import Dict, Any, List, Optional, Tuple
import logging
import re
import csv
import os
from pathlib import Path
from parsers.area_parser import AreaParser
from utils.data_loader import safe_float

logger = logging.getLogger(__name__)
# --- Explicitly set logging level for this module ---
# logger.setLevel(logging.DEBUG) # Keep or remove as needed
# ---

class EnergyRatingParser:
    """
    Processes energy consumption data from EnergyPlus output files (eplusout.csv).
    Uses area data from AreaParser for energy per area calculations.
    """
    def __init__(self, data_loader, area_parser: AreaParser):
        self.data_loader = data_loader
        self.area_parser = area_parser
        self.energy_data_by_area = {}  # Stores processed energy data by area ID
        self.processed = False
        self.zone_pattern = re.compile(r'(\d{2}):(\d{2})X([A-Za-z0-9_]+)(?:\s+([A-Za-z0-9_ ]+))?:([A-Za-z0-9_ ]+(?:\s+[A-Za-z0-9_ ]+)*)\s+\[([A-Za-z0-9/]+)\]\(([A-Za-z0-9]+)\)')

    def process_output(self, output_file_path: Optional[str] = None) -> None:
        """
        Process EnergyPlus output file to extract energy consumption data.
        
        Args:
            output_file_path: Path to the eplusout.csv file. If None, tries to find it in the same directory as the IDF file.
        """
        if self.processed:
            # Skip if already processed
            return

        # Try to find eplusout.csv if path not provided
        if not output_file_path:
            idf_path = self.data_loader.get_idf_path()
            if idf_path:
                idf_dir = os.path.dirname(idf_path)
                possible_paths = [
                    os.path.join(idf_dir, "eplusout.csv"),
                    os.path.join(os.path.dirname(idf_dir), "tests", "eplusout.csv")
                ]
                for path in possible_paths:
                    if os.path.exists(path):
                        output_file_path = path
                        break
        
        if not output_file_path or not os.path.exists(output_file_path):
            logger.error(f"Cannot find EnergyPlus output file: {output_file_path}")
            return
            
        logger.info(f"Processing EnergyPlus output file: {output_file_path}")
        
        # Make sure area parser has processed the data
        if not self.area_parser.processed:
            logger.info("Area parser not processed yet, processing now...")
            self.area_parser.process_idf(None)  # Process with default settings
            
        # Process the CSV file
        try:
            with open(output_file_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)
                headers = next(reader)
                
                # Get the last row which should contain the run period values
                last_row = None
                for row in reader:
                    last_row = row
                    
                if not last_row:
                    logger.error("No data found in EnergyPlus output file")
                    return
                    
                # Process headers and extract zone energy data
                self._process_headers_and_values(headers, last_row)
                
            # Perform final calculations
            self._calculate_totals()
            
            self.processed = True
            logger.info(f"Successfully processed energy data for {len(self.energy_data_by_area)} areas")
            
        except Exception as e:
            logger.error(f"Error processing EnergyPlus output file: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def _process_headers_and_values(self, headers: List[str], values: List[str]) -> None:
        """
        Process headers to extract zone information and corresponding values.
        
        Args:
            headers: List of header strings from CSV file
            values: List of value strings from the last row of CSV file
        """
        # Initialize data structure
        self.energy_data_by_area = {}
        
        # Process each header
        for i, header in enumerate(headers):
            # Skip Date/Time and non-zone headers
            if i == 0 or "X" not in header:
                continue
            
            # Try to match zone pattern
            match = self.zone_pattern.search(header)
            if not match:
                continue
                
            try:
                floor, area_id, zone_name, equipment_type, metric, unit, period = match.groups()
                
                # Skip if not RunPeriod
                if period != "RunPeriod":
                    continue
                    
                # Get value for this header
                if i < len(values):
                    value = safe_float(values[i], 0.0)
                else:
                    value = 0.0
                
                # Process value based on header type
                processed_value = self._process_value(value, header.lower())
                
                # Create area_id key if it doesn't exist
                area_key = f"{floor}:{area_id}"
                if area_key not in self.energy_data_by_area:
                    self.energy_data_by_area[area_key] = {
                        'floor': floor,
                        'area_id': area_id,
                        'zone_name': zone_name,
                        'zones': set([zone_name]),
                        'lighting': 0.0,
                        'heating': 0.0,
                        'cooling': 0.0,
                        'total': 0.0,
                        'location': self._determine_location(area_id),
                        'total_area': self._get_area_total_for_area_id(area_id)
                    }
                else:
                    self.energy_data_by_area[area_key]['zones'].add(zone_name)
                
                # Add value to appropriate category
                category = None
                if 'light' in header.lower():
                    category = 'lighting'
                elif 'heating' in header.lower():
                    category = 'heating'
                elif 'cooling' in header.lower():
                    category = 'cooling'
                
                if category:
                    self.energy_data_by_area[area_key][category] += processed_value
                    
            except Exception as e:
                logger.error(f"Error processing header {header}: {e}")
    
    def _process_value(self, value: float, header_lower: str) -> float:
        """
        Process value based on header type and divide by appropriate factor.
        
        Args:
            value: The raw value from CSV
            header_lower: Lowercase header string for category determination
            
        Returns:
            float: Processed value
        """
        # Divide by appropriate factor based on header type
        if 'light' in header_lower:
            processed = value / 3600000.0
        elif 'heating' in header_lower or 'cooling' in header_lower:
            processed = value / 10800000.0
        else:
            processed = value
            
        return processed
    
    def _calculate_totals(self) -> None:
        """
        Calculate total energy consumption and per area values.
        """
        for area_key, area_data in self.energy_data_by_area.items():
            # Calculate total for this area
            area_data['total'] = area_data['lighting'] + area_data['heating'] + area_data['cooling']
            
            # If area is available, calculate per area values
            if area_data['total_area'] > 0:
                area_data['lighting_per_area'] = area_data['lighting'] / area_data['total_area']
                area_data['heating_per_area'] = area_data['heating'] / area_data['total_area']
                area_data['cooling_per_area'] = area_data['cooling'] / area_data['total_area']
                area_data['total_per_area'] = area_data['total'] / area_data['total_area']
            else:
                # Set per area values to original if no area available
                area_data['lighting_per_area'] = area_data['lighting']
                area_data['heating_per_area'] = area_data['heating']
                area_data['cooling_per_area'] = area_data['cooling']
                area_data['total_per_area'] = area_data['total']
                
            # Convert zones set to list for easier serialization
            area_data['zones'] = list(area_data['zones'])
    def _get_area_total_for_area_id(self, area_id: str) -> float:
        """
        Get the total floor area for a specific area ID.
        
        Args:
            area_id: The area ID
            
        Returns:
            float: Total floor area for the area
        """
        # Use the existing method in area_parser to get total floor area
        area_totals = self.area_parser.get_area_totals(area_id)
        return area_totals.get("total_floor_area", 0.0)
    def _determine_location(self, area_id: str) -> str:
        """
        Determine the location for an area ID based on area parser data.
        
        Args:
            area_id: The area ID
            
        Returns:
            str: Location description
        """
        # Use the area_h_values data from area_parser to get location
        area_h_values = self.area_parser.get_area_h_values()
        
        for area_data in area_h_values:
            if area_data.get('area_id') == area_id:
                return area_data.get('location', 'Unknown')
        
        # If area_id not found in h_values data, try to extract from floor number
        if area_id and len(area_id) >= 2 and area_id[:2].isdigit():
            floor_num = int(area_id[:2])
            if floor_num == 0:
                return "Ground Floor"
            else:
                return "Intermediate Floor"
                
        return "Unknown"
    
    def get_energy_data_by_area(self) -> Dict[str, Dict[str, Any]]:
        """
        Get the processed energy data by area.
        
        Returns:
            Dict[str, Dict[str, Any]]: Dictionary of energy data by area ID
        """
        return self.energy_data_by_area
    
    def get_energy_rating_table_data(self) -> List[Dict[str, Any]]:
        """
        Get data for energy rating reports in table format.
        
        Returns:
            List[Dict[str, Any]]: List of energy rating data rows for report
        """
        table_data = []
        
        for area_key, area_data in self.energy_data_by_area.items():
            row = {
                'floor': area_data['floor'],
                'area_id': area_data['area_id'],
                'total_area': area_data['total_area'],
                'location': area_data['location'],
                'lighting': area_data['lighting_per_area'],
                'heating': area_data['heating_per_area'],
                'cooling': area_data['cooling_per_area'],
                'total': area_data['total_per_area'],
                'energy_consumption_model': '',  # Placeholder for future implementation
                'better_percent': '',  # Placeholder for future implementation
                'energy_rating': '',  # Placeholder for future implementation
                'multiplier': ''  # Placeholder for future implementation
            }
            table_data.append(row)
        
        return table_data
