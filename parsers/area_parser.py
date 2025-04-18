"""
Extracts and processes area information including floor areas and material properties.
"""
from typing import Dict, Any, List, Optional, Tuple
import time
import logging
from utils.data_loader import DataLoader
from parsers.materials_parser import MaterialsParser  # Import MaterialsParser for element_type function

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
        self.areas_by_zone = {}  # {zone_id: {"area_id": str, "properties": {}, "constructions": {}}}
        
    def process_idf(self, idf) -> None:
        """
        Process an entire IDF model to extract all area information.
        Implementation details moved from DataLoader.
        
        Args:
            idf: eppy IDF object (kept for compatibility)
        """
        start_time = time.time()
        
        try:
            # Process zones first to extract area IDs
            self._process_zones()
            
            # Then process surfaces for each zone
            self._process_surfaces()
            
            end_time = time.time()
            logger.info(f"Area processing completed in {end_time - start_time:.2f}s")
            
        except Exception as e:
            logger.error(f"Error during area processing: {str(e)}")
            raise
    
    def _process_zones(self) -> None:
        """
        Process zones to extract area IDs.
        Implementation details moved from DataLoader.
        """
        # Get cached zone data
        zones = self.data_loader.get_zones()
        
        # Initialize zone data structure
        for zone_id, zone_data in zones.items():
            # Extract area ID from zone ID
            area_id = None
            import re
            area_match = re.search(r':(\d{2})', zone_id)
            if area_match:
                area_id = area_match.group(1)
            
            # Skip zones without area ID
            if not area_id:
                continue
                
            # Initialize zone data structure
            self.areas_by_zone[zone_id] = {
                "area_id": area_id,
                "properties": {
                    "floor_area": zone_data['floor_area'],
                    "volume": zone_data['volume'],
                    "multiplier": zone_data['multiplier']
                },
                "constructions": {}  # Group elements by construction name
            }
    
    def _process_surfaces(self) -> None:
        """
        Process surfaces for all zones.
        Implementation details moved from DataLoader.
        """
        # Get cached surface data
        surfaces = self.data_loader.get_surfaces()
        
        # Group surfaces by zone
        for surface_id, surface_data in surfaces.items():
            zone_name = surface_data['zone_name']
            
            # Skip if zone was filtered out
            if zone_name not in self.areas_by_zone:
                continue
                
            # Skip if not a floor surface
            if surface_data['surface_type'].lower() != 'floor':
                continue
                
            # Get construction properties
            construction_name = surface_data['construction_name']
            construction_props = self._get_construction_properties(construction_name)
            
            # Get area directly from surface data
            area = surface_data['area']
            conductivity = construction_props['conductivity']
            
            # Initialize construction group if not exists
            if construction_name not in self.areas_by_zone[zone_name]["constructions"]:
                self.areas_by_zone[zone_name]["constructions"][construction_name] = {
                    "elements": [],
                    "total_area": 0.0,
                    "total_conductivity": 0.0
                }
            
            # Add element data and update totals
            element_data = {
                "zone": zone_name,
                "surface_name": surface_id,
                "element_type": "Floor",
                "area": area,
                "conductivity": conductivity,
                "area_conductivity": area * conductivity
            }
            
            constr_group = self.areas_by_zone[zone_name]["constructions"][construction_name]
            constr_group["elements"].append(element_data)
            constr_group["total_area"] += area
            constr_group["total_conductivity"] += area * conductivity
    
    def _get_construction_properties(self, construction_name: str) -> Dict[str, float]:
        """
        Get properties for a specific construction.
        Implementation details moved from DataLoader.
        
        Args:
            construction_name: Name of the construction
            
        Returns:
            Dict[str, float]: Dictionary with thickness and conductivity
        """
        # Get cached construction data
        constructions = self.data_loader.get_constructions()
        materials = self.data_loader.get_materials()
        
        if construction_name not in constructions:
            return {'thickness': 0.0, 'conductivity': 0.0}
            
        construction_data = constructions[construction_name]
        material_layers = construction_data['material_layers']
        
        total_thickness = 0.0
        total_resistance = 0.0
        
        # Calculate total thickness and resistance
        for layer_id in material_layers:
            if layer_id in materials:
                material_data = materials[layer_id]
                thickness = material_data['thickness']
                conductivity = material_data['conductivity']
                
                total_thickness += thickness
                if conductivity > 0:
                    total_resistance += thickness / conductivity
        
        # Calculate effective conductivity
        conductivity = total_thickness / total_resistance if total_resistance > 0 else 0.0
        
        return {
            'thickness': total_thickness,
            'conductivity': conductivity
        }
        
    def get_parsed_areas(self) -> Dict[str, Any]:
        """
        Returns the dictionary of parsed area information.
        
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
            
    def get_element_data(self, zone_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get processed elements grouped by construction name.
        
        Args:
            zone_id: Optional zone ID to filter elements by
            
        Returns:
            dict: Dictionary of elements grouped by construction name
        """
        if zone_id:
            return self.areas_by_zone.get(zone_id, {}).get("constructions", {})
        
        # Return all constructions grouped by zone
        all_constructions = {}
        for zone_id, zone_data in self.areas_by_zone.items():
            all_constructions[zone_id] = zone_data.get("constructions", {})
        return all_constructions
        
    def get_area_table_data(self, materials_parser: Optional[MaterialsParser] = None) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get all area data formatted for tables, grouped by area ID.
        
        Args:
            materials_parser: Optional MaterialsParser instance for getting element types
            
        Returns:
            Dict[str, List[Dict[str, Any]]]: Dictionary of area_id -> list of data rows
        """
        # Create a materials parser if not provided
        if materials_parser is None:
            try:
                materials_parser = MaterialsParser(self.data_loader)
                materials_parser.process_idf(None)  # Process data from DataLoader
            except Exception as e:
                materials_parser = None
        
        # Get surface data for element type detection
        surfaces = self.data_loader.get_surfaces()
        
        # Group by area ID
        result_by_area = {}
        
        # Process all zones and their constructions, grouped by zone+construction
        for zone_id, zone_data in self.areas_by_zone.items():
            area_id = zone_data.get("area_id", "unknown")
            
            # Initialize area in results if not already
            if area_id not in result_by_area:
                result_by_area[area_id] = []
            
            # Dictionary to store zone+construction combinations
            zone_constructions = {}
            
            for construction_name, construction_data in zone_data.get("constructions", {}).items():
                # Get element type using materials_parser if available
                element_type = "Floor"  # Default
                if materials_parser:
                    try:
                        element_type = materials_parser._get_element_type(construction_name, surfaces)
                    except Exception:
                        pass
                
                # Create a unique key for zone+construction combination 
                zone_constr_key = f"{zone_id}_{construction_name}"
                
                # Sum areas for same construction+zone
                if zone_constr_key not in zone_constructions:
                    zone_constructions[zone_constr_key] = {
                        "zone": zone_id,
                        "construction": construction_name,
                        "element_type": element_type,
                        "area": 0.0,
                        "conductivity": construction_data.get("elements", [{}])[0].get("conductivity", 0.0) if construction_data.get("elements") else 0.0,
                        "area_conductivity": 0.0,
                        "area_loss": 0.0  # Placeholder as requested
                    }
                
                # Add area and area_conductivity
                constr_sum = zone_constructions[zone_constr_key]
                constr_sum["area"] += construction_data.get("total_area", 0.0)
                constr_sum["area_conductivity"] += construction_data.get("total_conductivity", 0.0)
            
            # Add all zone+constructions to the area's result list
            result_by_area[area_id].extend(zone_constructions.values())
                
        return result_by_area