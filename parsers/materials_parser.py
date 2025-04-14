"""
Extracts and processes materials and constructions using eppy.
Calculates thermal properties for construction layers.
"""

class MaterialsParser:
    """
    Extracts material properties and construction definitions using eppy.
    Tracks materials and their properties within constructions.
    """
    def __init__(self):
        self.materials = {}  # {material_name: {properties}}
        self.constructions = {}  # {construction_name: {materials: []}}
        self.element_types = {}  # {construction_name: element_type}
        self.element_data = []  # Final processed data for report
        self.idf = None  # Store IDF reference for schedule checking
        
    def process_idf(self, idf):
        """
        Process an entire IDF model to extract materials and constructions.
        
        Args:
            idf: eppy IDF object
        """
        self.idf = idf  # Store reference for later use
        
        # Process materials first to ensure we have properties
        self._process_materials(idf)
        
        # Then process constructions to get material layers
        self._process_constructions(idf)
        
        # Process building surfaces to get element types
        self._process_surfaces(idf)
        
        # Generate final element data
        self._generate_element_data()

    def _process_materials(self, idf):
        """Process all material objects to extract their properties."""
        try:
            for material in idf.idfobjects['MATERIAL']:
                material_name = str(material.Name)
                try:
                    self.materials[material_name] = {
                        "conductivity": float(getattr(material, "Conductivity", 0.0)),
                        "density": float(getattr(material, "Density", 0.0)),
                        "specific_heat": float(getattr(material, "Specific_Heat", 0.0)),
                        "solar_absorptance": float(getattr(material, "Solar_Absorptance", 0.0)),
                        "thickness": float(getattr(material, "Thickness", 0.0))
                    }
                except (AttributeError, ValueError) as e:
                    print(f"Warning: Could not process material {material_name}: {e}")
        except Exception as e:
            print(f"Error processing materials: {e}")

    def _has_hvac_system(self, zone_name):
        """
        Check if a zone has HVAC systems by looking for heating/cooling schedules.
        
        Args:
            zone_name: Name of the zone to check
            
        Returns:
            bool: True if zone has HVAC systems, False otherwise
        """
        try:
            # Extract zone ID from name (first part before underscore)
            zone_id = zone_name.split('_')[0] if '_' in zone_name else zone_name
            zone_id = zone_id.lower()
            
            # Look through all Schedule:Compact objects
            schedules = self.idf.idfobjects['SCHEDULE:COMPACT']
            for schedule in schedules:
                schedule_name = str(schedule.Name).lower()
                
                # Check if schedule matches zone and contains heating/cooling keywords
                if zone_id in schedule_name and ("heating" in schedule_name or "cooling" in schedule_name):
                    return True
                    
            return False
            
        except Exception as e:
            print(f"Error checking HVAC system for zone {zone_name}: {e}")
            return False

    def _deduce_element_type(self, surface):
        """
        Deduce the element type based on surface properties and HVAC presence.
        
        Args:
            surface: eppy surface object
        Returns:
            str: Deduced element type
        """
        try:
            s_type = str(getattr(surface, "Surface_Type", "unknown")).lower()
            boundary = str(getattr(surface, "Outside_Boundary_Condition", "unknown")).lower()
            zone_name = str(getattr(surface, "Outside_Boundary_Condition_Object", ""))
            has_hvac = self._has_hvac_system(zone_name) if zone_name else False

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
            
        except Exception as e:
            print(f"Error deducing element type: {e}")
            return ""

    def _process_constructions(self, idf):
        """Process all construction objects to get their material layers."""
        try:
            for construction in idf.idfobjects['CONSTRUCTION']:
                construction_name = str(construction.Name)
                try:
                    layers = []
                    layer_thicknesses = []
                    
                    for i in range(1, len(construction.fieldvalues)):
                        layer = getattr(construction, f"Layer_{i}", None)
                        if layer:
                            layer_name = str(layer)
                            layers.append(layer_name)
                            if layer_name in self.materials:
                                layer_thicknesses.append(self.materials[layer_name]["thickness"])
                    
                    if layers:  # Only add if we found layers
                        self.constructions[construction_name] = {
                            "materials": layers,
                            "thicknesses": layer_thicknesses
                        }
                        self.element_types[construction_name] = ""  # Default empty type
                except (AttributeError, ValueError) as e:
                    print(f"Warning: Could not process construction {construction_name}: {e}")
        except Exception as e:
            print(f"Error processing constructions: {e}")

    def _process_surfaces(self, idf):
        """Process building surfaces to determine element types for constructions."""
        try:
            for surface in idf.idfobjects['BUILDINGSURFACE:DETAILED']:
                construction_name = str(getattr(surface, "Construction_Name", ""))
                if construction_name in self.element_types:
                    element_type = self._deduce_element_type(surface)
                    # Only update if we don't have a type yet
                    if not self.element_types[construction_name]:
                        self.element_types[construction_name] = element_type
        except Exception as e:
            print(f"Error processing surfaces: {e}")

    def _calculate_properties(self, material_name, thickness):
        """
        Calculate thermal properties for a material layer.
        
        Args:
            material_name: Name of the material
            thickness: Thickness of the layer
        Returns:
            dict: Calculated properties
        """
        try:
            material = self.materials[material_name]
            conductivity = material["conductivity"]
            return {
                "thickness": thickness,
                "conductivity": conductivity,
                "density": material["density"],
                "mass": material["density"] * thickness,
                "thermal_resistance": thickness / conductivity if conductivity != 0 else 0.0,
                "solar_absorptance": material["solar_absorptance"],
                "specific_heat": material["specific_heat"]
            }
        except Exception as e:
            print(f"Error calculating properties for material {material_name}: {e}")
            return None

    def _generate_element_data(self):
        """Generate final processed data for the report."""
        try:
            self.element_data = []
            
            for construction_name, construction in self.constructions.items():
                element_type = self.element_types.get(construction_name, "")
                
                # Process each material layer in the construction
                for material_name, thickness in zip(construction["materials"], construction["thicknesses"]):
                    if material_name in self.materials:
                        properties = self._calculate_properties(material_name, thickness)
                        if properties:  # Only add if we successfully calculated properties
                            self.element_data.append({
                                "element_type": element_type,
                                "element_name": construction_name,
                                "material_name": material_name,
                                **properties
                            })
        except Exception as e:
            print(f"Error generating element data: {e}")

    def get_element_data(self):
        """
        Returns the list of processed element data.
        
        Returns:
            list: List of dictionaries containing element data and calculated properties
        """
        return self.element_data