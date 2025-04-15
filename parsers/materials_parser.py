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
        try:
            # Use cached constructions from DataLoader
            constructions = self.data_loader.get_all_constructions()
            
            # Process each construction
            for construction_id, construction_data in constructions.items():
                if "_rev" in construction_id.lower():
                    continue
                # Get all materials in the construction
                for layer_id in construction_data.material_layers:
                    material_data = self.data_loader.get_material(layer_id)
                    if material_data:
                        element_type = self._get_element_type(construction_data)
                        
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
            
    def _get_element_type(self, construction_data) -> str:
        """
        Determine element type based on construction usage.
        
        Args:
            construction_data: ConstructionData from cache
            
        Returns:
            str: Element type description
        """
        # Get all surfaces using this construction
        surfaces = self.data_loader.get_all_surfaces()
        construction_surfaces = [
            s for s in surfaces.values() 
            if s.construction_name == construction_data.name
        ]
        
        if not construction_surfaces:
            return ""
            
        surface = construction_surfaces[0]
        s_type = surface.surface_type.lower()
        boundary = surface.boundary_condition.lower()
        zone_name = surface.zone_name
        
        has_hvac = self._check_zone_hvac(zone_name)
        
        if s_type == "wall":
            if boundary == "outdoors" or boundary == "ground":
                return "External wall"
            else:
                return "Internal wall" if has_hvac else "Separation wall"
                
        if s_type == "floor":
            if boundary == "outdoors":
                return "External floor"
            elif boundary == "ground":
                return "Ground floor"
            else:
                return "Intermediate floor" if has_hvac else "Separation floor"
                
        if s_type == "ceiling":
            if boundary == "ground":
                return "Ground ceiling"
            elif boundary == "outdoors":
                return "External ceiling"
            else:
                return "Intermediate ceiling" if has_hvac else "Separation ceiling"
                
        if s_type == "roof":
            return "Roof"
            
        return ""
        
    def _check_zone_hvac(self, zone_name: str) -> bool:
        """
        Check if a zone has HVAC systems by looking for heating/cooling schedules.
        Uses cached zone data.
        
        Args:
            zone_name: Name of the zone to check
            
        Returns:
            bool: True if zone has HVAC systems, False otherwise
        """
        try:
            if not zone_name:
                return False
                
            zone_id = zone_name.split('_')[0] if '_' in zone_name else zone_name
            zone_id = zone_id.lower()
            
            schedules = self.data_loader.get_all_schedules()
            for schedule in schedules.values():
                if schedule.zone_id.lower() == zone_id:
                    # Check if the schedule is for heating or cooling
                    if "heating" in schedule.type.lower() or "cooling" in schedule.type.lower():
                        return True
            
        except Exception as e:
            print(f"Error checking HVAC system for zone {zone_name}: {e}")
            return False
            
    def get_element_data(self) -> list:
        """
        Returns the list of processed element data.
        
        Returns:
            list: List of dictionaries containing element data and calculated properties
        """
        return self.element_data