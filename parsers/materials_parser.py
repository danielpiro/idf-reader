"""
Extracts and processes materials and constructions.
Uses DataLoader for cached access to IDF data.
"""
from typing import Dict, Any, Optional
from utils.data_loader import DataLoader
from utils.data_models import MaterialData, ConstructionData
from utils.logging_config import get_logger

logger = get_logger(__name__)

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

    def _get_element_type(self, construction_id: str, surfaces: Dict[str, Dict[str, Any]], construction_mapping: Dict[str, str] = None):
        """
        Determine element type based on construction usage.
        Implementation moved from DataLoader.

        Args:
            construction_id: ID of the construction
            surfaces: Dictionary of surface data from cache
            construction_mapping: Dictionary mapping _rev construction names to base names

        Returns:
            tuple: (element_types, dont_use) where:
                  - element_types: list - List of element type descriptions
                  - dont_use: bool - Flag indicating if this construction should be excluded from output
        """
        # Find surfaces that reference this construction directly
        construction_surfaces = [s for s in surfaces.values() if s.get('construction_name') == construction_id]
        
        # Also find surfaces that reference _rev versions that map to this construction
        if construction_mapping:
            for rev_name, base_name in construction_mapping.items():
                if base_name == construction_id:
                    mapped_surfaces = [s for s in surfaces.values() if s.get('construction_name') == rev_name]
                    construction_surfaces.extend(mapped_surfaces)
        
        if not construction_surfaces:
            return [], False

        element_types = set()
        is_zone_interior = False
        dont_use = False
        zones = self.data_loader.get_hvac_zones()
        

        surfaces_with_hvac_zones = 0
        surfaces_without_hvac_zones = 0
        
        for surface in construction_surfaces:
            
            if surface.get('is_glazing', False):
                element_types.add("Glazing")
                continue

            s_type = surface.get('surface_type', '').lower() if surface.get('surface_type') else ""
            boundary = surface.get('boundary_condition', '').lower() if surface.get('boundary_condition') else ""


            raw_object = surface.get('raw_object')
            outside_boundary_obj_name = None
            is_zone_interior = False
            surface_has_hvac_zones = False

            # Only check HVAC zones if boundary condition is "surface"
            if boundary == "surface":
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
                                surface_has_hvac_zones = False
                            else:
                                surface_has_hvac_zones = True
                                is_zone_interior = is_hvac_inside and is_hvac_outside

                except Exception as e:
                    pass
            else:
                # For non-surface boundaries (outdoors, ground), automatically mark as having HVAC zones
                surface_has_hvac_zones = True

            # Track whether this surface has HVAC zones
            if surface_has_hvac_zones:
                surfaces_with_hvac_zones += 1
            else:
                surfaces_without_hvac_zones += 1

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
        
        # Determine dont_use based on whether ANY surfaces have HVAC zones
        # Only mark as dont_use if ALL surfaces lack HVAC zones
        dont_use = surfaces_with_hvac_zones == 0 and surfaces_without_hvac_zones > 0
        
        # Only log detailed info for problematic constructions
        if dont_use or not element_types:
            logger.debug(f"Construction '{construction_id}' issue - Surfaces: {len(construction_surfaces)}, HVAC surfaces: {surfaces_with_hvac_zones}, Element types: {list(element_types)}, Dont_use: {dont_use}")
            if not element_types:
                surface_types = [f"{s.get('surface_type', 'unknown')}({s.get('boundary_condition', 'unknown')})" for s in construction_surfaces]
                logger.debug(f"  Surface types found: {surface_types}")

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

        if element_type in ["internal wall","intermediate ceiling" ,"intermediate floor"]:
            return 0.0
        if element_type in ["ground floor", "ground wall" , "ground ceiling"]:
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
        logger.debug(f"Returning {len(self.element_data)} element data entries")
        return self.element_data

    def get_all_materials(self) -> Dict[str, MaterialData]:
        """
        Get all processed materials.

        Returns:
            Dict[str, MaterialData]: Dictionary of all materials
        """
        logger.debug(f"Returning {len(self.materials)} processed materials")
        if not self.materials:
            logger.warning("No materials available - materials dictionary is empty")
        return self.materials

    def get_all_constructions(self) -> Dict[str, ConstructionData]:
        """
        Get all processed constructions.

        Returns:
            Dict[str, ConstructionData]: Dictionary of all constructions
        """
        logger.debug(f"Returning {len(self.constructions)} processed constructions")
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
        logger.debug(f"Calculating mass per area for construction: {construction_id}")
        
        construction = self.constructions.get(construction_id)
        if not construction:
            logger.warning(f"Construction '{construction_id}' not found for mass calculation")
            return 0.0
        
        logger.debug(f"Construction '{construction_id}' has material layers: {construction.material_layers}")
        
        total_mass_per_area = 0.0
        found_low_conductivity = False
        
        for layer_id in construction.material_layers:
            material = self.materials.get(layer_id)
            if material:
                logger.debug(f"Processing layer '{layer_id}' - density: {material.density}, thickness: {material.thickness}, conductivity: {material.conductivity}")
                
                # Use helper method but only apply low conductivity reduction to first occurrence
                if not found_low_conductivity and material.conductivity is not None and material.conductivity < 0.2 and material.conductivity != 0:
                    layer_mass = self._calculate_material_mass_with_low_conductivity_adjustment(material)
                    found_low_conductivity = True
                    logger.debug(f"Applied low conductivity adjustment to layer '{layer_id}' - adjusted mass: {layer_mass}")
                else:
                    layer_mass = (material.density or 0.0) * (material.thickness or 0.0)
                    logger.debug(f"Normal mass calculation for layer '{layer_id}': {layer_mass}")
                
                total_mass_per_area += layer_mass
            else:
                logger.warning(f"Material '{layer_id}' not found for construction '{construction_id}'")
        
        logger.debug(f"Total mass per area for construction '{construction_id}': {total_mass_per_area}")
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
