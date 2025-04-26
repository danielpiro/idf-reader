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
                 idf_objects: Any = None):
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
        # Simple glazing systems already have U/SHGC/VT defined in the IDF object
        for construction_id, construction_data in self._constructions_glazing_cache.items():
            if construction_data.get('type') == 'simple':
                simple_glazing_key = 'Simple ' + construction_id
                if simple_glazing_key in self._window_simple_glazing_cache:
                    simple_data = self._window_simple_glazing_cache[simple_glazing_key]
                    processed_data[construction_id] = {
                        'id': construction_id,
                        'name': construction_id,
                        'type': 'Simple',
                        'system_details': {
                            'Name': construction_id,
                            'Type': 'Simple Glazing',
                            'Thickness': None, # Not available for simple glazing
                            'U-Value': simple_data.get('u_factor'),
                            'VT': simple_data.get('visible_transmittance'),
                            'SHGC': simple_data.get('shgc')
                        },
                        'glazing_layers': [],
                        'shading_layers': [],
                        'raw_object': construction_data.get('raw_object')
                    }
                # else: It might be a shade control definition, handle later

        # else: It might be a shade control definition, handle later

        # --- DEBUG: Print keys after Step 1 ---
        # print(f"\n--- DEBUG: Processed Data after Step 1 (Simple Glazing): {list(processed_data.keys())} ---") # DEBUG ADDED
        # --- Step 2: Process Detailed Glazing Constructions ---
        # print("\n--- DEBUG: Processing Step 2 (Detailed Glazing) ---") # DEBUG ADDED
        for construction_id, construction_data in self._constructions_glazing_cache.items():
             # Skip simple ones already processed or potential shade controls
            if construction_data.get('type') == 'simple':
                 continue

            glazing_layers_details = []
            shading_layers_details = []
            total_thickness = 0.0
            # Note: Calculating U-Value, VT, SHGC for detailed constructions requires complex physics
            # For now, we'll extract layer info but leave system values as None/TBD

            for layer_name in construction_data.get('material_layers', []):
                if layer_name in self._window_glazing_cache:
                    glazing = self._window_glazing_cache[layer_name]
                    thickness = safe_float(glazing.get('thickness'))
                    total_thickness += thickness
                    glazing_layers_details.append({
                        'Name': layer_name,
                        'Type': 'Glazing',
                        'Thickness': thickness,
                        'Conductivity': safe_float(glazing.get('conductivity')),
                        'VT': safe_float(glazing.get('visible_transmittance')),
                        'ST': safe_float(glazing.get('solar_transmittance')) # Solar Transmittance
                    })
                elif layer_name in self._window_gas_cache:
                    gas = self._window_gas_cache[layer_name]
                    thickness = safe_float(gas.get('thickness'))
                    total_thickness += thickness
                    glazing_layers_details.append({
                        'Name': layer_name,
                        'Type': f'Gas ({gas.get("gas_type", "Unknown")})',
                        'Thickness': thickness,
                        'Conductivity': None, # Gas conductivity is complex
                        'VT': None,
                        'ST': None
                    })
                elif layer_name in self._window_shade_cache:
                    shade = self._window_shade_cache[layer_name]
                    thickness = safe_float(shade.get('thickness'))
                    # Note: Shades contribute to overall system but aren't typically part of thickness calc
                    shading_layers_details.append({
                        'Name': layer_name,
                        'Thickness': thickness,
                        'Conductivity': safe_float(shade.get('conductivity')),
                        'Transmittance': safe_float(shade.get('solar_transmittance')),
                        'Reflectivity': safe_float(shade.get('solar_reflectance'))
                        # Position will be added later from control cache
                     })

            # Only add if it contains glazing or gas layers (is actually a window/glazing construction)
            if glazing_layers_details:
                 # print(f"DEBUG:   Processing Detailed Construction ID: '{construction_id}'") # DEBUG ADDED
                 # --- Get properties from simulation output if available ---
                 sim_props = self._sim_properties.get(construction_id, {})
                 # print(f"DEBUG:     -> Retrieved sim_props: {sim_props}") # DEBUG ADDED
                 # if not sim_props: # Removed debug print for no match
                 #     # print(f"DEBUG:   -> No match found in sim properties for '{construction_id}'")
                 #     pass
                 u_value_sim = sim_props.get('U-Value')
                 shgc_sim = sim_props.get('SHGC')
                 vt_sim = sim_props.get('VT')
                 # ---

                 processed_data[construction_id] = {
                    'id': construction_id,
                    'name': construction_id,
                    'type': 'Detailed',
                    'system_details': {
                        'Name': construction_id,
                        'Type': 'Detailed Glazing',
                        'Thickness': total_thickness if total_thickness > 0 else None,
                        'U-Value': u_value_sim, # Use value from simulation
                        'VT': vt_sim,           # Use value from simulation
                        'SHGC': shgc_sim        # Use value from simulation
                    },
                    'glazing_layers': glazing_layers_details,
                    'shading_layers': shading_layers_details, # Store associated shades if any
                    'raw_object': construction_data.get('raw_object'),
                    # NOTE: U-Value, VT, SHGC are now sourced from simulation output (eplustbl.csv)
                }

        # --- DEBUG: Print after Step 2 ---
        # print(f"\n--- DEBUG: Processed Data after Step 2 (Detailed Glazing): {list(processed_data.keys())} ---") # DEBUG ADDED

        # --- Step 3: Link Shades defined via separate constructions (like Construction:WithShading) ---
        # This part assumes constructions marked 'simple' with no 'data' link shades
        # print("\n--- DEBUG: Processing Step 3: Linking Shades ---") # DEBUG PRINT
        keys_to_delete = [] # Track shade-defining constructions to remove later
        for construction_id, construction_data in self._constructions_glazing_cache.items():
            # Check if it's a 'simple' type construction NOT already processed as a simple glazing system itself
            if construction_data.get('type') == 'simple' and construction_id not in processed_data:
                # This might be a construction defining shades for another construction
                current_shades_info = []
                base_construction_id = None
                material_layers = construction_data.get('material_layers', [])

                for layer_name in material_layers:
                    if layer_name in self._window_shade_cache:
                        shade = self._window_shade_cache[layer_name]
                        current_shades_info.append({
                            'Name': layer_name,
                            'Thickness': safe_float(shade.get('thickness')),
                            'Conductivity': safe_float(shade.get('conductivity')),
                            'Transmittance': safe_float(shade.get('solar_transmittance')),
                            'Reflectivity': safe_float(shade.get('solar_reflectance'))
                            # Position will be added later from control cache
                         })
                    # Check if layer is a known base construction (simple OR detailed)
                    else:
                        # Attempt to derive base construction ID from material name
                        # Assumes construction name = material name without "Simple " prefix
                        potential_base_id_derived = None
                        if layer_name.startswith("Simple "):
                            potential_base_id_derived = layer_name[len("Simple "):]

                        if potential_base_id_derived and potential_base_id_derived in processed_data:
                            # Found base construction via derived ID
                            base_construction_id = potential_base_id_derived
                            break # Assume first non-shade is the base
                        elif layer_name in processed_data:
                            # Found base construction directly by layer name (e.g., for detailed constructions)
                            base_construction_id = layer_name
                            break # Assume first non-shade is the base
                        else:
                             # Layer is not a shade and didn't match a processed construction directly or via derivation
                             # print(f"DEBUG:   Layer '{layer_name}' is not a shade and did not match a processed construction (derived: '{potential_base_id_derived}').") # DEBUG PRINT
                             pass

                if base_construction_id and current_shades_info:
                    # print(f"DEBUG:   Attempting to link shades { [s['Name'] for s in current_shades_info] } to base: {base_construction_id}") # DEBUG PRINT
                    # Add/Update shading layers in the base construction
                    if base_construction_id in processed_data:
                        # Merge shades, avoiding duplicates if necessary
                        existing_shades = {s['Name'] for s in processed_data[base_construction_id]['shading_layers']}
                        for shade_info in current_shades_info:
                            if shade_info['Name'] not in existing_shades:
                                processed_data[base_construction_id]['shading_layers'].append(shade_info)
                        # Mark this shade-defining construction for removal
                        keys_to_delete.append(construction_id)

        # Clean up: Remove the constructions that only defined shades
        # (We could keep them if needed, but they aren't glazing systems themselves)
        # for key in keys_to_delete:
        #     if key in processed_data: # Should not happen based on logic, but safe check
        #         del processed_data[key]

        # --- NEW Step 4: Transfer shades based on naming convention ---
        # print(f"\nDEBUG: Calling Step 4 (Transferring Shades). Data size before: {len(processed_data)}") # DEBUG
        # Perform transfer *before* filtering based on missing sim properties
        try:
            processed_data_after_transfer = self._transfer_shades_based_on_naming(processed_data)
            # print(f"DEBUG: Data size after Step 4 (Transferring Shades): {len(processed_data_after_transfer)}") # DEBUG ADDED
        except Exception as e:
             print(f"ERROR: Exception during Step 4 (Transferring Shades): {e}")
             import traceback
             traceback.print_exc()
             processed_data_after_transfer = processed_data # Fallback to pre-transfer data on error
        # --- End NEW Step 4 ---

        # --- NEW Step 5: Update Shading Position via Window Control Link ---
        # print("\n--- DEBUG: Entering Step 5: Updating Shade Positions (New Logic) ---")
        # print(f"--- DEBUG: Window Shading Control Cache Content: {list(self._window_shading_control_cache.keys())}") # Print keys only for brevity
        # print(f"--- DEBUG: Windows Cache Content: {list(self._windows_cache.keys())}") # Print keys only for brevity
        try:
            # Keep track of constructions whose shades have been updated to avoid redundant work
            updated_constructions = set()

            # Iterate through control objects as the source of position info
            for control_key, control_data in self._window_shading_control_cache.items():
                shade_position = control_data.get('shading_type')
                window_names = control_data.get('window_names', [])

                if not shade_position or not window_names:
                    # print(f"--- DEBUG: Skipping control '{control_key}': Missing position ('{shade_position}') or window names ('{window_names}').")
                    continue

                # print(f"--- DEBUG: Processing Control '{control_key}': Position='{shade_position}', Windows='{window_names}'")

                # Process each window controlled by this object
                for window_name in window_names:
                    window_data = self._windows_cache.get(window_name)
                    if not window_data:
                        # print(f"--- DEBUG:   Window '{window_name}' (from control '{control_key}') not found in windows cache. Skipping.")
                        continue

                    # Get the construction used by this window (could be base or shaded version)
                    window_construction_name = window_data.get('construction_name')
                    if not window_construction_name:
                        # print(f"--- DEBUG:   Window '{window_name}' has no construction name. Skipping.")
                        continue

                    # print(f"--- DEBUG:   Window '{window_name}' uses construction '{window_construction_name}'.")

                    # Determine the corresponding base construction ID
                    base_construction_id = None
                    try:
                        # Check if it follows the shaded pattern (e.g., "xxx - 2xxx")
                        prefix, suffix = window_construction_name.rsplit(' - ', 1)
                        if suffix.startswith('2') and len(suffix) == 4 and suffix.isdigit():
                            # Derive base ID (e.g., "xxx - 1xxx")
                            base_suffix = '1' + suffix[1:]
                            base_construction_id = f"{prefix} - {base_suffix}"
                            # print(f"--- DEBUG:     Derived base construction ID '{base_construction_id}' from shaded '{window_construction_name}'.")
                        else:
                            # Assume window uses the base construction directly
                            base_construction_id = window_construction_name
                            # print(f"--- DEBUG:     Assuming '{window_construction_name}' is the base construction ID.")
                    except ValueError:
                        # Doesn't follow "Prefix - Suffix" pattern, assume it's the base ID
                        base_construction_id = window_construction_name
                        # print(f"--- DEBUG:     Assuming '{window_construction_name}' (no suffix pattern) is the base construction ID.")

                    # Check if this base construction exists in our processed data and hasn't been updated yet
                    if base_construction_id in processed_data_after_transfer and base_construction_id not in updated_constructions:
                        target_construction_data = processed_data_after_transfer[base_construction_id]
                        if target_construction_data.get('shading_layers'):
                            # print(f"--- DEBUG:     Updating position for shades in base construction '{base_construction_id}' to '{shade_position}'.")
                            # Update position for ALL shade layers in this construction
                            for shade_layer in target_construction_data['shading_layers']:
                                shade_layer['Position'] = shade_position
                            updated_constructions.add(base_construction_id) # Mark as updated
                        # else:
                            # print(f"--- DEBUG:     Base construction '{base_construction_id}' found, but has no shading layers to update.")
                    # elif base_construction_id in updated_constructions:
                        # print(f"--- DEBUG:     Base construction '{base_construction_id}' already updated by another control. Skipping redundant update.")
                    # else:
                        # print(f"--- DEBUG:     Derived/Assumed base construction ID '{base_construction_id}' not found in processed data. Cannot update position.")

            # print(f"--- DEBUG: Finished Step 5. Updated positions for constructions: {updated_constructions}")

        except Exception as e_pos:
            print(f"ERROR: Exception during Step 5 (Updating Shade Positions - New Logic): {e_pos}")
            import traceback
            traceback.print_exc()
            # Continue with potentially incomplete positions

        # --- End NEW Step 5 ---

        # --- Step 6 (was Step 5): Filter out detailed constructions missing simulation properties ---
        # print(f"\n--- DEBUG: Processing Step 6 (Filtering Results) ---") # Update step number
        # Use the data *after* transfer and position update for filtering
        constructions_to_remove = []
        # Iterate through the data *after* transfer and position update
        for construction_id, data in processed_data_after_transfer.items():
            # print(f"DEBUG:   Filtering check for ID: '{construction_id}'") # DEBUG ADDED
            is_detailed = data.get('type') == 'Detailed'
            if is_detailed:
                system_details = data.get('system_details', {})
                u_value = system_details.get('U-Value')
                shgc = system_details.get('SHGC')
                vt = system_details.get('VT')

                # Check if any simulation property is missing (is None) AND it has NO shading layers
                # Check the 'shading_layers' status *after* potential transfer
                has_shading = bool(data.get('shading_layers'))
                if (u_value is None or shgc is None or vt is None) and not has_shading:
                    # print(f"DEBUG:     -> Marking for removal (Missing props, no shades): {construction_id}") # DEBUG ADDED
                    constructions_to_remove.append(construction_id)
                elif (u_value is None or shgc is None or vt is None) and has_shading:
                    # print(f"DEBUG:     -> Keeping (Missing props, but has shades): {construction_id}") # DEBUG ADDED
                    pass
                else:
                    # print(f"DEBUG:     -> Keeping (Has props or is Simple): {construction_id}") # DEBUG ADDED
                    pass

        # Remove from the data *after* transfer and position update
        final_filtered_data = processed_data_after_transfer.copy()
        for construction_id in constructions_to_remove:
            if construction_id in final_filtered_data: # Check existence before deleting
                 del final_filtered_data[construction_id]

        # --- End Step 6 (Filtering) ---

        self.parsed_glazing_data = final_filtered_data # Assign the final filtered data
        # print(f"\n--- DEBUG: Final Parsed Glazing Data Keys: {list(self.parsed_glazing_data.keys())} ---") # DEBUG ADDED
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
