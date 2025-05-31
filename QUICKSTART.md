# IDF Report Generator - Quick Start Guide

## 🚀 Get Running in 5 Minutes

This guide gets you from zero to running the IDF Report Generator in just a few minutes.

## Prerequisites Check

Before starting, ensure you have:

- [ ] **Python 3.8+** installed
- [ ] **Git** for cloning the repository
- [ ] **EnergyPlus 9.4.0+** installed (or can install it)

## Step 1: Clone and Setup (2 minutes)

```bash
# Clone the repository
git clone <repository-url>
cd idf-reader

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Step 2: Install EnergyPlus (2 minutes)

### Windows

1. Download from: https://energyplus.net/downloads
2. Install to default location: `C:\EnergyPlusV9-4-0\`
3. Verify installation: Check that `C:\EnergyPlusV9-4-0\energyplus.exe` exists

### Linux (Ubuntu/Debian)

```bash
wget https://github.com/NREL/EnergyPlus/releases/download/v9.4.0/EnergyPlus-9.4.0-998c4b761e-Linux-Ubuntu18.04-x86_64.sh
sudo bash EnergyPlus-9.4.0-998c4b761e-Linux-Ubuntu18.04-x86_64.sh
```

### macOS

```bash
# Via Homebrew
brew install --cask energyplus

# Or download from website and install manually
```

## Step 3: Test the Installation (1 minute)

### Quick CLI Test

```bash
# Test with sample file
python main.py tests/3.1.idf --idd "C:\EnergyPlusV9-4-0\Energy+.idd" -o test_output

# You should see:
# ✅ Processing completed successfully
# 📁 Reports generated in: test_output/reports/
```

### Quick GUI Test

```bash
# Launch GUI
python main.py

# You should see:
# 🏗️ Modern GUI application opens
# 🎉 Welcome message in activity log
```

## Step 4: Try a Complete Workflow

### Using the GUI (Recommended for first time)

1. **Launch GUI**: `python main.py`

2. **Configure inputs**:

   - **IDF File**: Click "Browse" → Select `tests/3.1.idf`
   - **EnergyPlus Dir**: Click "Browse" → Select your EnergyPlus installation directory
   - **Output Dir**: Click "Browse" → Select/create an output folder
   - **City**: Type "תל" → Select "תל אביב - יפו" from dropdown
   - **ISO Type**: Select "RESIDNTIAL 2023"

3. **Generate Reports**: Click "🚀 Generate Reports"

4. **Watch Progress**: Monitor the activity log and progress bar

5. **View Results**: Reports will automatically open when complete

### Using the CLI

```bash
python main.py tests/3.1.idf \
  --idd "C:\EnergyPlusV9-4-0\Energy+.idd" \
  -o quick_test_output
```

## Expected Output

After successful processing, you should see:

```
quick_test_output/
├── reports/
│   ├── settings.pdf          # Building configuration
│   ├── schedules.pdf         # Operating schedules
│   ├── loads.pdf            # HVAC and internal loads
│   ├── materials.pdf        # Construction materials
│   ├── glazing.pdf          # Windows and glazing
│   ├── lighting.pdf         # Lighting analysis
│   ├── area-loss.pdf        # Thermal loss calculations
│   ├── energy-rating.pdf    # Energy compliance rating
│   └── zones/              # Individual zone reports
│       ├── zone_01_report.pdf
│       └── ...
└── simulation_run_YYYYMMDD_HHMMSS/  # EnergyPlus simulation files
    ├── eplustbl.csv
    └── ...
```

## Troubleshooting Common Issues

### ❌ "EnergyPlus not found"

**Solution**: Verify EnergyPlus installation path

```bash
# Check if EnergyPlus is installed
# Windows:
dir "C:\EnergyPlusV9-4-0\energyplus.exe"
# Linux/macOS:
ls /usr/local/EnergyPlus-9-4-0/energyplus
```

### ❌ "Module not found" errors

**Solution**: Ensure virtual environment is activated and dependencies installed

```bash
# Reactivate environment
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/macOS

# Reinstall dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### ❌ Hebrew text appears garbled

**Solution**: This is expected in CLI output. GUI handles Hebrew properly.

### ❌ "Permission denied" for output directory

**Solution**: Choose a different output directory or run as administrator

### ❌ Very slow processing

**Solution**: Normal for first run. Large buildings may take 5-15 minutes.

## Quick Development Setup

If you want to modify the code:

### 1. IDE Setup (VS Code recommended)

```bash
# Install VS Code extensions
code --install-extension ms-python.python
code --install-extension ms-python.pylint

# Open project
code .
```

### 2. Development Dependencies

```bash
# Install development tools
pip install black pylint pytest

# Format code
black .

# Run linter
pylint main.py

# Run tests
pytest tests/ -v
```

### 3. Make a Quick Change

Try modifying the welcome message in `gui.py`:

```python
# Line ~420 in gui.py
self.show_status("🎉 Welcome! Configure fields to begin.")
# Change to:
self.show_status("🎉 Hello Developer! Ready to analyze buildings?")
```

Run `python main.py` to see your change.

## Understanding the Project Structure

```
📁 idf-reader/
├── 🐍 main.py              # Entry point (CLI/GUI launcher)
├── 🖥️ gui.py               # Modern GUI interface
├── ⚙️ processing_manager.py # Core processing orchestrator
├── 📋 requirements.txt     # Python dependencies
├── ⚙️ settings.json        # User settings (auto-created)
│
├── 📁 utils/               # Core utilities
│   ├── data_loader.py      # IDF data caching
│   ├── eppy_handler.py     # EnergyPlus file handling
│   └── hebrew_text_utils.py # Hebrew text processing
│
├── 📁 parsers/             # Data extraction modules
│   ├── area_parser.py      # Zones and surfaces
│   ├── energy_rating_parser.py # Energy calculations
│   ├── materials_parser.py # Construction materials
│   └── ...                 # 8 specialized parsers
│
├── 📁 generators/          # PDF report creators
│   ├── area_report_generator.py
│   ├── energy_rating_report_generator.py
│   └── ...                 # 8 report generators
│
├── 📁 data/                # Configuration and weather files
│   ├── countries-selection.csv # City → climate zone mapping
│   ├── 2017_model.csv      # ISO 2017 energy standards
│   ├── *.epw               # Weather files (a.epw, 1.epw, etc.)
│   └── ...
│
└── 📁 tests/               # Sample IDF files for testing
    ├── 3.1.idf            # Main test file
    └── ...
```

## Key Concepts to Understand

### 1. **Data Flow**

```
IDF File → DataLoader → Parsers → ProcessingManager → Generators → PDF Reports
    ↓
EnergyPlus Simulation → CSV Output → Energy Rating Analysis
```

### 2. **Hebrew Language Support**

- Cities are stored in Hebrew: "תל אביב - יפו"
- Climate zones use Hebrew letters: א, ב, ג, ד
- GUI handles RTL text display automatically
- PDF reports render Hebrew text correctly

### 3. **Climate Zone Integration**

```python
# Climate zone mapping
"תל אביב - יפו" → Area "א" → Code "1" → Weather file "1.epw" (ISO 2023)
                                    → Weather file "a.epw" (other ISO types)
```

### 4. **Report Types**

- **Settings**: Building configuration and simulation parameters
- **Schedules**: Operating schedules (occupancy, equipment, lighting)
- **Loads**: HVAC loads, internal gains, ventilation
- **Materials**: Construction materials and thermal properties
- **Glazing**: Windows, glass properties, shading controls
- **Lighting**: Fixtures, controls, daylighting
- **Area Loss**: Thermal bridging and heat loss calculations
- **Energy Rating**: Compliance with Israeli energy standards

## Next Steps

### For Users

1. **Read the full README.md** for comprehensive usage instructions
2. **Try different ISO types** (RESIDENTIAL 2017/2023, HOTEL, OFFICE, etc.)
3. **Test with your own IDF files**
4. **Explore different Israeli cities** and climate zones

### For Developers

1. **Read ARCHITECTURE.md** to understand the system design
2. **Check CONTRIBUTING.md** for development guidelines
3. **Review API_REFERENCE.md** for detailed class documentation
4. **Try adding a custom parser** following the established patterns

### Example: Adding a Custom Feature

1. **Create a new parser** in `parsers/custom_parser.py`:

```python
class CustomParser:
    def __init__(self, data_loader):
        self.data_loader = data_loader

    def parse(self):
        # Your custom parsing logic
        return {"custom_data": "Hello World"}
```

2. **Create a report generator** in `generators/custom_generator.py`:

```python
def generate_custom_report_pdf(data, output_path, project_name, run_id, **kwargs):
    # Your custom PDF generation logic
    return True
```

3. **Integrate with ProcessingManager** (lines ~140, ~200, ~300):

```python
# Add parser initialization
parsers["custom"] = CustomParser(data_loader)

# Add data extraction
"custom": parsers["custom"].parse(),

# Add report generation
self._generate_report_item("Custom", generate_custom_report_pdf, ...)
```

## Resources and Documentation

- 📖 **README.md**: Complete project overview and usage guide
- 🏗️ **ARCHITECTURE.md**: Technical architecture and design patterns
- 🤝 **CONTRIBUTING.md**: Development guidelines and code standards
- 🚀 **DEPLOYMENT.md**: Building and deployment instructions
- 📚 **API_REFERENCE.md**: Detailed API documentation
- 🆘 **This file (QUICKSTART.md)**: Getting started quickly

## Getting Help

### Check These First

1. **Error messages** in the GUI activity log or CLI output
2. **Log files** (if configured for your environment)
3. **EnergyPlus installation** and version compatibility
4. **File permissions** for input/output directories

### Common Solutions

- **Restart** the application if GUI becomes unresponsive
- **Check Hebrew text encoding** if city names look wrong
- **Verify EPW weather files** exist in the `data/` directory
- **Try smaller IDF files** if experiencing memory issues

### Community and Support

- Review existing **Issues** and **Discussions** in the repository
- Check the **documentation files** for detailed explanations
- Test with the **sample files** in `tests/` directory

---

🎉 **Congratulations!** You now have the IDF Report Generator running and understand the basic workflow. Start exploring and building amazing energy analysis reports!
