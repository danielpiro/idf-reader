# IDF Report Generator - API Reference

## Overview

This document provides comprehensive API documentation for the IDF Report Generator's core classes, methods, and interfaces.

## Core Processing Classes

### ProcessingManager

Main orchestrator for IDF file processing and report generation.

```python
class ProcessingManager:
    """
    Manages the processing of IDF files, including parsing, data extraction,
    and report generation.
    """
```

#### Constructor

```python
def __init__(self, status_callback=None, progress_callback=None, simulation_output_csv=None):
    """
    Initializes the ProcessingManager.

    Args:
        status_callback (callable, optional): Function to receive status updates.
            Signature: status_callback(message: str) -> None
        progress_callback (callable, optional): Function to receive progress updates.
            Signature: progress_callback(value: float) -> None
            Value range: 0.0 to 1.0
        simulation_output_csv (str, optional): Path to EnergyPlus simulation output CSV.

    Example:
        def status_handler(message):
            print(f"Status: {message}")

        def progress_handler(value):
            print(f"Progress: {value*100:.1f}%")

        manager = ProcessingManager(
            status_callback=status_handler,
            progress_callback=progress_handler
        )
    """
```

#### Primary Methods

```python
def process_idf(self, input_file: str, idd_path: str, output_dir: str) -> bool:
    """
    Main method to process an IDF file and generate all reports.

    Args:
        input_file (str): Path to the input IDF file
        idd_path (str): Path to the Energy+.idd file
        output_dir (str): Base directory for output files

    Returns:
        bool: True if processing completed successfully, False otherwise

    Raises:
        FileNotFoundError: If input files are not found
        IOError: If file operations fail
        Exception: For unexpected errors during processing

    Example:
        success = manager.process_idf(
            input_file="building.idf",
            idd_path="C:/EnergyPlusV9-4-0/Energy+.idd",
            output_dir="./reports"
        )
    """

def cancel(self) -> None:
    """
    Signals that the current processing should be cancelled.

    Note: Cancellation is cooperative and may not stop immediately.
    EnergyPlus simulations cannot be cancelled once started.
    """

def update_status(self, message: str) -> None:
    """
    Sends a status update message via the callback.

    Args:
        message (str): Status message to send
    """

def update_progress(self, value: float) -> None:
    """
    Sends a progress update value via the callback.

    Args:
        value (float): Progress value between 0.0 and 1.0
    """
```

#### Properties

```python
@property
def is_cancelled(self) -> bool:
    """Returns True if processing has been cancelled."""

@property
def city_info(self) -> Dict[str, str]:
    """
    Returns city information including:
    - city: Hebrew city name
    - area_name: Climate zone letter (א, ב, ג, ד)
    - area_code: Numeric climate zone (1, 2, 3, 4)
    - iso_type: Selected ISO compliance type
    """
```

### DataLoader

Centralized IDF data caching and retrieval system.

```python
class DataLoader:
    """DataLoader for caching and retrieving IDF data."""
```

#### Constructor

```python
def __init__(self):
    """
    Initializes the DataLoader with empty caches.
    Call load_file() to populate caches with IDF data.
    """
```

#### Primary Methods

```python
def load_file(self, idf_path: str, idd_path: Optional[str] = None) -> None:
    """
    Load IDF file and cache raw data.

    Args:
        idf_path (str): Path to the IDF file
        idd_path (str, optional): Path to the IDD file

    Raises:
        FileNotFoundError: If IDF or IDD file not found
        Exception: If file parsing fails

    Example:
        loader = DataLoader()
        loader.load_file("building.idf", "Energy+.idd")
    """

def ensure_output_variables(self, idf_path: str = None, idd_path: Optional[str] = None) -> bool:
    """
    Ensure required output variables exist in the IDF file.

    Args:
        idf_path (str, optional): Path to IDF file. Uses loaded file if None.
        idd_path (str, optional): Path to IDD file

    Returns:
        bool: True if output variables were successfully checked/added

    Note:
        Adds these output variables if missing:
        - Zone Ideal Loads Supply Air Total Cooling Energy
        - Zone Ideal Loads Supply Air Total Heating Energy
        - Lights Electricity Energy
    """
```

#### Data Access Methods

```python
def get_zones(self) -> Dict[str, Dict[str, Any]]:
    """
    Get cached zone data.

    Returns:
        Dict mapping zone IDs to zone information:
        {
            "zone_id": {
                "id": str,
                "name": str,
                "area_id": str,
                "floor_area": float,
                "volume": float,
                "multiplier": int,
                "raw_object": eppy object,
                "surfaces": list
            }
        }
    """

def get_surfaces(self) -> Dict[str, Dict[str, Any]]:
    """
    Get cached surface data.

    Returns:
        Dict mapping surface IDs to surface information:
        {
            "surface_id": {
                "id": str,
                "name": str,
                "surface_type": str,
                "construction_name": str,
                "boundary_condition": str,
                "zone_name": str,
                "area": float,
                "raw_object": eppy object
            }
        }
    """

def get_materials(self) -> Dict[str, Dict[str, Any]]:
    """
    Get cached material data (all material types merged).

    Returns:
        Dict mapping material IDs to material information:
        {
            "material_id": {
                "id": str,
                "name": str,
                "type": str,  # "Material", "WindowMaterial:Glazing", etc.
                "conductivity": float,
                "density": float,
                "specific_heat": float,
                "thickness": float,
                # ... type-specific properties
                "raw_object": eppy object
            }
        }
    """

def get_constructions(self) -> Dict[str, Dict[str, Any]]:
    """Get cached construction data."""

def get_schedules(self) -> Dict[str, Dict[str, Any]]:
    """Get cached schedule data."""

def get_people_loads(self, zone_name: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
    """Get cached people loads, optionally filtered by zone."""

def get_lights_loads(self, zone_name: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
    """Get cached lights loads, optionally filtered by zone."""

def get_equipment_loads(self, zone_name: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
    """Get cached equipment loads, optionally filtered by zone."""

def get_windows(self) -> Dict[str, Dict[str, Any]]:
    """Get cached window data."""

def get_window_glazing_materials(self) -> Dict[str, Dict[str, Any]]:
    """Get cached window glazing materials."""

def get_window_shading_controls(self) -> Dict[str, Dict[str, Any]]:
    """Get cached window shading controls."""
```

#### Utility Methods

```python
def get_idf(self):
    """
    Get the raw IDF object for direct access.

    Returns:
        eppy IDF object or None if not loaded

    Note:
        Use this for operations not covered by cached data accessors.
    """

def get_cache_status(self) -> Dict[str, bool]:
    """
    Get the loading status of cache sections.

    Returns:
        Dict with cache section status:
        {
            "zones": bool,
            "surfaces": bool,
            "materials": bool,
            "constructions": bool,
            "schedules": bool
        }
    """
```

## GUI Classes

### IDFProcessorGUI

Main GUI application using CustomTkinter.

```python
class IDFProcessorGUI(ctk.CTk):
    """
    Main GUI application for IDF processing.
    Provides modern interface with Hebrew text support.
    """
```

#### Constructor

```python
def __init__(self):
    """
    Initializes the GUI application.

    Features:
    - Modern CustomTkinter interface
    - Hebrew text display support
    - Real-time input validation
    - Progress tracking
    - Settings persistence
    """
```

#### Key Methods

```python
def start_processing(self) -> None:
    """
    Initiates the IDF processing workflow.

    Workflow:
    1. Validate all input fields
    2. Create processing thread
    3. Run EnergyPlus simulation
    4. Generate reports via ProcessingManager
    5. Display results
    """

def cancel_processing(self) -> None:
    """
    Attempts to cancel the current processing operation.

    Note: Cancellation is cooperative and may not be immediate.
    """

def show_status(self, message: str, level: str = "info") -> None:
    """
    Display a status message in the activity log.

    Args:
        message (str): Status message to display
        level (str): Message level ("info", "success", "warning", "error")

    Note:
        Messages are automatically color-coded and timestamped.
    """

def load_settings(self) -> None:
    """Load user settings from settings.json file."""

def save_settings(self) -> None:
    """Save current user settings to settings.json file."""
```

#### Event Handlers

```python
def select_input_file(self) -> None:
    """Opens file dialog to select IDF input file."""

def select_output_dir(self) -> None:
    """Opens directory dialog to select output directory."""

def select_energyplus_dir(self) -> None:
    """Opens directory dialog to select EnergyPlus installation."""

def on_city_selected(self, selected_value: str = None) -> None:
    """
    Handles city selection events.

    Args:
        selected_value (str, optional): Selected city name

    Note:
        Automatically populates climate zone information.
    """
```

### Hebrew Text Support

```python
def fix_hebrew_text_display(text: str) -> str:
    """
    Fix Hebrew text display for GUI components.

    Args:
        text (str): Input text that may contain Hebrew characters

    Returns:
        str: Text with corrected word order for proper display

    Note:
        Handles RTL text ordering issues where Hebrew words
        appear in reverse order in tkinter widgets.

    Example:
        original = "תל אביב - יפו"
        fixed = fix_hebrew_text_display(original)
        # Properly orders Hebrew and punctuation
    """
```

## Parser Classes

### Base Parser Interface

```python
class BaseParser(ABC):
    """Abstract base class for all IDF parsers."""

    def __init__(self, data_loader: DataLoader, **kwargs):
        """
        Initialize parser with data loader and dependencies.

        Args:
            data_loader (DataLoader): Loaded IDF data cache
            **kwargs: Parser-specific dependencies
        """

    @abstractmethod
    def parse(self) -> Dict[str, Any]:
        """
        Extract and process domain-specific data.

        Returns:
            Dict containing structured, parsed data
        """
```

### AreaParser

```python
class AreaParser:
    """Parser for extracting zone and surface data from IDF files."""

    def __init__(self, data_loader: DataLoader, materials_parser: 'MaterialsParser',
                 simulation_output_csv: Optional[str] = None):
        """
        Initialize area parser.

        Args:
            data_loader (DataLoader): IDF data cache
            materials_parser (MaterialsParser): Material data dependency
            simulation_output_csv (str, optional): Path to simulation output
        """

    def parse(self) -> Dict[str, Any]:
        """
        Parse zone and surface data.

        Returns:
            Dict with zone analysis:
            {
                "zones": Dict[str, ZoneData],
                "surfaces": Dict[str, SurfaceData],
                "thermal_analysis": Dict[str, ThermalData]
            }
        """

    def get_zone_data(self, zone_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed data for specific zone."""

    def get_surface_data(self, surface_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed data for specific surface."""
```

### EnergyRatingParser

```python
class EnergyRatingParser:
    """Parser for energy rating and compliance calculations."""

    def __init__(self, data_loader: DataLoader, area_parser: AreaParser):
        """
        Initialize energy rating parser.

        Args:
            data_loader (DataLoader): IDF data cache
            area_parser (AreaParser): Zone and area data dependency
        """

    def process_output(self, simulation_csv: Optional[str] = None) -> None:
        """
        Process EnergyPlus simulation output for energy rating.

        Args:
            simulation_csv (str, optional): Path to eplustbl.csv output file
        """

    def get_energy_consumption(self, zone_id: str = None) -> Dict[str, float]:
        """
        Get energy consumption data.

        Args:
            zone_id (str, optional): Specific zone or all zones if None

        Returns:
            Dict with energy consumption by category:
            {
                "heating": float,
                "cooling": float,
                "lighting": float,
                "total": float
            }
        """

    def get_compliance_rating(self) -> Dict[str, Any]:
        """
        Get building energy compliance rating.

        Returns:
            Dict with compliance information:
            {
                "rating": str,  # A+, A, B, C, D, E, F
                "score": float,
                "compliant": bool,
                "requirements": Dict[str, float]
            }
        """
```

### MaterialsParser

```python
class MaterialsParser:
    """Parser for construction materials and thermal properties."""

    def __init__(self, data_loader: DataLoader):
        """Initialize materials parser."""

    def parse(self) -> Dict[str, Any]:
        """
        Parse material data from IDF.

        Returns:
            Dict with material information:
            {
                "materials": Dict[str, MaterialData],
                "constructions": Dict[str, ConstructionData],
                "thermal_properties": Dict[str, ThermalData]
            }
        """

    def get_material_properties(self, material_id: str) -> Optional[Dict[str, Any]]:
        """Get thermal properties for specific material."""

    def get_construction_layers(self, construction_id: str) -> List[str]:
        """Get ordered list of material layers in construction."""
```

## Report Generator Functions

### Function-based Generators

```python
def generate_settings_report_pdf(data: Dict[str, Any], output_path: str,
                                project_name: str, run_id: str,
                                city_name: str = "N/A", area_name: str = "N/A",
                                **kwargs) -> bool:
    """
    Generate building settings PDF report.

    Args:
        data (Dict): Parsed settings data from SettingsExtractor
        output_path (str): Full path for output PDF file
        project_name (str): Name of the building/project
        run_id (str): Unique identifier for this processing run
        city_name (str): Hebrew city name
        area_name (str): Climate zone designation (א,ב,ג,ד)
        **kwargs: Additional report parameters

    Returns:
        bool: True if report generated successfully

    Example:
        success = generate_settings_report_pdf(
            data=settings_data,
            output_path="reports/settings.pdf",
            project_name="Office Building",
            run_id="20240101_120000",
            city_name="תל אביב - יפו",
            area_name="א"
        )
    """

def generate_area_reports(area_parser: AreaParser, output_dir: str,
                         project_name: str, run_id: str,
                         city_name: str = "N/A", area_name: str = "N/A",
                         **kwargs) -> None:
    """
    Generate zone-specific area analysis reports.

    Args:
        area_parser (AreaParser): Initialized parser with processed data
        output_dir (str): Directory for zone report files
        project_name (str): Building/project name
        run_id (str): Processing run identifier
        city_name (str): Hebrew city name
        area_name (str): Climate zone designation

    Note:
        Creates separate PDF file for each zone in the building.
        Files named as: zone_<zone_id>_report.pdf
    """
```

### Class-based Generators

```python
class LightingReportGenerator:
    """Advanced lighting analysis report generator."""

    def __init__(self, data: Dict[str, Any], output_path: str,
                 project_name: str, run_id: str,
                 city_name: str = "N/A", area_name: str = "N/A",
                 **kwargs):
        """
        Initialize lighting report generator.

        Args:
            data (Dict): Parsed lighting data
            output_path (str): Output PDF path
            project_name (str): Project name
            run_id (str): Run identifier
            city_name (str): Hebrew city name
            area_name (str): Climate zone
        """

    def generate_report(self) -> bool:
        """
        Generate comprehensive lighting analysis report.

        Returns:
            bool: True if successful

        Report Sections:
        - Lighting fixture inventory
        - Power density analysis
        - Daylighting controls
        - Energy consumption breakdown
        - Compliance verification
        """

class EnergyRatingReportGenerator:
    """Energy rating and compliance report generator."""

    def __init__(self, energy_rating_parser: EnergyRatingParser,
                 output_dir: str, model_year: int, model_area_definition: str,
                 selected_city_name: str, project_name: str, run_id: str,
                 area_name: str = "N/A"):
        """
        Initialize energy rating report generator.

        Args:
            energy_rating_parser (EnergyRatingParser): Parser with processed data
            output_dir (str): Base output directory
            model_year (int): ISO compliance year (2017 or 2023)
            model_area_definition (str): Climate zone letter (A, B, C, D)
            selected_city_name (str): Hebrew city name
            project_name (str): Project name
            run_id (str): Run identifier
            area_name (str): Climate zone designation
        """

    def generate_report(self, output_filename: str = "energy-rating.pdf") -> bool:
        """
        Generate energy rating compliance report.

        Args:
            output_filename (str): Output PDF filename

        Returns:
            bool: True if successful
        """

    def generate_total_energy_rating_report(self, output_filename: str = "total_energy_rating.pdf") -> Optional[str]:
        """
        Generate comprehensive total energy rating report.

        Args:
            output_filename (str): Output PDF filename

        Returns:
            str: Full path to generated report, or None if failed
        """
```

## Utility Functions

### Energy Consumption Lookup

```python
def get_energy_consumption(iso_type_input: str, area_location_input: str,
                          area_definition_input: str) -> float:
    """
    Retrieves energy consumption value from CSV models.

    Args:
        iso_type_input (str): ISO type (e.g., "RESIDNTIAL 2017", "RESIDNTIAL 2023")
        area_location_input (str): Area type description
        area_definition_input (str): Climate zone letter ("A", "B", "C", "D")

    Returns:
        float: Energy consumption value in appropriate units

    Raises:
        ValueError: If iso_type or area_definition is invalid
        FileNotFoundError: If model CSV file not found
        KeyError: If area_location not found in CSV

    Example:
        consumption = get_energy_consumption(
            "RESIDNTIAL 2023",
            "Ground Floor & Intermediate ceiling",
            "A"
        )
    """
```

### Safe Type Conversion

```python
def safe_float(value: Any, default: float = 0.0) -> float:
    """
    Safely convert a value to float with fallback.

    Args:
        value (Any): Value to convert
        default (float): Default value if conversion fails

    Returns:
        float: Converted value or default

    Example:
        area = safe_float(zone.Floor_Area, 0.0)
    """
```

### Hebrew Text Processing

```python
def fix_hebrew_text_display(text: str) -> str:
    """
    Fix Hebrew text display issues in GUI components.

    Args:
        text (str): Text containing Hebrew characters

    Returns:
        str: Text with corrected word order

    Note:
        Handles RTL display issues in tkinter where Hebrew words
        appear in reverse order.
    """
```

## Error Handling

### Exception Classes

```python
class IDFProcessingError(Exception):
    """Base exception for IDF processing errors."""
    pass

class FileValidationError(IDFProcessingError):
    """Raised when input files fail validation."""
    pass

class EnergyPlusSimulationError(IDFProcessingError):
    """Raised when EnergyPlus simulation fails."""
    pass

class ReportGenerationError(IDFProcessingError):
    """Raised when PDF report generation fails."""
    pass
```

### Error Handling Patterns

```python
try:
    # IDF processing operation
    result = process_idf_data()
except FileNotFoundError as e:
    logger.error(f"Required file not found: {e}")
    # Handle missing file scenario
except ValueError as e:
    logger.error(f"Invalid data format: {e}")
    # Handle data validation errors
except IDFProcessingError as e:
    logger.error(f"Processing error: {e}")
    # Handle domain-specific errors
except Exception as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)
    # Handle unexpected errors
    raise
```

## Configuration Constants

### ISO Types

```python
ISO_TYPES = [
    "RESIDNTIAL 2023",
    "RESIDNTIAL 2017",
    "HOTEL",
    "EDUCATION",
    "OFFICE",
    "CORE & ENVELOPE"
]
```

### Climate Zones

```python
CLIMATE_ZONES = {
    "hebrew_letters": ["א", "ב", "ג", "ד"],
    "latin_letters": ["A", "B", "C", "D"],
    "numeric_codes": ["1", "2", "3", "4"],
    "mapping": {
        "א": {"latin": "A", "code": "1"},
        "ב": {"latin": "B", "code": "2"},
        "ג": {"latin": "C", "code": "3"},
        "ד": {"latin": "D", "code": "4"}
    }
}
```

### Report Types

```python
REPORT_TYPES = {
    "settings": "Building Settings and Configuration",
    "schedules": "Operating Schedules Analysis",
    "loads": "HVAC and Internal Loads",
    "materials": "Construction Materials Specifications",
    "glazing": "Windows and Glazing Systems",
    "lighting": "Lighting Systems Analysis",
    "area_loss": "Thermal Loss Calculations",
    "energy_rating": "Energy Rating and Compliance"
}
```

## Usage Examples

### Basic Processing Workflow

```python
from processing_manager import ProcessingManager
from utils.data_loader import DataLoader

def process_building():
    """Complete building analysis workflow."""

    # Initialize processing manager with callbacks
    def status_update(message):
        print(f"Status: {message}")

    def progress_update(value):
        print(f"Progress: {value*100:.1f}%")

    manager = ProcessingManager(
        status_callback=status_update,
        progress_callback=progress_update
    )

    # Set city information for climate zone selection
    manager.city_info = {
        "city": "תל אביב - יפו",
        "area_name": "א",
        "area_code": "1",
        "iso_type": "RESIDNTIAL 2023"
    }

    # Process IDF file
    success = manager.process_idf(
        input_file="office_building.idf",
        idd_path="C:/EnergyPlusV9-4-0/Energy+.idd",
        output_dir="./analysis_results"
    )

    if success:
        print("Analysis completed successfully!")
        print("Reports available in: ./analysis_results/reports/")
    else:
        print("Analysis failed. Check logs for details.")

if __name__ == "__main__":
    process_building()
```

### Custom Parser Implementation

```python
from utils.data_loader import DataLoader
from typing import Dict, Any

class CustomFeatureParser:
    """Example custom parser for specific IDF features."""

    def __init__(self, data_loader: DataLoader):
        self.data_loader = data_loader
        self._parsed_data = {}

    def parse(self) -> Dict[str, Any]:
        """Parse custom feature data."""

        # Access raw IDF objects
        idf = self.data_loader.get_idf()
        custom_objects = idf.idfobjects.get('CUSTOM_OBJECT_TYPE', [])

        # Process objects
        for obj in custom_objects:
            obj_id = str(obj.Name)
            self._parsed_data[obj_id] = {
                "name": obj_id,
                "property1": self._safe_float(obj.Property1),
                "property2": str(obj.Property2),
                "processed_at": datetime.now().isoformat()
            }

        return self._parsed_data

    def _safe_float(self, value, default=0.0):
        """Helper method for safe type conversion."""
        try:
            return float(value) if value else default
        except (ValueError, TypeError):
            return default

# Usage
loader = DataLoader()
loader.load_file("building.idf")
parser = CustomFeatureParser(loader)
results = parser.parse()
```

### GUI Integration Example

```python
import customtkinter as ctk
from gui import IDFProcessorGUI

class ExtendedGUI(IDFProcessorGUI):
    """Extended GUI with custom features."""

    def __init__(self):
        super().__init__()
        self._add_custom_controls()

    def _add_custom_controls(self):
        """Add custom GUI controls."""

        # Add custom section
        custom_frame = ctk.CTkFrame(self)
        custom_frame.grid(row=10, column=0, sticky="ew", padx=20, pady=10)

        ctk.CTkLabel(
            custom_frame,
            text="Custom Analysis Options",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(pady=10)

        # Custom checkbox
        self.custom_analysis = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            custom_frame,
            text="Enable advanced thermal analysis",
            variable=self.custom_analysis
        ).pack(pady=5)

    def start_processing(self):
        """Override to include custom processing options."""

        if self.custom_analysis.get():
            self.show_status("Custom analysis enabled")

        # Call parent processing method
        super().start_processing()

if __name__ == "__main__":
    app = ExtendedGUI()
    app.mainloop()
```

---

_This API reference provides comprehensive documentation for extending and integrating with the IDF Report Generator system._
