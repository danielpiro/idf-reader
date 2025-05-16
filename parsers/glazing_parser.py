import csv
import os
from typing import Dict, Any

def safe_float(value: Any, default: float = 0.0) -> float:
    """
    Safely convert a value to float, returning a default if conversion fails.
    Handles numpy float types by converting them to Python floats.

    Args:
        value: Value to convert to float
        default: Default value to return if conversion fails

    Returns:
        float: Converted value or default
    """
    if value is None or value == '':
        return default

    try:
        if hasattr(value, 'item'):
            return float(value.item())
        return float(value)
    except (ValueError, TypeError, AttributeError):
        return default

class GlazingParser:
    """
    Parses glazing-related data from IDF caches and simulation output.
    """
    def __init__(self,
                 constructions_glazing_cache: Dict[str, Dict[str, Any]],
                 window_simple_glazing_cache: Dict[str, Dict[str, Any]],
                 window_glazing_cache: Dict[str, Dict[str, Any]],
                 window_gas_cache: Dict[str, Dict[str, Any]],
                 window_shade_cache: Dict[str, Dict[str, Any]],
                 window_shading_control_cache: Dict[str, Dict[str, Any]],
                 windows_cache: Dict[str, Dict[str, Any]],
                 simulation_output_csv: str = None,
                 idf_objects: Any = None,
                 frame_divider_cache: Dict[str, Dict[str, Any]] = None):
        self._constructions_glazing_cache = constructions_glazing_cache
        self._window_simple_glazing_cache = window_simple_glazing_cache
        self._window_glazing_cache = window_glazing_cache
        self._window_gas_cache = window_gas_cache
        self._window_shade_cache = window_shade_cache
        self._window_shading_control_cache = window_shading_control_cache
        self._windows_cache = windows_cache
        self._frame_divider_cache = frame_divider_cache if frame_divider_cache is not None else {}
        self._simulation_output_csv = simulation_output_csv
        self._sim_properties = {}
        self._idf = idf_objects
        self.parsed_glazing_data = {}

    def _parse_simulation_output_csv(self):
        """Parses the eplustbl.csv file to extract window properties from the 'Exterior Fenestration' table."""
        if not self._simulation_output_csv or not os.path.exists(self._simulation_output_csv):
            return

        self._sim_properties = {}
        try:
            with open(self._simulation_output_csv, 'r', encoding='utf-8', errors='ignore') as csvfile:
                reader = csv.reader(csvfile)
                in_target_table = False
                headers_found = False
                header_map = {
                    "construction": 1,
                    "area of multiplied openings [m2]": 6,
                    "glass u-factor [w/m2-k]": 7,
                    "glass shgc": 8,
                    "glass visible transmittance": 9
                }
                col_indices = {}

                for row in reader:
                    if not row or not any(field.strip() for field in row): continue

                    if not in_target_table and row[0].strip().lower() == "exterior fenestration":
                        in_target_table = True
                        headers_found = False
                        col_indices = {}
                        continue

                    if in_target_table:
                        if not headers_found:
                            current_headers_norm = [h.strip().lower() for h in row]
                            if "construction" in current_headers_norm and "glass u-factor [w/m2-k]" in current_headers_norm:
                                try:
                                    for key, _ in header_map.items():
                                        if key in current_headers_norm:
                                            actual_index = current_headers_norm.index(key)
                                            col_indices[key] = actual_index
                                        else:
                                            raise ValueError(f"Missing required header: '{key}'")

                                    if len(col_indices) != len(header_map):
                                        missing = set(header_map.keys()) - set(col_indices.keys())
                                        raise ValueError(f"Missing required headers: {missing}")

                                    headers_found = True
                                except ValueError as e:
                                    in_target_table = False
                                continue
                            else:
                                continue

                        else:
                            is_total_row = row[0].strip().lower().endswith("total or average")
                            is_blank_data_row = not row[0].strip() and (len(row) < 2 or not row[1].strip())

                            if is_total_row or is_blank_data_row:
                                in_target_table = False
                                continue

                            max_index = max(col_indices.values()) if col_indices else -1
                            if max_index == -1:
                                in_target_table = False
                                continue

                            if len(row) > max_index:
                                try:
                                    construction_name = row[col_indices["construction"]].strip()
                                    u_value = safe_float(row[col_indices["glass u-factor [w/m2-k]"]])
                                    shgc = safe_float(row[col_indices["glass shgc"]])
                                    vt = safe_float(row[col_indices["glass visible transmittance"]])
                                    area = safe_float(row[col_indices["area of multiplied openings [m2]"]])

                                    if construction_name:
                                        if construction_name not in self._sim_properties:
                                            self._sim_properties[construction_name] = {
                                                'U-Value': u_value,
                                                'SHGC': shgc,
                                                'VT': vt,
                                                'Area': area
                                            }
                                except Exception:
                                    continue

        except Exception as e:
            raise RuntimeError(f"Error parsing simulation output CSV: {e}")

    def _transfer_shades_based_on_naming(self, processed_data: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Identifies pairs of constructions (base vs. shaded) based on naming convention,
        transfers shading layers to the base, and removes the shaded version.
        Example pairs: 'xxx - 1001' (base) and 'xxx - 2001' (shaded)
                       'yyy - 4444' (base) and 'yyy - 6666' (shaded)
        """

        try:
            constructions_with_shades = {
                cid: data for cid, data in processed_data.items() if data.get('shading_layers')
            }
            constructions_without_shades = {
                cid: data for cid, data in processed_data.items() if not data.get('shading_layers')
            }

            keys_to_remove = set()

            for base_id, base_data in constructions_without_shades.items():
                try:
                    base_prefix, base_suffix = base_id.rsplit(' - ', 1)
                except ValueError:
                    continue

                for shade_id, shade_data in constructions_with_shades.items():
                    if shade_id in keys_to_remove or shade_id == base_id:
                        continue

                    try:
                        shade_prefix, shade_suffix = shade_id.rsplit(' - ', 1)
                    except ValueError:
                        continue

                    if base_prefix == shade_prefix:
                        try:
                            is_base_pattern = base_suffix.startswith('1') and len(base_suffix) == 4 and base_suffix.isdigit()
                            is_shade_pattern = shade_suffix.startswith('2') and len(shade_suffix) == 4 and shade_suffix.isdigit()

                            if is_base_pattern and is_shade_pattern:
                                pass
                            else:
                                continue

                        except Exception as suffix_check_error:
                            continue

                        shades_to_transfer = shade_data.get('shading_layers', [])
                        if shades_to_transfer:
                            if 'shading_layers' not in base_data:
                                 base_data['shading_layers'] = []

                            existing_base_shades = {s['Name'] for s in base_data['shading_layers']}
                            added_count = 0
                            for shade_info in shades_to_transfer:
                                 if shade_info['Name'] not in existing_base_shades:
                                     base_data['shading_layers'].append(shade_info)
                                     added_count += 1

                            if added_count > 0:
                                keys_to_remove.add(shade_id)
                                break
                        else:
                             pass

            final_data = processed_data.copy()
            removed_count = 0
            for key in keys_to_remove:
                if key in final_data:
                    del final_data[key]
                    removed_count += 1

            return final_data

        except Exception as e_transfer:
            raise RuntimeError(f"Error transferring shades based on naming: {e_transfer}")

    def parse_glazing_data(self) -> Dict[str, Dict[str, Any]]:
        """
        Processes the cached glazing constructions to extract detailed data,
        incorporating properties from the simulation output CSV if available.
        Populates self.parsed_glazing_data.
        """
        self._parse_simulation_output_csv()
        self._sim_properties_lower = {k.lower(): v for k, v in self._sim_properties.items()}

        processed_data = {}

        for construction_id, construction_data in self._constructions_glazing_cache.items():
            material_layers = construction_data.get('material_layers', [])
            if not material_layers:
                continue

            first_layer_name = material_layers[0]
            if first_layer_name in self._window_simple_glazing_cache:
                simple_data = self._window_simple_glazing_cache[first_layer_name]
                processed_data[construction_id] = {
                    'id': construction_id,
                    'name': construction_id,
                    'type': 'Simple',
                    'system_details': {
                        'Name': construction_id,
                        'Type': 'Simple Glazing',
                        'Thickness': None,
                        'U-Value': simple_data.get('u_factor'),
                        'VT': simple_data.get('visible_transmittance'),
                        'SHGC': simple_data.get('shgc'),
                        'Area': self._sim_properties.get(construction_id, self._sim_properties_lower.get(construction_id.lower(), {})).get('Area')
                    },
                    'glazing_layers': [],
                    'shading_layers': [],
                    'raw_object': construction_data.get('raw_object')
                }

        for construction_id, construction_data in self._constructions_glazing_cache.items():
            if construction_id in processed_data:
                continue

            material_layers = construction_data.get('material_layers', [])
            glazing_layers_details = []
            shading_layers_details = []
            total_thickness = 0.0
            has_glazing_or_gas = False

            for layer_name in material_layers:
                if layer_name in self._window_glazing_cache:
                    glazing = self._window_glazing_cache[layer_name]
                    thickness = safe_float(glazing.get('thickness'))
                    total_thickness += thickness
                    glazing_layers_details.append({
                        'Name': layer_name, 'Type': 'Glazing', 'Thickness': thickness,
                        'Conductivity': safe_float(glazing.get('conductivity')),
                        'VT': safe_float(glazing.get('visible_transmittance')),
                        'ST': safe_float(glazing.get('solar_transmittance'))
                    })
                    has_glazing_or_gas = True
                elif layer_name in self._window_gas_cache:
                    gas = self._window_gas_cache[layer_name]
                    thickness = safe_float(gas.get('thickness'))
                    total_thickness += thickness
                    glazing_layers_details.append({
                        'Name': layer_name, 'Type': f'Gas ({gas.get("gas_type", "Unknown")})',
                        'Thickness': thickness, 'Conductivity': None, 'VT': None, 'ST': None
                    })
                    has_glazing_or_gas = True
                elif layer_name in self._window_shade_cache:
                    shade = self._window_shade_cache[layer_name]
                    thickness = safe_float(shade.get('thickness'))
                    shading_layers_details.append({
                        'Name': layer_name, 'Thickness': thickness,
                        'Conductivity': safe_float(shade.get('conductivity')),
                        'Transmittance': safe_float(shade.get('solar_transmittance')),
                        'Reflectivity': safe_float(shade.get('solar_reflectance'))
                    })

            if has_glazing_or_gas:
                sim_props = self._sim_properties.get(construction_id)
                if not sim_props:
                    sim_props = self._sim_properties_lower.get(construction_id.lower(), {})

                u_value_sim = sim_props.get('U-Value')
                shgc_sim = sim_props.get('SHGC')
                vt_sim = sim_props.get('VT')

                processed_data[construction_id] = {
                    'id': construction_id,
                    'name': construction_id,
                    'type': 'Detailed',
                    'system_details': {
                        'Name': construction_id,
                        'Type': 'Detailed Glazing',
                        'Thickness': total_thickness if total_thickness > 0 else None,
                        'U-Value': u_value_sim,
                        'VT': vt_sim,
                        'SHGC': shgc_sim,
                        'Area': sim_props.get('Area')
                    },
                    'glazing_layers': glazing_layers_details,
                    'shading_layers': shading_layers_details,
                    'raw_object': construction_data.get('raw_object')
                }

        keys_to_delete = []
        for construction_id, construction_data in self._constructions_glazing_cache.items():
            if construction_id in processed_data:
                continue

            current_shades_info = []
            base_construction_id = None
            material_layers = construction_data.get('material_layers', [])
            potential_base_layer = None

            for layer_name in material_layers:
                if layer_name in self._window_shade_cache:
                    shade = self._window_shade_cache[layer_name]
                    current_shades_info.append({
                        'Name': layer_name,
                        'Thickness': safe_float(shade.get('thickness')),
                        'Conductivity': safe_float(shade.get('conductivity')),
                        'Transmittance': safe_float(shade.get('solar_transmittance')),
                        'Reflectivity': safe_float(shade.get('solar_reflectance'))
                    })
                elif not potential_base_layer:
                    potential_base_layer = layer_name

            if potential_base_layer:
                if potential_base_layer in processed_data:
                    base_construction_id = potential_base_layer
                else:
                    potential_base_id_derived = None
                    if potential_base_layer.startswith("Simple "):
                         potential_base_id_derived = potential_base_layer[len("Simple "):]
                    if potential_base_id_derived and potential_base_id_derived in processed_data:
                        base_construction_id = potential_base_id_derived

            if base_construction_id and current_shades_info:
                if base_construction_id in processed_data:
                    if 'shading_layers' not in processed_data[base_construction_id]:
                        processed_data[base_construction_id]['shading_layers'] = []
                    existing_shades = {s['Name'] for s in processed_data[base_construction_id]['shading_layers']}
                    for shade_info in current_shades_info:
                        if shade_info['Name'] not in existing_shades:
                            processed_data[base_construction_id]['shading_layers'].append(shade_info)

        try:
            processed_data = self._transfer_shades_based_on_naming(processed_data)
        except Exception as e:

             import traceback
             traceback.print_exc()

        try:
            updated_constructions = set()
            for control_key, control_data in self._window_shading_control_cache.items():
                shade_position = control_data.get('shading_type')
                window_names = control_data.get('window_names', [])

                if not shade_position or not window_names:
                    continue

                for window_name in window_names:
                    window_data = self._windows_cache.get(window_name)
                    if not window_data:
                        continue

                    window_construction_name = window_data.get('construction_name')
                    if not window_construction_name:
                        continue

                    base_construction_id = window_construction_name
                    try:
                        prefix, suffix = window_construction_name.rsplit(' - ', 1)
                        if suffix.startswith('2') and len(suffix) == 4 and suffix.isdigit():
                            base_suffix = '1' + suffix[1:]
                            potential_base_id = f"{prefix} - {base_suffix}"
                            if potential_base_id in processed_data:
                                base_construction_id = potential_base_id
                    except ValueError:
                        pass

                    if base_construction_id in processed_data and base_construction_id not in updated_constructions:
                        target_construction_data = processed_data[base_construction_id]
                        if target_construction_data.get('shading_layers'):
                            for shade_layer in target_construction_data['shading_layers']:
                                if 'Position' not in shade_layer or shade_layer.get('Position') in [None, '-', 'Unknown']:
                                     shade_layer['Position'] = shade_position
                            updated_constructions.add(base_construction_id)

        except Exception as e_pos:

            import traceback
            traceback.print_exc()

        constructions_to_remove = []
        for construction_id, data in processed_data.items():
            is_detailed = data.get('type') == 'Detailed'
            if is_detailed:
                system_details = data.get('system_details', {})
                u_value = system_details.get('U-Value')
                shgc = system_details.get('SHGC')
                vt = system_details.get('VT')

                has_shading = bool(data.get('shading_layers'))
                if (u_value is None or shgc is None or vt is None) and not has_shading:
                    constructions_to_remove.append(construction_id)

        final_filtered_data = processed_data.copy()
        for construction_id in constructions_to_remove:
            if construction_id in final_filtered_data:
                 del final_filtered_data[construction_id]

        for construction_id, data in final_filtered_data.items():
            data['frame_details'] = None

            potential_shaded_id = None
            try:
                prefix, suffix = construction_id.rsplit(' - ', 1)
                if suffix.startswith('1') and len(suffix) == 4 and suffix.isdigit():
                    shaded_suffix = '2' + suffix[1:]
                    potential_shaded_id = f"{prefix} - {shaded_suffix}"
                    if potential_shaded_id not in self._constructions_glazing_cache:
                        potential_shaded_id = None
            except ValueError:
                pass

            for window_id, window_data in self._windows_cache.items():
                window_construction_name = window_data.get('construction_name')

                if window_construction_name == construction_id or \
                   (potential_shaded_id and window_construction_name == potential_shaded_id):

                    window_obj = window_data.get('raw_object')
                    if not window_obj: continue

                    frame_divider_name = getattr(window_obj, 'Frame_and_Divider_Name', None)
                    if frame_divider_name and frame_divider_name in self._frame_divider_cache:
                        frame_data = self._frame_divider_cache[frame_divider_name]
                        data['frame_details'] = {
                            'id': frame_divider_name,
                            'frame_width': frame_data.get('frame_width'),
                            'frame_conductance': frame_data.get('frame_conductance')
                        }
                        break

        self.parsed_glazing_data = final_filtered_data
        return self.parsed_glazing_data
