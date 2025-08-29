# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an EnergyPlus IDF (Input Data File) Report Generator - a comprehensive building energy analysis tool that processes IDF files and generates detailed PDF reports with Hebrew language support for Israeli building energy compliance.

## Development Commands

### Setup and Running
```bash
# Setup development environment (Windows)
dev.bat

# Manual setup
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# Run application (GUI mode by default)
python main.py

# Run CLI mode
python main.py path/to/file.idf --idd "C:\EnergyPlusV9-4-0\Energy+.idd" -o output_directory
```

### Build and Distribution
```bash
# Build executable with version management (if exists)
python build_with_version.py

# Generate license keys
python generate_license_key.py
```

### Testing
```bash
# Test with sample files
python main.py tests/in-office.idf --idd "C:\EnergyPlusV9-4-0\Energy+.idd" -o test_output

# The tests/ directory contains various sample IDF files:
# - BGU.idf, in-office.idf, in-24.idf, in-megurim.idf, in-mesradim.idf, lights.idf
# Also contains EPJSON formats and simulation output files
```

## Architecture Overview

### Core Processing Flow
```
IDF File → DataLoader → Parsers → ProcessingManager → Generators → PDF Reports
    ↓
EnergyPlus Simulation → eplustbl.csv → EnergyRatingParser → Energy Rating Report
```

### Key Components

1. **Entry Points**
   - `main.py` - CLI and GUI launcher  
   - `modern_gui.py` - Flet-based modern GUI using Material Design 3

2. **Core Processing** 
   - `processing_manager.py:ProcessingManager` - Orchestrates entire pipeline
   - `utils/data_loader.py:DataLoader` - Centralized IDF data caching and retrieval

3. **Parser Layer** (`parsers/`)
   - Each parser extracts specific data domains (areas, materials, lighting, etc.)
   - All follow pattern: `__init__(data_loader)` → `parse()` → returns structured dict

4. **Generator Layer** (`generators/`) 
   - Creates PDF reports using ReportLab with Hebrew RTL text support
   - Pattern: `generate_*_report_pdf(data, output_path, project_name, run_id, city_name, area_name, **kwargs)`

5. **Utilities** (`utils/`)
   - `epjson_handler.py` - EnergyPlus EPJSON file handling
   - `idf_version_checker.py` - Version compatibility checking
   - `hebrew_text_utils.py` - Hebrew RTL text processing
   - `license_manager.py` - License validation and management
   - `sentry_config.py` - Error monitoring and crash reporting
   - `logging_config.py` - Centralized logging configuration
   - `update_manager.py` - Application update management
   - `path_utils.py` - File path utilities

### Data Models and Patterns

- **Parser Pattern**: All parsers inherit from base classes and implement `parse()` method
- **Generator Pattern**: Report generators are standalone functions accepting standardized parameters
- **Caching**: DataLoader caches all IDF object types on initial load for performance
- **Hebrew Support**: Text processing with RTL handling throughout the stack

## Key Features and Constraints

### EnergyPlus Integration
- Requires EnergyPlus 9.4.0+ installation
- Automatically runs simulations and processes `eplustbl.csv` output
- Injects required OUTPUT:VARIABLE entries into IDF files before simulation

### Israeli Climate Zone Support
```python
# Climate zone mapping
area_mapping = {
    "א": "a",  # Zone A (hottest) 
    "ב": "b",  # Zone B
    "ג": "c",  # Zone C  
    "ד": "d"   # Zone D (coolest)
}

# ISO 2023 uses numeric codes
iso_2023_mapping = {"א": "1", "ב": "2", "ג": "3", "ד": "4"}
```

### Report Types Generated
1. Settings Report - Building configuration and compliance
2. Schedules Report - Operating schedules analysis  
3. Loads Report - HVAC and internal loads
4. Materials Report - Construction materials specifications
5. Glazing Report - Window and glazing systems
6. Lighting Report - Lighting load analysis
7. Area Loss Report - Thermal loss calculations
8. Natural Ventilation Report - Ventilation analysis
9. Energy Rating Report - Energy consumption and rating
10. Zone Reports - Individual zone analysis (multiple PDFs)
11. Automatic Error Detection Report - Building model validation

### File Structure Notes
- `settings.json` - Persists user settings (last used paths, city, ISO type)
- `data/` - Contains EPW weather files and city/climate zone mappings
- `output/` - Generated reports organized by timestamp folders
- `logs/` - Application logs with Hebrew text support

## Development Guidelines

### Adding New Report Types
1. Create parser in `parsers/` following existing pattern
2. Create generator in `generators/` following function signature pattern  
3. Update `ProcessingManager._initialize_parsers()` and `_generate_all_reports()`
4. Test with Hebrew city names and various ISO types

### Hebrew Text Handling
- Use `utils/hebrew_text_utils.py` functions for RTL text processing
- Test GUI components with actual Hebrew city names
- Ensure UTF-8 encoding in all file operations
- ReportLab PDF generation requires Hebrew font support

### Error Handling
- Use structured logging via `utils/logging_config.py`  
- Sentry integration for production error monitoring via `utils/sentry_config.py`
- Graceful degradation when EnergyPlus simulation fails
- User-friendly error messages in Hebrew where appropriate
- Comprehensive data validation via `utils/report_data_validator.py`

## Dependencies and External Requirements

### Core Dependencies
```
reportlab>=3.6.8      # PDF generation
flet>=0.24.1          # Modern GUI framework  
numpy>=1.24.0         # Numerical computations
pandas>=2.0.0         # Data manipulation
pyinstaller>=6.3.0    # Executable packaging
cryptography>=41.0.0  # License encryption
pymongo>=4.5.0        # MongoDB for license management
sentry-sdk>=1.32.0    # Error monitoring
python-dotenv>=1.0.0  # Environment configuration
openpyxl>=3.1.0       # Excel file support
```

### External Requirements
- **EnergyPlus 9.4.0+** installed at system level
- Windows 10+ (primary platform)
- Hebrew font support for PDF generation

### Build Configuration
- PyInstaller spec includes hidden imports for `reportlab`, `flet`
- Data files include entire `data/` directory with EPW weather files
- Single-file executable output for distribution

## Performance Considerations

- **File Size Limits**: Tested up to 50MB IDF files
- **Memory Usage**: 2-4GB for large commercial buildings  
- **Processing Time**: 2-15 minutes depending on complexity
- **Caching Strategy**: DataLoader caches all objects on initial load
- **Background Processing**: GUI uses threading for responsiveness

## Security and Licensing

- MongoDB-based license validation system via `database/mongo_license_db.py`
- License keys tied to hardware fingerprinting via `utils/license_manager.py`
- Customer management tools in `tools/` directory
- License key generation via `generate_license_key.py`
- Secure storage of customer data and license information
- No sensitive data logged or persisted in reports
- Version management and update checking via `version.py` and `utils/update_manager.py`