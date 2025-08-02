"""
Extracts and processes area information including floor areas and material properties.
"""
from typing import Dict, Any, List, Optional
from parsers.materials_parser import MaterialsParser
from utils.data_loader import safe_float
from parsers.eplustbl_reader import read_glazing_data_from_csv

class AreaParser:
    """
    Processes area information from IDF files, including distribution of zones in areas.
    Uses cached data from DataLoader for efficient access.
    """
    def __init__(self, data_loader, materials_parser: MaterialsParser, csv_path: Optional[str] = None):
        self.data_loader = data_loader
        try:
            self.glazing_data_from_csv = read_glazing_data_from_csv(csv_path)
            if self.glazing_data_from_csv:
                pass
            else:
                pass
        except FileNotFoundError:
            pass
            self.glazing_data_from_csv = {}
        except (ValueError, RuntimeError) as e:
            pass
            self.glazing_data_from_csv = {}
        except Exception as e:
            pass
            self.glazing_data_from_csv = {}
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
            pass
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
        except ValueError as ve:
            pass
            raise
        except KeyError as ke:
            pass
            raise
        except Exception as e:
            pass
            raise

    def _process_zones(self) -> None:
        """
        Process zones to initialize the data structure.
        """
        try:
            zones = self.data_loader.get_zones()
            if not zones:
                pass
                return

            for zone_id, zone_data in zones.items():
                try:
                    if not zone_id:
                        pass
                        continue

                    # Use enhanced area_id extraction for better grouping
                    area_id = self._extract_area_id_enhanced(zone_id)
                    
                    # Also extract base zone ID for potential grouping
                    base_zone_id = self._extract_base_zone_id(zone_id)

                    floor_area = safe_float(zone_data.get("floor_area"))
                    multiplier = int(safe_float(zone_data.get("multiplier"), 1))

                    self.areas_by_zone[zone_id] = {
                        "area_id": area_id,
                        "base_zone_id": base_zone_id,
                        "floor_area": floor_area,
                        "multiplier": multiplier,
                        "constructions": {}
                    }
                except (TypeError, ValueError, AttributeError) as e_inner:
                    pass
                    continue
        except Exception as e:
            pass

    def _process_surfaces(self) -> None:
        """
        Process surfaces to extract construction and area information.
        """
        try:
            surfaces = self.data_loader.get_surfaces()
            if not surfaces:
                pass
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
                    pass

            for surface_id, surface in surfaces.items():
                try:
                    zone_name = surface.get("zone_name")
                    if not zone_name or zone_name not in self.areas_by_zone:
                        continue

                    construction_name = surface.get("construction_name")
                    if not construction_name:
                        continue

                    original_area = safe_float(surface.get("area"))
                    if original_area is None or original_area <= 0.0:
                        continue

                    area = original_area
                    if not surface.get("is_glazing", False) and surface_id in windows_by_base_surface:
                        try:
                            window_areas = sum(w.get("area", 0.0) for w in windows_by_base_surface.get(surface_id, []))
                            area = max(0.0, original_area - window_areas)
                        except Exception as e_sum:
                            pass
                            area = original_area

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

                    if construction_name not in self.areas_by_zone[zone_name]["constructions"]:
                        self.areas_by_zone[zone_name]["constructions"][construction_name] = {
                            "elements": [], "total_area": 0.0, "total_u_value": 0.0
                        }

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
                        "area": final_area, "original_area": original_area, "u_value": u_value,
                        "area_u_value": final_area * u_value
                    }

                    constr_group = self.areas_by_zone[zone_name]["constructions"][construction_name]
                    constr_group["elements"].append(element_data)
                    constr_group["total_area"] += final_area
                    constr_group["total_u_value"] += final_area * u_value

                except (TypeError, ValueError, AttributeError, KeyError) as e_surf:
                    pass
                    continue
        except Exception as e:
            pass

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
        ONLY IF they share the exact same set of element types determined by MaterialsParser.
        Sums total_area and total_u_value, combines elements, and removes the reverse entry.
        Important: Glazing constructions (identified by CSV or element type) are not merged.
        """
        try:
            surfaces = self.data_loader.get_surfaces()
            if not self.areas_by_zone:
                return

            for zone_id, zone_data in self.areas_by_zone.items():
                try:
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

                            if base_name in self.glazing_data_from_csv or reverse_name in self.glazing_data_from_csv:
                                continue

                            base_elements = constructions.get(base_name, {}).get("elements", [])
                            reverse_elements = constructions.get(reverse_name, {}).get("elements", [])

                            has_base_glazing_element = any(
                                element.get("element_type", "").endswith("Glazing") for element in base_elements
                            )
                            has_reverse_glazing_element = any(
                                element.get("element_type", "").endswith("Glazing") for element in reverse_elements
                            )
                            if has_base_glazing_element or has_reverse_glazing_element:
                                continue

                            try:
                                base_types_list, base_dont_use = materials_parser._get_element_type(base_name, surfaces)
                                reverse_types_list, reverse_dont_use = materials_parser._get_element_type(reverse_name, surfaces)

                                if base_dont_use or reverse_dont_use:
                                    continue

                                base_types_set = set(bt for bt in base_types_list if bt and "Glazing" not in bt)
                                reverse_types_set = set(rt for rt in reverse_types_list if rt and "Glazing" not in rt)

                                if base_types_set and base_types_set == reverse_types_set:
                                    base_constr = constructions[base_name]
                                    reverse_constr = constructions[reverse_name]

                                    base_constr["total_area"] += reverse_constr.get("total_area", 0.0)
                                    base_constr["total_u_value"] += reverse_constr.get("total_u_value", 0.0)
                                    base_constr["elements"].extend(reverse_constr.get("elements", []))
                                    to_remove.append(reverse_name)
                                else:
                                    pass

                            except Exception as e_type:
                                pass

                    for key_to_remove in to_remove:
                        if key_to_remove in constructions:
                            del constructions[key_to_remove]

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

    def get_area_totals(self, area_id: str) -> Dict[str, float]:
        """
        Get totals for a specific area (e.g., floor area, wall area, window area).
        Returns a dictionary with zeroed values if area_id is not found or an error occurs.
        """
        result = {"total_floor_area": 0.0, "wall_area": 0.0, "window_area": 0.0}
        if not area_id:
            pass
            return result
        if not self.processed:
            pass
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
                        elif is_wall_construction:
                            result["wall_area"] += safe_float(construction_data.get("total_area", 0.0), 0.0)
                    except (TypeError, AttributeError) as e_constr:
                        pass
                        continue

            if not found_area:
                pass
            return result
        except Exception as e:
            pass
            return result

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

            for zone_id, zone_data in self.areas_by_zone.items():
                try:
                    area_id = zone_data.get("area_id", "unknown")
                    if "core" in area_id.lower():
                        continue

                    if area_id not in result_by_area:
                        result_by_area[area_id] = []

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
                    result_by_area[area_id].extend(filtered_results)

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
            for zone_id, zone_data in self.areas_by_zone.items():
                try:
                    area_id = zone_data.get("area_id", "unknown")
                    if "core" in area_id.lower():
                        continue
                    if area_id not in area_floor_totals:
                        area_floor_totals[area_id] = 0.0
                    area_floor_totals[area_id] += (
                        safe_float(zone_data.get("floor_area", 0.0), 0.0) *
                        int(safe_float(zone_data.get("multiplier", 1), 1))
                    )
                except (TypeError, ValueError) as e_floor_total:
                    pass

            from collections import defaultdict
            grouped_data = defaultdict(list)
            for area_id_key, rows in area_data_for_h_calc.items():
                grouped_data[area_id_key].extend(rows)

            external_keywords = ["external", "outside"]
            ground_keywords = ["ground", "slab on grade", "slab-on-grade"]
            roof_keywords = ["roof"]
            separation_keywords = ["separation"]
            floor_keywords = ["floor"]
            ceiling_keywords = ["ceiling"]

            for area_id, rows_for_area in grouped_data.items():
                try:
                    total_floor_area = area_floor_totals.get(area_id, 0.0)
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
                        'area_id': area_id, 'location': location, 'h_value': h_value,
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

    def _extract_area_id_enhanced(self, zone_id: str) -> str:
        """
        Enhanced area_id extraction that handles various zone naming patterns.
        For zones like '25:A338XLIV', extracts 'A338' as the area_id.
        """
        if ":" not in zone_id:
            return "unknown"
        
        try:
            parts = zone_id.split(":", 1)
            if len(parts) < 2 or not parts[1]:
                return "unknown"
                
            zone_part = parts[1]
            
            # Handle patterns like A338X... where A338 should be the area_id
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
        except Exception as e:
            pass
            return "unknown"

    def get_area_groupings_by_base_zone(self) -> Dict[str, List[str]]:
        """
        Get groupings of zones by their base zone identifier.
        Returns a dictionary where keys are base zone IDs and values are lists of full zone IDs.
        This ensures zones like '25:A338XLIV' and '25:A338XMMD' are grouped together under '25:A338'.
        """
        if not self.processed:
            pass
            return {}
        
        try:
            base_zone_groupings = {}
            
            for zone_id, zone_data in self.areas_by_zone.items():
                base_zone_id = zone_data.get("base_zone_id", zone_id)
                
                if base_zone_id not in base_zone_groupings:
                    base_zone_groupings[base_zone_id] = []
                
                base_zone_groupings[base_zone_id].append(zone_id)
            
            pass
            
            return base_zone_groupings
        except Exception as e:
            pass
            return {}

    def get_area_table_data_by_base_zone(self, materials_parser: Optional[MaterialsParser] = None) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get data for area reports grouped by base zone ID instead of area_id.
        This ensures zones like '25:A338XLIV' and '25:A338XMMD' are in the same report.
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

            for zone_id, zone_data in self.areas_by_zone.items():
                try:
                    area_id = zone_data.get("area_id", "unknown")
                    base_zone_id = zone_data.get("base_zone_id", zone_id)
                    
                    if "core" in area_id.lower():
                        continue

                    if base_zone_id not in result_by_base_zone:
                        result_by_base_zone[base_zone_id] = []

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

    def get_glazing_table_data(self, materials_parser: Optional[MaterialsParser] = None) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get data for glazing reports in table format, separate from main area data.
        Includes shading information for each glazing element.
        
        Returns:
            Dict[str, List[Dict[str, Any]]]: Dictionary with area_id as keys and lists of glazing data as values
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

            for zone_id, zone_data in self.areas_by_zone.items():
                try:
                    area_id = zone_data.get("area_id", "unknown")
                    if "core" in area_id.lower():
                        continue

                    if area_id not in result_by_area:
                        result_by_area[area_id] = []

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
                                    for glazing_entry in result_by_area[area_id]:
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
                                        result_by_area[area_id].append(glazing_row)

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
