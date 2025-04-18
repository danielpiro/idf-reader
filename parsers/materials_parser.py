"""
Extracts and processes materials and constructions.
Uses DataLoader for cached access to IDF data.
"""
import re
from typing import Dict, Any, Optional, List
import numpy as np
from utils.data_loader import DataLoader, safe_float
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
            print("Error: MaterialsParser requires a DataLoader instance.")
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
                    conductivity=raw_material_data['conductivity'],
                    density=raw_material_data['density'],
                    specific_heat=raw_material_data['specific_heat'],
                    thickness=raw_material_data['thickness'],
                    solar_absorptance=raw_material_data['solar_absorptance']
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
                        print(f"Warning: Material '{layer_id}' not found while calculating thickness for construction '{construction_id}'.")

                self.constructions[construction_id] = ConstructionData(
                    id=construction_id,
                    name=construction_id,
                    material_layers=material_layers,
                    thickness=total_thickness
                )

            # --- Process Element Data (using populated self.materials and self.constructions) ---
            self._process_element_data()

        except Exception as e:
            print(f"Error processing materials and constructions: {str(e)}")
            # Optionally re-raise or handle more gracefully
            import traceback
            traceback.print_exc()

    def _process_element_data(self) -> None:
        """
        Process element data for report generation.
        This combines materials and constructions to create report data.
        (This method remains largely the same, but ensure self.element_data is cleared beforehand)
        """
        # Get cached surface data (still needed for element type)
        surfaces = self.data_loader.get_surfaces()
        
        # Process each construction (using the populated self.constructions)
        for construction_id, construction_data in self.constructions.items():
            pattern = r'_(?:[Rr]ev|[Rr]eversed)$'
            if bool(re.search(pattern, construction_id)):
                continue            
            element_type = self._get_element_type(construction_id, surfaces)
            
            # Process each material layer in the construction
            for layer_id in construction_data.material_layers:
                # Use the populated self.materials dictionary
                material_data = self.materials.get(layer_id) 
                if material_data:
                    thermal_resistance = (
                        material_data.thickness / material_data.conductivity 
                        if material_data.conductivity != 0 else 0.0
                    )
                    
                    self.element_data.append({
                        "element_type": element_type,
                        "element_name": construction_id,
                        "material_name": layer_id,
                        "thickness": material_data.thickness,
                        "conductivity": material_data.conductivity,
                        "density": material_data.density,
                        "mass": material_data.density * material_data.thickness,
                        "thermal_resistance": thermal_resistance,
                        "solar_absorptance": material_data.solar_absorptance,
                        "specific_heat": material_data.specific_heat
                    })
                else:
                    # This print remains important for debugging missing material definitions
                    print(f"DEBUG:   Material data NOT FOUND for '{layer_id}' in self.materials - SKIPPING layer in report") 

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
            if surface['construction_name'] == construction_id:
                construction_surfaces.append(surface)
                # Break early once we have one surface (for efficiency)
                if len(construction_surfaces) >= 1:
                    break
        
        if not construction_surfaces:
            return ""
        
        # Check if this is a glazing surface
        surface = construction_surfaces[0]
        if surface.get('is_glazing', False):
            return "Glazing"
            
        try:
            s_type = surface['surface_type'].lower() if surface['surface_type'] else ""
            boundary = surface['boundary_condition'].lower() if surface['boundary_condition'] else ""
        except (AttributeError, IndexError, KeyError):
            return ""
        
        zones = self.data_loader.get_hvac_zones() # Assumes this returns a dict/set of zone names
        
        # Safely get the outside boundary object name
        raw_object = surface.get('raw_object')
        outside_boundary_obj_name = None
        if isinstance(raw_object, dict):
             outside_boundary_obj_name = raw_object['Outside_Boundary_Condition_Object']

        # Process if the boundary object name is found and is a string
        if isinstance(outside_boundary_obj_name, str) and outside_boundary_obj_name:
            # Assuming the zone name is the first part if spaces exist
            zone_name_candidate = outside_boundary_obj_name.split("_")[0].strip()
            if zone_name_candidate:
                 is_zone_interior = zone_name_candidate in zones
            else:
                is_zone_interior = False
        
        if s_type == "wall":
            if boundary == "outdoors":
                return "External wall"
            elif boundary == "ground":
                return "Ground wall"
            else:
                return "Internal wall" if is_zone_interior else "Separation wall"
                
        if s_type == "floor":
            if boundary == "outdoors":
                return "External floor"
            elif boundary == "ground":
                return "Ground floor"
            else:
                return "Intermediate floor" if is_zone_interior else "Separation floor"
                
        if s_type == "ceiling":
            if boundary == "ground":
                return "Ground ceiling"
            elif boundary == "outdoors":
                return "External ceiling"
            else:
                return "Intermediate ceiling" if is_zone_interior else "Separation ceiling"
                
        if s_type == "roof":
            return "Roof"
            
        return ""
        
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
    
    def get_material(self, material_id: str) -> Optional[MaterialData]:
        """
        Get a specific material by ID.
        
        Args:
            material_id: ID of the material to retrieve
            
        Returns:
            Optional[MaterialData]: Material data if found, None otherwise
        """
        return self.materials.get(material_id)
    
    def get_construction(self, construction_id: str) -> Optional[ConstructionData]:
        """
        Get a specific construction by ID.
        
        Args:
            construction_id: ID of the construction to retrieve
            
        Returns:
            Optional[ConstructionData]: Construction data if found, None otherwise
        """
        return self.constructions.get(construction_id)
    
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