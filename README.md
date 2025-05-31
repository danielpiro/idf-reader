# IDF Report Generator - Developer Documentation

## Project Overview

The IDF Report Generator is a comprehensive building energy analysis tool that processes EnergyPlus IDF (Input Data File) files and generates detailed PDF reports. The application supports both GUI and CLI interfaces and includes Hebrew language support for Israeli building energy compliance reporting.

### Key Features

- **EnergyPlus Integration**: Runs EnergyPlus simulations and processes output data
- **Multi-Report Generation**: Creates 8+ different report types (settings, schedules, loads, materials, glazing, lighting, area loss, energy rating)
- **Hebrew Language Support**: Full RTL text support for Israeli cities and regulations
- **ISO Compliance**: Supports multiple ISO types including RESIDENTIAL 2017/2023, HOTEL, EDUCATION, OFFICE, CORE & ENVELOPE
- **Climate Zone Integration**: Automatic EPW weather file selection based on Israeli climate zones (א, ב, ג, ד)
- **Dual Interface**: Modern GUI using CustomTkinter and CLI support

## Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Entry Points  │    │  Core Processing │    │   Report Output │
├─────────────────┤    ├─────────────────┤    ├─────────────────┤
│ main.py         │ -> │ ProcessingManager│ -> │ PDF Reports     │
│ gui.py          │    │ DataLoader      │    │ Zone Reports    │
└─────────────────┘    │ EppyHandler     │    │ CSV Exports     │
                       └─────────────────┘    └─────────────────┘
```

### Core Components

1. **Entry Layer** ([`main.py`](main.py:1), [`gui.py`](gui.py:1))
2. **Processing Layer** ([`processing_manager.py`](processing_manager.py:1))
3. **Data Layer** ([`utils/`](utils/))
4. **Parser Layer** ([`parsers/`](parsers/))
5. **Generator Layer** ([`generators/`](generators/))

## Project Structure

```
idf-reader/
├── main.py                     # CLI entry point
├── gui.py                      # GUI application with CustomTkinter
├── processing_manager.py       # Core processing orchestrator
├── requirements.txt            # Python dependencies
├── settings.json              # User settings persistence
├── build.py                   # PyInstaller build script
├── package.py                 # Distribution packaging
├── idf_code_cleaner.py        # IDF file cleanup utility
├── create_final_documentation.py  # Documentation generator
│
├── utils/                     # Core utilities
│   ├── data_loader.py         # IDF data caching and loading
│   ├── data_models.py         # Data structure definitions
│   ├── eppy_handler.py        # EnergyPlus file handling
│   └── hebrew_text_utils.py   # Hebrew text processing
│
├── parsers/                   # Data extraction modules
│   ├── area_parser.py         # Zone and surface parsing
│   ├── area_loss_parser.py    # Thermal loss calculations
│   ├── energy_rating_parser.py # Energy rating analysis
│   ├── eplustbl_reader.py     # EnergyPlus table parsing
│   ├── glazing_parser.py      # Window and glazing systems
│   ├── lighting_parser.py     # Lighting load analysis
│   ├── load_parser.py         # HVAC and internal loads
│   ├── materials_parser.py    # Construction materials
│   ├── schedule_parser.py     # Operating schedules
│   └── settings_parser.py     # Building settings
│
├── generators/                # Report generation modules
│   ├── area_report_generator.py        # Zone-specific reports
│   ├── area_loss_report_generator.py   # Thermal loss reports
│   ├── energy_rating_report_generator.py # Energy rating reports
│   ├── glazing_report_generator.py     # Glazing analysis
│   ├── lighting_report_generator.py    # Lighting reports
│   ├── load_report_generator.py        # Load analysis
│   ├── materials_report_generator.py   # Material specifications
│   ├── schedule_report_generator.py    # Schedule analysis
│   └── settings_report_generator.py    # Building settings
│
├── data/                      # Configuration and weather data
│   ├── countries-selection.csv # City and climate zone mapping
│   ├── 2017_model.csv         # 2017 ISO energy consumption data
│   ├── *.epw                  # Weather files (a.epw, b.epw, c.epw, d.epw, 1.epw, 2.epw, etc.)
│   └── ...
│
└── tests/                     # Test IDF files
    ├── 3.1.idf
    ├── in.idf
    └── ...
```

## Setup and Installation

### Prerequisites

- **Python 3.8+**
- **EnergyPlus 9.4.0+** (installed separately)
- Windows 10+ (primary platform)

### Installation Steps

1. **Clone the repository**

```bash
git clone <repository-url>
cd idf-reader
```

2. **Create virtual environment**

```bash
python -m venv venv
venv\Scripts\activate  # Windows
# or
source venv/bin/activate  # Linux/Mac
```

3. **Install dependencies**

```bash
pip install -r requirements.txt
```

4. **Install EnergyPlus**
   - Download from https://energyplus.net/
   - Install to default location (e.g., `C:\EnergyPlusV9-4-0\`)
   - Note the installation path for configuration

### Dependencies

```python
# Core dependencies from requirements.txt
reportlab>=3.6.8      # PDF generation
eppy>=0.5.63          # EnergyPlus file handling
customtkinter>=5.2.0  # Modern GUI framework
pyinstaller>=6.3.0    # Executable packaging
numpy>=1.24.0         # Numerical computations
pandas>=2.0.0         # Data manipulation
openpyxl>=3.1.0       # Excel file support
colorama>=0.4.6       # CLI color output
tabulate>=0.8.10      # Table formatting
```

## Usage

### GUI Mode (Recommended)

```bash
python main.py
```

The GUI provides:

- File selection dialogs
- City selection with Hebrew support
- ISO type selection
- Real-time progress tracking
- Activity logging
- Automatic EnergyPlus integration

### CLI Mode

```bash
python main.py input.idf --idd "C:\EnergyPlusV9-4-0\Energy+.idd" -o output_directory
```

**CLI Arguments:**

- `idf_file`: Path to input IDF file (required)
- `--idd`: Path to Energy+.idd file (required)
- `-o, --output`: Output directory (default: 'output')

### Configuration

Settings are automatically saved to [`settings.json`](settings.json:1):

```json
{
  "last_input": "path/to/file.idf",
  "last_eplus_dir": "C:/EnergyPlusV9-4-0",
  "last_output": "C:/output/path",
  "last_city": "אכסאל",
  "last_iso_type": "RESIDNTIAL 2023"
}
```

## Development Workflow

### Code Organization Principles

The project follows these core CS principles:

- **DRY (Don't Repeat Yourself)**: Shared functionality in utils/
- **SRP (Single Responsibility)**: Each parser/generator handles one domain
- **Separation of Concerns**: GUI, processing, and data layers are isolated
- **Modularity**: Reusable components across parsers and generators

### Adding New Report Types

1. **Create Parser** (if needed)

```python
# parsers/new_feature_parser.py
class NewFeatureParser:
    def __init__(self, data_loader):
        self.data_loader = data_loader

    def parse(self):
        # Extract data from IDF
        return processed_data
```

2. **Create Generator**

```python
# generators/new_feature_generator.py
def generate_new_feature_report_pdf(data, output_path, **kwargs):
    # Generate PDF report
    pass
```

3. **Update ProcessingManager**

```python
# Add to _initialize_parsers()
parsers["new_feature"] = NewFeatureParser(data_loader)

# Add to _extract_data_from_parsers()
"new_feature": parsers["new_feature"].parse()

# Add to _generate_all_reports()
self._generate_report_item("New Feature", generate_new_feature_report_pdf, ...)
```

### Key Data Flow

```
IDF File -> DataLoader -> Parsers -> ProcessingManager -> Generators -> PDF Reports
    ↓
EnergyPlus Simulation -> eplustbl.csv -> EnergyRatingParser -> Energy Rating Report
```

## Key Classes and Modules

### Core Processing

#### [`ProcessingManager`](processing_manager.py:34)

- **Purpose**: Orchestrates the entire processing pipeline
- **Key Methods**:
  - [`process_idf()`](processing_manager.py:375): Main processing entry point
  - [`_initialize_parsers()`](processing_manager.py:127): Sets up all parsers
  - [`_generate_all_reports()`](processing_manager.py:246): Coordinates report generation
- **Status Callbacks**: Provides real-time progress updates

#### [`DataLoader`](utils/data_loader.py:100)

- **Purpose**: Centralized IDF data caching and retrieval
- **Key Features**:
  - Comprehensive caching system for all IDF object types
  - Hebrew text handling
  - EnergyPlus output variable management
- **Key Methods**:
  - [`load_file()`](utils/data_loader.py:156): Loads and caches IDF data
  - [`ensure_output_variables()`](utils/data_loader.py:133): Adds required output variables
  - [`get_zones()`](utils/data_loader.py:687), [`get_materials()`](utils/data_loader.py:734), etc.: Data accessors

### GUI System

#### [`IDFProcessorGUI`](gui.py:67)

- **Purpose**: Modern GUI using CustomTkinter
- **Key Features**:
  - Hebrew text display with [`fix_hebrew_text_display()`](gui.py:15)
  - Real-time input validation
  - Progress tracking with cancellation support
  - Settings persistence
- **Key Methods**:
  - [`start_processing()`](gui.py:530): Initiates processing workflow
  - [`process_file_thread_target()`](gui.py:675): Background processing
  - [`_run_energyplus_simulation()`](gui.py:617): EnergyPlus integration

### Parser Layer

Each parser follows a consistent pattern:

```python
class Parser:
    def __init__(self, data_loader, additional_deps=None):
        self.data_loader = data_loader

    def parse(self) -> Dict:
        # Extract and process data
        return structured_data
```

**Key Parsers:**

- [`AreaParser`](parsers/area_parser.py): Zone and surface analysis
- [`EnergyRatingParser`](parsers/energy_rating_parser.py): Energy consumption calculations
- [`GlazingParser`](parsers/glazing_parser.py): Window and glazing systems
- [`MaterialsParser`](parsers/materials_parser.py): Construction materials

### Generator Layer

Generators create PDF reports using ReportLab:

```python
def generate_report_pdf(data, output_path, project_name, run_id,
                       city_name="N/A", area_name="N/A", **kwargs):
    # Create PDF using ReportLab
    # Handle Hebrew text rendering
    # Generate tables, charts, and analysis
```

## Climate Zone Integration

The application maps Israeli cities to climate zones:

```python
# Climate zone mapping (Hebrew letters to Latin letters)
area_mapping = {
    "א": "a",  # Zone A (hottest)
    "ב": "b",  # Zone B
    "ג": "c",  # Zone C
    "ד": "d"   # Zone D (coolest)
}

# ISO 2023 uses numeric codes
iso_2023_mapping = {
    "א": "1",
    "ב": "2",
    "ג": "3",
    "ד": "4"
}
```

### EPW File Selection Logic

```python
if iso_type == "RESIDNTIAL 2023":
    epw_file = f"{area_code}.epw"  # 1.epw, 2.epw, etc.
else:
    epw_file = f"{area_letter}.epw"  # a.epw, b.epw, etc.
```

## Hebrew Language Support

### Text Processing

The [`fix_hebrew_text_display()`](gui.py:15) function handles RTL text display issues:

```python
def fix_hebrew_text_display(text):
    # Handles Hebrew character range \u0590-\u05FF
    # Reverses word order for mixed Hebrew-English text
    # Addresses tkinter RTL display limitations
```

### Font Handling

For PDF generation, ensure Hebrew fonts are available:

- Use fonts like "Arial" or "David" that support Hebrew
- Handle RTL text direction in ReportLab
- Test with actual Hebrew city names

## Testing

### Test Files

Located in [`tests/`](tests/) directory:

- [`3.1.idf`](tests/3.1.idf): Sample IDF file
- [`in.idf`](tests/in.idf): Basic test case
- Various simulation output files

### Running Tests

```bash
# Test CLI functionality
python main.py tests/3.1.idf --idd "C:\EnergyPlusV9-4-0\Energy+.idd" -o test_output

# Test GUI (manual)
python main.py
```

### Validation Points

- **Input Validation**: File existence, EnergyPlus installation
- **Data Integrity**: IDF parsing accuracy
- **Report Generation**: PDF creation success
- **Hebrew Support**: RTL text rendering
- **Climate Integration**: Correct EPW file selection

## Building and Deployment

### Development Build

```bash
python build.py
```

Uses PyInstaller with configuration in [`IDF-Processor.spec`](IDF-Processor.spec).

### Distribution Package

```bash
python package.py
```

Creates distributable package with all dependencies.

### Build Configuration

Key build settings:

- **Hidden Imports**: `eppy`, `reportlab`, `customtkinter`
- **Data Files**: Include `data/` directory
- **Icon**: Application icon file
- **One File**: Single executable output

## Common Issues and Solutions

### EnergyPlus Integration

**Problem**: EnergyPlus simulation fails
**Solution**:

- Verify EnergyPlus installation path
- Check IDF file validity
- Ensure EPW weather file exists
- Review simulation error logs

### Hebrew Text Display

**Problem**: Hebrew text appears reversed or corrupted
**Solution**:

- Use [`fix_hebrew_text_display()`](gui.py:15) for GUI components
- Verify UTF-8 encoding in file operations
- Test with actual Hebrew city names

### Memory Usage

**Problem**: Large IDF files cause memory issues
**Solution**:

- DataLoader uses caching to optimize memory
- Process reports incrementally
- Clear caches between large files

### Report Generation Errors

**Problem**: PDF generation fails
**Solution**:

- Check ReportLab installation
- Verify output directory permissions
- Handle missing data gracefully
- Log specific error details

## Contributing Guidelines

### Code Style

- Follow PEP 8 for Python code style
- Use type hints where appropriate
- Document all public methods and classes
- Maintain consistent error handling

### Adding Features

1. **Create feature branch**
2. **Follow established patterns** (Parser -> Generator flow)
3. **Add comprehensive logging**
4. **Test with Hebrew text**
5. **Update documentation**

### Testing Requirements

- Test with multiple IDF file types
- Verify Hebrew text handling
- Test all ISO types and climate zones
- Validate report generation accuracy

## API Reference

### Core Classes

```python
# Main processing
ProcessingManager(status_callback, progress_callback, simulation_output_csv)

# Data access
DataLoader()
    .load_file(idf_path, idd_path)
    .get_zones() -> Dict
    .get_materials() -> Dict
    .get_surfaces() -> Dict

# GUI
IDFProcessorGUI()
    .start_processing()
    .show_status(message, level)
```

### Configuration Constants

```python
# ISO types
ISO_TYPES = [
    "RESIDNTIAL 2023", "RESIDNTIAL 2017", "HOTEL",
    "EDUCATION", "OFFICE", "CORE & ENVELOPE"
]

# Climate zones
CLIMATE_ZONES = ["א", "ב", "ג", "ד"]  # A, B, C, D

# Report types
REPORT_TYPES = [
    "settings", "schedules", "loads", "materials",
    "glazing", "lighting", "area_loss", "energy_rating"
]
```

## Performance Considerations

### Optimization Strategies

1. **Caching**: DataLoader caches all IDF objects on load
2. **Lazy Loading**: Reports generated only when requested
3. **Memory Management**: Clear large objects after use
4. **Background Processing**: GUI uses threading for responsiveness

### Scalability Limits

- **File Size**: Tested up to 50MB IDF files
- **Memory**: Approximately 2-4GB for large commercial buildings
- **Processing Time**: 2-15 minutes depending on building complexity

## Security Considerations

### File Handling

- Validate file paths to prevent directory traversal
- Sanitize user input for file names
- Use temporary directories for EnergyPlus simulation

### External Process Execution

- EnergyPlus is called as subprocess with controlled parameters
- Validate EnergyPlus installation path
- Handle subprocess errors gracefully

## Future Development

### Planned Features

1. **Multi-language Support**: Additional language interfaces
2. **Cloud Integration**: Remote EnergyPlus processing
3. **Advanced Analytics**: Machine learning insights
4. **Web Interface**: Browser-based version
5. **API Endpoints**: RESTful service interface

### Technical Debt

1. **Logging Centralization**: Consolidate logging configuration
2. **Error Handling**: Standardize exception handling patterns
3. **Configuration Management**: Environment-based settings
4. **Test Coverage**: Automated testing suite

## Support and Maintenance

### Troubleshooting

1. **Check logs** in application output
2. **Verify EnergyPlus** installation and version
3. **Validate IDF file** structure
4. **Test with sample files** in `tests/` directory

### Getting Help

- Review error messages and logs
- Check Hebrew text encoding issues
- Verify climate zone and EPW file mapping
- Test with known working IDF files

---

_This documentation is maintained alongside the codebase. Please update when making significant changes to the architecture or adding new features._
