# Contributing to IDF Report Generator

## Development Setup

### Quick Start

1. **Fork and clone the repository**

```bash
git clone https://github.com/your-fork/idf-reader.git
cd idf-reader
```

2. **Set up development environment**

```bash
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

3. **Install EnergyPlus**

- Download EnergyPlus 9.4.0+ from https://energyplus.net/
- Note installation path for testing

4. **Run tests**

```bash
python main.py tests/3.1.idf --idd "C:\EnergyPlusV9-4-0\Energy+.idd" -o test_output
```

## Code Standards

### Python Style Guide

- **PEP 8 compliance** for all Python code
- **Type hints** for function parameters and return values
- **Docstrings** for all public classes and methods
- **Meaningful variable names** (avoid abbreviations)

### Example Code Style

```python
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)

class ExampleParser:
    """
    Parses example data from IDF files.

    Args:
        data_loader: DataLoader instance for accessing cached IDF data
        simulation_csv: Optional path to simulation output CSV
    """

    def __init__(self, data_loader: 'DataLoader', simulation_csv: Optional[str] = None):
        self.data_loader = data_loader
        self.simulation_csv = simulation_csv
        self._parsed_data: Dict[str, Any] = {}

    def parse(self) -> Dict[str, Any]:
        """
        Extract and process data from the IDF.

        Returns:
            Dictionary containing parsed data structures

        Raises:
            ValueError: If required data is missing from IDF
        """
        try:
            # Implementation here
            logger.info("Successfully parsed example data")
            return self._parsed_data
        except Exception as e:
            logger.error(f"Failed to parse example data: {e}", exc_info=True)
            raise
```

### File Organization

```python
# Standard library imports
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Third-party imports
import pandas as pd
from reportlab.lib.pagesizes import letter

# Local imports
from utils.data_loader import DataLoader
from utils.hebrew_text_utils import fix_hebrew_text
```

## Architecture Patterns

### Parser Pattern

All parsers should follow this consistent interface:

```python
class BaseParser:
    def __init__(self, data_loader: 'DataLoader', **kwargs):
        self.data_loader = data_loader

    def parse(self) -> Dict[str, Any]:
        """Main parsing method - returns structured data"""
        raise NotImplementedError

    def _validate_data(self, data: Any) -> bool:
        """Validate parsed data integrity"""
        return True
```

### Generator Pattern

Report generators should follow this pattern:

```python
def generate_report_pdf(data: Dict[str, Any],
                       output_path: str,
                       project_name: str,
                       run_id: str,
                       city_name: str = "N/A",
                       area_name: str = "N/A",
                       **kwargs) -> bool:
    """
    Generate PDF report from parsed data.

    Args:
        data: Structured data from parser
        output_path: Full path for output PDF file
        project_name: Name of the project/building
        run_id: Unique identifier for this run
        city_name: Hebrew city name
        area_name: Climate zone designation (א,ב,ג,ד)

    Returns:
        True if report generated successfully, False otherwise
    """
    try:
        # Report generation logic
        return True
    except Exception as e:
        logger.error(f"Failed to generate report: {e}", exc_info=True)
        return False
```

## Adding New Features

### 1. Adding a New Parser

Create `parsers/new_feature_parser.py`:

```python
from typing import Dict, Any
from utils.data_loader import DataLoader

class NewFeatureParser:
    """Parser for extracting new feature data from IDF files."""

    def __init__(self, data_loader: DataLoader):
        self.data_loader = data_loader
        self._cache = {}

    def parse(self) -> Dict[str, Any]:
        """Parse new feature data from IDF."""
        # Get relevant IDF objects
        idf_objects = self.data_loader.get_idf().idfobjects.get('OBJECT_TYPE', [])

        parsed_data = {}
        for obj in idf_objects:
            # Extract and process data
            obj_id = str(obj.Name)
            parsed_data[obj_id] = {
                'name': obj_id,
                'property1': self._safe_float(obj.Property1),
                'property2': str(obj.Property2),
                # Add more properties as needed
            }

        return parsed_data

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        """Safely convert value to float."""
        try:
            return float(value) if value else default
        except (ValueError, TypeError):
            return default
```

### 2. Adding a New Report Generator

Create `generators/new_feature_generator.py`:

```python
from typing import Dict, Any
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table
from reportlab.lib.styles import getSampleStyleSheet
import logging

logger = logging.getLogger(__name__)

def generate_new_feature_report_pdf(data: Dict[str, Any],
                                   output_path: str,
                                   project_name: str,
                                   run_id: str,
                                   city_name: str = "N/A",
                                   area_name: str = "N/A",
                                   **kwargs) -> bool:
    """Generate PDF report for new feature analysis."""

    try:
        # Create PDF document
        doc = SimpleDocTemplate(output_path, pagesize=A4)
        story = []
        styles = getSampleStyleSheet()

        # Add title
        title = f"New Feature Analysis Report - {project_name}"
        story.append(Paragraph(title, styles['Title']))

        # Add metadata
        metadata_text = f"""
        Project: {project_name}<br/>
        City: {city_name}<br/>
        Climate Zone: {area_name}<br/>
        """
        story.append(Paragraph(metadata_text, styles['Normal']))

        # Process data and create tables/charts
        if data:
            table_data = [['Item', 'Property 1', 'Property 2']]
            for item_id, item_data in data.items():
                table_data.append([
                    item_id,
                    str(item_data.get('property1', 'N/A')),
                    str(item_data.get('property2', 'N/A'))
                ])

            table = Table(table_data)
            story.append(table)

        # Build PDF
        doc.build(story)
        logger.info(f"New feature report generated: {output_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to generate new feature report: {e}", exc_info=True)
        return False
```

### 3. Integration with ProcessingManager

Update [`processing_manager.py`](processing_manager.py):

```python
# In _initialize_parsers method
from parsers.new_feature_parser import NewFeatureParser

parsers["new_feature"] = NewFeatureParser(data_loader)

# In _extract_data_from_parsers method
"new_feature": parsers["new_feature"].parse(),

# In _generate_all_reports method
from generators.new_feature_generator import generate_new_feature_report_pdf

self._generate_report_item(
    "New Feature",
    generate_new_feature_report_pdf,
    extracted_data["new_feature"],
    report_paths["new_feature"],
    project_name,
    run_id,
    city_name_hebrew,
    area_name_hebrew
)
```

## Hebrew Language Support

### Text Processing Guidelines

```python
from utils.hebrew_text_utils import fix_hebrew_text_display

def handle_hebrew_text(text: str) -> str:
    """Process Hebrew text for display/PDF generation."""
    if not text:
        return ""

    # Fix display issues
    display_text = fix_hebrew_text_display(text)

    # Additional processing for PDFs
    # Ensure proper encoding
    return display_text
```

### Font Handling in PDFs

```python
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

def setup_hebrew_fonts():
    """Register Hebrew-compatible fonts for PDF generation."""
    try:
        # Register system fonts that support Hebrew
        pdfmetrics.registerFont(TTFont('Hebrew', 'arial.ttf'))
        return True
    except:
        # Fallback to default fonts
        return False
```

### Testing Hebrew Support

```python
def test_hebrew_display():
    """Test Hebrew text processing."""
    test_cases = [
        "תל אביב - יפו",  # Mixed Hebrew-punctuation
        "ירושלים",        # Pure Hebrew
        "אכסאל"           # Hebrew city name
    ]

    for case in test_cases:
        processed = fix_hebrew_text_display(case)
        print(f"Original: {case}")
        print(f"Processed: {processed}")
```

## Testing Guidelines

### Unit Testing

Create test files following this pattern:

```python
import unittest
from parsers.new_feature_parser import NewFeatureParser
from utils.data_loader import DataLoader

class TestNewFeatureParser(unittest.TestCase):

    def setUp(self):
        """Set up test environment."""
        self.data_loader = DataLoader()
        self.data_loader.load_file('tests/3.1.idf')
        self.parser = NewFeatureParser(self.data_loader)

    def test_parse_returns_dict(self):
        """Test that parse method returns a dictionary."""
        result = self.parser.parse()
        self.assertIsInstance(result, dict)

    def test_parse_with_empty_idf(self):
        """Test parsing behavior with empty IDF."""
        # Test edge cases
        pass

if __name__ == '__main__':
    unittest.main()
```

### Integration Testing

```python
def test_full_workflow():
    """Test complete processing workflow."""
    # Test CLI mode
    result = subprocess.run([
        'python', 'main.py',
        'tests/3.1.idf',
        '--idd', 'C:/EnergyPlusV9-4-0/Energy+.idd',
        '-o', 'test_output'
    ], capture_output=True, text=True)

    assert result.returncode == 0
    assert os.path.exists('test_output/reports')
```

### Manual Testing Checklist

- [ ] GUI launches without errors
- [ ] File selection dialogs work
- [ ] Hebrew city names display correctly
- [ ] EnergyPlus simulation runs successfully
- [ ] All report types generate without errors
- [ ] PDF files open and display correctly
- [ ] Hebrew text renders properly in PDFs

## Error Handling

### Logging Standards

```python
import logging

logger = logging.getLogger(__name__)

def example_function():
    try:
        # Operation that might fail
        result = risky_operation()
        logger.info("Operation completed successfully")
        return result
    except SpecificException as e:
        logger.error(f"Specific error occurred: {e}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Unexpected error in example_function: {e}", exc_info=True)
        raise
```

### User-Friendly Error Messages

```python
def create_user_error_message(error: Exception) -> str:
    """Convert technical errors to user-friendly messages."""
    error_messages = {
        FileNotFoundError: "The specified file could not be found. Please check the file path.",
        PermissionError: "Permission denied. Please check file/folder permissions.",
        ValueError: "Invalid data format detected. Please verify your input file."
    }

    return error_messages.get(type(error), f"An unexpected error occurred: {str(error)}")
```

## Performance Guidelines

### Memory Management

```python
def process_large_idf():
    """Example of memory-efficient processing."""
    data_loader = DataLoader()
    try:
        data_loader.load_file(large_idf_path)

        # Process in chunks
        for zone_batch in chunked(data_loader.get_zones(), chunk_size=100):
            process_zone_batch(zone_batch)

    finally:
        # Clean up large objects
        del data_loader
        import gc
        gc.collect()
```

### Optimization Tips

1. **Cache frequently accessed data** in DataLoader
2. **Use generators** for large datasets
3. **Process reports incrementally** rather than all at once
4. **Clear unused variables** in long-running operations
5. **Use appropriate data structures** (sets for lookups, lists for ordered data)

## Documentation Standards

### Code Documentation

```python
def complex_function(param1: str, param2: Dict[str, Any],
                    optional_param: Optional[bool] = None) -> List[str]:
    """
    Brief description of what the function does.

    Longer description explaining the algorithm, use cases, or important
    implementation details.

    Args:
        param1: Description of the first parameter
        param2: Description of the second parameter with expected structure
        optional_param: Description of optional parameter and default behavior

    Returns:
        Description of return value and its structure

    Raises:
        ValueError: When param1 is empty or invalid
        KeyError: When required keys are missing from param2

    Example:
        >>> result = complex_function("example", {"key": "value"})
        >>> print(result)
        ['processed', 'data']
    """
    pass
```

### README Updates

When adding features, update:

- **Project Structure** section with new files
- **Usage** section with new options
- **API Reference** with new classes/methods
- **Architecture Overview** if patterns change

## Pull Request Process

### Before Submitting

1. **Run full test suite** with your changes
2. **Test Hebrew text handling** if applicable
3. **Update documentation** for any API changes
4. **Check code style** with linting tools
5. **Test with multiple IDF file types**

### PR Description Template

```markdown
## Description

Brief description of changes and motivation.

## Type of Change

- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Performance improvement
- [ ] Code refactoring

## Testing

- [ ] Tested with sample IDF files
- [ ] Hebrew text rendering verified
- [ ] All report types generate successfully
- [ ] No regressions in existing functionality

## Checklist

- [ ] Code follows project style guidelines
- [ ] Documentation updated
- [ ] Tests added/updated
- [ ] No breaking changes (or marked as such)
```

## Common Issues and Solutions

### EnergyPlus Integration Problems

```python
def debug_energyplus_issue():
    """Common debugging steps for EnergyPlus issues."""
    # 1. Check EnergyPlus installation
    eplus_path = "C:/EnergyPlusV9-4-0/energyplus.exe"
    if not os.path.exists(eplus_path):
        print(f"EnergyPlus not found at {eplus_path}")

    # 2. Verify IDF file validity
    # 3. Check EPW weather file exists
    # 4. Review simulation error logs
```

### Memory Issues with Large Files

```python
def handle_large_files():
    """Strategies for processing large IDF files."""
    # Use streaming parsers
    # Process zones in batches
    # Clear caches periodically
    # Monitor memory usage
```

## Release Process

### Version Management

- Follow semantic versioning (MAJOR.MINOR.PATCH)
- Update version in `__version__.py` or similar
- Tag releases in git
- Maintain CHANGELOG.md

### Build Process

```bash
# Create distribution
python build.py

# Test executable
./dist/IDF-Processor.exe tests/3.1.idf --idd "C:\EnergyPlusV9-4-0\Energy+.idd" -o test_output

# Package for distribution
python package.py
```

---

_Thank you for contributing to the IDF Report Generator! Your improvements help make building energy analysis more accessible and accurate._
