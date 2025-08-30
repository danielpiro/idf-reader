"""
Extracts and processes area information including floor areas and material properties.
"""
from typing import Dict, Any, List, Optional
from parsers.materials_parser import MaterialsParser
from .utils import safe_float
from parsers.eplustbl_reader import read_glazing_data_from_csv, read_zone_areas_from_csv
from .base_parser import SurfaceDataParser

class AreaParser(SurfaceDataParser):
    """
    Processes area information from IDF files, including distribution of zones in areas.
    Uses cached data from DataLoader for efficient access.
    """
    def __init__(self, data_loader, materials_parser: MaterialsParser, csv_path: Optional[str] = None):
        super().__init__(data_loader, "AreaParser")
        try:
            self.glazing_data_from_csv = read_glazing_data_from_csv(csv_path)
        except Exception:
            self.glazing_data_from_csv = {}
            
        # Load construction areas from eplustbl.csv for both glazing and opaque constructions
        try:
            from parsers.eplustbl_reader import read_construction_areas_from_csv
            self.construction_areas_from_csv = read_construction_areas_from_csv(csv_path)
        except Exception as e:
            self.construction_areas_from_csv = {}
            
        # Load zone areas from eplustbl.csv Zone Summary table
        try:
            self.zone_areas_from_csv = read_zone_areas_from_csv(csv_path)
            if self.zone_areas_from_csv:
                self.logger.info(f"Loaded zone areas from CSV: {len(self.zone_areas_from_csv)} zones found")
                # Log first few zone names for debugging
                sample_zones = list(self.zone_areas_from_csv.keys())[:3]
                self.logger.debug(f"Sample CSV zone names: {sample_zones}")
            else:
                self.logger.warning(f"No zone areas loaded from CSV path: {csv_path}")
        except Exception as e:
            self.logger.error(f"Error loading zone areas from CSV: {e}")
            self.zone_areas_from_csv = {}
            
        self.materials_parser = materials_parser
        self.areas_by_zone = {}

    def process_idf(self, idf) -> None:
        """
        Extract area information.

        Args:
            idf: IDF data object (not directly used but passed to materials_parser)
        """
        if not self._validate_initialization():
            return
        if self._ensure_not_processed():
            return
        try:
            if self.materials_parser and not self.materials_parser.element_data:
                self.materials_parser.process_idf(idf)

            self._process_zones()
            self._process_surfaces()

            if self.materials_parser:
                self._merge_reverse_constructions(self.materials_parser)

            # Log summary of processed zone areas
            if self.areas_by_zone:
                total_zones = len(self.areas_by_zone)
                csv_used_count = 0
                calculated_used_count = 0
                
                for zone_id, zone_data in self.areas_by_zone.items():
                    floor_area = zone_data.get("floor_area", 0)
                    # Try to determine if CSV was used by checking if this area matches CSV
                    csv_area = self._get_zone_area_from_csv(zone_id)
                    if csv_area is not None and abs(floor_area - csv_area) < 0.01:
                        csv_used_count += 1
                    else:
                        calculated_used_count += 1
                
                self.logger.info(f"Zone area processing summary: {total_zones} zones processed")
                self.logger.info(f"Zone area sources: {csv_used_count} from CSV, {calculated_used_count} from calculations")
                
                # Log a few sample zones for verification
                sample_zones = list(self.areas_by_zone.items())[:3]
                for zone_id, zone_data in sample_zones:
                    self.logger.info(f"Sample zone '{zone_id}': floor_area={zone_data.get('floor_area')}, multiplier={zone_data.get('multiplier')}")
            
            self.processed = True
        except (ValueError, KeyError, Exception):
            raise

    def _process_zones(self) -> None:
        """
        Process zones to initialize the data structure.
        """
        try:
            zones = self.data_loader.get_zones()
            if not zones:
                return

            for zone_id, zone_data in zones.items():
                try:
                    if not zone_id:
                        continue

                    # Use enhanced floor_id extraction for better grouping
                    floor_id = self._extract_floor_id_enhanced(zone_id)
                    
                    # Also extract base zone ID for potential grouping
                    base_zone_id = self._extract_base_zone_id(zone_id)
                    
                    # Get group key for debugging
                    group_key = self.data_loader.get_zone_group_key(zone_id)

                    # Try to get floor area from eplustbl.csv first, fallback to calculated value
                    csv_floor_area = self._get_zone_area_from_csv(zone_id)
                    calculated_floor_area = safe_float(zone_data.get("floor_area"))
                    
                    if csv_floor_area is not None and csv_floor_area > 0:
                        floor_area = csv_floor_area
                        self.logger.info(f"Using CSV zone area for '{zone_id}': {csv_floor_area} m² (calculated was: {calculated_floor_area})")
                    else:
                        floor_area = calculated_floor_area
                        self.logger.warning(f"Using calculated zone area for '{zone_id}': {calculated_floor_area} m² (CSV not found or invalid)")
                    
                    # Try to get multiplier from eplustbl.csv first, fallback to IDF value
                    csv_multiplier = self._get_zone_multiplier_from_csv(zone_id)
                    calculated_multiplier = int(safe_float(zone_data.get("multiplier"), 1))
                    
                    if csv_multiplier is not None and csv_multiplier > 0:
                        multiplier = csv_multiplier
                        if csv_multiplier != calculated_multiplier:
                            self.logger.info(f"Using CSV zone multiplier for '{zone_id}': {csv_multiplier} (calculated was: {calculated_multiplier})")
                    else:
                        multiplier = calculated_multiplier

                    self.areas_by_zone[zone_id] = {
                        "floor_id": floor_id,
                        "base_zone_id": base_zone_id,
                        "floor_area": floor_area,
                        "multiplier": multiplier,
                        "constructions": {}
                    }
                except (TypeError, ValueError, AttributeError):
                    continue
        except Exception:
            pass

    def _process_surfaces(self) -> None:
        """
        Process surfaces to extract construction and area information.
        """
        try:
            surfaces = self.data_loader.get_surfaces()
            
            if not surfaces:
                return

            windows_by_base_surface = {}
            
            # First, try to use base_surface property for window-wall mapping
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
                    pass
            
            # Second, use naming pattern matching for windows that weren't matched
            # Pattern: wall name followed by window suffix (e.g., 02:10XOFFICE_Wall_2_0_0 -> 02:10XOFFICE_WALL_2_0_0_*_WIN)
            for surface_id, surface in surfaces.items():
                try:
                    if surface.get("is_glazing", False):
                        # Skip if already matched by base_surface
                        already_matched = False
                        for wall_surfaces in windows_by_base_surface.values():
                            if any(w["window_id"] == surface_id for w in wall_surfaces):
                                already_matched = True
                                break
                        
                        if already_matched:
                            continue
                            
                        # Try to match by naming pattern
                        window_name_upper = surface_id.upper()
                        if "_WIN" in window_name_upper:
                            # Extract the base wall name from window name
                            # Convert 02:10XOFFICE_WALL_2_0_0_*_WIN to 02:10XOFFICE_Wall_2_0_0
                            parts = window_name_upper.split("_WIN")[0]  # Remove _WIN suffix
                            # Remove the window-specific parts (numbers after the wall base name)
                            base_parts = parts.split("_")
                            if len(base_parts) >= 4:  # Should have zone:name_WALL_x_y_z format
                                # Find potential wall name by trying different combinations
                                for wall_surface_id in surfaces.keys():
                                    if not surfaces[wall_surface_id].get("is_glazing", False):
                                        wall_name_upper = wall_surface_id.upper()
                                        # Check if window name starts with wall name pattern
                                        if self._is_window_for_wall(window_name_upper, wall_name_upper):
                                            if wall_surface_id not in windows_by_base_surface:
                                                windows_by_base_surface[wall_surface_id] = []
                                            windows_by_base_surface[wall_surface_id].append({
                                                "window_id": surface_id,
                                                "area": safe_float(surface.get("area", 0.0), 0.0),
                                            })
                                            break
                except (TypeError, AttributeError) as e_win:
                    pass

            processed_surfaces = 0
            surfaces_with_constructions = 0
            
            for surface_id, surface in surfaces.items():
                try:
                    processed_surfaces += 1
                    zone_name = surface.get("zone_name")
                    
                    if processed_surfaces <= 5:  # Log first 5 surfaces for debugging
                        pass
                    
                    if not zone_name:
                        if processed_surfaces <= 5:
                            pass
                        continue
                        
                    if zone_name not in self.areas_by_zone:
                        if processed_surfaces <= 5:
                            pass
                        continue
                        
                    # Check if this is a window/glazing surface
                    is_window_surface = surface.get("is_glazing", False)

                    construction_name = surface.get("construction_name")
                    if not construction_name:
                        if processed_surfaces <= 5:
                            pass
                        continue
                        
                    if processed_surfaces <= 5:
                        pass

                    # Get area from eplustbl.csv if available, using containment checks
                    csv_area = None
                    csv_matched_key = None
                    
                    # Helper function to find CSV key using containment check
                    def find_csv_key_by_containment(search_id):
                        """Find CSV key using containment check (both directions)"""
                        search_upper = search_id.upper()
                        # Try exact match first
                        if search_upper in self.construction_areas_from_csv:
                            return search_upper
                        # Try containment check - find CSV key that contains search_id
                        for csv_key in self.construction_areas_from_csv.keys():
                            if search_upper in csv_key:
                                return csv_key
                        # Try reverse containment - find if search_id contains any CSV key
                        for csv_key in self.construction_areas_from_csv.keys():
                            if csv_key in search_upper:
                                return csv_key
                        return None
                    
                    if is_window_surface:
                        # For glazing, prioritize surface_id lookup
                        csv_matched_key = find_csv_key_by_containment(surface_id)
                        if csv_matched_key:
                            csv_area = safe_float(self.construction_areas_from_csv[csv_matched_key].get('Area', 0.0))
                            self.logger.debug(f"Found glazing CSV match: '{surface_id}' -> '{csv_matched_key}', area: {csv_area}")
                    else:
                        # For opaque surfaces, try surface_id first, then construction_name
                        csv_matched_key = find_csv_key_by_containment(surface_id)
                        if csv_matched_key:
                            csv_area = safe_float(self.construction_areas_from_csv[csv_matched_key].get('Area', 0.0))
                            self.logger.debug(f"Found surface CSV match: '{surface_id}' -> '{csv_matched_key}', area: {csv_area}")
                        elif construction_name:
                            csv_matched_key = find_csv_key_by_containment(construction_name)
                            if csv_matched_key:
                                csv_area = safe_float(self.construction_areas_from_csv[csv_matched_key].get('Area', 0.0))
                                self.logger.debug(f"Found construction CSV match: '{construction_name}' -> '{csv_matched_key}', area: {csv_area}")
                       
                    
                    # Use CSV area if available and valid, otherwise use calculated area
                    if csv_area and csv_area > 0.0:
                        area = csv_area
                    else:
                        area = safe_float(surface.get("area"))       
                        if area is None or area <= 0.0:
                            continue
                    surfaces_with_constructions += 1
                    
                    if not surface.get("is_glazing", False) and surface_id in windows_by_base_surface:
                        try:
                            # Calculate total window area - prioritize CSV data when available
                            window_areas = 0.0
                            windows_list = windows_by_base_surface.get(surface_id, [])
                            
                            for window_info in windows_list:
                                window_id = window_info["window_id"]
                                window_area = window_info["area"]
                                
                                # Try to get more accurate area from CSV data using containment check
                                csv_window_area = None
                                csv_window_key = find_csv_key_by_containment(window_id)
                                if csv_window_key:
                                    csv_window_area = safe_float(self.construction_areas_from_csv[csv_window_key].get('Area', 0.0))
                                    self.logger.debug(f"Found window CSV match: '{window_id}' -> '{csv_window_key}', area: {csv_window_area}")
                                
                                if csv_window_area and csv_window_area > 0.0:
                                    window_areas += csv_window_area
                                else:
                                    window_areas += window_area
                            
                            area = max(0.0, area - window_areas)
                        except Exception as e_sum:
                            pass
                            # Keep the area as-is if window subtraction fails

                    u_value = None
                    is_glazing_from_idf = surface.get("is_glazing", False)
                    is_glazing_from_csv = False
                    glazing_area_override = None
                    
                    surface_id_upper = surface_id.upper()
                    if not isinstance(surface_id, str):
                        pass
                        surface_id_upper = None

                    if surface_id_upper and surface_id_upper in self.glazing_data_from_csv:
                        glazing_details_csv = self.glazing_data_from_csv[surface_id_upper]

                        csv_construction_name = glazing_details_csv.get('Construction')
                        if csv_construction_name and csv_construction_name.lower() != construction_name.lower():
                            pass

                        u_value_from_glazing = glazing_details_csv.get('U-Value')
                        area_from_glazing = glazing_details_csv.get('Area')

                        if u_value_from_glazing is not None:
                            u_value = safe_float(u_value_from_glazing)
                        else:
                            pass
                            u_value = self._calculate_u_value(construction_name)

                        if area_from_glazing is not None:
                            glazing_area_override = safe_float(area_from_glazing)

                        is_glazing_from_csv = True
                    else:
                        u_value = self._calculate_u_value(construction_name)

                    surface_type = surface.get("surface_type", "wall")
                    is_glazing = is_glazing_from_csv or is_glazing_from_idf
                    boundary_condition = surface.get("boundary_condition", "unknown")
                                        

                    if construction_name not in self.areas_by_zone[zone_name]["constructions"]:
                        self.areas_by_zone[zone_name]["constructions"][construction_name] = {
                            "elements": [], "total_area": 0.0, "total_u_value": 0.0
                        }
                        if processed_surfaces <= 5:
                            pass

                    element_type_str = surface_type.capitalize()
                    if is_glazing:
                        is_external_boundary = False
                        base_surface_name = surface.get("base_surface")
                        if base_surface_name and base_surface_name in surfaces:
                            base_surface_data = surfaces.get(base_surface_name)
                            if base_surface_data:
                                obc = base_surface_data.get("boundary_condition")
                                if obc and isinstance(obc, str) and obc.lower() == "outdoors":
                                    is_external_boundary = True
                        element_type_str = "External Glazing" if is_external_boundary else "Internal Glazing"
                        

                    final_area = area
                    if is_glazing and glazing_area_override is not None and glazing_area_override > 0:
                        final_area = glazing_area_override
                    elif is_glazing:
                         pass

                    if final_area <= 0.0 and not is_glazing_from_csv:
                        continue

                    element_data = {
                        "zone": zone_name, "surface_name": surface_id, "element_type": element_type_str,
                        "area": final_area, "original_area": area, "u_value": u_value,
                        "area_u_value": final_area * u_value
                    }

                    constr_group = self.areas_by_zone[zone_name]["constructions"][construction_name]
                    constr_group["elements"].append(element_data)
                    constr_group["total_area"] += final_area
                    constr_group["total_u_value"] += final_area * u_value
                    
                    if processed_surfaces <= 5:
                        pass

                except (TypeError, ValueError, AttributeError, KeyError) as e_surf:
                    if processed_surfaces <= 5:
                        pass
                    continue
                    
            
            # Log construction summary for first few zones
            zones_logged = 0
            for zone_id, zone_data in self.areas_by_zone.items():
                if zones_logged < 3:
                    constructions = zone_data.get("constructions", {})
                    zones_logged += 1
                    
        except Exception as e:
            self.logger.error(f"Exception in _process_surfaces: {e}", exc_info=True)

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
                pass
                return default_properties

            construction_data = constructions[construction_name]
            material_layers = construction_data.get('material_layers', [])
            if not material_layers:
                pass
                return default_properties

            total_thickness = 0.0
            total_resistance = 0.0

            for layer_id in material_layers:
                if not layer_id or layer_id not in materials:
                    pass
                    continue

                material_data = materials[layer_id]
                try:
                    thickness = safe_float(material_data.get('thickness'), 0.0)
                    conductivity = safe_float(material_data.get('conductivity'), 0.0)
                    resistance = safe_float(material_data.get('thermal_resistance'), 0.0)

                    total_thickness += thickness
                    if resistance > 0:
                        total_resistance += resistance
                    elif conductivity > 0 and thickness > 0:
                        total_resistance += thickness / conductivity
                    else:
                        pass
                except (TypeError, ValueError) as e_mat:
                    pass
                    continue

            final_conductivity = total_thickness / total_resistance if total_resistance > 0 else 0.0

            return {
                'thickness': total_thickness,
                'conductivity': final_conductivity,
                'r_value': total_resistance
            }
        except (TypeError, ValueError, AttributeError, KeyError) as e:
            pass
            return default_properties
        except Exception as e_crit:
            pass
            return default_properties

    def _calculate_u_value(self, construction_name: str) -> float:
        """
        Calculate U-Value for a construction.
        Prioritizes direct U-Factor for simple glazing, then uses CSV if available,
        otherwise calculates based on layer resistance including film resistance.
        """
        try:

            constructions_opaque = self.data_loader.get_constructions()
            constructions_glazing = self.data_loader.get_constructions_glazing()
            all_constructions = {**constructions_opaque, **constructions_glazing}

            materials = self.data_loader.get_materials()
            surfaces = self.data_loader.get_surfaces()

            if not construction_name or construction_name not in all_constructions:
                pass
                return 0.0

            construction_data = all_constructions[construction_name]
            material_layers = construction_data.get('material_layers', [])

            if material_layers:
                first_layer_id = material_layers[0]
                if first_layer_id in materials:
                    first_material_data = materials[first_layer_id]
                    mat_type = first_material_data.get('type')
                    if mat_type == 'WindowMaterial:SimpleGlazingSystem':
                        u_factor = first_material_data.get('u_factor')
                        if u_factor is not None:
                            u_value_float = safe_float(u_factor, -1.0)
                            if u_value_float >= 0:
                                return u_value_float
                            else:
                                pass
                        else:
                             pass

            total_material_resistance = 0.0
            if not material_layers:
                 pass

            for layer_id in material_layers:
                if not layer_id or layer_id not in materials:
                    pass
                    continue

                material_data = materials[layer_id]
                try:
                    thickness = safe_float(material_data.get('thickness'), -1.0)
                    conductivity = safe_float(material_data.get('conductivity'), -1.0)
                    resistance = safe_float(material_data.get('thermal_resistance'), -1.0)

                    layer_r = 0.0
                    if resistance >= 0:
                        layer_r = resistance
                    elif thickness >= 0 and conductivity > 0:
                        layer_r = thickness / conductivity
                    else:
                        pass
                    total_material_resistance += layer_r
                except (TypeError, ValueError) as e_mat_calc:
                    pass
                    continue

            film_resistance = 0.0
            try:
                element_type_for_film = "Wall"
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
                    pass
            except Exception as e_film:
                pass

            r_value_with_film = total_material_resistance + film_resistance
            u_value = 1.0 / r_value_with_film if r_value_with_film > 0 else 0.0
            return u_value

        except (TypeError, ValueError, AttributeError, KeyError) as e:
            pass
            return 0.0
        except Exception as e_crit:
            pass
            return 0.0


    def _merge_reverse_constructions(self, materials_parser: MaterialsParser) -> None:
        """
        Merges constructions with '_rev' or '_reverse' suffixes into their base counterparts
        based on the same filtering logic as materials_parser._filter_element_data.
        Uses comprehensive comparison of element types, materials, and suffix priority.
        Sums total_area and total_u_value, combines elements, and removes duplicate entries.
        """
        try:
            if not self.areas_by_zone or not materials_parser:
                return

            surfaces = self.data_loader.get_surfaces()
            if not surfaces:
                return

            for zone_id, zone_data in self.areas_by_zone.items():
                try:
                    constructions = zone_data.get("constructions", {})
                    if not constructions:
                        continue

                    constructions_to_remove = []
                    processed_pairs = set()

                    for construction_id in list(constructions.keys()):
                        if construction_id in constructions_to_remove:
                            continue
                            
                        construction_id_lower = construction_id.lower()
                        base_name = None
                        
                        # Extract base name by removing suffix
                        if construction_id_lower.endswith('_reversed_rev'):
                            base_name = construction_id[:-len('_reversed_rev')]
                        elif construction_id_lower.endswith('_reversed'):
                            base_name = construction_id[:-len('_reversed')]
                        elif construction_id_lower.endswith('_rev'):
                            base_name = construction_id[:-len('_rev')]
                        else:
                            base_name = construction_id
                            
                        # Look for other constructions with the same base name but different suffixes
                        potential_matches = []
                        for other_id in constructions.keys():
                            if other_id == construction_id or other_id in constructions_to_remove:
                                continue
                                
                            other_id_lower = other_id.lower()
                            other_base_name = None
                            
                            if other_id_lower.endswith('_reversed_rev'):
                                other_base_name = other_id[:-len('_reversed_rev')]
                            elif other_id_lower.endswith('_reversed'):
                                other_base_name = other_id[:-len('_reversed')]
                            elif other_id_lower.endswith('_rev'):
                                other_base_name = other_id[:-len('_rev')]
                            else:
                                other_base_name = other_id
                            
                            if other_base_name and other_base_name.lower() == base_name.lower():
                                potential_matches.append(other_id)
                        
                        # Compare current construction with all potential matches
                        for match_id in potential_matches:
                            pair_key = tuple(sorted([construction_id, match_id]))
                            if pair_key in processed_pairs:
                                continue
                            processed_pairs.add(pair_key)
                            
                            construction1_data = constructions[construction_id]
                            construction2_data = constructions[match_id]
                            
                            # Skip glazing constructions
                            elements1 = construction1_data.get("elements", [])
                            elements2 = construction2_data.get("elements", [])
                            
                            has_glazing1 = any(elem.get("element_type", "").endswith("Glazing") for elem in elements1)
                            has_glazing2 = any(elem.get("element_type", "").endswith("Glazing") for elem in elements2)
                            
                            if has_glazing1 or has_glazing2:
                                continue
                            
                            # Compare element types using materials_parser logic
                            try:
                                types1, dont_use1 = materials_parser._get_element_type(construction_id, surfaces, {})
                                types2, dont_use2 = materials_parser._get_element_type(match_id, surfaces, {})
                                
                                if dont_use1 or dont_use2:
                                    continue
                                
                                # Convert to sets for comparison
                                type_set1 = set(types1)
                                type_set2 = set(types2)
                                
                                # Compare materials from constructions data
                                constructions_dict = self.data_loader.get_constructions()
                                materials1 = set()
                                materials2 = set()
                                
                                if construction_id in constructions_dict:
                                    materials1 = set(constructions_dict[construction_id].get('material_layers', []))
                                if match_id in constructions_dict:
                                    materials2 = set(constructions_dict[match_id].get('material_layers', []))
                                
                                # If same materials and one element type set is subset of the other, merge them
                                if materials1 == materials2 and (type_set1 == type_set2 or type_set1.issubset(type_set2) or type_set2.issubset(type_set1)):
                                    # Determine which one to remove using same priority logic as materials_parser
                                    to_remove = None
                                    
                                    construction_id_has_suffix = (construction_id.lower().endswith('_rev') or 
                                                                construction_id.lower().endswith('_reversed') or 
                                                                construction_id.lower().endswith('_reversed_rev'))
                                    match_id_has_suffix = (match_id.lower().endswith('_rev') or 
                                                         match_id.lower().endswith('_reversed') or 
                                                         match_id.lower().endswith('_reversed_rev'))
                                    
                                    # Priority 1: Keep the one with more element types (superset)
                                    if type_set1.issuperset(type_set2) and not type_set2.issuperset(type_set1):
                                        to_remove = match_id
                                    elif type_set2.issuperset(type_set1) and not type_set1.issuperset(type_set2):
                                        to_remove = construction_id
                                    # Priority 2: Keep base version (no suffix) over suffix version
                                    elif not construction_id_has_suffix and match_id_has_suffix:
                                        to_remove = match_id
                                    elif construction_id_has_suffix and not match_id_has_suffix:
                                        to_remove = construction_id
                                    # Priority 3: Both have suffixes, prefer _rev over _reversed
                                    elif construction_id_has_suffix and match_id_has_suffix:
                                        if construction_id.lower().endswith('_rev') and match_id.lower().endswith('_reversed'):
                                            to_remove = match_id
                                        elif construction_id.lower().endswith('_reversed') and match_id.lower().endswith('_rev'):
                                            to_remove = construction_id
                                        else:  # Both same suffix type, keep first alphabetically
                                            to_remove = max(construction_id, match_id)
                                    else:
                                        to_remove = max(construction_id, match_id)
                                    
                                    if to_remove and to_remove not in constructions_to_remove:
                                        # Merge the data before removing
                                        keep_id = match_id if to_remove == construction_id else construction_id
                                        remove_data = constructions[to_remove]
                                        keep_data = constructions[keep_id]
                                        
                                        # Sum the areas and u_values
                                        keep_data["total_area"] += remove_data.get("total_area", 0.0)
                                        keep_data["total_u_value"] += remove_data.get("total_u_value", 0.0)
                                        keep_data["elements"].extend(remove_data.get("elements", []))
                                        
                                        constructions_to_remove.append(to_remove)
                                        
                            except Exception as e_type:
                                pass
                    
                    # Remove the identified constructions after merging
                    for construction_id in constructions_to_remove:
                        if construction_id in constructions:
                            del constructions[construction_id]
                            
                except (TypeError, ValueError, AttributeError, KeyError) as e_zone_merge:
                    pass
                    continue
        except Exception as e:
            pass

    def get_areas_by_zone(self) -> Dict[str, Dict[str, Any]]:
        """
        Get the processed area data by zone.
        Returns an empty dictionary if not processed or if an error occurs.
        """
        if not self.processed:
            pass
            return {}
        try:
            return self.areas_by_zone
        except Exception as e:
            pass
            return {}

    def get_area_totals(self, floor_id: str) -> Dict[str, float]:
        """
        Get totals for a specific area (e.g., floor area, wall area, window area).
        Returns a dictionary with zeroed values if floor_id is not found or an error occurs.
        """
        result = {"total_floor_area": 0.0, "wall_area": 0.0, "window_area": 0.0}
        if not floor_id:
            pass
            return result
        if not self.processed:
            pass
            return result

        found_area = False
        try:
            for zone_id, zone_data in self.areas_by_zone.items():
                if zone_data.get("floor_id") != floor_id:
                    continue
                found_area = True

                zone_floor_area = safe_float(zone_data.get("floor_area", 0.0), 0.0)
                zone_multiplier = int(safe_float(zone_data.get("multiplier", 1), 1))
                zone_contribution = zone_floor_area * zone_multiplier
                result["total_floor_area"] += zone_contribution
                
                self.logger.debug(f"AREA TOTALS DEBUG - Zone {zone_id} (floor {floor_id}): floor_area={zone_floor_area}, multiplier={zone_multiplier}, contribution={zone_contribution}")

                for construction_name, construction_data in zone_data.get("constructions", {}).items():
                    try:
                        is_glazing_construction = any(
                            element.get("element_type", "").endswith("Glazing")
                            for element in construction_data.get("elements", [])
                        )
                        is_wall_construction = any(
                            "wall" in element.get("element_type", "").lower() and not element.get("element_type", "").endswith("Glazing")
                            for element in construction_data.get("elements", [])
                        )
                        
                        # Check specifically for external walls
                        is_external_wall_construction = any(
                            element.get("element_type", "").lower() == "wall" and 
                            any(surf.get("boundary_condition", "").lower() == "outdoors" 
                                for surf_id, surf in self.data_loader.get_surfaces().items() 
                                if surf.get("construction_name") == construction_name and surf_id == element.get("surface_name"))
                            for element in construction_data.get("elements", [])
                        )

                        construction_area = safe_float(construction_data.get("total_area", 0.0), 0.0)
                        
                        if is_glazing_construction:
                            result["window_area"] += construction_area
                        elif is_wall_construction:
                            result["wall_area"] += construction_area
                            if is_external_wall_construction:
                                pass
                            else:
                                pass
                    except (TypeError, AttributeError) as e_constr:
                        pass
                        continue

            return result
        except Exception as e:
            pass
            return result

    def get_area_table_data_by_individual_zones(self, materials_parser: Optional[MaterialsParser] = None) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get data for area reports with each zone as individual report (for office ISO).
        Returns data grouped by zone_id instead of floor_id.
        """
        result_by_zone: Dict[str, List[Dict[str, Any]]] = {}
        try:
            self.logger.info(f"INDIVIDUAL ZONES DEBUG - Starting get_area_table_data_by_individual_zones")
            parser_to_use = materials_parser if materials_parser else self.materials_parser
            if not parser_to_use:
                self.logger.warning(f"INDIVIDUAL ZONES DEBUG - No materials parser available")
                return result_by_zone
            if not self.processed:
                self.logger.warning(f"INDIVIDUAL ZONES DEBUG - Area parser not processed yet")
                return result_by_zone
            surfaces = self.data_loader.get_surfaces()
            if not self.areas_by_zone:
                self.logger.warning(f"INDIVIDUAL ZONES DEBUG - No areas_by_zone data available")
                return result_by_zone
            
            total_zones_to_process = len(self.areas_by_zone)
            self.logger.info(f"INDIVIDUAL ZONES DEBUG - Processing {total_zones_to_process} zones")
            
            zones_with_core = 0
            zones_without_constructions = 0
            zones_with_glazing_only = 0
            zones_with_zero_area = 0
            zones_successfully_processed = 0
            
            # Get HVAC zones from data loader for proper filtering
            hvac_zones = set(self.data_loader.get_hvac_zones())
            self.logger.info(f"INDIVIDUAL ZONES DEBUG - Found {len(hvac_zones)} HVAC zones for filtering")
            
            for zone_id, zone_data in self.areas_by_zone.items():
                try:
                    # Use proper HVAC zone filtering instead of name-based filtering
                    if zone_id not in hvac_zones:
                        zones_with_core += 1  # Reusing this counter for non-HVAC zones
                        # Check if it's one of our problematic zones
                        if zone_id in ["02XED:17XCR", "02XED:11XCR", "02XED:10XCR"]:
                            self.logger.error(f"INDIVIDUAL ZONES DEBUG - Problematic zone '{zone_id}' skipped - not in HVAC zones")
                        continue
                    
                    # For office ISO: each zone gets its own report
                    if zone_id not in result_by_zone:
                        result_by_zone[zone_id] = []
                        
                    zone_constructions_aggregated = {}
                    constructions_in_zone = zone_data.get("constructions", {})
                    
                    if not constructions_in_zone:
                        zones_without_constructions += 1
                        if zone_id in ["02XED:17XCR", "02XED:11XCR", "02XED:10XCR"]:
                            self.logger.error(f"INDIVIDUAL ZONES DEBUG - Problematic zone '{zone_id}' skipped due to no constructions")
                        continue

                    # Special debugging for problematic zones
                    if zone_id in ["02XED:17XCR", "02XED:11XCR", "02XED:10XCR"]:
                        self.logger.info(f"INDIVIDUAL ZONES DEBUG - Processing problematic zone '{zone_id}' with {len(constructions_in_zone)} constructions: {list(constructions_in_zone.keys())}")

                    for construction_name, construction_data in constructions_in_zone.items():
                        try:
                            # Filter surfaces to only include those from current zone for accurate element type detection
                            zone_surfaces = {k: v for k, v in surfaces.items() 
                                           if v.get('zone_name', '').lower() == zone_id.lower()}
                            determined_element_types, dont_use = parser_to_use._get_element_type(construction_name, zone_surfaces)
                            if dont_use or not determined_element_types:
                                continue

                            # Check if this construction is entirely glazing - if so, skip it completely
                            elements = construction_data.get("elements", [])
                            if not elements:
                                continue
                            
                            is_glazing_construction = True
                            for element in elements:
                                element_specific_type = element.get("element_type", "Unknown")
                                if not element_specific_type.endswith("Glazing"):
                                    is_glazing_construction = False
                                    break
                            
                            if is_glazing_construction:
                                continue

                            total_area_constr = safe_float(construction_data.get("total_area", 0.0), 0.0)
                            total_area_u_value_constr = safe_float(construction_data.get("total_u_value", 0.0), 0.0)

                            if total_area_constr <= 0.0:
                                continue

                            construction_u_value_avg = total_area_u_value_constr / total_area_constr if total_area_constr > 0 else 0.0
                            cleaned_construction_name = construction_name

                            primary_non_glazing_type = next((t for t in determined_element_types if t and "Glazing" not in t), "Unknown")

                            for element in elements:
                                try:
                                    element_area = safe_float(element.get("area", 0.0), 0.0)
                                    if element_area <= 0.0:
                                        continue

                                    element_specific_type = element.get("element_type", "Unknown")
                                    is_glazing_element = element_specific_type.endswith("Glazing")

                                    if is_glazing_element:
                                        continue

                                    display_element_type = primary_non_glazing_type
                                    zone_constr_key = f"{zone_id}_{cleaned_construction_name}_{display_element_type}"
                                    reported_u_value = construction_u_value_avg

                                    if zone_constr_key not in zone_constructions_aggregated:
                                        zone_constructions_aggregated[zone_constr_key] = {
                                            "zone": zone_id, "construction": cleaned_construction_name,
                                            "element_type": display_element_type, "area": 0.0,
                                            "u_value": reported_u_value,
                                            "area_loss": 0.0,
                                        }

                                    constr_agg = zone_constructions_aggregated[zone_constr_key]
                                    constr_agg["area"] += element_area
                                    constr_agg["area_loss"] += element_area * constr_agg["u_value"]

                                except (TypeError, ValueError, AttributeError, KeyError) as e_elem:
                                    continue

                        except (TypeError, ValueError, AttributeError, KeyError) as e_constr_proc:
                            continue

                    filtered_results = [entry for entry in zone_constructions_aggregated.values() if entry.get("area", 0.0) > 0.0]
                    if filtered_results:
                        result_by_zone[zone_id].extend(filtered_results)
                        zones_successfully_processed += 1
                    else:
                        zones_with_zero_area += 1
                        if zone_id in ["02XED:17XCR", "02XED:11XCR", "02XED:10XCR"]:
                            self.logger.error(f"INDIVIDUAL ZONES DEBUG - Problematic zone '{zone_id}' had zero area after processing")

                except (TypeError, ValueError, AttributeError, KeyError) as e_zone_proc:
                    self.logger.warning(f"INDIVIDUAL ZONES DEBUG - Error processing zone '{zone_id}': {e_zone_proc}")
                    continue

            # Final statistics logging
            self.logger.info(f"INDIVIDUAL ZONES DEBUG - Processing summary:")
            self.logger.info(f"INDIVIDUAL ZONES DEBUG - Total zones: {total_zones_to_process}")
            self.logger.info(f"INDIVIDUAL ZONES DEBUG - Non-HVAC zones (skipped): {zones_with_core}")
            self.logger.info(f"INDIVIDUAL ZONES DEBUG - Zones without constructions: {zones_without_constructions}")
            self.logger.info(f"INDIVIDUAL ZONES DEBUG - Zones with glazing only: {zones_with_glazing_only}")
            self.logger.info(f"INDIVIDUAL ZONES DEBUG - Zones with zero area: {zones_with_zero_area}")
            self.logger.info(f"INDIVIDUAL ZONES DEBUG - Zones successfully processed: {zones_successfully_processed}")
            self.logger.info(f"INDIVIDUAL ZONES DEBUG - Final result count: {len(result_by_zone)}")
            
            return result_by_zone
        except Exception as e:
            self.logger.error(f"INDIVIDUAL ZONES DEBUG - Exception in get_area_table_data_by_individual_zones: {e}", exc_info=True)
            return result_by_zone

    def get_area_table_data(self, materials_parser: Optional[MaterialsParser] = None) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get data for area reports in table format.
        Now excludes glazing elements - those are handled separately by get_glazing_table_data.
        Returns an empty dictionary if errors occur or prerequisites are not met.
        """
        result_by_area: Dict[str, List[Dict[str, Any]]] = {}
        try:
            parser_to_use = materials_parser if materials_parser else self.materials_parser
            if not parser_to_use:
                pass
                return result_by_area
            if not self.processed:
                pass
                return result_by_area

            surfaces = self.data_loader.get_surfaces()
            if not self.areas_by_zone:
                return result_by_area

            # Get HVAC zones for proper filtering
            hvac_zones = set(self.data_loader.get_hvac_zones())

            for zone_id, zone_data in self.areas_by_zone.items():
                try:
                    # Use proper HVAC zone filtering instead of name-based filtering
                    if zone_id not in hvac_zones:
                        continue
                    
                    floor_id = zone_data.get("floor_id", "unknown")

                    if floor_id not in result_by_area:
                        result_by_area[floor_id] = []

                    zone_constructions_aggregated = {}
                    constructions_in_zone = zone_data.get("constructions", {})
                    if not constructions_in_zone:
                        continue

                    for construction_name, construction_data in constructions_in_zone.items():
                        try:
                            # Filter surfaces to only include those from current zone for accurate element type detection
                            zone_surfaces = {k: v for k, v in surfaces.items() 
                                           if v.get('zone_name', '').lower() == zone_id.lower()}
                            determined_element_types, dont_use = parser_to_use._get_element_type(construction_name, zone_surfaces)
                            if dont_use or not determined_element_types:
                                continue

                            # Check if this construction is entirely glazing - if so, skip it completely
                            elements = construction_data.get("elements", [])
                            if not elements:
                                continue
                            
                            is_glazing_construction = True
                            for element in elements:
                                element_specific_type = element.get("element_type", "Unknown")
                                if not element_specific_type.endswith("Glazing"):
                                    is_glazing_construction = False
                                    break
                            
                            if is_glazing_construction:
                                continue

                            total_area_constr = safe_float(construction_data.get("total_area", 0.0), 0.0)
                            total_area_u_value_constr = safe_float(construction_data.get("total_u_value", 0.0), 0.0)

                            if total_area_constr <= 0.0:
                                continue

                            construction_u_value_avg = total_area_u_value_constr / total_area_constr if total_area_constr > 0 else 0.0
                            cleaned_construction_name = construction_name

                            primary_non_glazing_type = next((t for t in determined_element_types if t and "Glazing" not in t), "Unknown")

                            for element in elements:
                                try:
                                    element_area = safe_float(element.get("area", 0.0), 0.0)
                                    if element_area <= 0.0:
                                        continue

                                    element_specific_type = element.get("element_type", "Unknown")
                                    is_glazing_element = element_specific_type.endswith("Glazing")

                                    if is_glazing_element:
                                        continue

                                    display_element_type = primary_non_glazing_type
                                    zone_constr_key = f"{zone_id}_{cleaned_construction_name}_{display_element_type}"
                                    reported_u_value = construction_u_value_avg

                                    if zone_constr_key not in zone_constructions_aggregated:
                                        zone_constructions_aggregated[zone_constr_key] = {
                                            "zone": zone_id, "construction": cleaned_construction_name,
                                            "element_type": display_element_type, "area": 0.0,
                                            "u_value": reported_u_value,
                                            "area_loss": 0.0,
                                        }

                                    constr_agg = zone_constructions_aggregated[zone_constr_key]
                                    constr_agg["area"] += element_area
                                    constr_agg["area_loss"] += element_area * constr_agg["u_value"]

                                except (TypeError, ValueError, AttributeError, KeyError) as e_elem:
                                    pass
                                    continue

                        except (TypeError, ValueError, AttributeError, KeyError) as e_constr_proc:
                            pass
                            continue

                    filtered_results = [entry for entry in zone_constructions_aggregated.values() if entry.get("area", 0.0) > 0.0]
                    result_by_area[floor_id].extend(filtered_results)

                except (TypeError, ValueError, AttributeError, KeyError) as e_zone_proc:
                    pass
                    continue

            return result_by_area
        except Exception as e:
            pass
            return result_by_area

    def get_area_h_values(self) -> List[Dict[str, Any]]:
        """
        Calculates the H-Value for each area.
        Returns an empty list if errors occur or prerequisites are not met.
        """
        h_values_by_area: List[Dict[str, Any]] = []
        try:
            if not self.processed:
                pass
                return h_values_by_area
            if not self.materials_parser:
                pass
                return h_values_by_area

            area_data_for_h_calc = self.get_area_table_data()
            if not area_data_for_h_calc:
                pass
                return h_values_by_area

            area_floor_totals = {}
            # Get HVAC zones for proper filtering
            hvac_zones = set(self.data_loader.get_hvac_zones())
            
            for zone_id, zone_data in self.areas_by_zone.items():
                try:
                    # Use proper HVAC zone filtering instead of name-based filtering
                    if zone_id not in hvac_zones:
                        continue
                        
                    floor_id = zone_data.get("floor_id", "unknown")
                    if floor_id not in area_floor_totals:
                        area_floor_totals[floor_id] = 0.0
                    area_floor_totals[floor_id] += (
                        safe_float(zone_data.get("floor_area", 0.0), 0.0) *
                        int(safe_float(zone_data.get("multiplier", 1), 1))
                    )
                except (TypeError, ValueError) as e_floor_total:
                    pass

            from collections import defaultdict
            grouped_data = defaultdict(list)
            for floor_id_key, rows in area_data_for_h_calc.items():
                grouped_data[floor_id_key].extend(rows)

            external_keywords = ["external", "outside"]
            ground_keywords = ["ground", "slab on grade", "slab-on-grade"]
            roof_keywords = ["roof"]
            separation_keywords = ["separation"]
            floor_keywords = ["floor"]
            ceiling_keywords = ["ceiling"]

            for floor_id, rows_for_area in grouped_data.items():
                try:
                    total_floor_area = area_floor_totals.get(floor_id, 0.0)
                    if total_floor_area <= 0:
                        pass
                        continue

                    external_roof_loss_sum = 0.0
                    separation_loss_sum = 0.0
                    sum_ground_floor, sum_external_floor, sum_separation_floor, sum_intermediate_floor = 0.0, 0.0, 0.0, 0.0
                    sum_roof, sum_intermediate_ceiling, sum_separation_ceiling = 0.0, 0.0, 0.0

                    for row in rows_for_area:
                        try:
                            element_type = row.get('element_type', '').lower()
                            area = safe_float(row.get('area', 0.0), 0.0)
                            area_loss = safe_float(row.get('area_loss', 0.0), 0.0)

                            is_external_roof = any(keyword in element_type for keyword in external_keywords + roof_keywords)
                            is_separation = any(keyword in element_type for keyword in separation_keywords)

                            if is_external_roof:
                                external_roof_loss_sum += area_loss
                            elif is_separation:
                                separation_loss_sum += area_loss

                            if any(keyword in element_type for keyword in floor_keywords):
                                if any(keyword in element_type for keyword in ground_keywords): sum_ground_floor += area
                                elif any(keyword in element_type for keyword in external_keywords): sum_external_floor += area
                                elif any(keyword in element_type for keyword in separation_keywords): sum_separation_floor += area
                                else: sum_intermediate_floor += area
                            elif any(keyword in element_type for keyword in ceiling_keywords + roof_keywords):
                                if any(keyword in element_type for keyword in roof_keywords): sum_roof += area
                                elif any(keyword in element_type for keyword in separation_keywords): sum_separation_ceiling += area
                                else: sum_intermediate_ceiling += area
                        except (TypeError, ValueError, AttributeError) as e_row:
                            pass
                            continue

                    h_value = (external_roof_loss_sum + 0.5 * separation_loss_sum) / total_floor_area if total_floor_area > 0 else 0.0

                    group1_values = {"ground_floor": sum_ground_floor, "external_floor": sum_external_floor,
                                     "separation_floor": sum_separation_floor, "intermediate_floor": sum_intermediate_floor}
                    group2_values = {"roof": sum_roof, "intermediate_ceiling": sum_intermediate_ceiling,
                                     "separation_ceiling": sum_separation_ceiling}

                    # Default values
                    max_floor_type = "intermediate_floor"
                    max_ceiling_type = "intermediate_ceiling"
                    
                    # Calculate floor type with 60% threshold logic
                    if any(v > 0 for v in group1_values.values()):
                        # Sum all non-intermediate floor types
                        other_floor_sum = sum(v for k, v in group1_values.items() if k != "intermediate_floor")
                        if total_floor_area > 0 and (other_floor_sum / total_floor_area) > 0.6:
                            # Find dominant type among non-intermediate types
                            non_intermediate_floors = {k: v for k, v in group1_values.items() if k != "intermediate_floor" and v > 0}
                            if non_intermediate_floors:
                                max_floor_type = max(non_intermediate_floors, key=non_intermediate_floors.get)
                    
                    # Calculate ceiling type with 60% threshold logic
                    if any(v > 0 for v in group2_values.values()):
                        # Sum all non-intermediate ceiling types
                        other_ceiling_sum = sum(v for k, v in group2_values.items() if k != "intermediate_ceiling")
                        if total_floor_area > 0 and (other_ceiling_sum / total_floor_area) > 0.6:
                            # Find dominant type among non-intermediate types
                            non_intermediate_ceilings = {k: v for k, v in group2_values.items() if k != "intermediate_ceiling" and v > 0}
                            if non_intermediate_ceilings:
                                max_ceiling_type = max(non_intermediate_ceilings, key=non_intermediate_ceilings.get)

                    location = "Unknown"
                    if max_floor_type == "ground_floor":
                        if max_ceiling_type == "intermediate_ceiling": location = "Ground Floor & Intermediate ceiling"
                        elif max_ceiling_type == "roof": location = "Ground Floor & External ceiling"
                        elif max_ceiling_type == "separation_ceiling": location = "Ground Floor & Separation ceiling"
                    elif max_floor_type == "external_floor":
                        if max_ceiling_type == "roof": location = "External Floor & External ceiling"
                        elif max_ceiling_type == "intermediate_ceiling": location = "External Floor & Intermediate ceiling"
                        elif max_ceiling_type == "separation_ceiling": location = "External Floor & Separation ceiling"
                    elif max_floor_type == "intermediate_floor":
                         if max_ceiling_type == "intermediate_ceiling": location = "Intermediate Floor & Intermediate ceiling"
                         elif max_ceiling_type == "roof": location = "Intermediate Floor & External ceiling"
                         elif max_ceiling_type == "separation_ceiling": location = "Intermediate Floor & Separation ceiling"
                    elif max_floor_type == "separation_floor":
                         if max_ceiling_type == "intermediate_ceiling": location = "Separation Floor & Intermediate ceiling"
                         elif max_ceiling_type == "roof": location = "Separation Floor & External ceiling"
                         elif max_ceiling_type == "separation_ceiling": location = "Separation Floor & Separation ceiling"

                    h_values_by_area.append({
                        'floor_id': floor_id, 'location': location, 'h_value': h_value,
                        'total_floor_area': total_floor_area
                    })
                except (TypeError, ValueError, AttributeError, KeyError, ZeroDivisionError) as e_area_h:
                    pass
                    continue

            return h_values_by_area
        except Exception as e:
            pass
            return h_values_by_area

    def _extract_base_zone_id(self, zone_id: str) -> str:
        """
        Extract the base zone identifier for grouping related zones.
        For zones like '25:A338XLIV' and '25:A338XMMD', returns '25:A338'
        This groups zones that share the same floor, area, and zone number.
        """
        if ":" not in zone_id:
            return zone_id
        
        try:
            parts = zone_id.split(":", 1)
            if len(parts) < 2:
                return zone_id
                
            floor_part = parts[0]
            zone_part = parts[1]
            
            # Look for pattern like A338X where A338 is the base zone
            if "X" in zone_part:
                x_index = zone_part.find("X")
                base_zone_part = zone_part[:x_index]
                return f"{floor_part}:{base_zone_part}"
            
            return zone_id
        except Exception as e:
            pass
            return zone_id

    def _extract_floor_id_enhanced(self, zone_id: str) -> str:
        """
        Enhanced floor_id extraction using corrected grouping rules.
        
        Rules:
        - For A:BXC or A:B_C patterns: floor_id = group_key (A:B)
        - For A:B or A patterns: floor_id = zone_id (individual)
        """
        try:
            # Get the zone group key from DataLoader
            group_key = self.data_loader.get_zone_group_key(zone_id)
            
            # The group key is either zone_id (individual) or A:B (grouped)
            return group_key
                
        except Exception as e:
            # Fallback to original logic if there's any error
            if ":" not in zone_id:
                return "unknown"
            
            parts = zone_id.split(":", 1)
            if len(parts) < 2 or not parts[1]:
                return "unknown"
                
            zone_part = parts[1]
            
            # Handle patterns like A338X... where A338 should be the floor_id
            if "X" in zone_part:
                x_index = zone_part.find("X")
                area_candidate = zone_part[:x_index]
                if area_candidate and len(area_candidate) >= 2:
                    return area_candidate
            
            # Fallback to original logic
            if len(zone_part) >= 2 and zone_part[:2].isdigit():
                return zone_part[:2]
            elif zone_part:
                return zone_part
                
            return "unknown"

    def get_area_groupings_by_base_zone(self) -> Dict[str, List[str]]:
        """
        Get groupings of zones using new generalized grouping rules.
        Returns a dictionary where keys are group keys and values are lists of full zone IDs.
        Uses the new zone grouping logic from DataLoader.
        """
        if not self.processed:
            return {}
        
        try:
            base_zone_groupings = {}
            
            for zone_id, zone_data in self.areas_by_zone.items():
                # Use the new zone group key logic
                group_key = self.data_loader.get_zone_group_key(zone_id)
                
                if group_key not in base_zone_groupings:
                    base_zone_groupings[group_key] = []
                
                base_zone_groupings[group_key].append(zone_id)
            
            for group_key, zone_list in base_zone_groupings.items():
                pass
            
            return base_zone_groupings
        except Exception as e:
            pass
            return {}

    def get_area_table_data_by_base_zone(self, materials_parser: Optional[MaterialsParser] = None) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get data for area reports grouped by base zone ID instead of floor_id.
        Constructions are now merged per zone (not per area) using zone-specific merge keys.
        """
        result_by_base_zone: Dict[str, List[Dict[str, Any]]] = {}
        try:
            parser_to_use = materials_parser if materials_parser else self.materials_parser
            if not parser_to_use:
                pass
                return result_by_base_zone
            if not self.processed:
                pass
                return result_by_base_zone

            surfaces = self.data_loader.get_surfaces()
            if not self.areas_by_zone:
                return result_by_base_zone

            zones_processed = 0
            # Get HVAC zones for proper filtering
            hvac_zones = set(self.data_loader.get_hvac_zones())
            
            for zone_id, zone_data in self.areas_by_zone.items():
                try:
                    zones_processed += 1
                    floor_id = zone_data.get("floor_id", "unknown")
                    base_zone_id = zone_data.get("base_zone_id", zone_id)
                    
                    if zones_processed <= 3:
                        pass
                    
                    # Use proper HVAC zone filtering instead of name-based filtering
                    if zone_id not in hvac_zones:
                        if zones_processed <= 3:
                            pass
                        continue

                    if base_zone_id not in result_by_base_zone:
                        result_by_base_zone[base_zone_id] = []

                    zone_constructions_aggregated = {}
                    constructions_in_zone = zone_data.get("constructions", {})
                    
                    if zones_processed <= 3:
                        pass
                    
                    if not constructions_in_zone:
                        if zones_processed <= 3:
                            pass
                        continue

                    for construction_name, construction_data in constructions_in_zone.items():
                        try:
                            # Filter surfaces to only include those from current zone for accurate element type detection
                            zone_surfaces = {k: v for k, v in surfaces.items() 
                                           if v.get('zone_name', '').lower() == zone_id.lower()}
                            determined_element_types, dont_use = parser_to_use._get_element_type(construction_name, zone_surfaces)
                            if dont_use or not determined_element_types:
                                continue

                            # Check if this construction is entirely glazing - if so, skip it completely
                            elements = construction_data.get("elements", [])
                            if not elements:
                                continue
                            
                            is_glazing_construction = True
                            for element in elements:
                                element_specific_type = element.get("element_type", "Unknown")
                                if not element_specific_type.endswith("Glazing"):
                                    is_glazing_construction = False
                                    break
                            
                            if is_glazing_construction:
                                continue

                            total_area_constr = safe_float(construction_data.get("total_area", 0.0), 0.0)
                            total_area_u_value_constr = safe_float(construction_data.get("total_u_value", 0.0), 0.0)

                            if total_area_constr <= 0.0:
                                continue

                            construction_u_value_avg = total_area_u_value_constr / total_area_constr if total_area_constr > 0 else 0.0
                            cleaned_construction_name = construction_name

                            primary_non_glazing_type = next((t for t in determined_element_types if t and "Glazing" not in t), "Unknown")

                            for element in elements:
                                try:
                                    element_area = safe_float(element.get("area", 0.0), 0.0)
                                    if element_area <= 0.0:
                                        continue

                                    element_specific_type = element.get("element_type", "Unknown")
                                    is_glazing_element = element_specific_type.endswith("Glazing")

                                    if is_glazing_element:
                                        continue
                                        
                                    display_element_type = primary_non_glazing_type
                                    zone_constr_key = f"{zone_id}_{cleaned_construction_name}_{display_element_type}"
                                    reported_u_value = construction_u_value_avg

                                    if zone_constr_key not in zone_constructions_aggregated:
                                        zone_constructions_aggregated[zone_constr_key] = {
                                            "zone": zone_id, "construction": cleaned_construction_name,
                                            "element_type": display_element_type, "area": 0.0,
                                            "u_value": reported_u_value,
                                            "area_loss": 0.0,
                                        }

                                    zone_constructions_aggregated[zone_constr_key]["area"] += element_area
                                    zone_constructions_aggregated[zone_constr_key]["area_loss"] += element_area * reported_u_value

                                except (TypeError, ValueError) as e_element:
                                    pass
                                    continue

                        except (TypeError, ValueError, AttributeError) as e_constr:
                            pass
                            continue

                    for zone_constr_key, aggregated_data in zone_constructions_aggregated.items():
                        try:
                            aggregated_area = aggregated_data["area"]
                            aggregated_area_loss = aggregated_data["area_loss"]
                            
                            if aggregated_area <= 0:
                                continue

                            weighted_u_value = aggregated_area_loss / aggregated_area

                            final_row = {
                                "zone": aggregated_data["zone"],
                                "construction": aggregated_data["construction"],
                                "element_type": aggregated_data["element_type"],
                                "area": aggregated_area,
                                "u_value": aggregated_data["u_value"],
                                "weighted_u_value": weighted_u_value
                            }

                            # Check for existing row with same construction name, element type, and zone
                            merge_key = (final_row["construction"], final_row["element_type"], final_row["zone"])
                            existing_row = None
                            
                            for existing in result_by_base_zone[base_zone_id]:
                                existing_key = (existing["construction"], existing["element_type"], existing["zone"])
                                if existing_key == merge_key:
                                    existing_row = existing
                                    break
                            
                            if existing_row:
                                # Merge by summing areas and calculating weighted U-value
                                old_area = existing_row["area"]
                                new_area = aggregated_area
                                total_area = old_area + new_area
                                
                                # Calculate weighted average U-value based on areas
                                old_area_loss = old_area * existing_row["weighted_u_value"]
                                new_area_loss = new_area * weighted_u_value
                                total_area_loss = old_area_loss + new_area_loss
                                
                                existing_row["area"] = total_area
                                existing_row["weighted_u_value"] = total_area_loss / total_area if total_area > 0 else 0.0
                                
                            else:
                                # Add new row
                                result_by_base_zone[base_zone_id].append(final_row)
                        except (TypeError, ValueError) as e_final:
                            pass
                            continue

                except (TypeError, ValueError, AttributeError, KeyError) as e_zone:
                    pass
                    continue

            return result_by_base_zone
        except Exception as e:
            pass
            return result_by_base_zone

    def _get_shading_for_surface(self, surface_id: str) -> str:
        """
        Determine if a surface has shading and return the shading name.
        
        Args:
            surface_id: The surface/window ID to check for shading
            
        Returns:
            str: The shading name if found, "-" otherwise
        """
        try:
            window_shading_controls = self.data_loader.get_window_shading_controls()
            
            for control_id, control_data in window_shading_controls.items():
                window_names = control_data.get('window_names', [])
                
                # Check if this surface is controlled by this shading control
                if surface_id in window_names:
                    # Return the shading control name/ID as the shading name
                    if control_id:
                        return str(control_id)
                    else:
                        return "-"
            
            return "-"
        except Exception as e:
            pass
            return "-"

    def _get_zone_area_from_csv(self, zone_id: str) -> Optional[float]:
        """
        Get zone floor area from eplustbl.csv Zone Summary table.
        Handles zone name matching with spaces and different formats.
        
        Args:
            zone_id: The zone ID from IDF (e.g., "F01U01TZ", "01:10XOFFICE")
            
        Returns:
            Zone area in m2 or None if not found
        """
        if not self.zone_areas_from_csv:
            self.logger.debug(f"No CSV zone areas loaded for zone '{zone_id}'")
            return None
            
        self.logger.debug(f"Searching for zone '{zone_id}' in CSV data with {len(self.zone_areas_from_csv)} entries")
        
        # Log first few CSV zone names for comparison
        csv_zone_samples = list(self.zone_areas_from_csv.keys())[:5]
        self.logger.debug(f"Sample CSV zone names: {csv_zone_samples}")
        
        # Check if this specific zone exists in CSV (for debugging problematic cases)
        if zone_id == "02XED:17XCR":
            self.logger.info(f"SPECIFIC DEBUG - Looking for '{zone_id}' in CSV")
            if zone_id in self.zone_areas_from_csv:
                self.logger.info(f"SPECIFIC DEBUG - Found '{zone_id}' in CSV with area: {self.zone_areas_from_csv[zone_id]}")
            else:
                # Check if any similar zone exists
                similar_zones = [z for z in self.zone_areas_from_csv.keys() if "17XCR" in z]
                self.logger.info(f"SPECIFIC DEBUG - '{zone_id}' NOT found in CSV. Similar zones with '17XCR': {similar_zones}")
        
        try:
            # Try exact match first
            if zone_id in self.zone_areas_from_csv:
                area_data = self.zone_areas_from_csv[zone_id]
                area_value = safe_float(area_data.get('Area'))
                self.logger.debug(f"Found exact match for zone '{zone_id}': area = {area_value}")
                return area_value
            
            # Try case-insensitive match
            zone_id_lower = zone_id.lower()
            for csv_zone_name, area_data in self.zone_areas_from_csv.items():
                if csv_zone_name.lower() == zone_id_lower:
                    area_value = safe_float(area_data.get('Area'))
                    self.logger.debug(f"Found case-insensitive match for zone '{zone_id}' -> '{csv_zone_name}': area = {area_value}")
                    return area_value
            
            # Try containment matching (CSV zone contains IDF zone or vice versa)
            for csv_zone_name, area_data in self.zone_areas_from_csv.items():
                csv_zone_lower = csv_zone_name.lower().replace(' ', '').replace('_', '').replace('-', '')
                idf_zone_lower = zone_id.lower().replace(' ', '').replace('_', '').replace('-', '').replace(':', '')
                
                # Check if the cleaned names match
                if csv_zone_lower == idf_zone_lower:
                    area_value = safe_float(area_data.get('Area'))
                    self.logger.debug(f"Found cleaned name match for zone '{zone_id}' -> '{csv_zone_name}': area = {area_value}")
                    return area_value
                
                # Check containment in both directions
                if csv_zone_lower in idf_zone_lower or idf_zone_lower in csv_zone_lower:
                    area_value = safe_float(area_data.get('Area'))
                    self.logger.debug(f"Found containment match for zone '{zone_id}' -> '{csv_zone_name}': area = {area_value}")
                    return area_value
            
            self.logger.warning(f"No zone area match found for '{zone_id}' in CSV data. Available zones: {list(self.zone_areas_from_csv.keys())[:5]}...")
            return None
        except Exception as e:
            self.logger.warning(f"Error getting zone area from CSV for zone {zone_id}: {e}")
            return None
    
    def _get_zone_multiplier_from_csv(self, zone_id: str) -> Optional[float]:
        """
        Get zone multiplier from eplustbl.csv Zone Summary table.
        
        Args:
            zone_id: The zone ID from IDF
            
        Returns:
            Zone multiplier or None if not found
        """
        if not self.zone_areas_from_csv:
            return None
            
        try:
            # Use same matching logic as _get_zone_area_from_csv
            # Try exact match first
            if zone_id in self.zone_areas_from_csv:
                area_data = self.zone_areas_from_csv[zone_id]
                return safe_float(area_data.get('Multiplier'), 1.0)
            
            # Try case-insensitive match
            zone_id_lower = zone_id.lower()
            for csv_zone_name, area_data in self.zone_areas_from_csv.items():
                if csv_zone_name.lower() == zone_id_lower:
                    return safe_float(area_data.get('Multiplier'), 1.0)
            
            # Try containment matching
            for csv_zone_name, area_data in self.zone_areas_from_csv.items():
                csv_zone_lower = csv_zone_name.lower().replace(' ', '').replace('_', '').replace('-', '')
                idf_zone_lower = zone_id.lower().replace(' ', '').replace('_', '').replace('-', '').replace(':', '')
                
                if csv_zone_lower == idf_zone_lower:
                    return safe_float(area_data.get('Multiplier'), 1.0)
                
                if csv_zone_lower in idf_zone_lower or idf_zone_lower in csv_zone_lower:
                    return safe_float(area_data.get('Multiplier'), 1.0)
            
            return None
        except Exception as e:
            self.logger.warning(f"Error getting zone multiplier from CSV for zone {zone_id}: {e}")
            return None

    def _is_window_for_wall(self, window_name_upper: str, wall_name_upper: str) -> bool:
        """
        Check if a window belongs to a wall based on naming patterns.
        
        Examples:
        - Wall: 02:10XOFFICE_Wall_2_0_0
        - Windows: 02:10XOFFICE_WALL_2_0_0_0_0_10_WIN, 02:10XOFFICE_WALL_2_0_0_1_0_9_WIN, etc.
        
        Args:
            window_name_upper: Window name in uppercase
            wall_name_upper: Wall name in uppercase
            
        Returns:
            True if window belongs to the wall
        """
        try:
            # Convert wall name to expected window prefix format
            # 02:10XOFFICE_Wall_2_0_0 -> 02:10XOFFICE_WALL_2_0_0_
            wall_prefix = wall_name_upper.replace("_WALL_", "_WALL_").replace("_Wall_", "_WALL_")
            if not "_WALL_" in wall_prefix:
                return False
                
            # Check if window name starts with the wall prefix pattern
            expected_prefix = wall_prefix + "_"
            if window_name_upper.startswith(expected_prefix) and "_WIN" in window_name_upper:
                # Additional validation: ensure it ends with _WIN
                return window_name_upper.endswith("_WIN")
                
            return False
        except Exception as e:
            return False

    def get_glazing_table_data(self, materials_parser: Optional[MaterialsParser] = None) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get data for glazing reports in table format, separate from main area data.
        Includes shading information for each glazing element.
        
        Returns:
            Dict[str, List[Dict[str, Any]]]: Dictionary with floor_id as keys and lists of glazing data as values
        """
        result_by_area: Dict[str, List[Dict[str, Any]]] = {}
        try:
            parser_to_use = materials_parser if materials_parser else self.materials_parser
            if not parser_to_use:
                pass
                return result_by_area
            if not self.processed:
                pass
                return result_by_area

            surfaces = self.data_loader.get_surfaces()
            if not self.areas_by_zone:
                return result_by_area

            # Get HVAC zones for proper filtering
            hvac_zones = set(self.data_loader.get_hvac_zones())

            for zone_id, zone_data in self.areas_by_zone.items():
                try:
                    # Use proper HVAC zone filtering instead of name-based filtering
                    if zone_id not in hvac_zones:
                        continue
                        
                    floor_id = zone_data.get("floor_id", "unknown")

                    if floor_id not in result_by_area:
                        result_by_area[floor_id] = []

                    constructions_in_zone = zone_data.get("constructions", {})
                    if not constructions_in_zone:
                        continue

                    for construction_name, construction_data in constructions_in_zone.items():
                        try:
                            # Filter surfaces to only include those from current zone for accurate element type detection
                            zone_surfaces = {k: v for k, v in surfaces.items() 
                                           if v.get('zone_name', '').lower() == zone_id.lower()}
                            determined_element_types, dont_use = parser_to_use._get_element_type(construction_name, zone_surfaces)
                            if dont_use or not determined_element_types:
                                continue

                            elements = construction_data.get("elements", [])
                            if not elements:
                                continue

                            # Only process glazing elements
                            for element in elements:
                                try:
                                    element_area = safe_float(element.get("area", 0.0), 0.0)
                                    if element_area <= 0.0:
                                        continue

                                    element_specific_type = element.get("element_type", "Unknown")
                                    element_u_value = safe_float(element.get("u_value", 0.0), 0.0)
                                    element_surface_name = element.get("surface_name", "unknown_surface")

                                    # Only include glazing elements
                                    is_glazing_element = element_specific_type.endswith("Glazing")
                                    if not is_glazing_element:
                                        continue

                                    # Get shading information for this glazing element
                                    shading_info = self._get_shading_for_surface(element_surface_name)

                                    # Create merge key based on construction name, type, u-value, and shading
                                    merge_key = (construction_name, element_specific_type, element_u_value, shading_info)
                                    
                                    # Check if we already have an entry with the same merge criteria
                                    existing_entry = None
                                    for glazing_entry in result_by_area[floor_id]:
                                        entry_key = (
                                            glazing_entry["construction"],
                                            glazing_entry["element_type"],
                                            glazing_entry["u_value"],
                                            glazing_entry["shading"]
                                        )
                                        if entry_key == merge_key:
                                            existing_entry = glazing_entry
                                            break
                                    
                                    if existing_entry:
                                        # Merge by summing the area
                                        existing_entry["area"] += element_area
                                    else:
                                        # Create new entry
                                        glazing_row = {
                                            "zone": zone_id,
                                            "construction": construction_name,
                                            "element_type": element_specific_type,
                                            "area": element_area,
                                            "u_value": element_u_value,
                                            "shading": shading_info
                                        }
                                        result_by_area[floor_id].append(glazing_row)

                                except (TypeError, ValueError, AttributeError, KeyError) as e_elem:
                                    pass
                                    continue

                        except (TypeError, ValueError, AttributeError, KeyError) as e_constr_proc:
                            pass
                            continue

                except (TypeError, ValueError, AttributeError, KeyError) as e_zone_proc:
                    pass
                    continue

            return result_by_area
        except Exception as e:
            pass
            return result_by_area

    def _get_zone_area_from_csv(self, zone_id: str) -> Optional[float]:
        """
        Get zone floor area from CSV data loaded during initialization.
        
        Args:
            zone_id: Zone identifier to look up
            
        Returns:
            Zone floor area from CSV, or None if not found
        """
        if not hasattr(self, 'zone_areas_from_csv') or not self.zone_areas_from_csv:
            self.logger.debug(f"No CSV zone data available for lookup of '{zone_id}'")
            return None
            
        # Direct lookup first
        if zone_id in self.zone_areas_from_csv:
            area = safe_float(self.zone_areas_from_csv[zone_id].get('area', 0))
            self.logger.debug(f"Found CSV area for zone '{zone_id}': {area} m²")
            return area
            
        # Log available zones for debugging
        available_zones = list(self.zone_areas_from_csv.keys())[:5]
        self.logger.debug(f"Zone '{zone_id}' not found in CSV. Available zones: {available_zones}...")
        return None

    def _get_zone_multiplier_from_csv(self, zone_id: str) -> Optional[int]:
        """
        Get zone multiplier from CSV data loaded during initialization.
        
        Args:
            zone_id: Zone identifier to look up
            
        Returns:
            Zone multiplier from CSV, or None if not found
        """
        if not hasattr(self, 'zone_areas_from_csv') or not self.zone_areas_from_csv:
            return None
            
        if zone_id in self.zone_areas_from_csv:
            multiplier = int(safe_float(self.zone_areas_from_csv[zone_id].get('multiplier', 1), 1))
            self.logger.debug(f"Found CSV multiplier for zone '{zone_id}': {multiplier}")
            return multiplier
            
        return None
    
