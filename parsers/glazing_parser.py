# parsers/glazing_parser.py
import csv
import os
from typing import Dict, Any, List

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
        # Handle numpy float types by converting to Python float
        if hasattr(value, 'item'):  # Check if it's a numpy type
            return float(value.item())
        return float(value)
    except (ValueError, TypeError, AttributeError):
        return default

class GlazingParser:
    """Parses glazing-related data from IDF caches."""

    def __init__(self,
                 constructions_glazing_cache: Dict[str, Dict[str, Any]],
                 window_simple_glazing_cache: Dict[str, Dict[str, Any]],
                 window_glazing_cache: Dict[str, Dict[str, Any]],
                 window_gas_cache: Dict[str, Dict[str, Any]],
                 window_shade_cache: Dict[str, Dict[str, Any]],
                 # --- ADDED ---
                 window_shading_control_cache: Dict[str, Dict[str, Any]], # Add the new cache
                 # -------------
                 # --- ADDED ---
                 windows_cache: Dict[str, Dict[str, Any]], # Add windows cache parameter
                 # -------------
                 simulation_output_csv: str = None, # Added parameter for CSV path
                 idf_objects: Any = None,
                 frame_divider_cache: Dict[str, Dict[str, Any]] = None): # Added frame cache
       """
       Initializes the parser with necessary data caches and simulation output path.

       Args:
           constructions_glazing_cache: Cache containing pre-filtered glazing constructions.
           window_simple_glazing_cache: Cache for simple glazing system materials.
           window_glazing_cache: Cache for window glazing materials.
           window_gas_cache: Cache for window gas materials.
           window_shade_cache: Cache for window shade materials.
           window_shading_control_cache: Cache for window shading control objects. # Add docstring
           windows_cache: Cache for raw window objects (FenestrationSurface:Detailed). # Add docstring
           simulation_output_csv: Path to the eplustbl.csv file from simulation (optional).
           idf_objects: Raw IDF objects if direct access is needed (optional).
           frame_divider_cache: Cache for FrameAndDivider objects. # Added docstring
       """
       self._constructions_glazing_cache = constructions_glazing_cache
       self._window_simple_glazing_cache = window_simple_glazing_cache
       self._window_glazing_cache = window_glazing_cache
       self._window_gas_cache = window_gas_cache
       self._window_shade_cache = window_shade_cache
       # --- ADDED ---
       self._window_shading_control_cache = window_shading_control_cache # Store the cache
       # -------------
       # --- ADDED ---
       self._windows_cache = windows_cache # Store the windows cache
       # -------------
       # --- ADDED ---
       self._frame_divider_cache = frame_divider_cache if frame_divider_cache is not None else {} # Store frame cache
       # -------------
       self._simulation_output_csv = simulation_output_csv # Store the path
       self._sim_properties = {} # Dictionary to store properties read from CSV
       self._idf = idf_objects # Store if needed
       self.parsed_glazing_data = {} # Store results here

    def _parse_simulation_output_csv(self):
        """Parses the eplustbl.csv file to extract window properties from the 'Exterior Fenestration' table."""
        if not self._simulation_output_csv or not os.path.exists(self._simulation_output_csv):
            # print(f"DEBUG: Simulation output CSV not found or not provided: {self._simulation_output_csv}")
            return # No file to parse

        # print(f"DEBUG: Parsing simulation output CSV: {self._simulation_output_csv}")
        self._sim_properties = {} # Reset properties before parsing
        try:
            with open(self._simulation_output_csv, 'r', encoding='utf-8', errors='ignore') as csvfile:
                reader = csv.reader(csvfile)
                in_target_table = False
                headers_found = False
                # Define expected headers and their indices based on the sample CSV
                header_map = {
                    "construction": 1, # Actual construction name is in the *second* data column (index 2 in row)
                    "glass u-factor [w/m2-k]": 7,
                    "glass shgc": 8,
                    "glass visible transmittance": 9
                }
                col_indices = {}

                for row in reader:
                    if not row or not any(field.strip() for field in row): continue # Skip empty/blank rows

                    # Check for start of table title
                    if not in_target_table and row[0].strip().lower() == "exterior fenestration":
                        in_target_table = True
                        headers_found = False # Reset header flag for this table
                        col_indices = {} # Reset indices
                        continue # Skip the table title row itself

                    if in_target_table:
                        # --- Header Row Search ---
                        if not headers_found:
                            current_headers_norm = [h.strip().lower() for h in row]
                            # Check if this row looks like the header row (contains key elements)
                            if "construction" in current_headers_norm and "glass u-factor [w/m2-k]" in current_headers_norm:
                                try:
                                    # Validate and map expected headers to their actual indices
                                    for key, _ in header_map.items(): # Don't need expected_index here
                                        if key in current_headers_norm:
                                            actual_index = current_headers_norm.index(key)
                                            col_indices[key] = actual_index
                                            # # print(f"DEBUG: Mapped '{key}' to column index {actual_index}") # Less verbose
                                        else:
                                            # Fallback for 'construction' might not be needed if it's always present
                                            raise ValueError(f"Missing required header: '{key}'")

                                    # Check if all required headers were found
                                    if len(col_indices) != len(header_map):
                                        missing = set(header_map.keys()) - set(col_indices.keys())
                                        raise ValueError(f"Missing required headers: {missing}")

                                    headers_found = True
                                except ValueError as e:
                                    in_target_table = False # Abort if headers invalid
                                continue # Skip the header row once processed/validated
                            else:
                                # This row is between title and header (e.g., blank), skip it
                                continue
                        # --- End Header Row Search ---

                        # --- Data Row Processing or Table End Check ---
                        else: # headers_found is True
                            # Refined End Condition Check:
                            # End if:
                            # 1. First cell contains "total or average" (case-insensitive)
                            # 2. OR First cell is empty AND (row has < 2 cells OR second cell is also empty)
                            is_total_row = row[0].strip().lower().endswith("total or average")
                            is_blank_data_row = not row[0].strip() and (len(row) < 2 or not row[1].strip())

                            if is_total_row or is_blank_data_row:
                                in_target_table = False # Stop processing this table
                                continue # Skip this end/total/blank row

                            # Process data row (if not end condition)
                            max_index = max(col_indices.values()) if col_indices else -1
                            if max_index == -1: # Should not happen if headers were found
                                in_target_table = False
                                continue

                            if len(row) > max_index:
                                try:
                                    # Extract data using mapped indices
                                    construction_name = row[col_indices["construction"]].strip()
                                    u_value = safe_float(row[col_indices["glass u-factor [w/m2-k]"]])
                                    shgc = safe_float(row[col_indices["glass shgc"]])
                                    vt = safe_float(row[col_indices["glass visible transmittance"]])

                                    if construction_name:
                                        # Store properties using the construction name as the key
                                        if construction_name not in self._sim_properties: # Use first found
                                            self._sim_properties[construction_name] = {
                                                'U-Value': u_value,
                                                'SHGC': shgc,
                                                'VT': vt
                                            }
                                            # # print(f"DEBUG: Stored props for '{construction_name}': U={u_value}, SHGC={shgc}, VT={vt}")
                                        # else: # Less verbose logging for duplicates
                                            # # print(f"DEBUG: Duplicate construction '{construction_name}' found, using first entry.")
                                except IndexError:
                                    # print(f"DEBUG: Skipping row due to IndexError (mismatched length?): {row}")
                                    pass # Or log differently
                                except KeyError as e:
                                     # print(f"DEBUG: Skipping row due to KeyError (header mapping issue?): {e} | Row: {row}")
                                     pass # Or log differently
                                except Exception as e:
                                    # print(f"DEBUG: Error processing data row: {e} | Row: {row}")
                                    pass # Or log differently
                            else:
                                 # print(f"DEBUG: Skipping short data row: {row}")
                                 pass # Or log differently
                        # --- End Data Row Processing ---

        except FileNotFoundError:
            # print(f"DEBUG: Error - Simulation output CSV file not found at: {self._simulation_output_csv}")
            pass # Or log error differently
        except Exception as e:
            # print(f"DEBUG: Error reading or parsing simulation output CSV: {e}")
            import traceback
            traceback.print_exc() # Print full traceback for debugging CSV errors

        # print(f"DEBUG: Finished parsing CSV. Found properties for {len(self._sim_properties)} constructions.")

    # --- Helper method for transferring shades ---
    def _transfer_shades_based_on_naming(self, processed_data: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Identifies pairs of constructions (base vs. shaded) based on naming convention,
        transfers shading layers to the base, and removes the shaded version.
        Example pairs: 'xxx - 1001' (base) and 'xxx - 2001' (shaded)
                       'yyy - 4444' (base) and 'yyy - 6666' (shaded)
        """
        # This is now Step 4 in the main parse method
        # print("\n--- DEBUG: Processing Step 4 (Transferring Shades) ---")

        # Add try-except around the main logic of the transfer method
        try:
            # Correct indentation for the entire method body
            constructions_with_shades = {
                cid: data for cid, data in processed_data.items() if data.get('shading_layers')
            }
            constructions_without_shades = {
                cid: data for cid, data in processed_data.items() if not data.get('shading_layers')
            }

            keys_to_remove = set() # Track shaded constructions to remove after transfer

            # Iterate through base candidates (those without shades initially)
            for base_id, base_data in constructions_without_shades.items():
                try:
                    # Extract prefix assuming format "Prefix - Suffix"
                    base_prefix, base_suffix = base_id.rsplit(' - ', 1)
                except ValueError:
                    # Cannot split, likely not following the pattern
                    continue

                # Look for a corresponding construction with shades and the same prefix
                found_match = False
                for shade_id, shade_data in constructions_with_shades.items():
                    # Skip if already marked for removal or if it's the same ID
                    if shade_id in keys_to_remove or shade_id == base_id:
                        continue

                    try:
                        shade_prefix, shade_suffix = shade_id.rsplit(' - ', 1)
                    except ValueError:
                        continue

                    # Check if prefixes match AND suffixes follow the 1xxx/2xxx pattern
                    if base_prefix == shade_prefix:
                        try:
                            # Check if base suffix starts with '1' and shade suffix starts with '2'
                            # and both are 4-digit numbers
                            is_base_pattern = base_suffix.startswith('1') and len(base_suffix) == 4 and base_suffix.isdigit()
                            is_shade_pattern = shade_suffix.startswith('2') and len(shade_suffix) == 4 and shade_suffix.isdigit()

                            if is_base_pattern and is_shade_pattern:
                                # Prefixes match AND suffixes follow the 1xxx/2xxx pattern
                                # print(f"DEBUG:   Pattern match found: Base='{base_id}', Shade='{shade_id}'") # DEBUG
                                # Transfer shading layers
                                pass # Placeholder
                            else:
                                # Prefixes match, but suffixes don't follow the 1xxx/2xxx pattern
                                # # print(f"DEBUG:   Prefix match for '{base_id}' and '{shade_id}', but suffixes ('{base_suffix}', '{shade_suffix}') don't match 1xxx/2xxx pattern.")
                                continue # Skip to the next potential shade_id

                        except Exception as suffix_check_error:
                            # print(f"DEBUG:   Error checking suffix pattern for '{base_id}'/'{shade_id}': {suffix_check_error}")
                            continue # Skip to the next potential shade_id

                        # --- Transfer logic starts here (only runs if pattern matched) ---
                        shades_to_transfer = shade_data.get('shading_layers', [])
                        if shades_to_transfer:
                            # Ensure base_data has the key
                            if 'shading_layers' not in base_data:
                                 base_data['shading_layers'] = []

                            # Add shades (avoid duplicates just in case)
                            existing_base_shades = {s['Name'] for s in base_data['shading_layers']}
                            added_count = 0
                            for shade_info in shades_to_transfer:
                                 if shade_info['Name'] not in existing_base_shades:
                                     base_data['shading_layers'].append(shade_info)
                                     added_count += 1

                            if added_count > 0:
                                # print(f"DEBUG:   Transferred {added_count} shade(s) (e.g., '{shades_to_transfer[0]['Name']}') from '{shade_id}' to '{base_id}'.")
                                # Mark the shaded version for removal
                                keys_to_remove.add(shade_id)
                                break # Stop searching for other matches for this base_id
                        else:
                             # Should not happen based on constructions_with_shades filter, but good check
                             # print(f"DEBUG:   Potential match '{shade_id}' found for '{base_id}', but it has no shades to transfer.")
                             pass

                # if not found_match:
                #     # print(f"DEBUG:   No corresponding shaded construction found for base '{base_id}'.")
                #     pass

            # Remove the redundant shaded constructions from the original processed_data
            final_data = processed_data.copy() # Work on a copy
            removed_count = 0
            for key in keys_to_remove:
                if key in final_data:
                    del final_data[key]
                    removed_count += 1
                    
            return final_data # Correct indentation

        except Exception as e_transfer:
            print(f"ERROR: Exception inside _transfer_shades_based_on_naming: {e_transfer}")
            import traceback
            traceback.print_exc()
            return processed_data # Return original data on error within transfer logic
    # --- End Helper method ---

    def parse_glazing_data(self) -> Dict[str, Dict[str, Any]]:
        """
        Processes the cached glazing constructions to extract detailed data,
        incorporating properties from the simulation output CSV if available.
        Populates self.parsed_glazing_data.
        """
        # --- Parse Simulation Output First ---
        self._parse_simulation_output_csv() # Populate self._sim_properties
        # print(f"DEBUG: Initial _sim_properties: {self._sim_properties}") # DEBUG ADDED

        processed_data = {}

        # --- Step 1: Process Simple Glazing Systems ---
        # Identify constructions whose primary layer is a SimpleGlazingSystem material
        for construction_id, construction_data in self._constructions_glazing_cache.items():
            material_layers = construction_data.get('material_layers', [])
            if not material_layers:
                continue # Skip constructions with no layers

            first_layer_name = material_layers[0]
            if first_layer_name in self._window_simple_glazing_cache:
                simple_data = self._window_simple_glazing_cache[first_layer_name]
                processed_data[construction_id] = {
                    'id': construction_id,
                    'name': construction_id,
                    'type': 'Simple', # Assign type here
                    'system_details': {
                        'Name': construction_id,
                        'Type': 'Simple Glazing',
                        'Thickness': None, # Not available for simple glazing
                        'U-Value': simple_data.get('u_factor'),
                        'VT': simple_data.get('visible_transmittance'),
                        'SHGC': simple_data.get('shgc')
                    },
                    'glazing_layers': [], # Simple systems don't list layers
                    'shading_layers': [], # Shades handled later if present
                    'raw_object': construction_data.get('raw_object')
                }

        # --- DEBUG: Print keys after Step 1 ---
        # print(f"\n--- DEBUG: Processed Data after Step 1 (Simple Glazing): {list(processed_data.keys())} ---")

        # --- Step 2: Process Detailed Glazing Constructions ---
        # Process constructions not already identified as Simple
        # print("\n--- DEBUG: Processing Step 2 (Detailed Glazing) ---")
        for construction_id, construction_data in self._constructions_glazing_cache.items():
            # Skip if already processed as Simple
            if construction_id in processed_data:
                continue

            material_layers = construction_data.get('material_layers', [])
            glazing_layers_details = []
            shading_layers_details = []
            total_thickness = 0.0
            has_glazing_or_gas = False # Flag to check if it's a detailed glazing construction

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
                        # Position added later
                    })
                # else: It's some other material type, ignore for glazing details

            # Only add if it contains actual glazing or gas layers
            if has_glazing_or_gas:
                # print(f"DEBUG:   Processing Detailed Construction ID: '{construction_id}'")
                sim_props = self._sim_properties.get(construction_id, {})
                u_value_sim = sim_props.get('U-Value')
                shgc_sim = sim_props.get('SHGC')
                vt_sim = sim_props.get('VT')

                processed_data[construction_id] = {
                    'id': construction_id,
                    'name': construction_id,
                    'type': 'Detailed', # Assign type here
                    'system_details': {
                        'Name': construction_id,
                        'Type': 'Detailed Glazing',
                        'Thickness': total_thickness if total_thickness > 0 else None,
                        'U-Value': u_value_sim,
                        'VT': vt_sim,
                        'SHGC': shgc_sim
                    },
                    'glazing_layers': glazing_layers_details,
                    'shading_layers': shading_layers_details,
                    'raw_object': construction_data.get('raw_object')
                }

        # --- DEBUG: Print after Step 2 ---
        # print(f"\n--- DEBUG: Processed Data after Step 2 (Detailed Glazing): {list(processed_data.keys())} ---")

        # --- Step 3: Link Shades from separate constructions ---
        # Identify constructions NOT processed yet (likely shade-only definitions)
        # print("\n--- DEBUG: Processing Step 3: Linking Shades ---")
        keys_to_delete = [] # Track shade-defining constructions to remove later
        for construction_id, construction_data in self._constructions_glazing_cache.items():
            # Skip if already processed as Simple or Detailed
            if construction_id in processed_data:
                continue

            # This might be a construction defining shades for another construction
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
                        # Position added later
                    })
                elif not potential_base_layer: # Assume first non-shade is the base
                    potential_base_layer = layer_name

            # Now, try to link the potential base layer to an existing processed construction
            if potential_base_layer:
                # Check if the potential base layer name directly matches a processed construction ID
                if potential_base_layer in processed_data:
                    base_construction_id = potential_base_layer
                else:
                    # Attempt to derive base construction ID (e.g., from "Simple X" material to "X" construction)
                    potential_base_id_derived = None
                    if potential_base_layer.startswith("Simple "):
                         potential_base_id_derived = potential_base_layer[len("Simple "):]
                    if potential_base_id_derived and potential_base_id_derived in processed_data:
                        base_construction_id = potential_base_id_derived

            # If we found a base and have shades, link them
            if base_construction_id and current_shades_info:
                # print(f"DEBUG:   Linking shades { [s['Name'] for s in current_shades_info] } from '{construction_id}' to base: '{base_construction_id}'")
                if base_construction_id in processed_data:
                    # Ensure 'shading_layers' key exists
                    if 'shading_layers' not in processed_data[base_construction_id]:
                        processed_data[base_construction_id]['shading_layers'] = []
                    # Merge shades, avoiding duplicates
                    existing_shades = {s['Name'] for s in processed_data[base_construction_id]['shading_layers']}
                    for shade_info in current_shades_info:
                        if shade_info['Name'] not in existing_shades:
                            processed_data[base_construction_id]['shading_layers'].append(shade_info)
                    # Mark this shade-defining construction for removal from the final dict if desired
                    # keys_to_delete.append(construction_id) # Optional cleanup

        # Optional: Clean up shade-defining constructions from processed_data
        # for key in keys_to_delete:
        #     if key in processed_data:
        #         del processed_data[key]

        # --- Step 4: Transfer shades based on naming convention ---
        # print(f"\nDEBUG: Calling Step 4 (Transferring Shades). Data size before: {len(processed_data)}")
        try:
            # Modify processed_data in place or reassign
            processed_data = self._transfer_shades_based_on_naming(processed_data)
            # print(f"DEBUG: Data size after Step 4 (Transferring Shades): {len(processed_data)}")
        except Exception as e:
             print(f"ERROR: Exception during Step 4 (Transferring Shades): {e}")
             import traceback
             traceback.print_exc()
             # Fallback: continue with potentially unchanged data
        # --- End Step 4 ---

        # --- Step 5: Update Shading Position via Window Control Link ---
        # print("\n--- DEBUG: Entering Step 5: Updating Shade Positions ---")
        try:
            updated_constructions = set()
            for control_key, control_data in self._window_shading_control_cache.items():
                shade_position = control_data.get('shading_type') # e.g., 'InteriorShade'
                window_names = control_data.get('window_names', [])

                if not shade_position or not window_names:
                    continue

                # print(f"--- DEBUG: Processing Control '{control_key}': Position='{shade_position}', Windows='{window_names}'")

                for window_name in window_names:
                    window_data = self._windows_cache.get(window_name)
                    if not window_data:
                        continue

                    window_construction_name = window_data.get('construction_name')
                    if not window_construction_name:
                        continue

                    # Determine the base construction ID (handles cases where window uses "xxx - 2xxx")
                    base_construction_id = window_construction_name # Default assumption
                    try:
                        prefix, suffix = window_construction_name.rsplit(' - ', 1)
                        if suffix.startswith('2') and len(suffix) == 4 and suffix.isdigit():
                            base_suffix = '1' + suffix[1:]
                            potential_base_id = f"{prefix} - {base_suffix}"
                            # Check if this derived base ID actually exists in our processed data
                            if potential_base_id in processed_data:
                                base_construction_id = potential_base_id
                            # else: stick with the original window_construction_name as base
                    except ValueError:
                        pass # No " - " pattern, stick with original name

                    # Update the position in the identified base construction
                    if base_construction_id in processed_data and base_construction_id not in updated_constructions:
                        target_construction_data = processed_data[base_construction_id]
                        if target_construction_data.get('shading_layers'):
                            # print(f"--- DEBUG:     Updating position for shades in base '{base_construction_id}' to '{shade_position}'.")
                            for shade_layer in target_construction_data['shading_layers']:
                                # Only update if not already set or is default
                                if 'Position' not in shade_layer or shade_layer.get('Position') in [None, '-', 'Unknown']:
                                     shade_layer['Position'] = shade_position
                            updated_constructions.add(base_construction_id)

        except Exception as e_pos:
            print(f"ERROR: Exception during Step 5 (Updating Shade Positions): {e_pos}")
            import traceback
            traceback.print_exc()
        # --- End Step 5 ---

        # --- Step 6: Filter out detailed constructions missing simulation properties ---
        # print(f"\n--- DEBUG: Processing Step 6 (Filtering Results) ---")
        constructions_to_remove = []
        # Iterate through the potentially modified processed_data
        for construction_id, data in processed_data.items():
            # print(f"DEBUG:   Filtering check for ID: '{construction_id}'")
            is_detailed = data.get('type') == 'Detailed'
            if is_detailed:
                system_details = data.get('system_details', {})
                u_value = system_details.get('U-Value')
                shgc = system_details.get('SHGC')
                vt = system_details.get('VT')

                # Check if any simulation property is missing (is None) AND it has NO shading layers
                has_shading = bool(data.get('shading_layers'))
                if (u_value is None or shgc is None or vt is None) and not has_shading:
                    # print(f"DEBUG:     -> Marking for removal (Missing props, no shades): {construction_id}")
                    constructions_to_remove.append(construction_id)
                # else: Keep if props exist OR if it has shades (even if props missing)

        # Remove marked constructions
        final_filtered_data = processed_data.copy()
        for construction_id in constructions_to_remove:
            if construction_id in final_filtered_data:
                 del final_filtered_data[construction_id]

        # --- End Step 6 (Filtering) ---

        # --- Step 7: Add Frame and Divider Info (after filtering) ---
        # print("\n--- DEBUG: Processing Step 7: Adding Frame Info ---")
        for construction_id, data in final_filtered_data.items(): # Iterate over the filtered data
            data['frame_details'] = None # Initialize frame details as None

            # Determine potential shaded counterpart name (e.g., "xxx - 1xxx" -> "xxx - 2xxx")
            potential_shaded_id = None
            try:
                prefix, suffix = construction_id.rsplit(' - ', 1)
                if suffix.startswith('1') and len(suffix) == 4 and suffix.isdigit():
                    shaded_suffix = '2' + suffix[1:]
                    potential_shaded_id = f"{prefix} - {shaded_suffix}"
                    # Also need to check if this potential shaded ID existed *before* filtering
                    # This requires checking the original _constructions_glazing_cache
                    if potential_shaded_id not in self._constructions_glazing_cache:
                        potential_shaded_id = None # Reset if the shaded version wasn't in the original IDF
            except ValueError:
                pass # Not following the pattern

            # Find the first window using this construction OR its shaded counterpart to get frame info
            found_frame = False
            for window_id, window_data in self._windows_cache.items():
                window_construction_name = window_data.get('construction_name')

                # Check if window uses the base ID or the potential shaded ID
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
                        # print(f"DEBUG:   Added Frame '{frame_divider_name}' to construction '{construction_id}' (found via window using '{window_construction_name}')")
                        found_frame = True
                        break # Found frame info for this construction, stop checking windows
            # if not found_frame:
                # print(f"DEBUG:   No frame found for construction '{construction_id}' (checked base and potential shaded '{potential_shaded_id}')")
        # --- End Step 7 ---


        self.parsed_glazing_data = final_filtered_data # Assign the final filtered data
        # print(f"\n--- DEBUG: Final Parsed Glazing Data Keys: {list(self.parsed_glazing_data.keys())} ---")
        # print(f"--- DEBUG: Final Parsed Glazing Data Count: {len(self.parsed_glazing_data)} ---")
        return self.parsed_glazing_data # Correct indentation

    # Removed update_system_properties_from_eio method as properties are now read from eplustbl.csv

# Example Usage (if run directly or for testing)
if __name__ == '__main__':
    # Mock data for testing
    mock_constructions_glazing = {
        "Exterior Window Simple": {'type': 'simple', 'material_layers': ['Simple Glazing Material']},
        "Exterior Window Detailed": {'type': 'detailed', 'material_layers': ['Glass Layer 1', 'Air Gap', 'Glass Layer 2']},
        "Window With Shade": {'type': 'simple', 'material_layers': ['Exterior Window Detailed', 'Interior Shade Material']},
        "Exterior Wall": {'type': 'detailed', 'material_layers': ['Brick', 'Insulation', 'Gypsum']} # Should be ignored
    }
    mock_simple_glazing = {
        "Simple Exterior Window Simple": {'u_factor': 2.5, 'shgc': 0.6, 'visible_transmittance': 0.7}
    }
    mock_window_glazing = {
        "Glass Layer 1": {'thickness': 0.003, 'conductivity': 1.0, 'visible_transmittance': 0.8, 'solar_transmittance': 0.7},
        "Glass Layer 2": {'thickness': 0.003, 'conductivity': 1.0, 'visible_transmittance': 0.8, 'solar_transmittance': 0.7}
    }
    mock_window_gas = {
        "Air Gap": {'thickness': 0.0127, 'gas_type': 'Air'}
    }
    mock_window_shade = {
        "Interior Shade Material": {'thickness': 0.001, 'conductivity': 0.1, 'solar_transmittance': 0.2, 'solar_reflectance': 0.5}
    }

    parser = GlazingParser(
        mock_constructions_glazing,
        mock_simple_glazing,
        mock_window_glazing,
        mock_window_gas,
        mock_window_shade
    )
    parsed_data = parser.parse_glazing_data()

    import json
    print(json.dumps(parsed_data, indent=2))

    # Expected output structure:
    # {
    #   "Exterior Window Simple": { ... system_details populated ... },
    #   "Exterior Window Detailed": { ... glazing_layers populated, shading_layers has Interior Shade ... }
    # }
    # Note: "Window With Shade" construction itself might be removed or kept depending on final logic.
    # Note: "Exterior Wall" should not be present.
