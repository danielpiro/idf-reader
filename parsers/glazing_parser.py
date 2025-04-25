# parsers/glazing_parser.py
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
                 idf_objects: Any = None): # Pass relevant parts of idf if needed, or None
        """
        Initializes the parser with necessary data caches.

        Args:
            constructions_glazing_cache: Cache containing pre-filtered glazing constructions.
            window_simple_glazing_cache: Cache for simple glazing system materials.
            window_glazing_cache: Cache for window glazing materials.
            window_gas_cache: Cache for window gas materials.
            window_shade_cache: Cache for window shade materials.
            idf_objects: Raw IDF objects if direct access is needed (optional).
        """
        self._constructions_glazing_cache = constructions_glazing_cache
        self._window_simple_glazing_cache = window_simple_glazing_cache
        self._window_glazing_cache = window_glazing_cache
        self._window_gas_cache = window_gas_cache
        self._window_shade_cache = window_shade_cache
        self._idf = idf_objects # Store if needed
        self.parsed_glazing_data = {} # Store results here

    def parse_glazing_data(self) -> Dict[str, Dict[str, Any]]:
        """
        Processes the cached glazing constructions to extract detailed data.
        Adapts logic previously in DataLoader._filter_constructions_glazing.
        Populates self.parsed_glazing_data instead of modifying cache in place.
        """
        processed_data = {}

        # --- Step 1: Process Simple Glazing Systems ---
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
                 processed_data[construction_id] = {
                    'id': construction_id,
                    'name': construction_id,
                    'type': 'Detailed',
                    'system_details': { # Placeholder for detailed system values
                        'Name': construction_id,
                        'Type': 'Detailed Glazing',
                        'Thickness': total_thickness if total_thickness > 0 else None,
                        'U-Value': None, # Requires calculation
                        'VT': None,      # Requires calculation
                        'SHGC': None     # Requires calculation
                    },
                    'glazing_layers': glazing_layers_details,
                    'shading_layers': shading_layers_details, # Store associated shades if any
                    'raw_object': construction_data.get('raw_object'),
                    # NOTE: System U-Value, VT, SHGC for detailed constructions are complex to calculate
                    # from layers alone and require simulation or dedicated tools (e.g., WINDOW).
                    # They are intentionally left as None here.
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


        self.parsed_glazing_data = processed_data
        return self.parsed_glazing_data

    def update_system_properties_from_eio(self, eio_properties: Dict[str, Dict[str, float]]):
        """
        Updates the parsed_glazing_data with U-Value, SHGC, VT from EIO output.

        Args:
            eio_properties: Dictionary returned by parse_eio_for_window_properties.
        """
        if not eio_properties:
            print("DEBUG: No EIO properties provided to update GlazingParser data.")
            return

        updated_count = 0
        for construction_id, data in self.parsed_glazing_data.items():
            if construction_id in eio_properties:
                props = eio_properties[construction_id]
                # Update system_details, especially for detailed constructions
                if 'system_details' in data:
                    data['system_details']['U-Value'] = props.get('U-Value')
                    data['system_details']['SHGC'] = props.get('SHGC')
                    data['system_details']['VT'] = props.get('VT')
                    updated_count += 1
                    # print(f"DEBUG: Updated system properties for '{construction_id}' from EIO.") # Optional Debug
                else:
                     print(f"DEBUG: Warning - '{construction_id}' found in EIO but no 'system_details' in parser data.")
            # else: Construction not found in EIO report (might be opaque, etc.)

        print(f"DEBUG: Updated system properties for {updated_count} constructions from EIO data.")


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