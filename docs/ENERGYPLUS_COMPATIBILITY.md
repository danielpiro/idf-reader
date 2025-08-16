# EnergyPlus Version Compatibility Guide

## Current Issue: EnergyPlus 24.1 and eppy Compatibility

This application has encountered a known compatibility issue between the `eppy` Python library and EnergyPlus version 24.1. 

### The Problem

**Error**: `KeyError: 'field'` when trying to parse IDF files with eppy.

**Root Cause**: The EnergyPlus 24.1 IDD (Input Data Dictionary) file structure has changes that are incompatible with the current version of eppy. This is a recurring issue with newer EnergyPlus versions as the IDD format evolves.

### Recommended Solutions

#### Option 1: Use a Compatible EnergyPlus Version (Recommended)
Install an older, compatible version of EnergyPlus alongside 24.1:

1. **Download EnergyPlus 23.2** from the official EnergyPlus website
2. Install it in parallel with your existing 24.1 installation
3. The application will automatically detect and use the compatible version
4. Use EnergyPlus 24.1's IDFVersionUpdater to convert your files to 23.2 format

#### Option 2: Use EnergyPlus Native Tools
For EnergyPlus 24.1 files, bypass eppy entirely:

1. Use **EP-Launch** for file processing and analysis
2. Use **IDFEditor** for manual file editing
3. Use **EnergyPlus command-line tools** for automation
4. Export results to CSV/HTML for analysis in other tools

#### Option 3: File Conversion Workflow
Convert files to a compatible format:

1. Use **IDFVersionUpdater** to convert 24.1 files to 23.2 or older
2. Process with this application using the older format
3. Use transition tools to upgrade results if needed

### Technical Details

#### Why This Happens
- EnergyPlus updates the IDD file structure with each version
- The `eppy` library needs to parse the IDD to understand object definitions
- Changes in IDD field definitions cause parsing failures
- The "field" KeyError indicates missing or changed field structure in the IDD

#### Attempted Solutions
This application implements several compatibility strategies:

1. **Version Normalization**: Automatically converts IDF files using EnergyPlus transition tools
2. **EasyOpen**: Uses eppy's automatic version detection
3. **Graceful Fallbacks**: Multiple loading strategies with detailed error reporting

However, fundamental IDD incompatibility cannot be resolved at the application level.

### Current Status

**Working Versions**:
- EnergyPlus 23.2 and earlier
- EnergyPlus 22.x series
- EnergyPlus 9.x series

**Problematic Versions**:
- EnergyPlus 24.1 (current issue)
- Potentially newer versions (24.2, 25.x)

### Future Updates

This compatibility issue will be resolved when:
1. The `eppy` library is updated to support EnergyPlus 24.1+ IDD format
2. Alternative parsing libraries become available
3. EnergyPlus provides better backward compatibility

### Resources

- [EnergyPlus Downloads](https://energyplus.net/downloads)
- [eppy Documentation](https://eppy.readthedocs.io/)
- [EnergyPlus User Community](https://unmethours.com/)
- [GitHub Issues for eppy](https://github.com/santoshphilip/eppy/issues)

### Contact

If you need immediate processing of EnergyPlus 24.1 files, consider:
1. Using EnergyPlus native tools directly
2. Converting files to compatible versions
3. Waiting for eppy library updates

---
*Last updated: 2025-08-16*
*Application Version: 1.1.0*