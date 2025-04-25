"""
Extracts and processes area information including floor areas and material properties.
"""
from typing import Dict, Any, List, Optional, Tuple
import logging
from parsers.materials_parser import MaterialsParser  # Import MaterialsParser for element_type function
from utils.data_loader import safe_float # Import safe_float

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
        Calculate U-Value for a construction.
        Retrieves direct U-Factor for simple glazing systems, otherwise calculates
        based on layer resistance (1/R-value with film). Includes detailed debugging.

        Args:
            construction_name: Name of the construction

        Returns:
            float: U-Value
        """
        logger.debug(f"--- Calculating U-Value for construction: '{construction_name}' ---")
        # Get cached data - MERGE both construction caches
        constructions_opaque = self.data_loader.get_constructions()
        constructions_glazing = self.data_loader.get_constructions_glazing()
        all_constructions = {**constructions_opaque, **constructions_glazing} # Merge dicts

        materials = self.data_loader.get_materials() # Should contain all material types
        surfaces = self.data_loader.get_surfaces()

        # Check merged dictionary
        if construction_name not in all_constructions:
            logger.warning(f"Construction '{construction_name}' not found in combined cached construction data. Returning U=0.")
            return 0.0

        construction_data = all_constructions[construction_name] # Use merged dict
        material_layers = construction_data.get('material_layers', [])
        logger.debug(f"  Material layers: {material_layers}")

        # --- Check for Simple Glazing System ---
        simple_glazing_found = False
        for layer_id in material_layers:
            logger.debug(f"  Checking layer: '{layer_id}'")
            if layer_id in materials:
                material_data = materials[layer_id]
                mat_type = material_data.get('type')
                # Log the relevant parts of material_data for clarity
                log_mat_data = {k: v for k, v in material_data.items() if k in ['id', 'name', 'type', 'u_factor', 'thickness', 'conductivity', 'thermal_resistance']}
                logger.debug(f"    Material data (relevant): {log_mat_data}")
                logger.debug(f"    Material type: '{mat_type}'")

                # Adjust 'WindowMaterial:SimpleGlazingSystem' if the actual type name differs
                expected_simple_glazing_type = 'WindowMaterial:SimpleGlazingSystem'
                if mat_type == expected_simple_glazing_type:
                    logger.debug(f"    MATCH! Found '{expected_simple_glazing_type}'. Attempting to use direct U-Factor.")
                    simple_glazing_found = True
                    # Retrieve the U-Factor directly. Adjust key 'u_factor' if needed.
                    u_factor = material_data.get('u_factor') # Key confirmed from DataLoader cache logic
                    logger.debug(f"    Retrieved 'u_factor' from material data: {u_factor} (type: {type(u_factor)})")
                    if u_factor is not None:
                        try:
                            # Use safe_float for robust conversion
                            u_value_float = safe_float(u_factor, -1.0) # Use -1 default to indicate conversion failure vs actual 0
                            if u_value_float != -1.0:
                                logger.debug(f"    Successfully converted U-Factor. Returning direct U-Value: {u_value_float}")
                                return u_value_float
                            else:
                                logger.error(f"    safe_float conversion failed for U-Factor '{u_factor}'. Falling back.")
                        except Exception as e: # Catch any unexpected error during conversion
                             logger.error(f"    Error converting U-Factor '{u_factor}' to float for material '{layer_id}': {e}. Falling back.")
                    else:
                        logger.warning(f"    Simple glazing material '{layer_id}' has 'u_factor' key but value is None. Falling back.")
                    # If U-factor is None or conversion fails, fall through to resistance calculation
                    break # Stop checking layers if simple glazing type found but no valid U-factor obtained

            else:
                 logger.warning(f"  Layer '{layer_id}' not found in cached materials.")

        # --- Fallback: Calculate U-Value based on layer resistance ---
        if not simple_glazing_found:
             logger.debug(f"  No simple glazing found. Falling back to resistance calculation for '{construction_name}'.")
        else: # simple_glazing_found is True, but we fell through
             logger.debug(f"  Simple glazing found but failed to get valid U-factor. Falling back to resistance calculation for '{construction_name}'.")

        # Calculate film resistance using MaterialsParser logic
        film_resistance = 0.0 # Initialize
        try:
            element_type = "Wall" # Default assumption
            is_window = any(s.get('is_glazing', False) for s_id, s in surfaces.items() if s.get('construction_name') == construction_name)
            if is_window:
                element_type = "Window"
            logger.debug(f"    Determined element type for film resistance: '{element_type}'")

            # Ensure MaterialsParser._get_surface_film_resistance exists and is callable
            if hasattr(MaterialsParser, '_get_surface_film_resistance') and callable(getattr(MaterialsParser, '_get_surface_film_resistance')):
                 film_resistance = MaterialsParser._get_surface_film_resistance(self, element_type) # Assuming static call works or is adapted
                 logger.debug(f"    Calculated film resistance: {film_resistance}")
            else:
                 logger.warning(f"    MaterialsParser._get_surface_film_resistance not found or not callable. Using film_resistance=0.")

        except Exception as e:
             logger.warning(f"    Error calculating film resistance for {construction_name}: {e}. Using default 0.")
             film_resistance = 0.0

        # Calculate material thermal resistance
        total_resistance = 0.0
        logger.debug(f"    Calculating total material resistance...")
        for layer_id in material_layers:
            if layer_id in materials:
                material_data = materials[layer_id]
                # Log relevant properties for resistance calculation
                thickness = material_data.get('thickness')
                conductivity = material_data.get('conductivity')
                resistance = material_data.get('thermal_resistance') # Direct R-value
                logger.debug(f"      Layer '{layer_id}': Thickness={thickness}, Conductivity={conductivity}, Resistance={resistance}")

                layer_r = 0.0
                # Use safe_float for robustness
                thickness_f = safe_float(thickness, -1.0)
                conductivity_f = safe_float(conductivity, -1.0)
                resistance_f = safe_float(resistance, -1.0)

                if thickness_f != -1.0 and conductivity_f > 0: # Check conductivity > 0 strictly
                    layer_r = thickness_f / conductivity_f
                    logger.debug(f"        R = Thickness / Conductivity = {thickness_f} / {conductivity_f} = {layer_r}")
                elif resistance_f != -1.0: # Check if direct resistance is valid
                     layer_r = resistance_f
                     logger.debug(f"        R = {layer_r} (from direct thermal_resistance)")
                else:
                     logger.warning(f"        Layer '{layer_id}': No valid thickness/conductivity or resistance found. R=0 for this layer.")

                total_resistance += layer_r
            # else: logger already warned above if layer_id not in materials

        logger.debug(f"    Total material resistance (sum of layer R): {total_resistance}")

        # Total R-value with film
        r_value_with_film = total_resistance + film_resistance
        logger.debug(f"    Total R-value (material + film): {total_resistance} + {film_resistance} = {r_value_with_film}")

        # Calculate U-Value as 1 / R-Value with film
        u_value = 0.0 # Default
        if r_value_with_film > 0:
            u_value = 1.0 / r_value_with_film
            logger.debug(f"  Calculated fallback U-Value for '{construction_name}': 1.0 / {r_value_with_film} = {u_value}")
        else:
             logger.warning(f"  Resulting U-Value is 0 for '{construction_name}' because total R-value (material + film) is <= 0.")

        return u_value
    
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
        Get data for area reports in table format, aggregating glazing constructions.

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

            # Dictionary to store aggregated zone+construction combinations
            zone_constructions_aggregated = {}

            for construction_name, construction_data in zone_data.get("constructions", {}).items():
                # Determine element type and if it's glazing
                element_type = "Unknown"
                is_glazing_construction = False

                # Prioritize checking surface properties if available
                # Find a surface in *this zone* that uses this construction
                matched_surface = next((s for s_id, s in surfaces.items()
                                        if s.get('construction_name') == construction_name and s.get('zone_name') == zone_id), None)

                if matched_surface:
                    if matched_surface.get('is_glazing', False):
                        element_type = "Glazing"
                        is_glazing_construction = True
                    elif materials_parser:
                        try:
                            # Pass self if needed by the method signature in MaterialsParser
                            element_type = materials_parser._get_element_type(construction_name, surfaces)
                        except Exception as e:
                            logger.warning(f"Could not determine element type via MaterialsParser for {construction_name}: {e}")
                            # Fallback below if still Unknown
                    else: # No materials_parser, use surface_type from matched surface
                         element_type = matched_surface.get("surface_type", "Unknown").capitalize()

                # Fallback: Infer from first element if type is still Unknown
                if element_type == "Unknown" and construction_data.get("elements"):
                    first_element = construction_data["elements"][0]
                    element_type = first_element.get("element_type", "Unknown")
                    if element_type == "Glazing":
                        is_glazing_construction = True

                # --- Modifications for Glazing Aggregation and Values ---
                cleaned_construction_name = construction_name
                display_element_type = element_type

                if is_glazing_construction:
                    display_element_type = "Outside Glazing"  # Set display type for report
                    # Clean the name: remove trailing " - " and digits
                    parts = construction_name.split(' - ')
                    if len(parts) > 1 and parts[-1].strip().isdigit():
                        cleaned_construction_name = ' - '.join(parts[:-1]).strip()
                    # Example: "6+6+6 - 1001" -> "6+6+6"

                # Create a unique key for zone + cleaned_construction_name + display_element_type combination
                zone_constr_key = f"{zone_id}_{cleaned_construction_name}_{display_element_type}"

                # Aggregate data based on the key
                if zone_constr_key not in zone_constructions_aggregated:
                    # Get u_value from first element (should be consistent for the construction)
                    u_value = 0.0
                    if construction_data.get("elements"):
                        u_value = construction_data["elements"][0].get("u_value", 0.0)

                    zone_constructions_aggregated[zone_constr_key] = {
                        "zone": zone_id,
                        "construction": cleaned_construction_name,  # Use cleaned name
                        "element_type": display_element_type,  # Use adjusted display type
                        "area": 0.0,
                        "u_value": u_value,  # U-value per construction
                        "area_u_value": 0.0,  # Sum of (element area * element u_value)
                        "area_loss": 0.0  # Initialize area loss
                    }

                # Add area and area_u_value to the aggregated entry
                constr_agg = zone_constructions_aggregated[zone_constr_key]
                current_total_area = construction_data.get("total_area", 0.0)
                # total_u_value in construction_data is already sum(area*u_value) for that specific original construction
                current_total_area_u_value = construction_data.get("total_u_value", 0.0)

                constr_agg["area"] += current_total_area
                constr_agg["area_u_value"] += current_total_area_u_value

                # Calculate area_loss = aggregated sum(area * u_value)
                # This matches the user's example where area_loss = area * u_value
                constr_agg["area_loss"] = constr_agg["area_u_value"]

            # Add all aggregated zone+constructions to the area's result list
            result_by_area[area_id].extend(zone_constructions_aggregated.values())

        return result_by_area