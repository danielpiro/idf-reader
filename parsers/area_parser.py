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
            logger.info(f"Successfully loaded glazing data from CSV: {csv_path if csv_path else 'default path used by read_glazing_data_from_csv'}.")
            if self.glazing_data_from_csv: # Log only if data is loaded
                logger.debug(f"Glazing data from CSV (first 5 items): {dict(list(self.glazing_data_from_csv.items())[:5])}")
            else:
                logger.info("No glazing data loaded from CSV (file might be empty or not found).")
        except FileNotFoundError:
            logger.warning(f"Glazing CSV file not found at the specified/default path. Proceeding without CSV glazing data.")
            self.glazing_data_from_csv = {}
        except (ValueError, RuntimeError) as e: # Catch more specific errors from read_glazing_data_from_csv
            logger.error(f"Error reading or parsing glazing CSV: {e}. Proceeding without CSV glazing data.", exc_info=True)
            self.glazing_data_from_csv = {}
        except Exception as e: # Catch any other unexpected errors during init
            logger.error(f"Unexpected error during AreaParser initialization: {e}", exc_info=True)
            self.glazing_data_from_csv = {} # Ensure it's initialized
        self.materials_parser = materials_parser
        self.areas_by_zone = {}
        self.processed = False

    def process_idf(self, idf) -> None:
        """
        Extract area information.

        Args:
            idf: eppy IDF object (not directly used but passed to materials_parser)
        """
        if not self.data_loader:
            logger.error("AreaParser.process_idf called without a DataLoader instance.")
            raise ValueError("AreaParser requires a DataLoader instance.") # Fail fast
        if self.processed:
            logger.info("Area information already processed. Skipping.")
            return
        try:
            logger.info("Starting area information extraction process.")
            if self.materials_parser and not self.materials_parser.element_data:
                logger.info("Materials data not yet processed. Processing now.")
                self.materials_parser.process_idf(idf) # This can raise its own errors
            
            self._process_zones()
            self._process_surfaces()
            
            if self.materials_parser:
                self._merge_reverse_constructions(self.materials_parser)
            
            self.processed = True
            logger.info("Successfully extracted and processed area information.")
        except ValueError as ve: # Catch specific known errors
            logger.error(f"ValueError during area information extraction: {ve}", exc_info=True)
            raise # Re-raise to indicate failure
        except KeyError as ke:
            logger.error(f"KeyError during area information extraction, possibly missing data: {ke}", exc_info=True)
            raise # Re-raise
        except Exception as e: # Catch-all for unexpected issues
            logger.error(f"Unexpected error during area information extraction: {e}", exc_info=True)
            # Depending on desired behavior, you might set self.processed to False or clean up
            raise # Re-raise to indicate failure

    def _process_zones(self) -> None:
        """
        Process zones to initialize the data structure.
        """
        try:
            zones = self.data_loader.get_zones()
            if not zones:
                logger.warning("No zones found in DataLoader. Area processing for zones will be empty.")
                return

            for zone_id, zone_data in zones.items():
                try:
                    area_id = "unknown"
                    if not zone_id: # Should not happen if keys are proper
                        logger.warning(f"Encountered a zone with no ID (data: {zone_data}). Skipping.")
                        continue

                    if ":" in zone_id:
                        parts = zone_id.split(":")
                        if len(parts) > 1:
                            if len(parts[1]) >= 2 and parts[1][:2].isdigit():
                                area_id = parts[1][:2]
                            elif parts[1]: # Use the whole part if not starting with 2 digits
                                area_id = parts[1]
                    
                    floor_area = safe_float(zone_data.get("floor_area", 0.0), 0.0)
                    multiplier = int(safe_float(zone_data.get("multiplier", 1), 1)) # Ensure multiplier is int

                    self.areas_by_zone[zone_id] = {
                        "area_id": area_id,
                        "floor_area": floor_area,
                        "multiplier": multiplier,
                        "constructions": {}
                    }
                except (TypeError, ValueError, AttributeError) as e_inner:
                    logger.error(f"Error processing individual zone '{zone_id}': {e_inner}. Skipping this zone.", exc_info=True)
                    continue # Skip to the next zone
        except Exception as e:
            logger.error(f"Critical error in _process_zones: {e}", exc_info=True)
            # This is a more significant failure, might warrant re-raising or setting a failed state

    def _process_surfaces(self) -> None:
        """
        Process surfaces to extract construction and area information.
        """
        try:
            surfaces = self.data_loader.get_surfaces()
            if not surfaces:
                logger.warning("No surfaces found in DataLoader. Area processing for surfaces will be empty.")
                return

            windows_by_base_surface = {}
            for surface_id, surface in surfaces.items():
                try:
                    if surface.get("is_glazing", False):
                        base_surface = surface.get("base_surface")
                        if base_surface:
                            if base_surface not in windows_by_base_surface:
                                windows_by_base_surface[base_surface] = []
                            windows_by_base_surface[base_surface].append({
                                "window_id": surface_id,
                                "area": safe_float(surface.get("area", 0.0), 0.0),
                            })
                except (TypeError, AttributeError) as e_win:
                    logger.warning(f"Error processing window data for surface '{surface_id}': {e_win}. Skipping window linkage.", exc_info=True)


            for surface_id, surface in surfaces.items():
                try:
                    zone_name = surface.get("zone_name")
                    if not zone_name or zone_name not in self.areas_by_zone:
                        logger.debug(f"Surface '{surface_id}' skipped: zone '{zone_name}' not found or not in areas_by_zone.")
                        continue

                    construction_name = surface.get("construction_name")
                    if not construction_name:
                        logger.debug(f"Surface '{surface_id}' in zone '{zone_name}' skipped: no construction name.")
                        continue

                    original_area = safe_float(surface.get("area", 0.0), 0.0)
                    if original_area <= 0.0:
                        logger.debug(f"Surface '{surface_id}' (Construction: {construction_name}) in zone '{zone_name}' skipped: area is {original_area}.")
                        continue
                    
                    area = original_area
                    if not surface.get("is_glazing", False) and surface_id in windows_by_base_surface:
                        try:
                            window_areas = sum(w.get("area", 0.0) for w in windows_by_base_surface.get(surface_id, []))
                            area = max(0.0, original_area - window_areas)
                        except Exception as e_sum:
                            logger.warning(f"Error calculating net area for surface '{surface_id}': {e_sum}. Using original area.", exc_info=True)
                            area = original_area


                    u_value = 0.0
                    is_glazing_from_idf = surface.get("is_glazing", False)
                    is_glazing_from_csv = False
                    glazing_area_override = None

                    surface_id_upper = surface_id.upper() # Ensure surface_id is a string
                    if not isinstance(surface_id, str):
                        logger.warning(f"Surface ID '{surface_id}' is not a string. Skipping CSV lookup for this surface.")
                        surface_id_upper = None # Prevent lookup

                    if surface_id_upper and surface_id_upper in self.glazing_data_from_csv:
                        glazing_details_csv = self.glazing_data_from_csv[surface_id_upper]
                        logger.debug(f"Found uppercased surface_id '{surface_id_upper}' (original: '{surface_id}') in glazing_data_from_csv. Data: {glazing_details_csv}")

                        csv_construction_name = glazing_details_csv.get('Construction')
                        if csv_construction_name and csv_construction_name != construction_name:
                            logger.warning(
                                f"Mismatch for surface '{surface_id}' (lookup key '{surface_id_upper}'): IDF construction '{construction_name}' vs "
                                f"CSV construction '{csv_construction_name}'. Using CSV data for U-value/Area if available."
                            )
                        
                        u_value_from_glazing = glazing_details_csv.get('U-Value')
                        area_from_glazing = glazing_details_csv.get('Area')

                        if u_value_from_glazing is not None:
                            u_value = safe_float(u_value_from_glazing, 0.0) # Default to 0.0 if conversion fails
                            logger.debug(f"Using U-Value from CSV for '{surface_id}' (lookup key '{surface_id_upper}'): {u_value}")
                        else:
                            logger.warning(f"U-Value missing for surface '{surface_id}' (lookup key '{surface_id_upper}', construction '{construction_name}') in glazing CSV data. Calculating.")
                            u_value = self._calculate_u_value(construction_name)
                        
                        if area_from_glazing is not None:
                            glazing_area_override = safe_float(area_from_glazing, 0.0)
                            logger.debug(f"Using Area from CSV for '{surface_id}' (lookup key '{surface_id_upper}'): {glazing_area_override}")
                        
                        is_glazing_from_csv = True
                    else:
                        logger.debug(f"Surface_id '{surface_id_upper}' (original: '{surface_id}', Construction: '{construction_name}') not found in glazing_data_from_csv. Will calculate U-value and use IDF area.")
                        u_value = self._calculate_u_value(construction_name) # Calculate U-value if not from CSV

                    surface_type = surface.get("surface_type", "wall")
                    is_glazing = is_glazing_from_csv or is_glazing_from_idf

                    if construction_name not in self.areas_by_zone[zone_name]["constructions"]:
                        self.areas_by_zone[zone_name]["constructions"][construction_name] = {
                            "elements": [], "total_area": 0.0, "total_u_value": 0.0
                        }
                    
                    element_type_str = surface_type.capitalize()
                    if is_glazing:
                        is_external_boundary = False
                        base_surface_name = surface.get("base_surface")
                        if base_surface_name and base_surface_name in surfaces: # Check if base_surface_name exists
                            base_surface_data = surfaces.get(base_surface_name)
                            if base_surface_data:
                                obc = base_surface_data.get("boundary_condition")
                                if obc and isinstance(obc, str) and obc.lower() == "outdoors":
                                    is_external_boundary = True
                        element_type_str = "External Glazing" if is_external_boundary else "Internal Glazing"
                    
                    final_area = area
                    if is_glazing and glazing_area_override is not None and glazing_area_override > 0: # Use override if valid
                        final_area = glazing_area_override
                        logger.debug(f"For glazing surface '{surface_id}', final_area set to CSV override: {final_area}")
                    elif is_glazing:
                         logger.debug(f"For glazing surface '{surface_id}', no CSV area override or override is zero. Using IDF derived area: {final_area} (original: {original_area})")
                    
                    if final_area <= 0.0 and not is_glazing_from_csv: # Don't add zero area elements unless they are explicitly from CSV with area 0
                        logger.debug(f"Skipping element for surface '{surface_id}' as final_area is {final_area} and not explicitly from CSV.")
                        continue

                    element_data = {
                        "zone": zone_name, "surface_name": surface_id, "element_type": element_type_str,
                        "area": final_area, "original_area": original_area, "u_value": u_value,
                        "area_u_value": final_area * u_value
                    }
                    logger.debug(f"Processed element: {element_data}")

                    constr_group = self.areas_by_zone[zone_name]["constructions"][construction_name]
                    constr_group["elements"].append(element_data)
                    constr_group["total_area"] += final_area
                    constr_group["total_u_value"] += final_area * u_value
                
                except (TypeError, ValueError, AttributeError, KeyError) as e_surf:
                    logger.error(f"Error processing surface '{surface_id}': {e_surf}. Skipping this surface.", exc_info=True)
                    continue # Skip to the next surface
        except Exception as e:
            logger.error(f"Critical error in _process_surfaces: {e}", exc_info=True)
            # This is a more significant failure

    def _get_construction_properties(self, construction_name: str) -> Dict[str, float]:
        """
        Get properties for a specific construction.
        Returns default values if construction or materials are not found or if errors occur.
        """
        default_properties = {'thickness': 0.0, 'conductivity': 0.0, 'r_value': 0.0}
        try:
            constructions = self.data_loader.get_constructions()
            materials = self.data_loader.get_materials()

            if not construction_name or construction_name not in constructions:
                logger.warning(f"Construction '{construction_name}' not found in constructions data. Returning default properties.")
                return default_properties

            construction_data = constructions[construction_name]
            material_layers = construction_data.get('material_layers', [])
            if not material_layers:
                logger.warning(f"No material layers found for construction '{construction_name}'. Returning default properties.")
                return default_properties

            total_thickness = 0.0
            total_resistance = 0.0

            for layer_id in material_layers:
                if not layer_id or layer_id not in materials:
                    logger.warning(f"Material layer '{layer_id}' for construction '{construction_name}' not found in materials data. Skipping layer.")
                    continue
                
                material_data = materials[layer_id]
                try:
                    thickness = safe_float(material_data.get('thickness'), 0.0)
                    conductivity = safe_float(material_data.get('conductivity'), 0.0)
                    resistance = safe_float(material_data.get('thermal_resistance'), 0.0) # For Material:NoMass

                    total_thickness += thickness
                    if resistance > 0: # Material:NoMass or similar
                        total_resistance += resistance
                    elif conductivity > 0 and thickness > 0: # Standard material
                        total_resistance += thickness / conductivity
                    else:
                        logger.debug(f"Material layer '{layer_id}' in '{construction_name}' has zero resistance (thickness: {thickness}, conductivity: {conductivity}, explicit_R: {resistance}).")
                except (TypeError, ValueError) as e_mat:
                    logger.warning(f"Error processing material layer '{layer_id}' in construction '{construction_name}': {e_mat}. Skipping layer.", exc_info=True)
                    continue
            
            final_conductivity = total_thickness / total_resistance if total_resistance > 0 else 0.0
            
            return {
                'thickness': total_thickness,
                'conductivity': final_conductivity, # This is an effective conductivity
                'r_value': total_resistance
            }
        except (TypeError, ValueError, AttributeError, KeyError) as e:
            logger.error(f"Error getting properties for construction '{construction_name}': {e}. Returning default properties.", exc_info=True)
            return default_properties
        except Exception as e_crit: # Catch any other unexpected critical errors
            logger.critical(f"Unexpected critical error in _get_construction_properties for '{construction_name}': {e_crit}", exc_info=True)
            return default_properties


    def _calculate_u_value(self, construction_name: str) -> float:
        """
        Calculate U-Value for a construction.
        Prioritizes direct U-Factor for simple glazing, then uses CSV if available,
        otherwise calculates based on layer resistance including film resistance.
        """
        logger.debug(f"Calculating U-Value for construction: '{construction_name}'")
        try:
            # Check CSV data first if this construction might be glazing (more robust check needed if name alone isn't enough)
            # However, the main _process_surfaces already handles CSV U-value lookup.
            # This function is now more of a fallback or for opaque/complex calculations.

            constructions_opaque = self.data_loader.get_constructions()
            constructions_glazing = self.data_loader.get_constructions_glazing() # For WindowMaterial:SimpleGlazingSystem
            all_constructions = {**constructions_opaque, **constructions_glazing} # Combine them
            
            materials = self.data_loader.get_materials()
            surfaces = self.data_loader.get_surfaces() # For film resistance context

            if not construction_name or construction_name not in all_constructions:
                logger.warning(f"Construction '{construction_name}' not found in combined constructions data. Returning U=0.")
                return 0.0

            construction_data = all_constructions[construction_name]
            material_layers = construction_data.get('material_layers', [])

            # Check for WindowMaterial:SimpleGlazingSystem first
            if material_layers: # Only proceed if there are layers
                first_layer_id = material_layers[0]
                if first_layer_id in materials:
                    first_material_data = materials[first_layer_id]
                    mat_type = first_material_data.get('type')
                    if mat_type == 'WindowMaterial:SimpleGlazingSystem':
                        u_factor = first_material_data.get('u_factor')
                        if u_factor is not None:
                            u_value_float = safe_float(u_factor, -1.0)
                            if u_value_float >= 0: # U-factor should be non-negative
                                logger.debug(f"Using U-Factor {u_value_float} from WindowMaterial:SimpleGlazingSystem for '{construction_name}'.")
                                return u_value_float
                            else:
                                logger.warning(f"Invalid U-Factor '{u_factor}' for SimpleGlazingSystem '{construction_name}'. Proceeding to calculate.")
                        else:
                             logger.warning(f"U-Factor is None for SimpleGlazingSystem '{construction_name}'. Proceeding to calculate.")


            # Calculate R-value from layers
            total_material_resistance = 0.0
            if not material_layers:
                 logger.warning(f"No material layers found for construction '{construction_name}' when calculating R-value. Material resistance will be 0.")

            for layer_id in material_layers:
                if not layer_id or layer_id not in materials:
                    logger.warning(f"Material layer '{layer_id}' for '{construction_name}' not found. Skipping layer in R-value calculation.")
                    continue
                
                material_data = materials[layer_id]
                try:
                    thickness = safe_float(material_data.get('thickness'), -1.0)
                    conductivity = safe_float(material_data.get('conductivity'), -1.0)
                    resistance = safe_float(material_data.get('thermal_resistance'), -1.0) # For Material:NoMass

                    layer_r = 0.0
                    if resistance >= 0: # Prioritize explicit resistance if valid
                        layer_r = resistance
                    elif thickness >= 0 and conductivity > 0: # Must be >0, not >=0
                        layer_r = thickness / conductivity
                    else:
                        logger.debug(f"Material layer '{layer_id}' in '{construction_name}' has insufficient data for R-value (thickness: {thickness}, conductivity: {conductivity}, explicit_R: {resistance}).")
                    total_material_resistance += layer_r
                except (TypeError, ValueError) as e_mat_calc:
                    logger.warning(f"Error calculating resistance for material layer '{layer_id}' in '{construction_name}': {e_mat_calc}. Skipping layer.", exc_info=True)
                    continue
            
            # Get film resistance
            film_resistance = 0.0
            try:
                # Determine if the construction is predominantly a window or wall/roof/floor for film resistance context
                element_type_for_film = "Wall" # Default
                # Check if any surface using this construction is marked as glazing
                is_predominantly_window = any(
                    s.get('is_glazing', False)
                    for s in surfaces.values()
                    if s.get('construction_name') == construction_name
                )
                if is_predominantly_window:
                    element_type_for_film = "Window"
                
                if self.materials_parser and hasattr(self.materials_parser, '_get_surface_film_resistance') and \
                   callable(getattr(self.materials_parser, '_get_surface_film_resistance')):
                    film_resistance = self.materials_parser._get_surface_film_resistance(element_type_for_film)
                else:
                    logger.debug(f"MaterialsParser or _get_surface_film_resistance not available for '{construction_name}'. Defaulting film_resistance to 0.")
            except Exception as e_film:
                logger.warning(f"Error getting film resistance for '{construction_name}' (context type '{element_type_for_film}'): {e_film}. Defaulting film_resistance to 0.", exc_info=True)

            r_value_with_film = total_material_resistance + film_resistance
            u_value = 1.0 / r_value_with_film if r_value_with_film > 0 else 0.0
            logger.debug(f"Calculated U-Value for '{construction_name}': {u_value} (R_material={total_material_resistance}, R_film={film_resistance}, R_total={r_value_with_film})")
            return u_value

        except (TypeError, ValueError, AttributeError, KeyError) as e:
            logger.error(f"Error calculating U-Value for construction '{construction_name}': {e}. Returning U=0.", exc_info=True)
            return 0.0
        except Exception as e_crit: # Catch any other unexpected critical errors
            logger.critical(f"Unexpected critical error in _calculate_u_value for '{construction_name}': {e_crit}", exc_info=True)
            return 0.0


    def _merge_reverse_constructions(self, materials_parser: MaterialsParser) -> None:
        """
        Merges constructions with '_rev' or '_reverse' suffixes into their base counterparts
        ONLY IF they share the exact same set of element types determined by MaterialsParser.
        Sums total_area and total_u_value, combines elements, and removes the reverse entry.
        Important: Glazing constructions (identified by CSV or element type) are not merged.
        """
        try:
            surfaces = self.data_loader.get_surfaces()
            if not self.areas_by_zone:
                logger.info("No zones processed. Skipping reverse construction merging.")
                return

            for zone_id, zone_data in self.areas_by_zone.items():
                try:
                    constructions = zone_data.get("constructions", {})
                    if not constructions:
                        continue
                    
                    construction_names = list(constructions.keys()) # Work on a copy
                    to_remove = []

                    for name in construction_names:
                        if name in to_remove: # Already processed or marked for removal
                            continue
                        
                        base_name = None
                        if name.endswith("_rev"):
                            base_name = name[:-4]
                        elif name.endswith("_reverse"):
                            base_name = name[:-8]

                        if base_name and base_name in constructions and base_name not in to_remove:
                            reverse_name = name
                            
                            # Skip if either is explicitly known as glazing from CSV
                            if base_name in self.glazing_data_from_csv or reverse_name in self.glazing_data_from_csv:
                                logger.debug(f"Skipping merge for '{base_name}'/'{reverse_name}': one is in CSV glazing data.")
                                continue

                            base_elements = constructions.get(base_name, {}).get("elements", [])
                            reverse_elements = constructions.get(reverse_name, {}).get("elements", [])

                            # Skip if any element within these constructions is typed as glazing
                            has_base_glazing_element = any(
                                element.get("element_type", "").endswith("Glazing") for element in base_elements
                            )
                            has_reverse_glazing_element = any(
                                element.get("element_type", "").endswith("Glazing") for element in reverse_elements
                            )
                            if has_base_glazing_element or has_reverse_glazing_element:
                                logger.debug(f"Skipping merge for '{base_name}'/'{reverse_name}': one contains glazing elements.")
                                continue
                            
                            try:
                                base_types_list, base_dont_use = materials_parser._get_element_type(base_name, surfaces)
                                reverse_types_list, reverse_dont_use = materials_parser._get_element_type(reverse_name, surfaces)
                                
                                if base_dont_use or reverse_dont_use:
                                    logger.debug(f"Skipping merge for '{base_name}'/'{reverse_name}': one is marked 'dont_use'.")
                                    continue

                                base_types_set = set(bt for bt in base_types_list if bt and "Glazing" not in bt) # Exclude glazing types from comparison set
                                reverse_types_set = set(rt for rt in reverse_types_list if rt and "Glazing" not in rt)

                                if base_types_set and base_types_set == reverse_types_set: # Both non-empty and identical non-glazing types
                                    logger.info(f"Merging '{reverse_name}' into '{base_name}' for zone '{zone_id}'. Matched types: {base_types_set}")
                                    base_constr = constructions[base_name]
                                    reverse_constr = constructions[reverse_name]
                                    
                                    base_constr["total_area"] += reverse_constr.get("total_area", 0.0)
                                    base_constr["total_u_value"] += reverse_constr.get("total_u_value", 0.0) # This is sum of (Area*U)
                                    base_constr["elements"].extend(reverse_constr.get("elements", []))
                                    to_remove.append(reverse_name)
                                else:
                                    logger.debug(f"Not merging '{base_name}' and '{reverse_name}': non-glazing element types do not match or one is empty. Base: {base_types_set}, Reverse: {reverse_types_set}")

                            except Exception as e_type:
                                logger.warning(f"Error determining element types during merge check for '{base_name}'/'{reverse_name}' in zone '{zone_id}': {e_type}. Skipping merge for this pair.", exc_info=True)
                    
                    # Perform removals after iterating through names for the current zone
                    for key_to_remove in to_remove:
                        if key_to_remove in constructions:
                            del constructions[key_to_remove]
                            logger.debug(f"Removed '{key_to_remove}' from constructions in zone '{zone_id}' after merging.")
                
                except (TypeError, ValueError, AttributeError, KeyError) as e_zone_merge:
                    logger.error(f"Error during reverse construction merging for zone '{zone_id}': {e_zone_merge}. Skipping zone.", exc_info=True)
                    continue
        except Exception as e:
            logger.error(f"Critical error in _merge_reverse_constructions: {e}", exc_info=True)


    def get_areas_by_zone(self) -> Dict[str, Dict[str, Any]]:
        """
        Get the processed area data by zone.
        Returns an empty dictionary if not processed or if an error occurs.
        """
        if not self.processed:
            logger.warning("Area data not processed yet. Call process_idf() first. Returning empty dict.")
            return {}
        try:
            # Potentially add a deepcopy if modification by callers is a concern
            return self.areas_by_zone
        except Exception as e:
            logger.error(f"Error retrieving areas_by_zone: {e}", exc_info=True)
            return {}


    def get_area_totals(self, area_id: str) -> Dict[str, float]:
        """
        Get totals for a specific area (e.g., floor area, wall area, window area).
        Returns a dictionary with zeroed values if area_id is not found or an error occurs.
        """
        result = {"total_floor_area": 0.0, "wall_area": 0.0, "window_area": 0.0}
        if not area_id:
            logger.warning("get_area_totals called with no area_id. Returning zeroed totals.")
            return result
        if not self.processed:
            logger.warning(f"Area data not processed. Call process_idf() first. Returning zeroed totals for area '{area_id}'.")
            return result
        
        found_area = False
        try:
            for zone_id, zone_data in self.areas_by_zone.items():
                if zone_data.get("area_id") != area_id:
                    continue
                found_area = True

                result["total_floor_area"] += (
                    safe_float(zone_data.get("floor_area", 0.0), 0.0) *
                    int(safe_float(zone_data.get("multiplier", 1), 1))
                )

                for construction_name, construction_data in zone_data.get("constructions", {}).items():
                    try:
                        # Check based on element_type within elements list
                        is_glazing_construction = any(
                            element.get("element_type", "").endswith("Glazing")
                            for element in construction_data.get("elements", [])
                        )
                        is_wall_construction = any(
                            "wall" in element.get("element_type", "").lower() and not element.get("element_type", "").endswith("Glazing")
                            for element in construction_data.get("elements", [])
                        )

                        if is_glazing_construction:
                            result["window_area"] += safe_float(construction_data.get("total_area", 0.0), 0.0)
                        elif is_wall_construction: # Ensure it's not also counted as glazing if logic is complex
                            result["wall_area"] += safe_float(construction_data.get("total_area", 0.0), 0.0)
                    except (TypeError, AttributeError) as e_constr:
                        logger.warning(f"Error processing construction '{construction_name}' in zone '{zone_id}' for area totals: {e_constr}. Skipping construction.", exc_info=True)
                        continue
            
            if not found_area:
                logger.info(f"No zones found for area_id '{area_id}' in get_area_totals.")
            return result
        except Exception as e:
            logger.error(f"Error calculating area totals for area_id '{area_id}': {e}. Returning partially calculated or zeroed totals.", exc_info=True)
            return result # Return whatever was calculated or the initial zeroed dict


    def get_area_table_data(self, materials_parser: Optional[MaterialsParser] = None) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get data for area reports in table format.
        Returns an empty dictionary if errors occur or prerequisites are not met.
        """
        result_by_area: Dict[str, List[Dict[str, Any]]] = {}
        try:
            parser_to_use = materials_parser if materials_parser else self.materials_parser
            if not parser_to_use:
                logger.error("MaterialsParser instance is required for get_area_table_data but none provided or set. Returning empty data.")
                return result_by_area
            if not self.processed:
                logger.warning("Area data not processed. Call process_idf() first. Returning empty data for area table.")
                return result_by_area

            surfaces = self.data_loader.get_surfaces()
            if not self.areas_by_zone:
                logger.info("No zones processed (self.areas_by_zone is empty). Returning empty data for area table.")
                return result_by_area

            for zone_id, zone_data in self.areas_by_zone.items():
                try:
                    area_id = zone_data.get("area_id", "unknown")
                    if "core" in area_id.lower(): # Skip 'core' areas
                        continue
                    
                    if area_id not in result_by_area:
                        result_by_area[area_id] = []

                    zone_constructions_aggregated = {}
                    constructions_in_zone = zone_data.get("constructions", {})
                    if not constructions_in_zone:
                        logger.debug(f"Zone '{zone_id}' in area '{area_id}' has no constructions. Skipping.")
                        continue

                    for construction_name, construction_data in constructions_in_zone.items():
                        try:
                            determined_element_types, dont_use = parser_to_use._get_element_type(construction_name, surfaces)
                            if dont_use or not determined_element_types:
                                logger.debug(f"Construction '{construction_name}' in zone '{zone_id}' skipped: 'dont_use' is true or no element types determined.")
                                continue

                            total_area_constr = safe_float(construction_data.get("total_area", 0.0), 0.0)
                            total_area_u_value_constr = safe_float(construction_data.get("total_u_value", 0.0), 0.0)

                            if total_area_constr <= 0.0:
                                logger.debug(f"Construction '{construction_name}' in zone '{zone_id}' skipped: total_area is {total_area_constr}.")
                                continue
                            
                            # This is the average U-value for the opaque part of the construction
                            construction_u_value_avg = total_area_u_value_constr / total_area_constr if total_area_constr > 0 else 0.0
                            cleaned_construction_name = construction_name # Placeholder for future cleaning if needed

                            # Determine primary non-glazing type for the whole construction (used for opaque parts)
                            primary_non_glazing_type = next((t for t in determined_element_types if t and "Glazing" not in t), "Unknown")

                            elements = construction_data.get("elements", [])
                            if not elements:
                                logger.debug(f"Construction '{construction_name}' in zone '{zone_id}' has no elements. Skipping.")
                                continue
                                
                            for element in elements:
                                try:
                                    element_area = safe_float(element.get("area", 0.0), 0.0)
                                    if element_area <= 0.0:
                                        logger.debug(f"Element in '{construction_name}', surface '{element.get('surface_name')}' skipped: area is {element_area}.")
                                        continue

                                    element_specific_type = element.get("element_type", "Unknown") # This is from _process_surfaces
                                    element_u_value = safe_float(element.get("u_value", 0.0), 0.0)
                                    element_surface_name = element.get("surface_name", "unknown_surface")
                                    
                                    is_glazing_element = element_specific_type.endswith("Glazing")

                                    if is_glazing_element:
                                        display_element_type = element_specific_type
                                        # For individual glazing elements, use their specific U-value and create a unique key per surface
                                        zone_constr_key = f"{zone_id}_{cleaned_construction_name}_{display_element_type}_{element_surface_name}"
                                        reported_u_value = element_u_value
                                    else: # Opaque part of a construction
                                        display_element_type = primary_non_glazing_type
                                        # For opaque parts, group by the primary non-glazing type and use the construction's average U-value
                                        zone_constr_key = f"{zone_id}_{cleaned_construction_name}_{display_element_type}"
                                        reported_u_value = construction_u_value_avg
                                    
                                    if zone_constr_key not in zone_constructions_aggregated:
                                        zone_constructions_aggregated[zone_constr_key] = {
                                            "zone": zone_id, "construction": cleaned_construction_name,
                                            "element_type": display_element_type, "area": 0.0,
                                            "u_value": reported_u_value, # Store the U-value to be used for this aggregation group
                                            "area_loss": 0.0,
                                        }
                                    
                                    constr_agg = zone_constructions_aggregated[zone_constr_key]
                                    constr_agg["area"] += element_area
                                    # Area loss for this element is its area * the U-value of its aggregation group
                                    constr_agg["area_loss"] += element_area * constr_agg["u_value"]
                                
                                except (TypeError, ValueError, AttributeError, KeyError) as e_elem:
                                    logger.warning(f"Error processing element within construction '{construction_name}', zone '{zone_id}': {e_elem}. Skipping element.", exc_info=True)
                                    continue # Next element
                        
                        except (TypeError, ValueError, AttributeError, KeyError) as e_constr_proc:
                            logger.warning(f"Error processing construction '{construction_name}' in zone '{zone_id}': {e_constr_proc}. Skipping construction.", exc_info=True)
                            continue # Next construction
                    
                    # Append aggregated data for the zone to the area's list
                    result_by_area[area_id].extend(list(zone_constructions_aggregated.values()))

                except (TypeError, ValueError, AttributeError, KeyError) as e_zone_proc:
                    logger.error(f"Error processing zone '{zone_id}' for area table data: {e_zone_proc}. Skipping zone.", exc_info=True)
                    continue # Next zone
            
            return result_by_area
        except Exception as e:
            logger.critical(f"Critical error in get_area_table_data: {e}", exc_info=True)
            return result_by_area # Return empty or partially filled dict


    def get_area_h_values(self) -> List[Dict[str, Any]]:
        """
        Calculates the H-Value for each area.
        Returns an empty list if errors occur or prerequisites are not met.
        """
        h_values_by_area: List[Dict[str, Any]] = []
        try:
            if not self.processed:
                logger.error("IDF data must be processed before calculating H-values. Call process_idf() first. Returning empty list.")
                return h_values_by_area
            if not self.materials_parser: # Should be caught by get_area_table_data, but good to check
                logger.error("MaterialsParser instance is required for H-Value calculation. Returning empty list.")
                return h_values_by_area

            # This call now has its own robust error handling
            area_data_for_h_calc = self.get_area_table_data() # This already uses self.materials_parser
            if not area_data_for_h_calc:
                logger.warning("No data returned from get_area_table_data for H-value calculation. Returning empty list.")
                return h_values_by_area

            area_floor_totals = {}
            for zone_id, zone_data in self.areas_by_zone.items():
                try:
                    area_id = zone_data.get("area_id", "unknown")
                    if "core" in area_id.lower(): # Skip 'core' areas
                        continue
                    if area_id not in area_floor_totals:
                        area_floor_totals[area_id] = 0.0
                    area_floor_totals[area_id] += (
                        safe_float(zone_data.get("floor_area", 0.0), 0.0) *
                        int(safe_float(zone_data.get("multiplier", 1), 1))
                    )
                except (TypeError, ValueError) as e_floor_total:
                    logger.warning(f"Error calculating floor total for zone '{zone_id}': {e_floor_total}. Skipping zone for floor totals.", exc_info=True)

            from collections import defaultdict
            grouped_data = defaultdict(list)
            for area_id_key, rows in area_data_for_h_calc.items(): # area_id_key to avoid conflict
                grouped_data[area_id_key].extend(rows)

            external_keywords = ["external", "outside"]
            ground_keywords = ["ground", "slab on grade", "slab-on-grade"]
            roof_keywords = ["roof"]
            separation_keywords = ["separation"]
            floor_keywords = ["floor"]
            ceiling_keywords = ["ceiling"]

            for area_id, rows_for_area in grouped_data.items(): # Renamed rows to rows_for_area
                try:
                    total_floor_area = area_floor_totals.get(area_id, 0.0)
                    if total_floor_area <= 0:
                        logger.warning(f"Skipping H-Value calculation for Area '{area_id}': Total floor area is {total_floor_area}.")
                        continue

                    external_roof_loss_sum = 0.0
                    separation_loss_sum = 0.0
                    sum_ground_floor, sum_external_floor, sum_separation_floor, sum_intermediate_floor = 0.0, 0.0, 0.0, 0.0
                    sum_roof, sum_intermediate_ceiling, sum_separation_ceiling = 0.0, 0.0, 0.0

                    for row in rows_for_area: # Iterate through rows_for_area
                        try:
                            element_type = row.get('element_type', '').lower()
                            area = safe_float(row.get('area', 0.0), 0.0)
                            area_loss = safe_float(row.get('area_loss', 0.0), 0.0) # area_loss is Area * U-value

                            is_external_roof = any(keyword in element_type for keyword in external_keywords + roof_keywords)
                            is_separation = any(keyword in element_type for keyword in separation_keywords)
                            
                            if is_external_roof:
                                external_roof_loss_sum += area_loss
                            elif is_separation: # Only count as separation if not already external/roof
                                separation_loss_sum += area_loss
                            
                            # Location type determination based on area sums
                            if any(keyword in element_type for keyword in floor_keywords):
                                if any(keyword in element_type for keyword in ground_keywords): sum_ground_floor += area
                                elif any(keyword in element_type for keyword in external_keywords): sum_external_floor += area
                                elif any(keyword in element_type for keyword in separation_keywords): sum_separation_floor += area
                                else: sum_intermediate_floor += area
                            elif any(keyword in element_type for keyword in ceiling_keywords + roof_keywords): # Include roof here
                                if any(keyword in element_type for keyword in roof_keywords): sum_roof += area
                                elif any(keyword in element_type for keyword in separation_keywords): sum_separation_ceiling += area
                                else: sum_intermediate_ceiling += area
                        except (TypeError, ValueError, AttributeError) as e_row:
                            logger.warning(f"Error processing a row for H-value/location in area '{area_id}': {row}. Error: {e_row}. Skipping row.", exc_info=True)
                            continue # Next row
                    
                    h_value = (external_roof_loss_sum + 0.5 * separation_loss_sum) / total_floor_area if total_floor_area > 0 else 0.0
                    
                    # Determine location (simplified logic from original, ensure robustness)
                    group1_values = {"ground_floor": sum_ground_floor, "external_floor": sum_external_floor,
                                     "separation_floor": sum_separation_floor, "intermediate_floor": sum_intermediate_floor}
                    group2_values = {"roof": sum_roof, "intermediate_ceiling": sum_intermediate_ceiling,
                                     "separation_ceiling": sum_separation_ceiling}

                    max_floor_type = max(group1_values, key=group1_values.get) if any(v > 0 for v in group1_values.values()) else "unknown_floor"
                    max_ceiling_type = max(group2_values, key=group2_values.get) if any(v > 0 for v in group2_values.values()) else "unknown_ceiling"
                    
                    location = "Unknown" # Default
                    # This mapping logic can be complex and error-prone; consider a more structured approach if issues persist
                    if max_floor_type == "ground_floor":
                        if max_ceiling_type == "intermediate_ceiling": location = "Ground Floor & Intermediate ceiling"
                        elif max_ceiling_type == "roof": location = "Ground Floor & External ceiling"
                        elif max_ceiling_type == "separation_ceiling": location = "Ground Floor & Separation ceiling"
                    elif max_floor_type == "external_floor":
                        if max_ceiling_type == "roof": location = "External Floor & External ceiling"
                        elif max_ceiling_type == "intermediate_ceiling": location = "External Floor & Intermediate ceiling"
                        elif max_ceiling_type == "separation_ceiling": location = "External Floor & Separation ceiling"
                    # ... (add other combinations as per original logic, ensuring robustness)
                    elif max_floor_type == "intermediate_floor":
                         if max_ceiling_type == "intermediate_ceiling": location = "Intermediate Floor & Intermediate ceiling"
                         elif max_ceiling_type == "roof": location = "Intermediate Floor & External ceiling"
                         elif max_ceiling_type == "separation_ceiling": location = "Intermediate Floor & Separation ceiling"
                    elif max_floor_type == "separation_floor":
                         if max_ceiling_type == "intermediate_ceiling": location = "Separation Floor & Intermediate ceiling"
                         elif max_ceiling_type == "roof": location = "Separation Floor & External ceiling"
                         elif max_ceiling_type == "separation_ceiling": location = "Separation Floor & Separation ceiling"


                    h_values_by_area.append({
                        'area_id': area_id, 'location': location, 'h_value': h_value,
                        'total_floor_area': total_floor_area
                    })
                except (TypeError, ValueError, AttributeError, KeyError, ZeroDivisionError) as e_area_h:
                    logger.error(f"Error calculating H-value or location for area '{area_id}': {e_area_h}. Skipping this area.", exc_info=True)
                    continue # Next area_id
            
            return h_values_by_area
        except Exception as e:
            logger.critical(f"Critical error in get_area_h_values: {e}", exc_info=True)
            return h_values_by_area # Return empty or partially filled list
