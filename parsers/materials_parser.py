"""
Extracts and processes materials and constructions.
Uses DataLoader for cached access to IDF data.
"""
from typing import Dict, Any, Optional, List, Tuple
from utils.data_loader import DataLoader
from utils.data_models import MaterialData, ConstructionData
from .base_parser import BaseParser

# Surface film resistance configuration
SURFACE_FILM_RESISTANCE = {
    "internal wall": 0.0,
    "intermediate ceiling": 0.0, 
    "intermediate floor": 0.0,
    "ground floor": 0.1,
    "ground wall": 0.1,
    "ground ceiling": 0.1,
    "external wall": 0.17,
    "separation wall": 0.26,
    "external floor": 0.21,
    "separation floor": 0.34,
    "separation ceiling": 0.2,
    "default": 0.14
}

class MaterialsParser(BaseParser):
    """
    Extracts material properties and construction definitions using cached data from DataLoader.
    """
    def __init__(self, data_loader: Optional[DataLoader] = None):
        super().__init__(data_loader, "MaterialsParser")
        self.element_data = []
        self.materials = {}
        self.constructions = {}

    def process_idf(self, idf) -> None:
        """
        Process materials and constructions using data from DataLoader.
        """
        if not self.data_loader:
            raise RuntimeError("MaterialsParser requires a DataLoader instance.")
        
        
        try:
            self.materials.clear()
            self.constructions.clear()
            self.element_data.clear()
            
            # Process materials
            material_cache = self.data_loader.get_materials()
            
            for material_id, raw_material_data in material_cache.items():
                
                self.materials[material_id] = MaterialData(
                    id=material_id,
                    name=material_id,
                    conductivity=raw_material_data.get('conductivity'),
                    density=raw_material_data.get('density'),
                    specific_heat=raw_material_data.get('specific_heat'),
                    thickness=raw_material_data.get('thickness'),
                    solar_absorptance=raw_material_data.get('solar_absorptance')
                )
            
            construction_cache = self.data_loader.get_constructions()
            
            
            for construction_id, raw_construction_data in construction_cache.items():
                material_layers = raw_construction_data['material_layers']
                # Check for missing materials
                missing_materials = []
                total_thickness = 0.0
                
                for layer_id in material_layers:
                    if layer_id in self.materials:
                        material_thickness = self.materials[layer_id].thickness
                        if material_thickness:
                            total_thickness += material_thickness
                    else:
                        missing_materials.append(layer_id)
                
                
                self.constructions[construction_id] = ConstructionData(
                    id=construction_id,
                    name=construction_id,
                    material_layers=material_layers,
                    thickness=total_thickness
                )     
            self._process_element_data(construction_cache)
            
        except Exception as e:
            raise RuntimeError(f"Error processing materials and constructions: {e}")

    def _calculate_material_mass_with_low_conductivity_adjustment(self, material_data, element_type: str = None, construction_id: str = None, low_conductivity_found: Dict = None) -> float:
        """
        Calculate material mass with low conductivity adjustment logic.
        
        Args:
            material_data: Material data object
            element_type: Element type (for external wall specific logic)
            construction_id: Construction ID (for tracking)
            low_conductivity_found: Dictionary to track low conductivity materials found
            
        Returns:
            float: Adjusted mass value
        """        
        density = material_data.density or 0.0
        thickness = material_data.thickness or 0.0
        mass = density * thickness
        conductivity = material_data.conductivity
        
        # Apply low conductivity adjustment
        if conductivity is not None and conductivity < 0.2 and conductivity != 0:
            # For element data processing: only apply to external walls and track by construction
            if element_type and low_conductivity_found is not None:
                if element_type.lower() == "external wall" and construction_id not in low_conductivity_found.get(element_type, set()):
                    mass = mass / 2
                    if element_type not in low_conductivity_found:
                        low_conductivity_found[element_type] = set()
                    low_conductivity_found[element_type].add(construction_id)
            else:
                # For mass calculation: apply to first low conductivity material found
                mass = mass / 2
                
        return mass

    def _calculate_thermal_resistance(self, material_data) -> float:
        """
        Calculate thermal resistance for a material.
        
        Args:
            material_data: Material data object
            
        Returns:
            float: Thermal resistance value
        """
        thickness = material_data.thickness or 0.0
        conductivity = material_data.conductivity
        return thickness / conductivity if conductivity else 0.0

    def _process_element_data(self, construction_cache: Dict[str, Dict[str, Any]]) -> None:
        """
        Process element data for report generation.
        This combines materials and constructions to create report data.
        """
        # We only need surfaces for element type detection - get all surfaces once
        surfaces = self.data_loader.get_surfaces()
        
        
        # Create mapping for _rev constructions to their base versions
        construction_mapping = {}
        low_conductivity_found = {}

        for construction_id in construction_cache.keys():
            construction_data = self.constructions[construction_id]
            # Note: Reversed constructions are already filtered out during process_idf
            element_types, dont_use = self._get_element_type(construction_id, surfaces, construction_mapping)
            
            if dont_use or not element_types:
                continue
            
            s_type, boundary = self._get_surface_type_and_boundary(construction_id, surfaces, construction_mapping)
            
            
            # Process each element type separately, grouping all materials under each element type
            for element_type in element_types:
                film_resistance = self._get_surface_film_resistance(element_type)
                
                for layer_id in construction_data.material_layers:
                    material_data = self.materials.get(layer_id)
                    if not material_data:
                        continue
                    
                    thermal_resistance = self._calculate_thermal_resistance(material_data)
                    mass = self._calculate_material_mass_with_low_conductivity_adjustment(
                        material_data, element_type, construction_id, low_conductivity_found
                    )
                    
                    element_entry = {
                        "element_type": element_type,
                        "element_name": construction_id,
                        "material_name": layer_id,
                        "thickness": material_data.thickness,
                        "conductivity": material_data.conductivity,
                        "density": material_data.density,
                        "mass": mass,
                        "thermal_resistance": thermal_resistance,
                        "solar_absorptance": material_data.solar_absorptance,
                        "specific_heat": material_data.specific_heat,
                        "surface_film_resistance": film_resistance,
                        "surface_type": s_type,
                        "boundary_condition": boundary
                    }
                    
                    self.element_data.append(element_entry)
        
        # Filter the final element data after all processing is complete
        self._filter_element_data(construction_cache)

    def _filter_element_data(self, construction_cache: Dict[str, Dict[str, Any]]) -> None:
        """
        Filter the element data based on your criteria.
        This runs after all element types and properties are calculated.
        
        Args:
            construction_cache: Dictionary of construction data from DataLoader
        """
        # Filter constructions: remove duplicates with different suffixes
        constructions_to_remove = []
        processed_pairs = set()
        
        for construction_id in list(self.constructions.keys()):
            if construction_id in constructions_to_remove:
                continue
                
            construction_id_lower = construction_id.lower()
            base_name = None
            
            # Extract base name by removing suffix, or use construction_id as base name if no suffix
            if construction_id_lower.endswith('_reversed_rev'):
                base_name = construction_id[:-len('_reversed_rev')]
            elif construction_id_lower.endswith('_reversed'):
                base_name = construction_id[:-len('_reversed')]
            elif construction_id_lower.endswith('_rev'):
                base_name = construction_id[:-len('_rev')]
            else:
                # This construction has no suffix, so it could be a base construction
                base_name = construction_id
            
                
            # Look for other constructions with the same base name but different suffixes
            potential_matches = []
            for other_id in self.constructions.keys():
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
                    # This other construction has no suffix, so it could be a base construction
                    other_base_name = other_id
                
                if other_base_name and other_base_name.lower() == base_name.lower():
                    potential_matches.append(other_id)
            
            # Compare current construction with all potential matches
            for match_id in potential_matches:
                pair_key = tuple(sorted([construction_id, match_id]))
                if pair_key in processed_pairs:
                    continue
                processed_pairs.add(pair_key)
                
                construction1 = self.constructions[construction_id]
                construction2 = self.constructions[match_id]
                
                # Compare element types
                surfaces = self.data_loader.get_surfaces()
                types1, _ = self._get_element_type(construction_id, surfaces, {})
                types2, _ = self._get_element_type(match_id, surfaces, {})
                
                # Convert to sets for comparison
                type_set1 = set(types1)
                type_set2 = set(types2)
                
                # Compare materials (order doesn't matter)
                materials1 = set(construction1.material_layers)
                materials2 = set(construction2.material_layers)
                
                # If same materials and one element type set is subset of the other, remove the subset version
                if materials1 == materials2 and (type_set1 == type_set2 or type_set1.issubset(type_set2) or type_set2.issubset(type_set1)):
                    # Determine which one to remove - prefer keeping the one without suffix or with simpler suffix
                    to_remove = None
                    
                    # Check if either construction has a suffix
                    construction_id_has_suffix = (construction_id.lower().endswith('_rev') or 
                                                construction_id.lower().endswith('_reversed') or 
                                                construction_id.lower().endswith('_reversed_rev'))
                    match_id_has_suffix = (match_id.lower().endswith('_rev') or 
                                         match_id.lower().endswith('_reversed') or 
                                         match_id.lower().endswith('_reversed_rev'))
                    
                    # Priority 1: Keep the one with more element types (superset)
                    if type_set1.issuperset(type_set2) and not type_set2.issuperset(type_set1):
                        # construction_id has more types, remove match_id
                        to_remove = match_id
                    elif type_set2.issuperset(type_set1) and not type_set1.issuperset(type_set2):
                        # match_id has more types, remove construction_id
                        to_remove = construction_id
                    # Priority 2: Keep base version (no suffix) over suffix version
                    elif not construction_id_has_suffix and match_id_has_suffix:
                        # construction_id is base, match_id has suffix - remove suffix version
                        to_remove = match_id
                    elif construction_id_has_suffix and not match_id_has_suffix:
                        # match_id is base, construction_id has suffix - remove suffix version
                        to_remove = construction_id
                    # Priority 3: Both have suffixes, prefer _rev over _reversed
                    elif construction_id_has_suffix and match_id_has_suffix:
                        if construction_id.lower().endswith('_rev') and match_id.lower().endswith('_reversed'):
                            to_remove = match_id
                        elif construction_id.lower().endswith('_reversed') and match_id.lower().endswith('_rev'):
                            to_remove = construction_id
                        else:  # Both same suffix type, keep first alphabetically
                            to_remove = max(construction_id, match_id)
                    # If neither has suffix and same types, shouldn't happen but keep first alphabetically
                    else:
                        to_remove = max(construction_id, match_id)
                    
                    if to_remove and to_remove not in constructions_to_remove:
                        constructions_to_remove.append(to_remove)
        
        # Remove the identified constructions
        for construction_id in constructions_to_remove:
            del self.constructions[construction_id]
            # Also remove from element_data
            self.element_data = [element for element in self.element_data if element.get('element_name') != construction_id]

    def _get_surface_type_and_boundary(self, construction_id: str, surfaces: Dict[str, Dict[str, Any]], construction_mapping: Dict[str, str] = None):
        """
        Get the surface type and boundary condition for a given construction ID.

        Args:
            construction_id: The construction ID.
            surfaces: The surfaces data dictionary.
            construction_mapping: Dictionary mapping _rev construction names to base names

        Returns:
            tuple: A tuple containing the surface type and boundary condition.
        """
        # Check direct references first
        for surface in surfaces.values():
            if surface.get('construction_name') == construction_id:
                return surface.get('surface_type', '').lower(), surface.get('boundary_condition', '').lower()
        
        # Check mapped references
        if construction_mapping:
            for rev_name, base_name in construction_mapping.items():
                if base_name == construction_id:
                    for surface in surfaces.values():
                        if surface.get('construction_name') == rev_name:
                            return surface.get('surface_type', '').lower(), surface.get('boundary_condition', '').lower()
        
        return '', ''

    def _get_element_type(self, construction_id: str, surfaces: Dict[str, Dict[str, Any]], construction_mapping: Dict[str, str] = None) -> Tuple[List[str], bool]:
        """
        Determine element type based on construction usage - simplified version.
        """
        construction_surfaces = self._find_construction_surfaces(construction_id, surfaces, construction_mapping)
        
        if not construction_surfaces:
            return [], False

        element_types = set()
        hvac_zones = self.data_loader.get_hvac_zones()
        
        surfaces_with_hvac_zones = 0
        surfaces_without_hvac_zones = 0
        
        for surface in construction_surfaces:
            if surface.get('is_glazing', False):
                element_types.add("Glazing")
                continue
            
            surface_has_hvac, is_zone_interior = self._check_surface_hvac_zones(surface, hvac_zones)
            
            if surface_has_hvac:
                surfaces_with_hvac_zones += 1
            else:
                surfaces_without_hvac_zones += 1
                # Skip surfaces without HVAC zones - they shouldn't contribute to element types
                continue
            
            element_type = self._determine_surface_element_type(surface, is_zone_interior)
            
            if element_type:
                element_types.add(element_type)
        
        dont_use = surfaces_with_hvac_zones == 0 and surfaces_without_hvac_zones > 0
        
        return list(element_types), dont_use
    
    def _find_construction_surfaces(self, construction_id: str, surfaces: Dict[str, Dict[str, Any]], construction_mapping: Dict[str, str] = None) -> List[Dict[str, Any]]:
        """Find all surfaces that use this construction."""
        construction_surfaces = [s for s in surfaces.values() if s.get('construction_name') == construction_id]
        
        if construction_mapping:
            for rev_name, base_name in construction_mapping.items():
                if base_name == construction_id:
                    mapped_surfaces = [s for s in surfaces.values() if s.get('construction_name') == rev_name]
                    construction_surfaces.extend(mapped_surfaces)
        
        return construction_surfaces
    
    def _check_surface_hvac_zones(self, surface: Dict[str, Any], hvac_zones: List[str]) -> Tuple[bool, bool]:
        """Check if surface connects HVAC zones and if it's zone interior."""
        boundary = surface.get('boundary_condition', '').lower()
        
        # Convert hvac_zones to lowercase for case-insensitive comparison
        hvac_zones_lower = [zone.lower() for zone in hvac_zones] if hvac_zones else []
        
        if boundary != "surface":
            # Use the surface's zone_name directly instead of parsing from surface ID
            zone_name = surface.get('zone_name', '').lower()
            if zone_name in hvac_zones_lower:
                return True, False
            return False, False
        
        try:
            raw_object = surface.get('raw_object')
            if not raw_object:
                return False, False
            
            outside_boundary_obj_name = None
            if hasattr(raw_object, 'Outside_Boundary_Condition_Object'):
                outside_boundary_obj_name = raw_object.Outside_Boundary_Condition_Object
            elif isinstance(raw_object, dict) and 'Outside_Boundary_Condition_Object' in raw_object:
                outside_boundary_obj_name = raw_object['Outside_Boundary_Condition_Object']
            
            if not isinstance(outside_boundary_obj_name, str) or not outside_boundary_obj_name:
                return False, False
            
            zone_name_candidate = outside_boundary_obj_name.split("_")[0].strip().lower()
            construction_zone = raw_object.Name.split("_")[0].strip().lower()
            
            is_hvac_inside = construction_zone in hvac_zones_lower
            is_hvac_outside = zone_name_candidate in hvac_zones_lower
            
            surface_has_hvac_zones = is_hvac_inside or is_hvac_outside
            is_zone_interior = is_hvac_inside and is_hvac_outside
            
            return surface_has_hvac_zones, is_zone_interior
            
        except Exception:
            return False, False
    
    def _determine_surface_element_type(self, surface: Dict[str, Any], is_zone_interior: bool) -> str:
        """Determine element type based on surface type and boundary condition."""
        s_type = surface.get('surface_type', '').lower()
        boundary = surface.get('boundary_condition', '').lower()
        
        element_type_map = {
            "wall": {
                "outdoors": "External wall",
                "ground": "Ground wall",
                "default": "Internal wall" if is_zone_interior else "Separation wall"
            },
            "floor": {
                "outdoors": "External floor", 
                "ground": "Ground floor",
                "default": "Intermediate floor" if is_zone_interior else "Separation floor"
            },
            "ceiling": {
                "ground": "Ground ceiling",
                "outdoors": "External ceiling",
                "default": "Intermediate ceiling" if is_zone_interior else "Separation ceiling"
            },
            "roof": {
                "default": "Roof"
            }
        }
        
        if s_type in element_type_map:
            type_config = element_type_map[s_type]
            result = type_config.get(boundary, type_config.get("default", ""))
        else:
            result = ""
        
        
        return result

    def _get_surface_film_resistance(self, element_type: str) -> float:
        """
        Determine the surface film resistance constant based on element type.
        Now uses configuration instead of hardcoded values.
        """
        element_type_lower = element_type.lower()
        return SURFACE_FILM_RESISTANCE.get(element_type_lower, SURFACE_FILM_RESISTANCE["default"])

    def get_element_data(self) -> list:
        """
        Returns the list of processed element data.

        Returns:
            list: List of dictionaries containing element data and calculated properties
        """
        return self.element_data

    def get_all_materials(self) -> Dict[str, MaterialData]:
        """
        Get all processed materials.

        Returns:
            Dict[str, MaterialData]: Dictionary of all materials
        """
        return self.materials

    def get_all_constructions(self) -> Dict[str, ConstructionData]:
        """
        Get all processed constructions.

        Returns:
            Dict[str, ConstructionData]: Dictionary of all constructions
        """
        return self.constructions

    def calculate_construction_mass_per_area(self, construction_id: str) -> float:
        """
        Calculate the total mass per square meter for a given construction.
        Applies the same low conductivity reduction logic as the manual calculation.

        Args:
            construction_id: The ID of the construction.

        Returns:
            float: The total mass per square meter (kg/m²).
        """
        construction = self.constructions.get(construction_id)
        if not construction:
            return 0.0
        
        total_mass_per_area = 0.0
        found_low_conductivity = False
        
        for layer_id in construction.material_layers:
            material = self.materials.get(layer_id)
            if not material:
                continue
                
            density = material.density or 0.0
            thickness = material.thickness or 0.0
            conductivity = material.conductivity
            
            # Check for low conductivity adjustment
            applies_low_conductivity = (not found_low_conductivity and 
                                      conductivity is not None and 
                                      conductivity < 0.2 and 
                                      conductivity != 0)
            
            if applies_low_conductivity:
                layer_mass = self._calculate_material_mass_with_low_conductivity_adjustment(material)
                found_low_conductivity = True
            else:
                layer_mass = density * thickness
                
            total_mass_per_area += layer_mass
        
        return total_mass_per_area

    def calculate_construction_properties(self, construction_id: str) -> Dict[str, float]:
        """
        Calculate properties for a specific construction.

        Args:
            construction_id: ID of the construction

        Returns:
            Dict[str, float]: Dictionary with properties like thickness and conductivity
        """
        construction = self.constructions.get(construction_id)
        if not construction:
            return {'thickness': 0.0, 'conductivity': 0.0}

        total_resistance = 0.0
        total_thickness = construction.thickness

        for layer_id in construction.material_layers:
            material = self.materials.get(layer_id)
            if material:
                total_resistance += self._calculate_thermal_resistance(material)

        conductivity = total_thickness / total_resistance if total_resistance > 0 else 0.0

        return {
            'thickness': total_thickness,
            'conductivity': conductivity
        }

    def get_constructions_u_values(self) -> Dict[str, float]:
        """
        Get U-values for all constructions based on the calculations from materials report.

        Returns:
            Dict[str, float]: Dictionary mapping construction IDs to their U-values
        """
        u_values = {}
        for construction_id, construction_data in self.constructions.items():
            # Note: Reversed constructions are already filtered out during process_idf
            material_layers = construction_data.material_layers
            total_resistance = 0.0
            for layer_id in material_layers:
                material_data = self.materials.get(layer_id)
                if material_data:
                    total_resistance += self._calculate_thermal_resistance(material_data)
            element_types, _ = self._get_element_type(construction_id, self.data_loader.get_surfaces(), None)
            film_resistance = self._get_surface_film_resistance(element_types[0]) if element_types else 0.0
            r_value_with_film = total_resistance + film_resistance
            u_value = 1.0 / r_value_with_film if r_value_with_film > 0 else 0.0
            u_values[construction_id] = u_value
        return u_values
