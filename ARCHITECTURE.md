# IDF Report Generator - Technical Architecture

## System Overview

The IDF Report Generator is a multi-layered application designed for processing EnergyPlus IDF (Input Data File) files and generating comprehensive building energy analysis reports. The architecture emphasizes modularity, maintainability, and Hebrew language support for Israeli building energy compliance.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Interface Layer                      │
├─────────────────────────────────────────────────────────────────┤
│  GUI (CustomTkinter)           │         CLI Interface            │
│  - Hebrew text support         │         - Command line args     │
│  - Progress tracking           │         - Batch processing      │
│  - Real-time validation        │         - Automation support    │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Processing Orchestration                     │
├─────────────────────────────────────────────────────────────────┤
│                    ProcessingManager                            │
│  - Workflow coordination       │  - Progress reporting          │
│  - Error handling             │  - Cancellation support        │
│  - Status callbacks           │  - Resource management         │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Data Processing Layer                       │
├─────────────────────────────────────────────────────────────────┤
│    DataLoader           │    EppyHandler    │   EnergyPlus      │
│  - IDF caching         │  - File I/O       │   - Simulation    │
│  - Data validation     │  - Object access  │   - CSV output    │
│  - Memory management   │  - Format handling│   - Error logs    │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Analysis Layer                              │
├─────────────────────────────────────────────────────────────────┤
│  Specialized Parsers                                            │
│  ┌─────────────┬─────────────┬─────────────┬─────────────────┐   │
│  │ Area Parser │Load Parser  │Material     │Energy Rating    │   │
│  │- Zones      │- HVAC loads │Parser       │Parser           │   │
│  │- Surfaces   │- Internal   │- Materials  │- Consumption    │   │
│  │- Geometry   │  loads      │- Properties │- Compliance     │   │
│  └─────────────┴─────────────┴─────────────┴─────────────────┘   │
│  ┌─────────────┬─────────────┬─────────────┬─────────────────┐   │
│  │Glazing      │Lighting     │Schedule     │Settings Parser  │   │
│  │Parser       │Parser       │Parser       │- Building info  │   │
│  │- Windows    │- Fixtures   │- Operating  │- Simulation     │   │
│  │- Properties │- Controls   │  patterns   │  parameters     │   │
│  └─────────────┴─────────────┴─────────────┴─────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Report Generation Layer                     │
├─────────────────────────────────────────────────────────────────┤
│  PDF Report Generators                                          │
│  ┌─────────────┬─────────────┬─────────────┬─────────────────┐   │
│  │Area Reports │Load Reports │Material     │Energy Rating    │   │
│  │- Zone       │- HVAC       │Reports      │Reports          │   │
│  │  analysis   │  analysis   │- Specs      │- Compliance     │   │
│  │- Thermal    │- Internal   │- Thermal    │- Standards      │   │
│  │  properties │  loads      │  properties │- Calculations   │   │
│  └─────────────┴─────────────┴─────────────┴─────────────────┘   │
│  ┌─────────────┬─────────────┬─────────────┬─────────────────┐   │
│  │Glazing      │Lighting     │Schedule     │Settings Reports │   │
│  │Reports      │Reports      │Reports      │- Project info   │   │
│  │- Window     │- Fixture    │- Operating  │- Configuration  │   │
│  │  analysis   │  analysis   │  schedules  │- Metadata       │   │
│  └─────────────┴─────────────┴─────────────┴─────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## Core Components Deep Dive

### 1. Processing Manager (`processing_manager.py`)

**Responsibility**: Central orchestrator for the entire processing pipeline

**Key Design Patterns**:

- **Command Pattern**: Encapsulates processing operations
- **Observer Pattern**: Status and progress callbacks
- **Template Method**: Standardized processing workflow

```python
class ProcessingManager:
    """
    Orchestrates the complete IDF processing workflow.

    Workflow:
    1. Initialize core components (DataLoader, EppyHandler)
    2. Set up parsers with dependencies
    3. Process IDF data through all parsers
    4. Extract structured data
    5. Generate all report types
    6. Handle errors and cleanup
    """

    def process_idf(self, input_file: str, idd_path: str, output_dir: str) -> bool:
        # Template method implementation
        self._setup_output_paths()
        self._initialize_core_components()
        self._initialize_parsers()
        self._process_data_sources()
        self._extract_data_from_parsers()
        self._generate_all_reports()
```

**Error Handling Strategy**:

- Graceful degradation: Continue processing even if some reports fail
- Comprehensive logging with context
- User-friendly error messages
- Resource cleanup in finally blocks

### 2. Data Loader (`utils/data_loader.py`)

**Responsibility**: Centralized IDF data caching and access layer

**Key Design Patterns**:

- **Facade Pattern**: Simplifies complex eppy interactions
- **Cache Pattern**: In-memory storage for performance
- **Factory Pattern**: Creates appropriate data structures

```python
class DataLoader:
    """
    Comprehensive caching system for IDF data.

    Caching Strategy:
    - Load all data once during initialization
    - Organize by object type (zones, surfaces, materials, etc.)
    - Provide typed accessors for each data category
    - Handle Hebrew text encoding automatically
    """

    # Cache organization
    _zones_cache: Dict[str, Dict[str, Any]]
    _surfaces_cache: Dict[str, Dict[str, Any]]
    _materials_cache: Dict[str, Dict[str, Any]]
    _constructions_cache: Dict[str, Dict[str, Any]]
    # ... specialized caches for each IDF object type
```

**Memory Management**:

- Lazy loading for large objects
- Cache invalidation strategies
- Memory-efficient data structures
- Cleanup methods for large files

### 3. Parser Layer Architecture

**Design Philosophy**: Each parser is responsible for one domain of building data

**Common Parser Interface**:

```python
class BaseParser(ABC):
    def __init__(self, data_loader: DataLoader, **dependencies):
        self.data_loader = data_loader

    @abstractmethod
    def parse(self) -> Dict[str, Any]:
        """Extract and structure domain-specific data"""
        pass

    def _validate_data(self, data: Any) -> bool:
        """Validate extracted data integrity"""
        return True
```

**Parser Dependencies**:

```
AreaParser ←── MaterialsParser
    ↓
AreaLossParser ←── AreaParser + ClimateData
    ↓
EnergyRatingParser ←── AreaParser + SimulationOutput
```

#### Area Parser (`parsers/area_parser.py`)

- **Primary Function**: Zone and surface geometry analysis
- **Dependencies**: MaterialsParser for thermal properties
- **Output**: Zone definitions, surface areas, thermal characteristics

#### Energy Rating Parser (`parsers/energy_rating_parser.py`)

- **Primary Function**: Energy consumption and compliance calculations
- **Dependencies**: AreaParser + EnergyPlus simulation output
- **Output**: Energy ratings, compliance metrics, consumption analysis

#### Materials Parser (`parsers/materials_parser.py`)

- **Primary Function**: Construction material specifications
- **Dependencies**: DataLoader only (base parser)
- **Output**: Material properties, thermal characteristics, construction details

### 4. Report Generation Architecture

**Design Pattern**: Strategy Pattern for different report types

```python
class ReportGenerator(ABC):
    @abstractmethod
    def generate_report(self, data: Dict, output_path: str, **metadata) -> bool:
        pass

def generate_area_reports(parser_instance, output_dir, **metadata):
    """Function-based generator for area reports"""
    pass

class LightingReportGenerator:
    """Class-based generator for complex reports"""
    def __init__(self, data, output_path, **metadata):
        pass

    def generate_report(self) -> bool:
        pass
```

**Report Generation Pipeline**:

1. **Data Validation**: Ensure required data is available
2. **Template Setup**: Initialize PDF document with styles
3. **Content Generation**: Create tables, charts, and analysis
4. **Hebrew Text Processing**: Handle RTL text rendering
5. **File Output**: Write PDF with proper encoding

## Data Flow Architecture

### 1. Input Processing Flow

```
IDF File → EppyHandler → DataLoader → Cache Storage
    ↓
Weather File (EPW) → EnergyPlus Simulation → eplustbl.csv
    ↓
Combined Data → Parsers → Structured Analysis
```

### 2. Report Generation Flow

```
Parsed Data → Report Templates → PDF Generation → File Output
    ↓              ↓                  ↓
Validation → Hebrew Processing → Error Handling
```

### 3. Error Propagation Flow

```
Low-level Error → Logger → ProcessingManager → User Callback → GUI/CLI Display
```

## Hebrew Language Support Architecture

### Text Processing Pipeline

```python
# Input: Raw Hebrew text from IDF or user interface
hebrew_text = "תל אביב - יפו"

# Step 1: Character encoding validation
validated_text = ensure_utf8_encoding(hebrew_text)

# Step 2: Display correction for GUI
display_text = fix_hebrew_text_display(validated_text)

# Step 3: PDF rendering preparation
pdf_text = prepare_hebrew_for_pdf(display_text)
```

### RTL Text Handling Strategy

**Problem**: Tkinter and ReportLab handle Hebrew RTL text differently
**Solution**: Multi-layer text processing

```python
def fix_hebrew_text_display(text: str) -> str:
    """
    Handles Hebrew text display issues:
    1. Detects Hebrew character ranges (\u0590-\u05FF)
    2. Identifies mixed Hebrew-Latin content
    3. Reverses word order for proper display
    4. Preserves punctuation positioning
    """
```

## Climate Zone Integration Architecture

### Geographic Data Structure

```python
# City mapping structure
city_data = {
    "city_name_hebrew": {
        "area_name": "א",  # Climate zone letter
        "area_code": "1"   # Numeric code for ISO 2023
    }
}

# EPW file selection logic
def select_weather_file(iso_type: str, area_name: str, area_code: str) -> str:
    if "2023" in iso_type:
        return f"{area_code}.epw"  # 1.epw, 2.epw, 3.epw, 4.epw
    else:
        area_map = {"א": "a", "ב": "b", "ג": "c", "ד": "d"}
        return f"{area_map[area_name]}.epw"  # a.epw, b.epw, c.epw, d.epw
```

### Energy Consumption Lookup

```python
def get_energy_consumption(iso_type: str, area_location: str, area_definition: str) -> float:
    """
    Retrieves energy consumption values from CSV models:
    - 2017_model.csv for ISO 2017 compliance
    - 2023_model.csv for ISO 2023 compliance

    Lookup structure:
    area_location (index) → A, B, C, D (columns) → consumption value
    """
```

## Memory and Performance Architecture

### Caching Strategy

```python
class DataLoader:
    """
    Three-tier caching system:

    Tier 1: Raw IDF objects (direct eppy access)
    Tier 2: Processed data structures (typed dictionaries)
    Tier 3: Computed analysis results (derived values)
    """

    def _cache_zones(self):
        """Load and structure zone data once"""

    def _cache_materials(self):
        """Load and structure material data once"""

    def _build_all_materials_cache(self):
        """Merge all material types into unified cache"""
```

### Memory Management Patterns

1. **Lazy Loading**: Load data only when requested
2. **Cache Invalidation**: Clear unused caches during processing
3. **Batch Processing**: Handle large datasets in chunks
4. **Resource Cleanup**: Explicit cleanup of large objects

```python
def process_large_idf():
    data_loader = DataLoader()
    try:
        data_loader.load_file(large_file)
        # Process in batches
        for zone_batch in chunked(data_loader.get_zones().items(), 100):
            process_zones(zone_batch)
    finally:
        del data_loader
        gc.collect()
```

## Error Handling Architecture

### Multi-Level Error Strategy

```python
class ErrorHandlingLayers:
    """
    Layer 1: Low-level validation (file existence, data format)
    Layer 2: Business logic validation (data integrity, requirements)
    Layer 3: User interface error presentation
    Layer 4: Recovery and graceful degradation
    """
```

### Error Categories and Responses

| Error Type                    | Response Strategy                 | User Impact          |
| ----------------------------- | --------------------------------- | -------------------- |
| File Not Found                | Clear error message + file picker | Immediate correction |
| Invalid IDF Format            | Validation report + suggestions   | Guided fix           |
| EnergyPlus Simulation Failure | Continue with limited reports     | Partial results      |
| Hebrew Text Encoding          | Fallback to Latin transliteration | Reduced quality      |
| Memory Shortage               | Batch processing + cache clearing | Slower processing    |

## Security Architecture

### File System Security

```python
def validate_file_path(file_path: str) -> bool:
    """
    Security validations:
    1. Prevent directory traversal attacks
    2. Validate file extensions
    3. Check file size limits
    4. Verify read/write permissions
    """

def sanitize_output_filename(filename: str) -> str:
    """
    Sanitize user-provided filenames:
    1. Remove special characters
    2. Limit filename length
    3. Prevent system file overwrites
    """
```

### External Process Security

```python
def run_energyplus_simulation(energyplus_exe: str, args: List[str]) -> subprocess.CompletedProcess:
    """
    Secure subprocess execution:
    1. Validate executable path
    2. Sanitize command arguments
    3. Set execution timeouts
    4. Capture and log all output
    """
```

## Scalability Architecture

### Horizontal Scaling Considerations

```python
class ProcessingManager:
    """
    Designed for future scaling:
    - Stateless processing (no global state)
    - Configurable output paths
    - Cancellation support
    - Progress tracking
    - Resource cleanup
    """
```

### Performance Optimization Points

1. **Parser Parallelization**: Independent parsers can run concurrently
2. **Report Generation Batching**: Generate reports in parallel threads
3. **Cache Optimization**: Precompute frequently accessed data
4. **Memory Streaming**: Process large files without full memory load

## Future Architecture Evolution

### Planned Architectural Improvements

1. **Microservices Decomposition**:

   ```
   IDF Processing Service ←→ Report Generation Service
           ↓                           ↓
   EnergyPlus Service     ←→     PDF Generation Service
   ```

2. **API Layer Addition**:

   ```python
   @app.route('/api/process-idf', methods=['POST'])
   def process_idf_api():
       # RESTful API for processing
       pass
   ```

3. **Database Integration**:

   ```python
   class ProjectDatabase:
       """Store processing history and cached results"""
       def save_project(self, project_data: Dict) -> str:
           pass

       def load_project(self, project_id: str) -> Dict:
           pass
   ```

4. **Plugin Architecture**:
   ```python
   class PluginManager:
       """Support for custom parsers and generators"""
       def register_parser(self, parser_class: Type[BaseParser]):
           pass

       def register_generator(self, generator_func: Callable):
           pass
   ```

## Testing Architecture

### Test Layer Organization

```
Unit Tests
├── Parser Tests (isolated data processing)
├── Generator Tests (PDF output validation)
├── DataLoader Tests (caching and retrieval)
└── Utility Tests (Hebrew text, helpers)

Integration Tests
├── End-to-End Workflow Tests
├── EnergyPlus Integration Tests
├── File I/O Tests
└── Error Handling Tests

Performance Tests
├── Memory Usage Tests
├── Large File Processing Tests
├── Concurrent Processing Tests
└── Report Generation Speed Tests
```

### Test Data Management

```python
class TestDataManager:
    """
    Manages test IDF files and expected outputs:
    - Sample IDF files of varying complexity
    - Expected parser outputs
    - Reference PDF reports
    - Hebrew text test cases
    """
```

## Deployment Architecture

### Build Pipeline

```
Source Code → Linting/Testing → PyInstaller → Distribution Package
    ↓              ↓                ↓               ↓
Type Checking → Unit Tests → Executable → Installer Creation
```

### Distribution Strategy

```python
# PyInstaller configuration
spec = {
    'pathex': [],
    'binaries': [],
    'datas': [('data', 'data')],  # Include weather files
    'hiddenimports': ['eppy', 'reportlab', 'customtkinter'],
    'hookspath': [],
    'runtime_hooks': [],
    'excludes': [],
    'win_no_prefer_redirects': False,
    'win_private_assemblies': False,
    'cipher': None,
    'noarchive': False
}
```

---

_This architecture documentation provides the technical foundation for understanding, maintaining, and extending the IDF Report Generator system._
