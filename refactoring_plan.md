# Materials Parser and Generator Refactoring Plan

## New Requirements

Create a detailed table showing relationships between building surfaces, constructions, and materials with calculated thermal properties.

### Table Headers

1. element type
2. element name
3. material name
4. thickness
5. conductivity
6. density
7. calculated mass
8. thermal resistance
9. solar absorptance
10. Specific Heat

### Calculations

- thickness = from construction
- conductivity = from material
- density = from material
- mass = density \* thickness
- thermal resistance = thickness / conductivity
- solar absorptance = from material
- Specific Heat = from material

## Implementation Changes

### 1. Update MaterialsParser

```python
class MaterialsParser:
    def __init__(self):
        self.materials = {}
        self.constructions = {}
        self.surfaces = {}
        self.element_data = []  # Will store final processed data for report

    def process_idf(self, idf):
        # Process materials (unchanged)
        self._process_materials(idf)

        # Process constructions (unchanged)
        self._process_constructions(idf)

        # New: Process surfaces and deduce element types
        self._process_surfaces(idf)

        # New: Generate final element data with calculations
        self._generate_element_data()
```

Add new helper methods:

- `_deduce_element_type(surface)`: Implement element type deduction logic
- `_process_surfaces(idf)`: Process BUILDINGSURFACE:DETAILED objects
- `_calculate_properties(surface, construction, material)`: Calculate mass and thermal resistance
- `_generate_element_data()`: Compile final data structure for report

### 2. Update MaterialsReportGenerator

Create new table format with all required columns:

```python
def generate_materials_report_pdf(element_data, output_filename):
    # Create table with new headers
    headers = [
        "Element Type",
        "Element Name",
        "Material Name",
        "Thickness (m)",
        "Conductivity (W/m-K)",
        "Density (kg/m³)",
        "Mass (kg/m²)",
        "Thermal Resistance (m²K/W)",
        "Solar Absorptance",
        "Specific Heat (J/kg-K)"
    ]

    # Generate rows with calculated values
    data_rows = []
    for element in element_data:
        data_rows.append([
            element["element_type"],
            element["element_name"],
            element["material_name"],
            f"{element['thickness']:.3f}",
            f"{element['conductivity']:.3f}",
            f"{element['density']:.1f}",
            f"{element['mass']:.1f}",
            f"{element['thermal_resistance']:.3f}",
            f"{element['solar_absorptance']:.3f}",
            f"{element['specific_heat']:.1f}"
        ])
```

### 3. Update Main.py

Update main.py to handle the new data structure:

```python
# Process materials and surfaces
materials_extractor = MaterialsParser()
materials_extractor.process_idf(idf)

# Get processed element data
element_data = materials_extractor.get_element_data()

# Generate report with new format
materials_success = generate_materials_report_pdf(element_data, materials_pdf_path)
```

## Implementation Steps

1. Update MaterialsParser

   - Add new methods for surface processing
   - Implement element type deduction
   - Add property calculations

2. Update MaterialsReportGenerator

   - Create new table format
   - Update styling for new columns
   - Add calculations display

3. Test
   - Test with sample IDF file
   - Verify calculations
   - Check element type deduction
   - Validate report formatting

Would you like me to proceed with implementing these changes?
