"""
Extracts and processes materials and constructions.
Uses DataLoader for cached access to IDF data.
"""
from typing import Dict, Any, Optional, List, Tuple
from utils.data_loader import DataLoader
from utils.data_models import MaterialData, ConstructionData
from utils.logging_config import get_logger
from .utils import safe_float, filter_hvac_zones
from .base_parser import BaseParser

logger = get_logger(__name__)

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
            logger.error("MaterialsParser requires a DataLoader instance")
            raise RuntimeError("MaterialsParser requires a DataLoader instance.")
        
        
        try:
            self.materials.clear()
            self.constructions.clear()
            self.element_data.clear()
            
            # Process materials
            material_cache = self.data_loader.get_materials()
            materials_processed = 0
            materials_with_missing_data = 0
            
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
                materials_processed += 1
            
            construction_cache = self.data_loader.get_constructions()
            
            filtered_constructions = self._filter_reversed_constructions(construction_cache)
            constructions_processed = 0
            constructions_with_missing_materials = 0
            
            for construction_id, raw_construction_data in filtered_constructions.items():
                material_layers = raw_construction_data['material_layers']
                # Check for missing materials
                missing_materials = []
                valid_materials = []
                total_thickness = 0.0
                
                for layer_id in material_layers:
                    if layer_id in self.materials:
                        valid_materials.append(layer_id)
                        material_thickness = self.materials[layer_id].thickness
                        if material_thickness:
                            total_thickness += material_thickness
                        else:
                            logger.warning(f"Material '{layer_id}' in construction '{construction_id}' has no thickness")
                    else:
                        missing_materials.append(layer_id)
                
                if missing_materials:
                    constructions_with_missing_materials += 1
                    logger.warning(f"Construction '{construction_id}' references missing materials: {missing_materials}")
                
                self.constructions[construction_id] = ConstructionData(
                    id=construction_id,
                    name=construction_id,
                    material_layers=material_layers,
                    thickness=total_thickness
                )
                constructions_processed += 1     
            self._process_element_data(filtered_constructions)
            
        except Exception as e:
            logger.error(f"Error processing materials and constructions: {e}", exc_info=True)
            raise RuntimeError(f"Error processing materials and constructions: {e}")

    def _filter_reversed_constructions(self, construction_cache: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Filter constructions to handle reversed construction logic:
        - Never show constructions with _rev suffix (regardless of whether non-reversed version exists)
        - For _Reversed suffix: only show if no identical regular version exists (same materials)
        
        Args:
            construction_cache: Dictionary of all constructions from DataLoader
            
        Returns:
            Dict[str, Dict[str, Any]]: Filtered construction cache
        """ 
        return {k: v for k, v in construction_cache.items() if not k.lower().endswith('_rev')}

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
        
        # Apply low conductivity adjustment
        conductivity = material_data.conductivity
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

    def _process_element_data(self, filtered_constructions: Dict[str, Dict[str, Any]]) -> None:
        """
        Process element data for report generation.
        This combines materials and constructions to create report data.
        """
        logger.info("Starting element data processing")
        
        # We only need surfaces for element type detection - get all surfaces once
        surfaces = self.data_loader.get_surfaces()
        logger.info(f"Processing {len(filtered_constructions)} filtered constructions")
        
        
        # Create mapping for _rev constructions to their base versions
        construction_mapping = {}
        
        low_conductivity_found = {}
        element_data_count = 0
        skipped_constructions = 0
        skipped_reasons = {"dont_use": [], "no_element_types": [], "no_surfaces": []}
        
        for construction_id in filtered_constructions.keys():
            construction_data = self.constructions[construction_id]
            # Note: Reversed constructions are already filtered out during process_idf
            element_types, dont_use = self._get_element_type(construction_id, surfaces, construction_mapping)
            
            logger.info(f"Construction '{construction_id}' has element types: {element_types}, dont_use: {dont_use}")
            
            if dont_use:
                skipped_reasons["dont_use"].append(construction_id)
                skipped_constructions += 1
                continue
                
            if not element_types:
                skipped_reasons["no_element_types"].append(construction_id)
                skipped_constructions += 1
                continue
            
            s_type, boundary = self._get_surface_type_and_boundary(construction_id, surfaces, construction_mapping)
            
            
            # Process each element type separately, grouping all materials under each element type
            for element_type in element_types:
                film_resistance = self._get_surface_film_resistance(element_type)
                
                for layer_id in construction_data.material_layers:
                    material_data = self.materials.get(layer_id)
                    if not material_data:
                        logger.warning(f"Material '{layer_id}' not found in materials cache for construction '{construction_id}'")
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
                    element_data_count += 1
                    
        
        logger.info(f"Element data processing complete: {element_data_count} entries created, {skipped_constructions} constructions skipped")
        
        # Detailed debug logging for skipped constructions
        if skipped_constructions > 0:
            logger.info(f"=== CONSTRUCTION SKIP SUMMARY ===")
            logger.info(f"Total constructions processed: {len(filtered_constructions)}")
            logger.info(f"Total constructions skipped: {skipped_constructions}")
            
            if skipped_reasons["dont_use"]:
                logger.info(f"Constructions skipped due to 'dont_use' flag ({len(skipped_reasons['dont_use'])}): {skipped_reasons['dont_use']}")
            
            if skipped_reasons["no_element_types"]:
                logger.info(f"Constructions skipped due to 'no element types' ({len(skipped_reasons['no_element_types'])}): {skipped_reasons['no_element_types']}")
            
            if skipped_reasons["no_surfaces"]:
                logger.info(f"Constructions skipped due to 'no surfaces' ({len(skipped_reasons['no_surfaces'])}): {skipped_reasons['no_surfaces']}")
            
            logger.info(f"=== END CONSTRUCTION SKIP SUMMARY ===")
        

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
            logger.warning(f"No surfaces found for construction '{construction_id}' - element type detection may be incomplete")
            return [], False

        element_types = set()
        hvac_zones = self.data_loader.get_hvac_zones()
        
        surfaces_with_hvac_zones = 0
        surfaces_without_hvac_zones = 0
        
        for i, surface in enumerate(construction_surfaces):
            surface_name = surface.get('name', 'unnamed')
            
            # Detailed logging for _IntFloor1 construction
            if construction_id == '_IntFloor1':
                logger.warning(f"Processing _IntFloor1 surface {i+1}/{len(construction_surfaces)}: '{surface_name}'")
                logger.warning(f"  Surface type: {surface.get('surface_type', 'N/A')}")
                logger.warning(f"  Boundary condition: {surface.get('boundary_condition', 'N/A')}")
                logger.warning(f"  Is glazing: {surface.get('is_glazing', False)}")
            
            if surface.get('is_glazing', False):
                if construction_id == '_IntFloor1':
                    logger.warning(f"  -> Classified as: Glazing")
                element_types.add("Glazing")
                continue
            
            surface_has_hvac, is_zone_interior = self._check_surface_hvac_zones(surface, hvac_zones)
            
            if construction_id == '_IntFloor1':
                logger.warning(f"  HVAC check: has_hvac={surface_has_hvac}, is_zone_interior={is_zone_interior}")
            
            if surface_has_hvac:
                surfaces_with_hvac_zones += 1
            else:
                surfaces_without_hvac_zones += 1
            
            element_type = self._determine_surface_element_type(surface, is_zone_interior)
            
            if construction_id == '_IntFloor1':
                logger.warning(f"  Element type determined: '{element_type}'")
            
            if element_type:
                element_types.add(element_type)
                if construction_id == '_IntFloor1':
                    logger.warning(f"  -> Added to element types: '{element_type}'")
            else:
                if construction_id == '_IntFloor1':
                    logger.warning(f"  -> No element type determined")
                pass
        
        dont_use = surfaces_with_hvac_zones == 0 and surfaces_without_hvac_zones > 0
        
        # Log only summary for element type debugging
        if len(element_types) == 0 or dont_use:
            logger.warning(f"Element type detection issue for '{construction_id}': types={list(element_types)}, dont_use={dont_use}, surfaces_count={len(construction_surfaces)}")
            # Log surface details for problematic constructions to understand the issue
            if construction_id == '_IntFloor1':
                for i, surf in enumerate(construction_surfaces[:3]):  # Log first 3 surfaces
                    surf_name = surf.get('name', 'unnamed')
                    surf_type = surf.get('surface_type', 'N/A')
                    boundary = surf.get('boundary_condition', 'N/A')
                    logger.warning(f"  Surface {i+1}: name='{surf_name}', type='{surf_type}', boundary='{boundary}'")
        
        if dont_use or not element_types:
            logger.warning(f"Construction '{construction_id}' issue - Surfaces: {len(construction_surfaces)}, HVAC surfaces: {surfaces_with_hvac_zones}, Element types: {list(element_types)}, Dont_use: {dont_use}")
        
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
            raw_object = surface.get('raw_object')
            if not raw_object:
                return False, False
            zone_name = raw_object.Name.split("_")[0].strip().lower()
            if zone_name in hvac_zones_lower:
                return True, False
            return False, False  # Non-surface boundaries automatically have HVAC zones
        
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
            
            # Log HVAC detection for problematic constructions
            surface_name = surface.get('name', 'unnamed')
            construction_from_surface = surface.get('construction_name', '')
            if not surface_has_hvac_zones and construction_from_surface == '_IntFloor1':
                logger.warning(f"HVAC detection failed for surface '{surface_name}' (construction: {construction_from_surface}): construction_zone='{construction_zone}', outside_zone='{zone_name_candidate}', hvac_zones_count={len(hvac_zones)}")
                if len(hvac_zones) > 0:
                    logger.warning(f"  Available HVAC zones: {hvac_zones[:5]}")  # Show first 5 HVAC zones
            
            return surface_has_hvac_zones, is_zone_interior
            
        except Exception:
            return False, False
    
    def _determine_surface_element_type(self, surface: Dict[str, Any], is_zone_interior: bool) -> str:
        """Determine element type based on surface type and boundary condition."""
        s_type = surface.get('surface_type', '').lower()
        boundary = surface.get('boundary_condition', '').lower()
        surface_name = surface.get('name', 'unnamed')
        
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
            # Log unrecognized surface types - these might be the incorrect element type issue
            logger.warning(f"Unrecognized surface type '{s_type}' for surface '{surface_name}' (boundary: '{boundary}')")
            result = ""
        
        # Log potentially problematic classifications for debugging
        if s_type and boundary and result:
            # Check for suspicious combinations that might indicate incorrect element types
            suspicious = False
            if s_type == "wall" and "floor" in surface_name.lower():
                suspicious = True
            elif s_type == "floor" and "wall" in surface_name.lower():
                suspicious = True
            elif s_type == "ceiling" and ("wall" in surface_name.lower() or "floor" in surface_name.lower()):
                suspicious = True
                
            if suspicious:
                logger.warning(f"Suspicious element type classification: surface '{surface_name}' has type '{s_type}' -> '{result}' (boundary: '{boundary}')")
        
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
        if not self.materials:
            logger.warning("No materials available - materials dictionary is empty")
        return self.materials

    def get_all_constructions(self) -> Dict[str, ConstructionData]:
        """
        Get all processed constructions.

        Returns:
            Dict[str, ConstructionData]: Dictionary of all constructions
        """
        if not self.constructions:
            logger.warning("No constructions available - constructions dictionary is empty")
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
            logger.warning(f"Construction '{construction_id}' not found for mass calculation")
            return 0.0
        
        
        total_mass_per_area = 0.0
        found_low_conductivity = False
        
        for layer_id in construction.material_layers:
            material = self.materials.get(layer_id)
            if material:
                
                # Use helper method but only apply low conductivity reduction to first occurrence
                if not found_low_conductivity and material.conductivity is not None and material.conductivity < 0.2 and material.conductivity != 0:
                    layer_mass = self._calculate_material_mass_with_low_conductivity_adjustment(material)
                    found_low_conductivity = True
                else:
                    layer_mass = (material.density or 0.0) * (material.thickness or 0.0)
                
                total_mass_per_area += layer_mass
            else:
                logger.warning(f"Material '{layer_id}' not found for construction '{construction_id}'")
        
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
