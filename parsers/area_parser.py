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
    Processes area information from IDF files, including distribution of zones in areas.
    Uses cached data from DataLoader for efficient access.
    """
    def __init__(self, data_loader):
        self.data_loader = data_loader
        self.areas_by_zone = {}  # Dictionary to store area data by zone
        self.processed = False
        
    def process_idf(self, idf) -> None: # idf parameter kept for compatibility
        """
        Extract area information.
        
        Args:
            idf: eppy IDF object (not directly used)
        """
        if not self.data_loader:
            print("Error: AreaParser requires a DataLoader instance.")
            return
            
        if self.processed:
            # Skip if already processed
            return
            
        try:
            # Process zones to initialize data structure
            self._process_zones()
            
            # Process surfaces to extract construction information
            self._process_surfaces()
            
            self.processed = True
        
        except Exception as e:
            print(f"Error extracting area information: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def _process_zones(self) -> None:
        """
        Process zones to initialize the data structure.
        """
        # Get zones with area information from DataLoader
        zones = self.data_loader.get_zones()
        
        # Process each zone to create data structure
        for zone_id, zone_data in zones.items():
            # Extract the area ID from the zone name - it's the digits after the colon
            area_id = "unknown"
            
            if zone_id and ":" in zone_id:
                # Extract area ID after the colon
                parts = zone_id.split(":")
                if len(parts) > 1:
                    # If we have at least 2 digits, take the first two
                    if len(parts[1]) >= 2 and parts[1][:2].isdigit():
                        area_id = parts[1][:2]
                    # Otherwise use the entire part after the colon
                    elif parts[1]:
                        area_id = parts[1]
            
            # Create zone in areas_by_zone
            self.areas_by_zone[zone_id] = {
                "area_id": area_id,
                "floor_area": zone_data.get("floor_area", 0.0),
                "multiplier": zone_data.get("multiplier", 1),
                "constructions": {}  # Will be populated in _process_surfaces
            }
    
    def _process_surfaces(self) -> None:
        """
        Process surfaces to extract construction and area information.
        Implementation details moved from DataLoader.
        """
        # Get cached surface data
        surfaces = self.data_loader.get_surfaces()
        
        # Process each surface to extract construction and area information
        for surface_id, surface in surfaces.items():
            zone_name = surface.get("zone_name")
            
            # Skip if zone is missing
            if not zone_name or zone_name not in self.areas_by_zone:
                continue
                
            construction_name = surface.get("construction_name")
            if not construction_name:
                continue
                
            area = surface.get("area", 0.0)
            if area <= 0.0:
                continue
            
            # Get properties for the construction
            properties = self._get_construction_properties(construction_name)
            thickness = properties.get("thickness", 0.0)
            
            # Calculate U-Value using materials parser logic (1/R-value with film)
            u_value = self._calculate_u_value(construction_name)
            
            # Get surface type and determine if glazing
            surface_type = surface.get("surface_type", "wall")
            is_glazing = surface.get("is_glazing", False)
            
            # Add construction to zone if not already present
            if construction_name not in self.areas_by_zone[zone_name]["constructions"]:
                self.areas_by_zone[zone_name]["constructions"][construction_name] = {
                    "elements": [],
                    "total_area": 0.0,
                    "total_u_value": 0.0
                }
            
            # Add element data and update totals
            element_data = {
                "zone": zone_name,
                "surface_name": surface_id,
                "element_type": "Glazing" if is_glazing else surface_type.capitalize(),  # Mark glazing specifically
                "area": area,
                "u_value": u_value,
                "area_u_value": area * u_value
            }
            
            constr_group = self.areas_by_zone[zone_name]["constructions"][construction_name]
            constr_group["elements"].append(element_data)
            constr_group["total_area"] += area
            constr_group["total_u_value"] += area * u_value
            
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
        
    def _calculate_u_value(self, construction_name: str) -> float:
        """
        Calculate U-Value for a construction (1/R-value with film).
        
        Args:
            construction_name: Name of the construction
            
        Returns:
            float: U-Value
        """
        # Get cached construction and surface data
        constructions = self.data_loader.get_constructions()
        materials = self.data_loader.get_materials()
        surfaces = self.data_loader.get_surfaces()
        
        if construction_name not in constructions:
            return 0.0
            
        # Find surface using this construction to determine type and boundary
        s_type = "wall"  # Default
        boundary = "outdoors"  # Default
        
        for surface_id, surface in surfaces.items():
            if surface.get('construction_name') == construction_name:
                s_type = surface.get('surface_type', 'wall').lower()
                boundary = surface.get('boundary_condition', 'outdoors').lower()
                break
                
        # Calculate film resistance using MaterialsParser logic
        film_resistance = self._get_surface_film_resistance(s_type, boundary)
        
        # Calculate material thermal resistance
        construction_data = constructions[construction_name]
        material_layers = construction_data['material_layers']
        total_resistance = 0.0
        
        for layer_id in material_layers:
            if layer_id in materials:
                material_data = materials[layer_id]
                thickness = material_data['thickness']
                conductivity = material_data['conductivity']
                
                if conductivity > 0:
                    total_resistance += thickness / conductivity
        
        # Total R-value with film
        r_value_with_film = total_resistance + film_resistance
        
        # Calculate U-Value as 1 / R-Value with film
        u_value = 1.0 / r_value_with_film if r_value_with_film > 0 else 0.0
        
        return u_value
        
    def _get_surface_film_resistance(self, s_type: str, boundary: str) -> float:
        """
        Determine the surface film resistance constant based on element type and boundary.
        Delegates to the common implementation in MaterialsParser if available.
        
        Args:
            s_type: Surface type (wall, floor, ceiling, roof)
            boundary: Boundary condition (outdoors, ground, etc.)
            
        Returns:
            float: Surface film resistance constant to add to R-Value
        """
        # Try to use the MaterialsParser implementation if available
        try:
            from parsers.materials_parser import MaterialsParser
            materials_parser = MaterialsParser(self.data_loader)
            return materials_parser._get_surface_film_resistance(s_type, boundary)
        except ImportError:
            # Fallback implementation if MaterialsParser is not available
            s_type = s_type.lower() if s_type else ""
            boundary = boundary.lower() if boundary else ""
            
            if s_type == "wall":
                return 0.17 if boundary == "outdoors" else 0.26
            elif s_type == "ceiling" or s_type == "roof":
                return 0.14 if boundary == "outdoors" else 0.20
            elif s_type == "floor":
                return 0.21 if boundary == "outdoors" else 0.34
            else:
                return 0.00  # Default case
    
    def get_areas_by_zone(self) -> Dict[str, Dict[str, Any]]:
        """
        Get the processed area data by zone.
        
        Returns:
            Dict[str, Dict[str, Any]]: Dictionary of area data by zone
        """
        return self.areas_by_zone
        
    def get_area_totals(self, area_id: str) -> Dict[str, float]:
        """
        Get totals for a specific area.
        
        Args:
            area_id: ID of the area
            
        Returns:
            Dict[str, float]: Dictionary with area totals
        """
        result = {
            "total_floor_area": 0.0,
            "wall_area": 0.0,
            "window_area": 0.0
        }
        
        for zone_id, zone_data in self.areas_by_zone.items():
            if zone_data.get("area_id") != area_id:
                continue
            
            # Add floor area for this zone
            result["total_floor_area"] += (
                zone_data.get("floor_area", 0.0) * zone_data.get("multiplier", 1)
            )
            
            # Process constructions
            for construction_name, construction_data in zone_data.get("constructions", {}).items():
                # Check if any element is glazing
                is_glazing = False
                for element in construction_data.get("elements", []):
                    if element.get("element_type") == "Glazing":
                        is_glazing = True
                        break
                
                # Add to appropriate area total
                if is_glazing:
                    result["window_area"] += construction_data.get("total_area", 0.0)
                elif "wall" in [e.get("element_type", "").lower() for e in construction_data.get("elements", [])]:
                    result["wall_area"] += construction_data.get("total_area", 0.0)
        
        return result
        
    def get_area_table_data(self, materials_parser: Optional[MaterialsParser] = None) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get data for area reports in table format.
        
        Args:
            materials_parser: Optional MaterialsParser instance for better element type detection
            
        Returns:
            Dict[str, List[Dict[str, Any]]]: Dictionary of area table rows by area ID
        """
        result_by_area = {}
        
        # Get cached surfaces
        surfaces = self.data_loader.get_surfaces()
        
        # Process each zone
        for zone_id, zone_data in self.areas_by_zone.items():
            area_id = zone_data.get("area_id", "unknown")
            
            # Skip zones with "core" in their area ID
            if "core" in area_id.lower():
                continue
                
            # Initialize area in results if not already
            if area_id not in result_by_area:
                result_by_area[area_id] = []
            
            # Dictionary to store zone+construction combinations
            zone_constructions = {}
            
            for construction_name, construction_data in zone_data.get("constructions", {}).items():
                # Default element type
                element_type = "Unknown"
                
                # First try to determine element type from surfaces
                matched_surface = None
                for surface_id, surface in surfaces.items():
                    if surface.get('construction_name') == construction_name:
                        matched_surface = surface
                        break
                
                # If we found a surface using this construction, use it to determine element type
                if matched_surface:
                    # Check if this is a glazing surface first
                    if matched_surface.get('is_glazing', False):
                        element_type = "Glazing"
                    elif materials_parser:
                        # Use materials parser for accurate element type detection
                        try:
                            element_type = materials_parser._get_element_type(construction_name, surfaces)
                        except Exception as e:
                            pass
                
                # If still unknown, try to infer from elements
                if element_type == "Unknown":
                    # Try to get element type from first element as a fallback
                    if construction_data.get("elements") and len(construction_data["elements"]) > 0:
                        element_type = construction_data["elements"][0].get("element_type", "Unknown")
                
                # Create a unique key for zone+construction combination 
                zone_constr_key = f"{zone_id}_{construction_name}"
                
                # Sum areas for same construction+zone
                if zone_constr_key not in zone_constructions:
                    # Get u_value from first element if available
                    u_value = 0.0
                    if construction_data.get("elements") and len(construction_data["elements"]) > 0:
                        u_value = construction_data["elements"][0].get("u_value", 0.0)
                    
                    zone_constructions[zone_constr_key] = {
                        "zone": zone_id,
                        "construction": construction_name,
                        "element_type": element_type,
                        "area": 0.0,
                        "u_value": u_value,
                        "area_u_value": 0.0,
                        "area_loss": 0.0  # Placeholder as requested
                    }
                
                # Add area and area_u_value
                constr_sum = zone_constructions[zone_constr_key]
                constr_sum["area"] += construction_data.get("total_area", 0.0)
                constr_sum["area_u_value"] += construction_data.get("total_u_value", 0.0)
            
            # Add all zone+constructions to the area's result list
            result_by_area[area_id].extend(zone_constructions.values())
                
        return result_by_area