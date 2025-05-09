"""
Extracts and processes area information including floor areas and material properties.
"""
from typing import Dict, Any, List, Optional, Tuple
import logging
from parsers.materials_parser import MaterialsParser  # Import MaterialsParser for element_type function
from utils.data_loader import safe_float # Import safe_float

logger = logging.getLogger(__name__)
# --- Explicitly set logging level for this module ---
# logger.setLevel(logging.DEBUG) # Keep or remove as needed
# ---

class AreaParser:
    """
    Processes area information from IDF files, including distribution of zones in areas.
    Uses cached data from DataLoader for efficient access.
    """
    def __init__(self, data_loader, parsed_glazing_data: Dict[str, Dict[str, Any]], materials_parser: MaterialsParser): # Added materials_parser
        self.data_loader = data_loader
        self.parsed_glazing_data = parsed_glazing_data
        self.materials_parser = materials_parser # Store materials parser instance
        self.areas_by_zone = {}
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
            
        try:            # Make sure the materials parser has processed the data first
            # since we need its U-values for consistency
            if self.materials_parser:
                logger.info(f"Materials parser available with {len(self.materials_parser.constructions)} constructions")
                if not self.materials_parser.element_data:
                    logger.debug("Processing materials data in MaterialsParser first")
                    self.materials_parser.process_idf(idf)
                    logger.info(f"After processing, materials parser has {len(self.materials_parser.constructions)} constructions")
            else:
                logger.warning("No materials parser available in AreaParser")
            
            # Process zones to initialize data structure
            self._process_zones()
            
            # Process surfaces to extract construction information
            self._process_surfaces()

            # --- Conditional Merge ---
            if not self.materials_parser:
                 logger.error("MaterialsParser instance not available in AreaParser for merging.")
            else:
                 # Pass the stored materials_parser instance
                 self._merge_reverse_constructions(self.materials_parser)
            # --- End Conditional Merge ---

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

            # --- Determine U-Value ---
            u_value = 0.0
            is_glazing = surface.get("is_glazing", False) # Check if surface is marked as glazing

            # Check if this construction exists in the parsed glazing data
            if construction_name in self.parsed_glazing_data:
                glazing_details = self.parsed_glazing_data[construction_name].get('system_details', {})
                u_value_from_glazing = glazing_details.get('U-Value')

                if u_value_from_glazing is not None:
                    u_value = safe_float(u_value_from_glazing, 0.0)
                    # logger.debug(f"Using U-Value from GlazingParser for '{construction_name}': {u_value}")
                else:
                    # Glazing construction found, but U-Value is missing in parsed data - fallback? Log warning?
                    logger.warning(f"Glazing construction '{construction_name}' found in parsed data, but U-Value is missing. Falling back to calculation.")
                    # Decide if fallback calculation is appropriate here or just use 0.0
                    u_value = self._calculate_u_value(construction_name) # Or set u_value = 0.0                # Ensure is_glazing flag is consistent
                is_glazing = True # If it's in parsed_glazing_data, treat as glazing
            else:                # Not found in glazing data, assume opaque
                # First check if we can get the U-value from materials_parser for consistent values
                if self.materials_parser and hasattr(self.materials_parser, 'get_constructions_u_values'):
                    u_values_dict = self.materials_parser.get_constructions_u_values()
                    # Enhanced logging for debugging
                    if "ExtWall Pumice" in construction_name:
                        logger.info(f"Found ExtWall Pumice construction: '{construction_name}'")
                        logger.info(f"Is it in u_values_dict? {construction_name in u_values_dict}")
                        if construction_name in u_values_dict:
                            logger.info(f"U-value from dict: {u_values_dict[construction_name]}")
                    
                    if construction_name in u_values_dict:
                        u_value = u_values_dict[construction_name]
                        logger.debug(f"Using U-Value from MaterialsParser for '{construction_name}': {u_value}")
                    else:
                        # Fallback to calculation if construction not found in materials parser
                        u_value = self._calculate_u_value(construction_name)
                        logger.debug(f"Falling back to calculated U-Value for '{construction_name}': {u_value}")
                else:
                    # Fallback to calculation if materials_parser not available
                    u_value = self._calculate_u_value(construction_name)
                    logger.debug(f"Materials parser not available, using calculated U-Value for '{construction_name}': {u_value}")
                # logger.debug(f"Calculating U-Value for opaque construction '{construction_name}': {u_value}")
            # --- End Determine U-Value ---


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
            
            # Determine element type, specifically for glazing
            element_type_str = surface_type.capitalize()
            # Check if the surface type indicates it's a fenestration surface
            if surface_type.lower() in ['window', 'glassdoor', 'fenestrationsurface:detailed']: # Add other relevant types if needed
                # Determine Internal vs External Glazing based on base surface OBC
                is_external_glazing = False
                base_surface_name = surface.get("base_surface")
                if base_surface_name:
                    base_surface_data = surfaces.get(base_surface_name)
                    if base_surface_data:
                        obc = base_surface_data.get("boundary_condition")
                        if obc and obc.lower() == "outdoors":
                            is_external_glazing = True
                element_type_str = "External Glazing" if is_external_glazing else "Internal Glazing"
            # else: element_type_str remains the capitalized surface_type for non-glazing

            # Add element data and update totals
            element_data = {
                "zone": zone_name,
                "surface_name": surface_id,
                "element_type": element_type_str, # Use the determined type
                "area": area,
                "u_value": u_value, # Use the determined u_value
                "area_u_value": area * u_value
            }

            constr_group = self.areas_by_zone[zone_name]["constructions"][construction_name]
            constr_group["elements"].append(element_data)
            constr_group["total_area"] += area
            constr_group["total_u_value"] += area * u_value # Use determined u_value here too

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
        Calculate U-Value for a construction (NOW PRIMARILY FOR OPAQUE).
        Retrieves direct U-Factor for simple glazing systems, otherwise calculates
        based on layer resistance (1/R-value with film). Includes detailed debugging.

        Args:
            construction_name: Name of the construction

        Returns:
            float: U-Value
        """
        # NOTE: This function should ideally only be called for opaque constructions now.
        # The simple glazing check might be redundant if AreaParser relies on GlazingParser data.
        # Consider simplifying or removing glazing-specific logic here if it's fully handled above.

        logger.debug(f"--- Calculating U-Value (Fallback/Opaque) for construction: '{construction_name}' ---")
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
                                # logger.info(f"    RETURNING Simple Glazing U-Value for '{construction_name}': {u_value_float}") # REMOVED INFO LOG
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

    def _merge_reverse_constructions(self, materials_parser: MaterialsParser) -> None:
        """
        Merges constructions with '_rev' or '_reverse' suffixes into their base counterparts
        ONLY IF they share the exact same set of element types determined by MaterialsParser.
        Sums total_area and total_u_value, combines elements, and removes the reverse entry.
        """
        logger.debug("--- Starting conditional merge of reverse constructions ---")
        surfaces = self.data_loader.get_surfaces() # Needed for _get_element_type

        for zone_id, zone_data in self.areas_by_zone.items():
            constructions = zone_data.get("constructions", {})
            if not constructions:
                continue

            construction_names = list(constructions.keys())
            to_remove = []

            for name in construction_names:
                if name in to_remove:
                    continue

                base_name = None
                if name.endswith("_rev"):
                    base_name = name[:-4]
                elif name.endswith("_reverse"):
                    base_name = name[:-8]

                # Check if potential pair exists and base is not already marked for removal
                if base_name and base_name in constructions and base_name not in to_remove:
                    reverse_name = name

                    # Get element types for both base and reverse constructions
                    try:
                        base_types_list, base_dont_use = materials_parser._get_element_type(base_name, surfaces)
                        reverse_types_list, reverse_dont_use = materials_parser._get_element_type(reverse_name, surfaces)

                        # Convert to sets for comparison
                        base_types_set = set(base_types_list)
                        reverse_types_set = set(reverse_types_list)

                        # --- Conditional Merge Logic ---
                        # Merge only if types are identical AND not empty
                        if base_types_set and base_types_set == reverse_types_set:
                            logger.debug(f"  Merging '{reverse_name}' into '{base_name}' for zone '{zone_id}' (Types match: {base_types_set})")

                            base_constr = constructions[base_name]
                            reverse_constr = constructions[reverse_name]

                            # Sum areas and area*u_value sums (total_u_value is needed internally for weighted U-value calc)
                            base_constr["total_area"] += reverse_constr.get("total_area", 0.0)
                            base_constr["total_u_value"] += reverse_constr.get("total_u_value", 0.0)
                            base_constr["elements"].extend(reverse_constr.get("elements", []))
                            to_remove.append(reverse_name)
                            logger.debug(f"    Merged Area: {base_constr['total_area']}, Merged Internal Area*U: {base_constr['total_u_value']}")
                        else:
                             logger.debug(f"  Skipping merge for '{reverse_name}' and '{base_name}' in zone '{zone_id}'. Element types differ or empty (Base: {base_types_set}, Reverse: {reverse_types_set})")
                        # --- End Conditional Merge ---

                    except Exception as e:
                        logger.warning(f"  Error determining element types during merge check for '{base_name}'/'{reverse_name}': {e}. Skipping merge.")

            # Remove the merged reverse constructions
            if to_remove:
                logger.debug(f"  Removing merged constructions for zone '{zone_id}': {to_remove}")
                for key in to_remove:
                    del constructions[key]

        logger.debug("--- Finished conditional merging reverse constructions ---")


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
        Get data for area reports in table format, aggregating by zone, construction,
        and element type determined by MaterialsParser. Removes area_u_value from final output.
        Glazing constructions have their names cleaned.

        Args:
            materials_parser: Optional MaterialsParser instance (uses self.materials_parser if available).

        Returns:
            Dict[str, List[Dict[str, Any]]]: Dictionary of area table rows by area ID.
        """
        result_by_area = {}

        # Use the instance stored during __init__
        parser_to_use = self.materials_parser
        if not parser_to_use:
             logger.error("MaterialsParser instance is required for get_area_table_data (should be provided during AreaParser init).")
             return result_by_area

        surfaces = self.data_loader.get_surfaces()

        for zone_id, zone_data in self.areas_by_zone.items():
            area_id = zone_data.get("area_id", "unknown")

            if "core" in area_id.lower():
                continue
            if area_id not in result_by_area:
                result_by_area[area_id] = []

            zone_constructions_aggregated = {}

            for construction_name, construction_data in zone_data.get("constructions", {}).items():
                try:
                    determined_element_types, dont_use = parser_to_use._get_element_type(construction_name, surfaces)
                except Exception as e:
                    logger.warning(f"Error getting element type for '{construction_name}' from MaterialsParser: {e}. Skipping construction.")
                    continue
                if dont_use or not determined_element_types:
                    continue

                total_area = construction_data.get("total_area", 0.0)
                total_area_u_value = construction_data.get("total_u_value", 0.0) # Still needed for weighted U-value

                if total_area <= 0.0:
                    continue

                construction_u_value = total_area_u_value / total_area # Weighted U-value

                # --- Clean construction name ---
                cleaned_construction_name = construction_name
                is_glazing_type_present = "Glazing" in determined_element_types
                if is_glazing_type_present:
                    parts = construction_name.split(' - ')
                    if len(parts) > 1 and parts[-1].strip().isdigit():
                        cleaned_construction_name = ' - '.join(parts[:-1]).strip()
                # --- End Cleaning ---

                # Get the overall types for the construction from MaterialsParser
                # determined_element_types was already fetched earlier (line 531)
                # Find the primary non-glazing type for aggregation purposes
                primary_non_glazing_type = "Unknown" # Default if only glazing or error
                for t in determined_element_types:
                    if t != "Glazing" and "Glazing" not in t: # Check for "Glazing", "External Glazing", "Internal Glazing"
                        primary_non_glazing_type = t
                        break

                # Iterate through the individual elements within the construction
                elements = construction_data.get("elements", [])
                for element in elements:
                    element_area = element.get("area", 0.0)
                    if element_area <= 0.0:
                        continue

                    # Determine the type to use for aggregation/display
                    element_specific_type = element.get("element_type", "Unknown")
                    if element_specific_type in ["External Glazing", "Internal Glazing"]:
                        # Use the specific glazing type if applicable
                        display_element_type = element_specific_type
                    else:
                        # Otherwise, use the primary non-glazing type for the construction
                        display_element_type = primary_non_glazing_type

                    # Aggregate based on zone, cleaned construction name, and the determined display_element_type
                    zone_constr_key = f"{zone_id}_{cleaned_construction_name}_{display_element_type}"

                    if zone_constr_key not in zone_constructions_aggregated:
                        zone_constructions_aggregated[zone_constr_key] = {
                            "zone": zone_id,
                            "construction": cleaned_construction_name,
                            "element_type": display_element_type, # Use the determined type for the row
                            "area": 0.0,
                            "u_value": construction_u_value, # Report the construction's weighted U-value
                            "area_loss": 0.0,
                        }

                    # Aggregate area and calculate area_loss based on the element's area
                    constr_agg = zone_constructions_aggregated[zone_constr_key]
                    constr_agg["area"] += element_area
                    # Area loss uses the element's area and the construction's weighted U-value
                    constr_agg["area_loss"] += element_area * construction_u_value

            # Final cleanup before adding to results: remove internal weighted_u_value
            final_aggregated_list = []
            for agg_data in zone_constructions_aggregated.values():
                 if "weighted_u_value" in agg_data:
                     del agg_data["weighted_u_value"] # Remove before adding to final list
                 final_aggregated_list.append(agg_data)

            result_by_area[area_id].extend(final_aggregated_list)

        return result_by_area

    def get_area_h_values(self) -> List[Dict[str, Any]]:
        """
        Calculates the H-Value for each area based on external, roof, and separation losses.
        Also determines the location type for each area based on floor and ceiling construction types.

        Location types:
        - Ground Floor: When intermediate+ground floors dominates and has ground floor constructions
        - Intermediate Floor: When intermediate+ground floors dominates without ground floor constructions
        - Over Close Space: When separation floors dominates
        - Below Open Space: When roof ceiling dominates
        - Over Open Space: When external floors dominates

        H-Value = (sum(Area*U for external/roof) + 0.5 * sum(Area*U for separation)) / TotalFloorArea

        Returns:
            List[Dict[str, Any]]: A list of dictionaries, each containing:
                'area_id': The area identifier.
                'location': The determined location type based on floor/ceiling analysis.
                'h_value': The calculated H-Value.
                'total_floor_area': The total floor area for the area.
        """
        h_values_by_area = []
        if not self.processed:
            logger.error("IDF data must be processed before calculating H-values.")
            return h_values_by_area
        if not self.materials_parser:
             logger.error("MaterialsParser instance is required for H-Value calculation.")
             return h_values_by_area

        # Get the detailed table data which includes element types and area_loss
        # Note: get_area_table_data now returns data with 'area_loss' calculated
        area_data_for_h_calc = self.get_area_table_data() # Use self.materials_parser internally

        # Calculate total floor area for each area_id first
        area_floor_totals = {}
        for zone_id, zone_data in self.areas_by_zone.items():
            area_id = zone_data.get("area_id", "unknown")
            if "core" in area_id.lower(): # Skip core areas
                 continue
            if area_id not in area_floor_totals:
                area_floor_totals[area_id] = 0.0
            area_floor_totals[area_id] += (
                zone_data.get("floor_area", 0.0) * zone_data.get("multiplier", 1)
            )

        # Group the detailed data by area_id
        from collections import defaultdict # Import here if not already at top
        grouped_data = defaultdict(list)
        for area_id, rows in area_data_for_h_calc.items():
            grouped_data[area_id].extend(rows)

        # Calculate H-Value for each area
        for area_id, rows in grouped_data.items():
            total_floor_area = area_floor_totals.get(area_id, 0.0)
            if total_floor_area <= 0:
                logger.warning(f"Skipping H-Value calculation for Area '{area_id}': Total floor area is 0 or less.")
                continue

            external_roof_loss_sum = 0.0
            separation_loss_sum = 0.0

            # Sums for determining location
            sum_external_floors = 0.0
            sum_ground_floors = 0.0
            sum_intermediate_floors = 0.0
            sum_separation_floors = 0.0
            
            sum_roofs = 0.0
            sum_intermediate_ceilings = 0.0
            sum_separation_ceilings = 0.0
            
            # Track if we have any ground floor constructions
            has_ground_floor_construction = False

            for row in rows:
                element_type = row.get('element_type', '').lower()
                area = row.get('area', 0.0)
                area_loss = row.get('area_loss', 0.0) # area_loss = area * u_value

                # Check element type for classification
                is_external_roof = False
                is_separation = False

                # Define keywords (case-insensitive)
                external_keywords = ["external", "outside", "ground"] # Include ground contact
                roof_keywords = ["roof"]
                separation_keywords = ["separation"] # User specified "separation".
                floor_keywords = ["floor"]
                ceiling_keywords = ["ceiling"]
                ground_floor_keywords = ["ground floor", "slab on grade", "slab-on-grade"]

                # Check if this is a ground floor construction
                if any(keyword in element_type for keyword in ground_floor_keywords):
                    has_ground_floor_construction = True

                # More robust check for keywords in element type string
                if any(keyword in element_type for keyword in external_keywords) or \
                   any(keyword in element_type for keyword in roof_keywords):
                    is_external_roof = True

                if any(keyword in element_type for keyword in separation_keywords):
                     # Avoid double counting if it's somehow both (e.g., "External Separation Wall")
                     if not is_external_roof:
                         is_separation = True

                # Add to sums based on classification
                if is_external_roof:
                    external_roof_loss_sum += area_loss
                    
                    # For location determination - floors and ceilings
                    if any(keyword in element_type for keyword in floor_keywords):
                        sum_external_floors += area
                    elif any(keyword in element_type for keyword in roof_keywords):
                        sum_roofs += area
                        
                elif is_separation:
                    separation_loss_sum += area_loss
                    
                    # For location determination
                    if any(keyword in element_type for keyword in floor_keywords):
                        sum_separation_floors += area
                    elif any(keyword in element_type for keyword in ceiling_keywords):
                        sum_separation_ceilings += area
                else:
                    # Intermediate floors/ceilings (not external, not separation)
                    if any(keyword in element_type for keyword in floor_keywords):
                        if any(keyword in element_type for keyword in ground_floor_keywords):
                            sum_ground_floors += area
                        else:
                            sum_intermediate_floors += area
                    elif any(keyword in element_type for keyword in ceiling_keywords):
                        sum_intermediate_ceilings += area

            # Calculate H-Value
            h_value = (external_roof_loss_sum + 0.5 * separation_loss_sum) / total_floor_area
            
            # Determine location based on the detailed mapping logic
            location = "Unknown"  # Default value
            
            # First mapping: Floor and ceiling types to detailed location
            # Ground floor cases
            if sum_ground_floors > 0:
                if sum_intermediate_ceilings > sum_roofs and sum_intermediate_ceilings > sum_separation_ceilings:
                    location = "Ground Floor"
                elif sum_roofs > sum_intermediate_ceilings and sum_roofs > sum_separation_ceilings:
                    location = "Ground Floor Below Open Space"
                elif sum_separation_ceilings > sum_intermediate_ceilings and sum_separation_ceilings > sum_roofs:
                    location = "Ground Floor Below Unconditioned"
            # External floor cases
            elif sum_external_floors > 0:
                if sum_roofs > sum_intermediate_ceilings and sum_roofs > sum_separation_ceilings:
                    location = "External Below Open Space"
                elif sum_intermediate_ceilings > sum_roofs and sum_intermediate_ceilings > sum_separation_ceilings:
                    location = "External Floor"
                elif sum_separation_ceilings > sum_intermediate_ceilings and sum_separation_ceilings > sum_roofs:
                    location = "External Floor Below Unconditioned"
            # Separation floor cases
            elif sum_separation_floors > 0:
                if sum_roofs > sum_intermediate_ceilings and sum_roofs > sum_separation_ceilings:
                    location = "Separation Floor Below Open Space"
                elif sum_intermediate_ceilings > sum_roofs and sum_intermediate_ceilings > sum_separation_ceilings:
                    location = "Separation Floor"
                elif sum_separation_ceilings > sum_intermediate_ceilings and sum_separation_ceilings > sum_roofs:
                    location = "Separation Floor Below Unconditioned"
            # Intermediate floor cases
            elif sum_intermediate_floors > 0:
                if sum_roofs > sum_intermediate_ceilings and sum_roofs > sum_separation_ceilings:
                    location = "Intermediate Floor Below Open Space"
                elif sum_intermediate_ceilings > sum_roofs and sum_intermediate_ceilings > sum_separation_ceilings:
                    location = "Intermediate Floor"
                elif sum_separation_ceilings > sum_intermediate_ceilings and sum_separation_ceilings > sum_roofs:
                    location = "Intermediate Floor Below Unconditioned"
                    
            # Add debug logging for location determination
            logger.debug(f"Area {area_id} location determination:")
            logger.debug(f"  Floor values: External={sum_external_floors}, Ground={sum_ground_floors}, Intermediate={sum_intermediate_floors}, Separation={sum_separation_floors}")
            logger.debug(f"  Ceiling values: Roof={sum_roofs}, Intermediate={sum_intermediate_ceilings}, Separation={sum_separation_ceilings}")
            logger.debug(f"  Determined detailed location: {location}")

            h_values_by_area.append({
                'area_id': area_id,
                'location': location,  # Now using the determined location instead of area_id
                'h_value': h_value,
                'total_floor_area': total_floor_area
            })

        return h_values_by_area