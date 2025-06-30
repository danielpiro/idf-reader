"""
Extracts and processes materials and constructions.
Uses DataLoader for cached access to IDF data.
"""
from typing import Dict, Any, Optional
from utils.data_loader import DataLoader
from utils.data_models import MaterialData, ConstructionData

class MaterialsParser:
    """
    Extracts material properties and construction definitions using cached data from DataLoader.
    """
    def __init__(self, data_loader: Optional[DataLoader] = None):
        self.data_loader = data_loader
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
            material_cache = self.data_loader.get_materials()
            for material_id, raw_material_data in material_cache.items():
                self.materials[material_id] = MaterialData(
                    id=material_id,
                    name=material_id,
                    conductivity=raw_material_data.get('conductivity', 0.0),
                    density=raw_material_data.get('density', 0.0),
                    specific_heat=raw_material_data.get('specific_heat', 0.0),
                    thickness=raw_material_data.get('thickness', 0.0),
                    solar_absorptance=raw_material_data.get('solar_absorptance', 0.0)
                )
            construction_cache = self.data_loader.get_constructions()
            
            # Filter constructions to handle reversed logic
            filtered_constructions = self._filter_reversed_constructions(construction_cache)
            
            for construction_id, raw_construction_data in filtered_constructions.items():
                material_layers = raw_construction_data['material_layers']
                total_thickness = sum(self.materials[layer_id].thickness for layer_id in material_layers if layer_id in self.materials)
                self.constructions[construction_id] = ConstructionData(
                    id=construction_id,
                    name=construction_id,
                    material_layers=material_layers,
                    thickness=total_thickness
                )
            self._process_element_data()
        except Exception as e:
            raise RuntimeError(f"Error processing materials and constructions: {e}")

    def _filter_reversed_constructions(self, construction_cache: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Filter constructions to handle reversed construction logic:
        - Never show constructions with _rev suffix (regardless of whether non-reversed version exists)
        - For _Reversed suffix: only show if no non-reversed version exists
        
        Args:
            construction_cache: Dictionary of all constructions from DataLoader
            
        Returns:
            Dict[str, Dict[str, Any]]: Filtered construction cache
        """
        filtered = {}
        
        # First, identify all regular and reversed constructions
        regular_constructions = {}
        capital_reversed_constructions = {}  # Only for _Reversed suffix
        
        for construction_id, construction_data in construction_cache.items():
            construction_lower = construction_id.lower()
            
            # Skip all constructions with _rev suffix (never show them)
            if construction_lower.endswith('_rev'):
                continue
            elif construction_lower.endswith('_reversed'):
                # Handle _Reversed suffix with the original logic
                base_name = self._get_base_construction_name(construction_id)
                capital_reversed_constructions[base_name] = (construction_id, construction_data)
            else:
                # Regular construction
                regular_constructions[construction_id] = (construction_id, construction_data)
        
        # Add regular constructions
        for construction_id, (orig_id, construction_data) in regular_constructions.items():
            filtered[orig_id] = construction_data
        
        # Add _Reversed constructions only if no regular version exists
        for base_name, (reversed_id, construction_data) in capital_reversed_constructions.items():
            if base_name not in regular_constructions:
                filtered[reversed_id] = construction_data
        
        return filtered

    def _get_base_construction_name(self, construction_id: str) -> str:
        """
        Get the base construction name by removing reversed suffix.
        
        Args:
            construction_id: The construction ID that may have a reversed suffix
            
        Returns:
            str: The base construction name without reversed suffix
        """
        construction_lower = construction_id.lower()
        if construction_lower.endswith('_reversed'):
            return construction_id[:-9]  # Remove '_Reversed'
        elif construction_lower.endswith('_rev'):
            return construction_id[:-4]   # Remove '_rev'
        return construction_id

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
        mass = material_data.density * material_data.thickness
        
        # Apply low conductivity adjustment
        if material_data.conductivity < 0.2 and material_data.conductivity != 0:
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
        return material_data.thickness / material_data.conductivity if material_data.conductivity != 0 else 0.0

    def _process_element_data(self) -> None:
        """
        Process element data for report generation.
        This combines materials and constructions to create report data.
        """
        surfaces = self.data_loader.get_surfaces()
        low_conductivity_found = {}
        for construction_id, construction_data in self.constructions.items():
            # Note: Reversed constructions are already filtered out during process_idf
            element_types, dont_use = self._get_element_type(construction_id, surfaces)
            if dont_use or not element_types:
                continue
            s_type, boundary = self._get_surface_type_and_boundary(construction_id, surfaces)
            for layer_id in construction_data.material_layers:
                material_data = self.materials.get(layer_id)
                if not material_data:
                    continue
                thermal_resistance = self._calculate_thermal_resistance(material_data)
                for element_type in element_types:
                    film_resistance = self._get_surface_film_resistance(element_type)
                    mass = self._calculate_material_mass_with_low_conductivity_adjustment(
                        material_data, element_type, construction_id, low_conductivity_found
                    )
                    self.element_data.append({
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
                    })

    def _get_surface_type_and_boundary(self, construction_id: str, surfaces: Dict[str, Dict[str, Any]]):
        """
        Get the surface type and boundary condition for a given construction ID.

        Args:
            construction_id: The construction ID.
            surfaces: The surfaces data dictionary.

        Returns:
            tuple: A tuple containing the surface type and boundary condition.
        """
        for surface in surfaces.values():
            if surface.get('construction_name') == construction_id:
                return surface.get('surface_type', '').lower(), surface.get('boundary_condition', '').lower()
        return '', ''

    def _get_element_type(self, construction_id: str, surfaces: Dict[str, Dict[str, Any]]):
        """
        Determine element type based on construction usage.
        Implementation moved from DataLoader.

        Args:
            construction_id: ID of the construction
            surfaces: Dictionary of surface data from cache

        Returns:
            tuple: (element_types, dont_use) where:
                  - element_types: list - List of element type descriptions
                  - dont_use: bool - Flag indicating if this construction should be excluded from output
        """
        construction_surfaces = [s for s in surfaces.values() if s.get('construction_name') == construction_id]
        if not construction_surfaces:
            return [], False

        element_types = set()
        is_zone_interior = False
        dont_use = False
        zones = self.data_loader.get_hvac_zones()

        for surface in construction_surfaces:
            if surface.get('is_glazing', False):
                element_types.add("Glazing")
                continue

            s_type = surface.get('surface_type', '').lower() if surface.get('surface_type') else ""
            boundary = surface.get('boundary_condition', '').lower() if surface.get('boundary_condition') else ""

            raw_object = surface.get('raw_object')
            outside_boundary_obj_name = None
            is_zone_interior = False
            surface_dont_use = False

            try:
                if raw_object:
                    if hasattr(raw_object, 'Outside_Boundary_Condition_Object'):
                        outside_boundary_obj_name = raw_object.Outside_Boundary_Condition_Object
                    elif isinstance(raw_object, dict) and 'Outside_Boundary_Condition_Object' in raw_object:
                        outside_boundary_obj_name = raw_object['Outside_Boundary_Condition_Object']

                if isinstance(outside_boundary_obj_name, str) and outside_boundary_obj_name:
                    zone_name_candidate = outside_boundary_obj_name.split("_")[0].strip()
                    if zone_name_candidate:
                        construction_zone = raw_object.Name.split("_")[0].strip()
                        is_hvac_inside = construction_zone in zones
                        is_hvac_outside = zone_name_candidate in zones
                        if not is_hvac_inside and not is_hvac_outside:
                            surface_dont_use = True
                        else:
                            is_zone_interior = is_hvac_inside and is_hvac_outside

            except Exception:
                pass

            if surface_dont_use:
                dont_use = True

            element_type = ""
            if s_type == "wall":
                if boundary == "outdoors":
                    element_type = "External wall"
                elif boundary == "ground":
                    element_type = "Ground wall"
                else:
                    element_type = "Internal wall" if is_zone_interior else "Separation wall"

            elif s_type == "floor":
                if boundary == "outdoors":
                    element_type = "External floor"
                elif boundary == "ground":
                    element_type = "Ground floor"
                else:
                    element_type = "Intermediate floor" if is_zone_interior else "Separation floor"

            elif s_type == "ceiling":
                if boundary == "ground":
                    element_type = "Ground ceiling"
                elif boundary == "outdoors":
                    element_type = "External ceiling"
                else:
                    element_type = "Intermediate ceiling" if is_zone_interior else "Separation ceiling"

            elif s_type == "roof":
                element_type = "Roof"

            if element_type:
                element_types.add(element_type)

        return list(element_types), dont_use

    def _get_surface_film_resistance(self, element_type: str) -> float:
        """
        Determine the surface film resistance constant based on element type and boundary.

        Args:
            s_type: Surface type (wall, floor, ceiling, roof)
            boundary: Boundary condition (outdoors, ground, etc.)

        Returns:
            float: Surface film resistance constant to add to R-Value
        """

        element_type = element_type.lower()

        if element_type in ["internal wall", "ground floor", "ground ceiling", "intermediate ceiling" ,"intermediate floor"]:
            return 0.0
        if element_type == "ground wall":
            return 0.1
        if element_type == "external wall":
            return 0.17
        elif element_type == "separation wall":
            return 0.26
        elif element_type == "external floor":
            return 0.21
        elif element_type == "separation floor":
            return 0.34
        elif element_type == "separation ceiling":
            return 0.2
        else:
            return 0.14

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
            if material:
                # Use helper method but only apply low conductivity reduction to first occurrence
                if not found_low_conductivity and material.conductivity < 0.2 and material.conductivity != 0:
                    layer_mass = self._calculate_material_mass_with_low_conductivity_adjustment(material)
                    found_low_conductivity = True
                else:
                    layer_mass = material.density * material.thickness
                
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
            element_types, _ = self._get_element_type(construction_id, self.data_loader.get_surfaces())
            film_resistance = self._get_surface_film_resistance(element_types[0]) if element_types else 0.0
            r_value_with_film = total_resistance + film_resistance
            u_value = 1.0 / r_value_with_film if r_value_with_film > 0 else 0.0
            u_values[construction_id] = u_value
        return u_values
