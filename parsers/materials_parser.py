"""
Extracts and processes materials and constructions.
Uses DataLoader for cached access to IDF data.
"""
import re
from typing import Dict, Any, Optional
from colorama import Fore, Style
from utils.data_loader import DataLoader
from utils.data_models import MaterialData, ConstructionData

class MaterialsParser:
    """
    Extracts material properties and construction definitions.
    Uses cached data from DataLoader for efficient access.
    """
    def __init__(self, data_loader: Optional[DataLoader] = None):
        """
        Initialize MaterialsParser.
        
        Args:
            data_loader: DataLoader instance for accessing cached data
        """
        self.data_loader = data_loader
        self.element_data = []  # Final processed data for report
        self.materials = {}     # Processed materials indexed by ID
        self.constructions = {} # Processed constructions indexed by ID
        
    def process_idf(self, idf) -> None: # idf parameter kept for compatibility, but not used directly
        """
        Process materials and constructions using data from DataLoader.
        
        Args:
            idf: eppy IDF object (kept for compatibility)
        """
        if not self.data_loader:
            print(f"{Fore.RED}Error: MaterialsParser requires a DataLoader instance.{Style.RESET_ALL}")
            return
        
        try:
            # Clear previous processed data
            self.materials.clear()
            self.constructions.clear()
            self.element_data.clear()

            # --- Process Materials from DataLoader Cache ---
            material_cache = self.data_loader.get_materials()
            for material_id, raw_material_data in material_cache.items():
                self.materials[material_id] = MaterialData(
                    id=material_id,
                    name=material_id,
                    # Use .get() with default 0.0 for potentially missing properties
                    conductivity=raw_material_data.get('conductivity', 0.0),
                    density=raw_material_data.get('density', 0.0),
                    specific_heat=raw_material_data.get('specific_heat', 0.0),
                    thickness=raw_material_data.get('thickness', 0.0),
                    solar_absorptance=raw_material_data.get('solar_absorptance', 0.0)
                )

            # --- Process Constructions from DataLoader Cache ---
            construction_cache = self.data_loader.get_constructions()
            for construction_id, raw_construction_data in construction_cache.items():
                material_layers = raw_construction_data['material_layers']
                
                # Calculate total thickness using the already processed self.materials
                total_thickness = 0.0
                for layer_id in material_layers:
                    if layer_id in self.materials:
                        total_thickness += self.materials[layer_id].thickness
                    else:
                        # This case should ideally not happen if all materials are defined
                        print(f"{Fore.YELLOW}Warning: Material '{layer_id}' not found while calculating thickness for construction '{construction_id}'.{Style.RESET_ALL}")

                self.constructions[construction_id] = ConstructionData(
                    id=construction_id,
                    name=construction_id,
                    material_layers=material_layers,
                    thickness=total_thickness
                )

            # --- Process Element Data (using populated self.materials and self.constructions) ---
            self._process_element_data()

        except Exception as e:
            print(f"{Fore.RED}Error processing materials and constructions: {str(e)}{Style.RESET_ALL}")
            # Optionally re-raise or handle more gracefully
            import traceback
            traceback.print_exc()

    def _process_element_data(self) -> None:
        """
        Process element data for report generation.
        This combines materials and constructions to create report data.
        """
        # Get cached surface data (still needed for element type)
        surfaces = self.data_loader.get_surfaces()
        
        # Process each construction (using the populated self.constructions)
        for construction_id, construction_data in self.constructions.items():
            pattern = r'_(?:[Rr]ev|[Rr]eversed)$'
            if bool(re.search(pattern, construction_id)):
                continue            
            element_type = self._get_element_type(construction_id, surfaces)
            
            # Determine surface type and boundary condition for film resistance calculation
            s_type = ""
            boundary = ""
            
            # Find a surface using this construction to get its type and boundary
            for surface_id, surface in surfaces.items():
                if surface.get('construction_name') == construction_id:
                    s_type = surface.get('surface_type', '').lower()
                    boundary = surface.get('boundary_condition', '').lower()
                    break
            
            # Get surface film resistance based on surface type and boundary
            film_resistance = self._get_surface_film_resistance(element_type)
            
            # Flag to track if we've found a material with conductivity < 0.2 in this construction
            found_low_conductivity = False
            
            # Process each material layer in the construction
            for layer_id in construction_data.material_layers:
                # Use the populated self.materials dictionary
                material_data = self.materials.get(layer_id) 
                if material_data:
                    thermal_resistance = (
                        material_data.thickness / material_data.conductivity 
                        if material_data.conductivity != 0 else 0.0
                    )
                    
                    # Calculate mass - divide it if we haven't found a low conductivity material yet
                    mass = material_data.density * material_data.thickness
                    if not found_low_conductivity and element_type.lower() == "external wall":
                        if material_data.conductivity < 0.2:
                            # We found a material with conductivity < 0.2
                            found_low_conductivity = True
                            # Divide the mass for this material
                            mass = mass / 2
                    
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
                # Missing materials are silently skipped for report generation
                # No debug message needed here as warning was already shown during construction processing

    def _get_element_type(self, construction_id: str, surfaces: Dict[str, Dict[str, Any]]) -> str:
        """
        Determine element type based on construction usage.
        Implementation moved from DataLoader.
        
        Args:
            construction_id: ID of the construction
            surfaces: Dictionary of surface data from cache
            
        Returns:
            str: Element type description
        """
        # Find surfaces using this construction
        construction_surfaces = []
        for surface_id, surface in surfaces.items():
            if surface.get('construction_name') == construction_id:
                construction_surfaces.append(surface)
                # Break early once we have one surface (for efficiency)
                if len(construction_surfaces) >= 1:
                    break
        
        if not construction_surfaces:
            return ""
        
        # Get the first surface using this construction
        surface = construction_surfaces[0]
        
        # Check if this is a glazing surface
        if surface.get('is_glazing', False):
            return "Glazing"
            
        try:
            s_type = surface['surface_type'].lower() if surface.get('surface_type') else ""
            boundary = surface['boundary_condition'].lower() if surface.get('boundary_condition') else ""
        except (AttributeError, IndexError, KeyError):
            return ""
        
        zones = self.data_loader.get_hvac_zones()
        
        # Safely get the outside boundary object name
        raw_object = surface.get('raw_object')
        outside_boundary_obj_name = None
        is_zone_interior = False
        
        try:
            if raw_object:
                if hasattr(raw_object, 'Outside_Boundary_Condition_Object'):
                    outside_boundary_obj_name = raw_object.Outside_Boundary_Condition_Object
                elif isinstance(raw_object, dict) and 'Outside_Boundary_Condition_Object' in raw_object:
                    outside_boundary_obj_name = raw_object['Outside_Boundary_Condition_Object']
            
            # Process if the boundary object name is found and is a string
            if isinstance(outside_boundary_obj_name, str) and outside_boundary_obj_name:
                # Assuming the zone name is the first part if spaces exist
                zone_name_candidate = outside_boundary_obj_name.split("_")[0].strip()
                if zone_name_candidate:
                    is_zone_interior = zone_name_candidate in zones
            
        except Exception:
            pass
        
        result = ""
        if s_type == "wall":
            if boundary == "outdoors":
                result = "External wall"
            elif boundary == "ground":
                result = "Ground wall"
            else:
                result = "Internal wall" if is_zone_interior else "Separation wall"
                
        elif s_type == "floor":
            if boundary == "outdoors":
                result = "External floor"
            elif boundary == "ground":
                result = "Ground floor"
            else:
                result = "Intermediate floor" if is_zone_interior else "Separation floor"
                
        elif s_type == "ceiling":
            if boundary == "ground":
                result = "Ground ceiling"
            elif boundary == "outdoors":
                result = "External ceiling"
            else:
                result = "Intermediate ceiling" if is_zone_interior else "Separation ceiling"
                
        elif s_type == "roof":
            result = "Roof"
            
        return result

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

        if element_type in ["ground wall", "internal wall", "ground floor", "ground ceiling","intermediate ceiling"]:
            return 0.0
        if element_type == "external wall":
            return 0.17
        elif element_type == "separation wall":
            return 0.26
        elif element_type == "external floor":
            return 0.21
        elif element_type == "separation floor":
            return 0.34
        elif element_type == "external ceiling":
            return 0.14
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
        
        # Calculate total resistance
        for layer_id in construction.material_layers:
            material = self.materials.get(layer_id)
            if material and material.conductivity > 0:
                total_resistance += material.thickness / material.conductivity
        
        # Calculate effective conductivity
        conductivity = total_thickness / total_resistance if total_resistance > 0 else 0.0
        
        return {
            'thickness': total_thickness,
            'conductivity': conductivity
        }