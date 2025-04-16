"""
Extracts and processes materials and constructions.
Uses DataLoader for cached access to IDF data.
"""
from typing import Dict, Any, Optional
from utils.data_loader import DataLoader

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
        
    def process_idf(self, idf) -> None:
        """
        Process materials and constructions using cached data.
        
        Args:
            idf: eppy IDF object (kept for compatibility)
        """
        if not self.data_loader:
            print("Warning: MaterialsParser requires a DataLoader instance for efficient processing")
            return
        
        try:
            # Use cached constructions and materials from DataLoader
            constructions = self.data_loader._constructions or self.data_loader._load_all_constructions()
            materials = self.data_loader._materials or self.data_loader._load_all_materials()
            
            # Process each construction
            for construction_id, construction_data in constructions.items():
                if "rev" in construction_id.lower() and "reverse" not in construction_id.lower():
                    continue
                
                # Get all materials in the construction
                for layer_id in construction_data.material_layers:
                    material_data = materials.get(layer_id)
                    if material_data:
                        element_type = self._get_element_type_cached(construction_data)
                        
                        self.element_data.append({
                            "element_type": element_type,
                            "element_name": construction_id,
                            "material_name": layer_id,
                            "thickness": material_data.thickness,
                            "conductivity": material_data.conductivity,
                            "density": material_data.density,
                            "mass": material_data.density * material_data.thickness,
                            "thermal_resistance": (
                                material_data.thickness / material_data.conductivity 
                                if material_data.conductivity != 0 else 0.0
                            ),
                            "solar_absorptance": material_data.solar_absorptance,
                            "specific_heat": material_data.specific_heat
                        })
                        
        except Exception as e:
            print(f"Error processing materials and constructions: {str(e)}")
            
    def _get_element_type_cached(self, construction_data) -> str:
        """
        Determine element type based on construction usage using cached data.
        More efficient than the original method.
        
        Args:
            construction_data: ConstructionData from cache
            
        Returns:
            str: Element type description
        """
        # Access the surfaces cache directly instead of calling get_all_surfaces()
        surfaces = self.data_loader._surfaces or self.data_loader._load_all_surfaces()
        
        # Filter surfaces more efficiently
        construction_surfaces = []
        for surface_id, surface in surfaces.items():
            if surface.construction_name == construction_data.name:
                construction_surfaces.append(surface)
                # Break early once we have one surface (for efficiency)
                if len(construction_surfaces) >= 1:
                    break
        
        if not construction_surfaces:
            return ""
            
        try:
            surface = construction_surfaces[0]
            s_type = surface.surface_type.lower() if surface.surface_type else ""
            boundary = surface.boundary_condition.lower() if surface.boundary_condition else ""
        except (AttributeError, IndexError):
            return ""
        
        # Use cached zones directly instead of calling get_all_zones()
        zones = self.data_loader._zones or self.data_loader._load_all_zones()
        is_zone_interior = surface.zone_name in zones
        
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