"""
Extracts and processes area loss information for thermal performance analysis.
"""
from typing import Dict, Any, List
from utils.logging_config import get_logger
import re
from parsers.area_parser import AreaParser
from collections import defaultdict

logger = get_logger(__name__)

class AreaLossParser:
    """
    Calculates H-values and area loss compatibility using AreaParser data.
    """
    def __init__(self, area_parser: AreaParser, city_area_name: str = "א"):        
        self.area_parser = area_parser
        self.processed = False
        self.area_loss_data = []
        self.city_area_name = city_area_name
        self.apartments_per_level = {}

    def parse(self) -> List[Dict[str, Any]]:
        if self.processed:
            return self.area_loss_data
        try:
            self._calculate_apartments_per_level()
            if not hasattr(self.area_parser, 'get_area_h_values'):
                logger.error("AreaParser missing get_area_h_values method")
                return []
            self.area_loss_data = self.area_parser.get_area_h_values()
            wall_mass_data = self._get_wall_mass_per_area()
            for item in self.area_loss_data:
                area_id = item.get('area_id', '')
                location = item.get('location', 'Unknown')
                total_floor_area = item.get('total_floor_area')
                wall_mass_per_area = wall_mass_data.get(area_id)
                h_needed = self._calculate_h_needed(location, total_floor_area or 0, wall_mass_per_area or 0, area_id)
                item['h_needed'] = h_needed
                h_value = item.get('h_value')
                if h_value is None:
                    item['compatible'] = "No"
                else:
                    item['compatible'] = "Yes" if h_value < h_needed else "No"
            self.processed = True
            return self.area_loss_data
        except Exception as e:
            logger.error(f"Error parsing area loss data: {e}")
            return []

    def _calculate_apartments_per_level(self) -> None:
        try:
            zones_by_area = self.area_parser.areas_by_zone
            apartments_by_level = defaultdict(set)
            for zone_id in zones_by_area.keys():
                match = re.match(r'(?P<level>\d{2}):(?P<apt>\d{2})', zone_id)
                if match:
                    apartments_by_level[match.group('level')].add(match.group('apt'))
            self.apartments_per_level = {level: len(apts) for level, apts in apartments_by_level.items()}
        except Exception as e:
            logger.error(f"Error calculating apartments per level: {e}")
            self.apartments_per_level = {}

    def _get_wall_mass_per_area(self) -> Dict[str, float]:
        wall_mass_data = {}
        try:
            materials_parser = self.area_parser.materials_parser
            if not (materials_parser and hasattr(materials_parser, 'get_element_data')):
                logger.warning("MaterialsParser missing or missing get_element_data method")
                return wall_mass_data
            element_data = materials_parser.get_element_data()
            for element in element_data:
                if element.get('element_type', '').lower() == 'wall' and 'external' in element.get('boundary_condition', '').lower():
                    area_id = element.get('area_id', '')
                    if not area_id:
                        continue
                    mass = element.get('mass_per_area')
                    if mass is not None:
                        current_mass = wall_mass_data.get(area_id, 0.0)
                        wall_mass_data[area_id] = max(current_mass, mass)
        except Exception as e:
            logger.error(f"Error calculating wall mass per area: {e}")
        return wall_mass_data

    def _calculate_h_needed(self, location: str, total_floor_area: float, wall_mass_per_area: float, area_id: str) -> float:
        final_location_map = {
            "Ground Floor & Intermediate ceiling": 1,
            "Ground Floor & Separation ceiling": 1,
            "Intermediate Floor & Intermediate ceiling": 1,
            "Intermediate Floor & Separation ceiling": 1,
            "Separation Floor & Intermediate ceiling": 2,
            "Separation Floor & Separation ceiling": 2,
            "Ground Floor & External ceiling": 3,
            "External Floor & External ceiling": 3,
            "Separation Floor & External ceiling": 3,
            "Intermediate Floor & External ceiling": 3,
            "External Floor & Intermediate ceiling": 4,
            "External Floor & Separation ceiling": 4
        }
        location_num = final_location_map.get(location, 1)
        area_col = {"א": 0, "ב": 1, "ג": 2, "ד": 3}
        col_idx = area_col.get(self.city_area_name, 0)
        if location_num == 3:
            level = area_id[:2] if len(area_id) >= 2 and area_id[:2].isdigit() else None
            apts_per_level = self.apartments_per_level.get(level, 0) if level else 0
            is_single_apt = apts_per_level <= 1
            if wall_mass_per_area > 100:
                table_z = [
                    [4.6, 4.2, 3.8, 3.7],
                    [4.4, 4.0, 3.7, 3.6]
                ]
                row_idx = 0 if is_single_apt else 1
                return table_z[row_idx][col_idx]
            else:
                table_x = [
                    [3.9, 3.6, 3.3, 3.3],
                    [3.8, 3.5, 3.2, 3.2]
                ]
                row_idx = 0 if is_single_apt else 1
                return table_x[row_idx][col_idx]
        table1 = [
            [2.3, 2.2, 2.1, 2.0],
            [3.0, 2.6, 2.5, 2.5],
            [2.9, 2.8, 2.7, 2.6],
            [3.6, 3.2, 2.9, 2.9]
        ]
        table2 = [
            [1.8, 1.7, 1.7, 1.7],
            [2.5, 2.3, 2.1, 2.1],
            [2.4, 2.3, 2.3, 2.3],
            [3.1, 2.8, 2.5, 2.5]
        ]
        table3 = [
            [2.1, 2.0, 1.9, 1.8],
            [2.7, 2.5, 2.4, 2.3],
            [2.7, 2.6, 2.5, 2.4],
            [3.3, 3.0, 2.7, 2.7]
        ]
        table4 = [
            [1.7, 1.6, 1.6, 1.6],
            [2.3, 2.1, 2.0, 2.0],
            [2.3, 2.2, 2.2, 2.2],
            [2.9, 2.6, 2.4, 2.4]
        ]
        if total_floor_area <= 100:
            table = table1 if wall_mass_per_area >= 100 else table2
        else:
            table = table3 if wall_mass_per_area >= 100 else table4
        row_idx = min(max(location_num - 1, 0), 3)
        return table[row_idx][col_idx]

    def get_parsed_area_loss_data(self) -> List[Dict[str, Any]]:
        if not self.processed:
            return self.parse()
        return self.area_loss_data
