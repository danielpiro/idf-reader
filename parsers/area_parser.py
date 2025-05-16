"""
Extracts and processes area information including floor areas and material properties.
"""
from typing import Dict, Any, List, Optional
import logging
from parsers.materials_parser import MaterialsParser
from utils.data_loader import safe_float
from parsers.eplustbl_reader import read_glazing_data_from_csv

logger = logging.getLogger(__name__)

class AreaParser:
    """
    Processes area information from IDF files, including distribution of zones in areas.
    Uses cached data from DataLoader for efficient access.
    """
    def __init__(self, data_loader, materials_parser: MaterialsParser, csv_path: Optional[str] = None):
        self.data_loader = data_loader
        try:
            self.glazing_data_from_csv = read_glazing_data_from_csv(csv_path)
            logger.info(f"Successfully loaded glazing data from CSV: {csv_path if csv_path else 'default path'}")
        except FileNotFoundError:
            logger.warning(f"Glazing CSV file not found at {csv_path if csv_path else 'default path'} or simulation_output/eplustbl.csv. Proceeding without CSV glazing data.")
            self.glazing_data_from_csv = {}
        except (ValueError, RuntimeError) as e:
            logger.error(f"Error reading or parsing glazing CSV: {e}. Proceeding without CSV glazing data.")
            self.glazing_data_from_csv = {}
        self.materials_parser = materials_parser
        self.areas_by_zone = {}
        self.processed = False

    def process_idf(self, idf) -> None:
        """
        Extract area information.

        Args:
            idf: eppy IDF object (not directly used)
        """
        if not self.data_loader:
            raise ValueError("AreaParser requires a DataLoader instance.")
        if self.processed:
            return
        try:
            if self.materials_parser and not self.materials_parser.element_data:
                self.materials_parser.process_idf(idf)
            self._process_zones()
            self._process_surfaces()
            if self.materials_parser:
                self._merge_reverse_constructions(self.materials_parser)
            self.processed = True
        except Exception as e:
            logger.error(f"Error extracting area information: {e}")
            raise

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
        
        # First pass: Process window surfaces to track them by base surface
        windows_by_base_surface = {}
        for surface_id, surface in surfaces.items():
            # Only process windows (fenestration surfaces)
            if surface.get("is_glazing", False):
                base_surface = surface.get("base_surface")
                if base_surface:
                    if base_surface not in windows_by_base_surface:
                        windows_by_base_surface[base_surface] = []
                    windows_by_base_surface[base_surface].append({
                        "window_id": surface_id,
                        "area": surface.get("area", 0.0),
                    })
                
        # Second pass: Process all surfaces
        for surface_id, surface in surfaces.items():
            zone_name = surface.get("zone_name")
            
            # Skip if zone is missing
            if not zone_name or zone_name not in self.areas_by_zone:
                continue
                
            construction_name = surface.get("construction_name")
            if not construction_name:
                continue
            
            # Get original area and adjust if this is a wall with windows
            original_area = surface.get("area", 0.0)
            if original_area <= 0.0:
                continue

            # Adjust area if this is a wall with windows (subtract window areas)
            area = original_area
            if not surface.get("is_glazing", False) and surface_id in windows_by_base_surface:
                window_areas = sum(w["area"] for w in windows_by_base_surface[surface_id])
                # Subtract window areas from the wall area
                area = max(0.0, original_area - window_areas)
              # --- Determine U-Value and Area (for glazing) ---
            u_value = 0.0
            is_glazing = surface.get("is_glazing", False) # Check if surface is marked as glazing
            glazing_area_override = None # Initialize area override for glazing

            # Check if this construction exists in the parsed glazing data
            if construction_name in self.glazing_data_from_csv:
                glazing_details_csv = self.glazing_data_from_csv[construction_name]
                u_value_from_glazing = glazing_details_csv.get('U-Value')
                area_from_glazing = glazing_details_csv.get('Area')  # Get area from CSV data

                if u_value_from_glazing is not None:
                    u_value = safe_float(u_value_from_glazing, 0.0)
                else:
                    # Glazing construction found in CSV, but U-Value is missing - fallback? Log warning?
                    logger.warning(f"U-Value missing for '{construction_name}' in glazing CSV data. Calculating.")
                    u_value = self._calculate_u_value(construction_name)
                
                # Store area from CSV if available
                if area_from_glazing is not None:
                    glazing_area_override = safe_float(area_from_glazing, 0.0)
                
                # Ensure is_glazing flag is consistent
                is_glazing = True # If it's in glazing_data_from_csv, treat as glazing
            else:                # Not found in glazing data, assume opaque
                # First check if we can get the U-value from materials_parser for consistent values
                if self.materials_parser and hasattr(self.materials_parser, 'get_constructions_u_values'):
                    u_values_dict = self.materials_parser.get_constructions_u_values()
                    if construction_name in u_values_dict:
                        u_value = u_values_dict[construction_name]
                    else:
                        # Fallback to calculation if construction not found in materials parser
                        u_value = self._calculate_u_value(construction_name)
                else:
                    # Fallback to calculation if materials_parser not available
                    u_value = self._calculate_u_value(construction_name)
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
            # else: element_type_str remains the capitalized surface_type for non-glazing            # Add element data and update totals
              # If this is glazing and we have area from CSV, use that instead of the IDF area
            final_area = area  # Default to the adjusted area from IDF
            if is_glazing and glazing_area_override is not None:
                final_area = glazing_area_override
                
            element_data = {
                "zone": zone_name,
                "surface_name": surface_id,
                "element_type": element_type_str, # Use the determined type
                "area": final_area,  # Use area from CSV for glazing if available, otherwise use adjusted area
                "original_area": original_area,  # Store original area for reference                "u_value": u_value, # Use the determined u_value
                "area_u_value": final_area * u_value  # Update using final_area
            }
            
            constr_group = self.areas_by_zone[zone_name]["constructions"][construction_name]
            constr_group["elements"].append(element_data)
            constr_group["total_area"] += final_area  # Use final_area which might be from CSV for glazing
            constr_group["total_u_value"] += final_area * u_value # Use determined u_value with final_area

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
        logger.debug(f"Calculating U-Value for construction: '{construction_name}'")
        constructions_opaque = self.data_loader.get_constructions()
        constructions_glazing = self.data_loader.get_constructions_glazing()
        all_constructions = {**constructions_opaque, **constructions_glazing}
        materials = self.data_loader.get_materials()
        surfaces = self.data_loader.get_surfaces()
        if construction_name not in all_constructions:
            logger.warning(f"Construction '{construction_name}' not found. Returning U=0.")
            return 0.0
        construction_data = all_constructions[construction_name]
        material_layers = construction_data.get('material_layers', [])
        simple_glazing_found = False
        for layer_id in material_layers:
            if layer_id in materials:
                material_data = materials[layer_id]
                mat_type = material_data.get('type')
                if mat_type == 'WindowMaterial:SimpleGlazingSystem':
                    simple_glazing_found = True
                    u_factor = material_data.get('u_factor')
                    if u_factor is not None:
                        u_value_float = safe_float(u_factor, -1.0)
                        if u_value_float != -1.0:
                            return u_value_float
        film_resistance = 0.0
        try:
            element_type = "Wall"
            is_window = any(s.get('is_glazing', False) for s in surfaces.values() if s.get('construction_name') == construction_name)
            if is_window:
                element_type = "Window"
            if hasattr(MaterialsParser, '_get_surface_film_resistance') and callable(getattr(MaterialsParser, '_get_surface_film_resistance')):
                film_resistance = MaterialsParser._get_surface_film_resistance(self, element_type)
        except Exception as e:
            logger.warning(f"Error calculating film resistance for {construction_name}: {e}.")
            film_resistance = 0.0
        total_resistance = 0.0
        for layer_id in material_layers:
            if layer_id in materials:
                material_data = materials[layer_id]
                thickness = material_data.get('thickness')
                conductivity = material_data.get('conductivity')
                resistance = material_data.get('thermal_resistance')
                layer_r = 0.0
                thickness_f = safe_float(thickness, -1.0)
                conductivity_f = safe_float(conductivity, -1.0)
                resistance_f = safe_float(resistance, -1.0)
                if thickness_f != -1.0 and conductivity_f > 0:
                    layer_r = thickness_f / conductivity_f
                elif resistance_f != -1.0:
                    layer_r = resistance_f
                total_resistance += layer_r
        r_value_with_film = total_resistance + film_resistance
        u_value = 1.0 / r_value_with_film if r_value_with_film > 0 else 0.0
        return u_value

    def _merge_reverse_constructions(self, materials_parser: MaterialsParser) -> None:
        """
        Merges constructions with '_rev' or '_reverse' suffixes into their base counterparts
        ONLY IF they share the exact same set of element types determined by MaterialsParser.
        Sums total_area and total_u_value, combines elements, and removes the reverse entry.
        
        Important: Glazing constructions are never merged, even if they have the same element types.
        """
        surfaces = self.data_loader.get_surfaces()
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
                if base_name and base_name in constructions and base_name not in to_remove:
                    reverse_name = name
                    is_base_glazing = base_name in self.glazing_data_from_csv
                    is_reverse_glazing = reverse_name in self.glazing_data_from_csv
                    if is_base_glazing or is_reverse_glazing:
                        continue
                    base_elements = constructions[base_name].get("elements", [])
                    reverse_elements = constructions[reverse_name].get("elements", [])
                    has_base_glazing_element = any(
                        element.get("element_type") in ["External Glazing", "Internal Glazing"] 
                        for element in base_elements
                    )
                    has_reverse_glazing_element = any(
                        element.get("element_type") in ["External Glazing", "Internal Glazing"] 
                        for element in reverse_elements
                    )
                    if has_base_glazing_element or has_reverse_glazing_element:
                        continue
                    try:
                        base_types_list, base_dont_use = materials_parser._get_element_type(base_name, surfaces)
                        reverse_types_list, reverse_dont_use = materials_parser._get_element_type(reverse_name, surfaces)
                        base_types_set = set(base_types_list)
                        reverse_types_set = set(reverse_types_list)
                        if base_types_set and base_types_set == reverse_types_set:
                            base_constr = constructions[base_name]
                            reverse_constr = constructions[reverse_name]
                            base_constr["total_area"] += reverse_constr.get("total_area", 0.0)
                            base_constr["total_u_value"] += reverse_constr.get("total_u_value", 0.0)
                            base_constr["elements"].extend(reverse_constr.get("elements", []))
                            to_remove.append(reverse_name)
                    except Exception as e:
                        logger.warning(f"Error determining element types during merge check for '{base_name}'/'{reverse_name}': {e}.")
            for key in to_remove:
                del constructions[key]

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
                is_glazing = any(element.get("element_type") == "Glazing" for element in construction_data.get("elements", []))
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
            logger.error("MaterialsParser instance is required for get_area_table_data.")
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
                    logger.warning(f"Error getting element type for '{construction_name}' from MaterialsParser: {e}.")
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
                # IMPORTANT: No longer cleaning glazing construction names to preserve uniqueness
                # and ensure proper matching with CSV data values
                # is_glazing_type_present = "Glazing" in determined_element_types
                # if is_glazing_type_present:
                #     parts = construction_name.split(' - ')
                #     if len(parts) > 1 and parts[-1].strip().isdigit():
                #         cleaned_construction_name = ' - '.join(parts[:-1]).strip()
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
                    element_specific_type = element.get("element_type", "Unknown")
                    if element_specific_type in ["External Glazing", "Internal Glazing"]:
                        display_element_type = element_specific_type
                    else:
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

        Location types determined by comparing max values in two groups:
        Group 1: ground floor, external floor, separation floor, intermediate floor
        Group 2: roof, intermediate ceiling, separation ceiling

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

            # Sums for determining location - GROUP 1 (floors)
            sum_ground_floor = 0.0
            sum_external_floor = 0.0
            sum_separation_floor = 0.0
            sum_intermediate_floor = 0.0
            
            # Sums for determining location - GROUP 2 (ceilings)
            sum_roof = 0.0
            sum_intermediate_ceiling = 0.0
            sum_separation_ceiling = 0.0

            for row in rows:
                element_type = row.get('element_type', '').lower()
                area = row.get('area', 0.0)
                area_loss = row.get('area_loss', 0.0) # area_loss = area * u_value

                # Check element type for classification
                is_external_roof = False
                is_separation = False

                # Define keywords (case-insensitive) for element types
                external_keywords = ["external", "outside"]
                ground_keywords = ["ground", "slab on grade", "slab-on-grade"]
                roof_keywords = ["roof"]
                separation_keywords = ["separation"] 
                floor_keywords = ["floor"]
                ceiling_keywords = ["ceiling"]
                intermediate_keywords = ["intermediate"]

                # Check for external/roof elements for h-value calculation
                if any(keyword in element_type for keyword in external_keywords) or \
                   any(keyword in element_type for keyword in roof_keywords):
                    is_external_roof = True

                # Check for separation elements for h-value calculation
                if any(keyword in element_type for keyword in separation_keywords):
                    if not is_external_roof:  # Avoid double counting
                        is_separation = True

                # Accumulate sums for h-value calculation
                if is_external_roof:
                    external_roof_loss_sum += area_loss
                elif is_separation:
                    separation_loss_sum += area_loss
                
                # GROUP 1 - Floor type classification
                if any(keyword in element_type for keyword in floor_keywords):
                    # Check for ground floor
                    if any(keyword in element_type for keyword in ground_keywords):
                        sum_ground_floor += area
                    # Check for external floor
                    elif any(keyword in element_type for keyword in external_keywords):
                        sum_external_floor += area
                    # Check for separation floor
                    elif any(keyword in element_type for keyword in separation_keywords):
                        sum_separation_floor += area
                    # If none of the above, assume intermediate floor
                    else:
                        sum_intermediate_floor += area

                # GROUP 2 - Ceiling type classification
                elif any(keyword in element_type for keyword in ceiling_keywords) or \
                     any(keyword in element_type for keyword in roof_keywords):
                    # Check for roof
                    if any(keyword in element_type for keyword in roof_keywords):
                        sum_roof += area
                    # Check for separation ceiling
                    elif any(keyword in element_type for keyword in separation_keywords):
                        sum_separation_ceiling += area
                    # If none of the above, assume intermediate ceiling
                    else:
                        sum_intermediate_ceiling += area

            # Calculate H-Value
            h_value = (external_roof_loss_sum + 0.5 * separation_loss_sum) / total_floor_area if total_floor_area > 0 else 0.0

            # Find the maximum value in each group
            group1_values = {
                "ground_floor": sum_ground_floor,
                "external_floor": sum_external_floor,
                "separation_floor": sum_separation_floor,
                "intermediate_floor": sum_intermediate_floor
            }
            
            group2_values = {
                "roof": sum_roof,
                "intermediate_ceiling": sum_intermediate_ceiling,
                "separation_ceiling": sum_separation_ceiling
            }
            
            # Find max element in each group
            max_group1 = max(group1_values.items(), key=lambda x: x[1]) if group1_values else ("unknown", 0)
            max_group2 = max(group2_values.items(), key=lambda x: x[1]) if group2_values else ("unknown", 0)
            
            # Get the names of max elements
            max_floor_type = max_group1[0]
            max_ceiling_type = max_group2[0]
            
            # Determine location based on the max values from each group
            location = "Unknown"  # Default value
            
            # Logic based on max floor and ceiling types
            if max_floor_type == "ground_floor":
                if max_ceiling_type == "intermediate_ceiling":
                    location = "Ground Floor"
                elif max_ceiling_type == "roof":
                    location = "Ground Floor Below Open Space"
                elif max_ceiling_type == "separation_ceiling":
                    location = "Ground Floor Below Unconditioned"
            elif max_floor_type == "external_floor":
                if max_ceiling_type == "roof":
                    location = "External Below Open Space"
                elif max_ceiling_type == "intermediate_ceiling":
                    location = "External Floor"
                elif max_ceiling_type == "separation_ceiling":
                    location = "External Floor Below Unconditioned"
            elif max_floor_type == "separation_floor":
                if max_ceiling_type == "roof":
                    location = "Separation Floor Below Open Space"
                elif max_ceiling_type == "intermediate_ceiling":
                    location = "Separation Floor"
                elif max_ceiling_type == "separation_ceiling":
                    location = "Separation Floor Below Unconditioned"
            elif max_floor_type == "intermediate_floor":
                if max_ceiling_type == "roof":
                    location = "Intermediate Floor Below Open Space"
                elif max_ceiling_type == "intermediate_ceiling":
                    location = "Intermediate Floor"
                elif max_ceiling_type == "separation_ceiling":
                    location = "Intermediate Floor Below Unconditioned"

            h_values_by_area.append({
                'area_id': area_id,
                'location': location,
                'h_value': h_value,
                'total_floor_area': total_floor_area
            })

        return h_values_by_area