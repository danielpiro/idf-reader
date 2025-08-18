# Migration from Eppy to EPJSON

## Overview

This document outlines the comprehensive migration strategy from the `eppy` library to the native EPJSON format for EnergyPlus file handling. This migration will modernize our codebase, improve performance, and align with EnergyPlus future directions.

## Why Migrate to EPJSON?

### Advantages of EPJSON Format

1. **Native Python Integration**: EPJSON structure is similar to Python dictionaries, allowing manipulation using only standard libraries
2. **Better Performance**: More computationally efficient as it doesn't require parsing the IDD file
3. **Simpler Code**: Scripts are shorter and simpler compared to IDF-based approaches
4. **Future-Proof**: EnergyPlus is moving towards deprecating IDF in favor of EPJSON
5. **No Third-Party Dependencies**: Uses only Python's built-in `json` library

### Current Issues with Eppy

1. **Dependency on External Library**: Requires eppy package maintenance
2. **IDD File Requirement**: Needs IDD file for parsing
3. **Performance Overhead**: Slower parsing and manipulation
4. **Compatibility Issues**: Potential version conflicts with EnergyPlus updates

## Migration Strategy

### Phase 1: Prerequisites and Planning

1. **IDF Version Checking and Updating**
   - Implement version detection for IDF files
   - Create wrapper for IDFVersionUpdater.exe
   - Ensure all IDF files are upgraded to version 24.1.0 or higher

2. **Dependency Analysis**
   - Search entire codebase for eppy usage
   - Identify all files that import or use eppy
   - Map dependencies and usage patterns

### Phase 2: Implementation

1. **Create EPJSON Handler**
   - Replace `eppy_handler.py` with `epjson_handler.py`
   - Implement native JSON-based file operations
   - Add conversion utilities (IDF ↔ EPJSON)

2. **Update DataLoader**
   - Modify `data_loader.py` to use EPJSON
   - Replace eppy-specific code with JSON operations
   - Maintain backward compatibility during transition

3. **Version Management**
   - Implement automatic IDF version checking
   - Integrate IDFVersionUpdater automation
   - Handle file conversion pipeline

### Phase 3: Testing and Validation

1. **Comprehensive Testing**
   - Test with various IDF/EPJSON files
   - Validate data integrity after conversion
   - Performance benchmarking

2. **Cleanup**
   - Remove eppy dependencies
   - Clean up unused imports
   - Update documentation

## Technical Implementation Details

### IDF Version Detection

```python
def get_idf_version(idf_path: str) -> str:
    """Extract version from IDF file header."""
    with open(idf_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip().startswith('Version,'):
                # Extract version number
                version = line.split(',')[1].strip().rstrip(';')
                return version
    return None
```

### IDFVersionUpdater Integration

```python
def update_idf_version(idf_path: str, energyplus_path: str, target_version: str = "24.1.0") -> str:
    """Update IDF file to target version using IDFVersionUpdater."""
    updater_path = os.path.join(energyplus_path, "PreProcess", "IDFVersionUpdater")
    # Implementation details for version updating
```

### EPJSON Handler

```python
class EPJSONHandler:
    """Handle EPJSON files using native Python JSON operations."""
    
    def __init__(self, energyplus_path: str = None):
        self.energyplus_path = energyplus_path
    
    def load_epjson(self, file_path: str) -> dict:
        """Load EPJSON file into Python dictionary."""
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def save_epjson(self, data: dict, file_path: str) -> None:
        """Save Python dictionary as EPJSON file."""
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    
    def convert_idf_to_epjson(self, idf_path: str) -> str:
        """Convert IDF file to EPJSON using EnergyPlus converter."""
        # Use EnergyPlus command line: energyplus --convert-only filename
```

### Data Access Patterns

#### Current Eppy Pattern:
```python
# Old eppy way
for zone in self._idf.idfobjects['ZONE']:
    zone_id = str(zone.Name)
    floor_area = safe_float(getattr(zone, "Floor_Area", 0.0))
```

#### New EPJSON Pattern:
```python
# New EPJSON way
zones = self._epjson_data.get('Zone', {})
for zone_id, zone_data in zones.items():
    floor_area = safe_float(zone_data.get('floor_area', 0.0))
```

## File Structure Changes

### Files to Modify:
- `utils/data_loader.py` - Replace eppy with EPJSON
- `utils/eppy_handler.py` - Replace with `utils/epjson_handler.py`
- All files importing from eppy_handler

### Files to Create:
- `utils/epjson_handler.py` - New EPJSON handler
- `utils/idf_version_updater.py` - Version checking and updating
- `utils/file_converter.py` - IDF ↔ EPJSON conversion utilities

### Files to Remove:
- `utils/eppy_handler.py` (after migration complete)

## Dependencies Update

### Remove:
```
eppy>=0.5.x
```

### Add (if needed):
```
# No additional dependencies required - using built-in json library
```

## Migration Checklist

### Pre-Migration:
- [ ] Research EPJSON format thoroughly
- [ ] Identify all eppy usage in codebase
- [ ] Create backup of current codebase
- [ ] Plan testing strategy

### During Migration:
- [ ] Implement IDF version checker
- [ ] Create IDFVersionUpdater wrapper
- [ ] Implement EPJSON handler
- [ ] Update DataLoader to use EPJSON
- [ ] Update all imports and references
- [ ] Test with sample files

### Post-Migration:
- [ ] Remove eppy dependencies
- [ ] Clean up unused code
- [ ] Update documentation
- [ ] Performance testing
- [ ] Integration testing

## Benefits After Migration

1. **Reduced Dependencies**: No external libraries needed for file parsing
2. **Better Performance**: Faster file loading and manipulation
3. **Simpler Code**: More readable and maintainable code
4. **Future Compatibility**: Aligned with EnergyPlus roadmap
5. **Enhanced Debugging**: JSON structure easier to inspect and debug

## Potential Challenges

1. **IDF Comments Loss**: Converting IDF to EPJSON loses comments
2. **Field Ordering**: Object ordering may change during conversion
3. **Version Compatibility**: Need to ensure all files are updated to compatible versions
4. **Testing Coverage**: Need comprehensive testing of all file operations

## Timeline

- **Week 1**: Analysis and planning
- **Week 2**: IDF version checking and updating implementation
- **Week 3**: EPJSON handler development
- **Week 4**: DataLoader migration
- **Week 5**: Testing and validation
- **Week 6**: Cleanup and documentation

## Success Criteria

1. All IDF files can be automatically updated to version 24.1.0+
2. All data operations work identically with EPJSON format
3. Performance improvement measurable
4. No eppy dependencies remain in codebase
5. Comprehensive test coverage maintained