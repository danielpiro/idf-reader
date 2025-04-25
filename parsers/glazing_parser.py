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
            simulation_output_csv: Path to the eplustbl.csv file from simulation (optional).
            idf_objects: Raw IDF objects if direct access is needed (optional).
        """
        self._constructions_glazing_cache = constructions_glazing_cache
        self._window_simple_glazing_cache = window_simple_glazing_cache
        self._window_glazing_cache = window_glazing_cache
        self._window_gas_cache = window_gas_cache
        self._window_shade_cache = window_shade_cache
        self._simulation_output_csv = simulation_output_csv # Store the path
        self._sim_properties = {} # Dictionary to store properties read from CSV
        self._idf = idf_objects # Store if needed
        self.parsed_glazing_data = {} # Store results here

    def _parse_simulation_output_csv(self):
        """Parses the eplustbl.csv file to extract window properties from the 'Exterior Fenestration' table."""
        if not self._simulation_output_csv or not os.path.exists(self._simulation_output_csv):
            print(f"DEBUG: Simulation output CSV not found or not provided: {self._simulation_output_csv}")
            return # No file to parse

        print(f"DEBUG: Parsing simulation output CSV: {self._simulation_output_csv}")
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
                        print(f"DEBUG: Found target table title: 'Exterior Fenestration'")
                        continue # Skip the table title row itself

                    if in_target_table:
                        # --- Header Row Search ---
                        if not headers_found:
                            current_headers_norm = [h.strip().lower() for h in row]
                            # Check if this row looks like the header row (contains key elements)
                            if "construction" in current_headers_norm and "glass u-factor [w/m2-k]" in current_headers_norm:
                                print(f"DEBUG: Potential header row found: {current_headers_norm}")
                                try:
                                    # Validate and map expected headers to their actual indices
                                    for key, _ in header_map.items(): # Don't need expected_index here
                                        if key in current_headers_norm:
                                            actual_index = current_headers_norm.index(key)
                                            col_indices[key] = actual_index
                                            # print(f"DEBUG: Mapped '{key}' to column index {actual_index}") # Less verbose
                                        else:
                                            # Fallback for 'construction' might not be needed if it's always present
                                            raise ValueError(f"Missing required header: '{key}'")

                                    # Check if all required headers were found
                                    if len(col_indices) != len(header_map):
                                        missing = set(header_map.keys()) - set(col_indices.keys())
                                        raise ValueError(f"Missing required headers: {missing}")

                                    headers_found = True
                                    print(f"DEBUG: Successfully validated headers. Indices: {col_indices}")
                                except ValueError as e:
                                    print(f"DEBUG: Error validating required headers: {e}. Headers found: {current_headers_norm}")
                                    in_target_table = False # Abort if headers invalid
                                continue # Skip the header row once processed/validated
                            else:
                                # This row is between title and header (e.g., blank), skip it
                                print(f"DEBUG: Skipping row before header: {row}")
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
                                print(f"DEBUG: End of data rows detected (found '{row[0].strip()}', is_total={is_total_row}, is_blank={is_blank_data_row}).")
                                in_target_table = False # Stop processing this table
                                continue # Skip this end/total/blank row

                            # Process data row (if not end condition)
                            max_index = max(col_indices.values()) if col_indices else -1
                            if max_index == -1: # Should not happen if headers were found
                                print("DEBUG: Error - Headers marked found but col_indices is empty.")
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
                                            # print(f"DEBUG: Stored props for '{construction_name}': U={u_value}, SHGC={shgc}, VT={vt}")
                                        # else: # Less verbose logging for duplicates
                                            # print(f"DEBUG: Duplicate construction '{construction_name}' found, using first entry.")
                                except IndexError:
                                    print(f"DEBUG: Skipping row due to IndexError (mismatched length?): {row}")
                                except KeyError as e:
                                     print(f"DEBUG: Skipping row due to KeyError (header mapping issue?): {e} | Row: {row}")
                                except Exception as e:
                                    print(f"DEBUG: Error processing data row: {e} | Row: {row}")
                            else:
                                 print(f"DEBUG: Skipping short data row: {row}")
                        # --- End Data Row Processing ---


        except FileNotFoundError:
            print(f"DEBUG: Error - Simulation output CSV file not found at: {self._simulation_output_csv}")
        except Exception as e:
            print(f"DEBUG: Error reading or parsing simulation output CSV: {e}")
            import traceback
            traceback.print_exc() # Print full traceback for debugging CSV errors

        print(f"DEBUG: Finished parsing CSV. Found properties for {len(self._sim_properties)} constructions.")


    def parse_glazing_data(self) -> Dict[str, Dict[str, Any]]:
        """
        Processes the cached glazing constructions to extract detailed data,
        incorporating properties from the simulation output CSV if available.
        Populates self.parsed_glazing_data.
        """
        # --- Parse Simulation Output First ---
        self._parse_simulation_output_csv() # Populate self._sim_properties

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

        # --- Step 2: Process Detailed Glazing Constructions ---
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
                        'Reflectivity': safe_float(shade.get('solar_reflectance')),
                        'Position': 'Unknown' # Position needs context from WindowShadingControl
                    })

            # Only add if it contains glazing or gas layers (is actually a window/glazing construction)
            if glazing_layers_details:
                 # --- Get properties from simulation output if available ---
                 sim_props = self._sim_properties.get(construction_id, {})
                 # if not sim_props: # Removed debug print for no match
                 #     print(f"DEBUG:   -> No match found in sim properties for '{construction_id}'")
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

        # --- Step 3: Link Shades defined via separate constructions (like Construction:WithShading) ---
        # This part assumes constructions marked 'simple' with no 'data' link shades
        print("\n--- DEBUG: Processing Step 3: Linking Shades ---") # DEBUG PRINT
        keys_to_delete = [] # Track shade-defining constructions to remove later
        for construction_id, construction_data in self._constructions_glazing_cache.items():
            # Check if it's a 'simple' type construction NOT already processed as a simple glazing system itself
            if construction_data.get('type') == 'simple' and construction_id not in processed_data:
                print(f"DEBUG: Checking potential shade definition: {construction_id}") # DEBUG PRINT
                # This might be a construction defining shades for another construction
                current_shades_info = []
                base_construction_id = None
                material_layers = construction_data.get('material_layers', [])
                print(f"DEBUG:   Layers: {material_layers}") # DEBUG PRINT

                for layer_name in material_layers:
                    if layer_name in self._window_shade_cache:
                        shade = self._window_shade_cache[layer_name]
                        current_shades_info.append({
                            'Name': layer_name,
                            'Thickness': safe_float(shade.get('thickness')),
                            'Conductivity': safe_float(shade.get('conductivity')),
                            'Transmittance': safe_float(shade.get('solar_transmittance')),
                            'Reflectivity': safe_float(shade.get('solar_reflectance')),
                            'Position': 'Unknown' # Position needs context
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
                            print(f"DEBUG:   Found potential base construction '{base_construction_id}' from material '{layer_name}' (derived)") # DEBUG PRINT
                            break # Assume first non-shade is the base
                        elif layer_name in processed_data:
                            # Found base construction directly by layer name (e.g., for detailed constructions)
                            base_construction_id = layer_name
                            print(f"DEBUG:   Found potential base construction '{base_construction_id}' directly from layer name") # DEBUG PRINT
                            break # Assume first non-shade is the base
                        else:
                             # Layer is not a shade and didn't match a processed construction directly or via derivation
                             print(f"DEBUG:   Layer '{layer_name}' is not a shade and did not match a processed construction (derived: '{potential_base_id_derived}').") # DEBUG PRINT


                if base_construction_id and current_shades_info:
                    print(f"DEBUG:   Attempting to link shades { [s['Name'] for s in current_shades_info] } to base: {base_construction_id}") # DEBUG PRINT
                    # Add/Update shading layers in the base construction
                    if base_construction_id in processed_data:
                        # Merge shades, avoiding duplicates if necessary
                        existing_shades = {s['Name'] for s in processed_data[base_construction_id]['shading_layers']}
                        for shade_info in current_shades_info:
                            if shade_info['Name'] not in existing_shades:
                                processed_data[base_construction_id]['shading_layers'].append(shade_info)
                                print(f"DEBUG:     Added shade '{shade_info['Name']}' to '{base_construction_id}'") # DEBUG PRINT
                        # Mark this shade-defining construction for removal
                        keys_to_delete.append(construction_id)
                    else:
                        print(f"DEBUG:   WARNING - Base construction '{base_construction_id}' not found in processed_data.") # DEBUG PRINT
                elif current_shades_info:
                     print(f"DEBUG:   WARNING - Found shades but no base construction identified for '{construction_id}'.") # DEBUG PRINT


        # Clean up: Remove the constructions that only defined shades
        # (We could keep them if needed, but they aren't glazing systems themselves)
        # for key in keys_to_delete:
        #     if key in processed_data: # Should not happen based on logic, but safe check
        #         del processed_data[key]


        # --- Step 4: Filter out detailed constructions missing simulation properties ---
        print(f"\n--- DEBUG: Processing Step 4: Filtering Results ---")
        print(f"DEBUG: Pre-filter count: {len(processed_data)} constructions.")
        constructions_to_remove = []
        for construction_id, data in processed_data.items():
            # Check if it's a detailed construction
            is_detailed = data.get('type') == 'Detailed' # Check the type field added earlier
            if is_detailed:
                system_details = data.get('system_details', {})
                u_value = system_details.get('U-Value')
                shgc = system_details.get('SHGC')
                vt = system_details.get('VT')
                # Check if any simulation property is missing (is None)
                if u_value is None or shgc is None or vt is None:
                    constructions_to_remove.append(construction_id)
                    print(f"DEBUG: Marking detailed construction '{construction_id}' for removal (missing sim properties: U={u_value}, SHGC={shgc}, VT={vt}).")

        for construction_id in constructions_to_remove:
            del processed_data[construction_id]

        print(f"DEBUG: Post-filter count: {len(processed_data)} constructions.")
        # --- End Filtering ---


        self.parsed_glazing_data = processed_data # Assign the filtered data
        return self.parsed_glazing_data

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