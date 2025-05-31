# IDF Report Generator - Deployment Guide

## Overview

This guide covers deployment strategies for the IDF Report Generator, from development setup to production distribution.

## Environment Setup

### Development Environment

#### Prerequisites

- **Python 3.8+** (tested with 3.9, 3.10, 3.11)
- **EnergyPlus 9.4.0+** (required for simulation)
- **Git** for version control
- **Visual Studio Code** (recommended IDE)

#### Step-by-Step Setup

1. **Clone Repository**

```bash
git clone <repository-url>
cd idf-reader
```

2. **Create Virtual Environment**

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/macOS
python3 -m venv venv
source venv/bin/activate
```

3. **Install Dependencies**

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

4. **Install EnergyPlus**

   - Download from: https://energyplus.net/downloads
   - **Windows**: Install to `C:\EnergyPlusV9-4-0\` (recommended)
   - **Linux**: Install to `/usr/local/EnergyPlus-9-4-0/`
   - **macOS**: Install via installer or Homebrew

5. **Verify Installation**

```bash
# Test CLI mode
python main.py tests/3.1.idf --idd "C:\EnergyPlusV9-4-0\Energy+.idd" -o test_output

# Test GUI mode
python main.py
```

#### IDE Configuration (VS Code)

**.vscode/settings.json**:

```json
{
  "python.defaultInterpreterPath": "./venv/Scripts/python.exe",
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": true,
  "python.formatting.provider": "black",
  "python.testing.pytestEnabled": true,
  "files.associations": {
    "*.idf": "plaintext",
    "*.epw": "plaintext"
  }
}
```

**.vscode/launch.json**:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Debug GUI",
      "type": "python",
      "request": "launch",
      "program": "main.py",
      "console": "integratedTerminal",
      "cwd": "${workspaceFolder}"
    },
    {
      "name": "Debug CLI",
      "type": "python",
      "request": "launch",
      "program": "main.py",
      "args": [
        "tests/3.1.idf",
        "--idd",
        "C:\\EnergyPlusV9-4-0\\Energy+.idd",
        "-o",
        "debug_output"
      ],
      "console": "integratedTerminal",
      "cwd": "${workspaceFolder}"
    }
  ]
}
```

### Production Environment

#### System Requirements

**Minimum Requirements**:

- **OS**: Windows 10+, Ubuntu 18.04+, macOS 10.15+
- **RAM**: 4GB (8GB recommended for large files)
- **Storage**: 2GB free space
- **CPU**: Multi-core recommended for parallel processing

**Recommended Requirements**:

- **RAM**: 8GB+ for large commercial buildings
- **Storage**: 10GB+ for extensive report archives
- **CPU**: 4+ cores for optimal performance

#### Platform-Specific Setup

##### Windows Production Setup

```bash
# Install Python 3.9+ from python.org
# Install EnergyPlus to C:\EnergyPlusV9-4-0\
# Clone repository to C:\idf-reader\
cd C:\idf-reader
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

##### Linux Production Setup

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3.9 python3.9-venv python3-pip
wget https://github.com/NREL/EnergyPlus/releases/download/v9.4.0/EnergyPlus-9.4.0-998c4b761e-Linux-Ubuntu18.04-x86_64.sh
sudo bash EnergyPlus-9.4.0-998c4b761e-Linux-Ubuntu18.04-x86_64.sh

# Setup application
git clone <repository-url> /opt/idf-reader
cd /opt/idf-reader
python3.9 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

##### macOS Production Setup

```bash
# Install via Homebrew
brew install python@3.9
brew install --cask energyplus

# Setup application
git clone <repository-url> ~/idf-reader
cd ~/idf-reader
python3.9 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Build Process

### Development Builds

#### Quick Development Build

```bash
# Activate virtual environment
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/macOS

# Run directly from source
python main.py
```

#### Testing Build

```bash
# Run comprehensive tests
python -m pytest tests/ -v
python main.py tests/3.1.idf --idd "<energyplus-path>/Energy+.idd" -o test_output

# Test Hebrew text handling
python -c "
from gui import fix_hebrew_text_display
test_cases = ['תל אביב - יפו', 'ירושלים', 'אכסאל']
for case in test_cases:
    print(f'{case} -> {fix_hebrew_text_display(case)}')
"
```

### Production Builds

#### Using build.py Script

```bash
# Activate environment
venv\Scripts\activate

# Build executable
python build.py

# Output: dist/IDF-Processor.exe (Windows)
#         dist/IDF-Processor (Linux/macOS)
```

#### Manual PyInstaller Build

```bash
pyinstaller --onefile \
    --windowed \
    --name "IDF-Processor" \
    --icon "icon.ico" \
    --add-data "data;data" \
    --hidden-import "eppy" \
    --hidden-import "reportlab" \
    --hidden-import "customtkinter" \
    main.py
```

#### Build Configuration (IDF-Processor.spec)

```python
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('data', 'data'),  # Include weather files and city data
        ('README.md', '.'),
        ('CONTRIBUTING.md', '.'),
        ('ARCHITECTURE.md', '.')
    ],
    hiddenimports=[
        'eppy',
        'reportlab',
        'customtkinter',
        'pandas',
        'numpy',
        'openpyxl',
        'colorama',
        'tabulate'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='IDF-Processor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Set to True for CLI debugging
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico'  # Add application icon
)
```

### Build Optimization

#### Size Optimization

```bash
# Exclude unnecessary modules
pyinstaller --exclude-module matplotlib \
    --exclude-module scipy \
    --exclude-module jupyter \
    --onefile main.py
```

#### Performance Optimization

```bash
# Use UPX compression
pyinstaller --upx-dir /path/to/upx \
    --onefile main.py

# Optimize for speed
pyinstaller --optimize 2 \
    --onefile main.py
```

## Package Distribution

### Creating Distribution Package

#### Windows Distribution

```bash
# Run package.py script
python package.py

# Creates:
# - IDF-Processor-v1.0.0-Windows.zip
#   ├── IDF-Processor.exe
#   ├── README.md
#   ├── INSTALLATION.md
#   ├── data/
#   └── examples/
```

#### Linux Distribution

```bash
# Create .deb package (Ubuntu/Debian)
mkdir -p idf-processor-1.0.0/DEBIAN
mkdir -p idf-processor-1.0.0/opt/idf-processor
mkdir -p idf-processor-1.0.0/usr/local/bin

# Copy files
cp -r dist/IDF-Processor idf-processor-1.0.0/opt/idf-processor/
cp -r data idf-processor-1.0.0/opt/idf-processor/
cp README.md idf-processor-1.0.0/opt/idf-processor/

# Create control file
cat > idf-processor-1.0.0/DEBIAN/control << EOF
Package: idf-processor
Version: 1.0.0
Section: science
Priority: optional
Architecture: amd64
Depends: python3 (>= 3.8)
Maintainer: IDF Processor Team <team@example.com>
Description: EnergyPlus IDF Report Generator
 Processes EnergyPlus IDF files and generates comprehensive PDF reports
 with Hebrew language support for Israeli building energy compliance.
EOF

# Build package
dpkg-deb --build idf-processor-1.0.0
```

#### macOS Distribution

```bash
# Create .app bundle
mkdir -p "IDF Processor.app/Contents/MacOS"
mkdir -p "IDF Processor.app/Contents/Resources"

# Copy executable
cp dist/IDF-Processor "IDF Processor.app/Contents/MacOS/"

# Create Info.plist
cat > "IDF Processor.app/Contents/Info.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>IDF-Processor</string>
    <key>CFBundleIdentifier</key>
    <string>com.idfprocessor.app</string>
    <key>CFBundleName</key>
    <string>IDF Processor</string>
    <key>CFBundleVersion</key>
    <string>1.0.0</string>
</dict>
</plist>
EOF

# Create DMG
hdiutil create -srcfolder "IDF Processor.app" "IDF-Processor-v1.0.0.dmg"
```

### Distribution Checklist

- [ ] **Executable runs without Python installation**
- [ ] **All data files included (weather files, city data)**
- [ ] **Hebrew text displays correctly**
- [ ] **EnergyPlus integration works**
- [ ] **All report types generate successfully**
- [ ] **Documentation included**
- [ ] **Example IDF files provided**
- [ ] **Installation instructions clear**

## Deployment Strategies

### Standalone Deployment

#### Single Executable Deployment

```bash
# Advantages:
# - No installation required
# - Self-contained
# - Easy distribution

# Disadvantages:
# - Large file size (50-100MB)
# - Slower startup
# - No automatic updates

# Best for:
# - Individual users
# - Offline environments
# - Portable installations
```

#### Installer-Based Deployment

```bash
# Windows: Use NSIS or Inno Setup
# - Professional installation experience
# - Registry integration
# - Uninstaller creation
# - Start menu shortcuts

# Create installer script (NSIS example)
!define APPNAME "IDF Processor"
!define COMPANYNAME "IDF Processor Team"
!define DESCRIPTION "EnergyPlus IDF Report Generator"
!define VERSIONMAJOR 1
!define VERSIONMINOR 0
!define VERSIONBUILD 0

OutFile "IDF-Processor-Setup.exe"
InstallDir "$PROGRAMFILES\${APPNAME}"

Section "Install"
    SetOutPath $INSTDIR
    File "dist\IDF-Processor.exe"
    File /r "data"
    File "README.md"

    CreateDirectory "$SMPROGRAMS\${APPNAME}"
    CreateShortCut "$SMPROGRAMS\${APPNAME}\${APPNAME}.lnk" "$INSTDIR\IDF-Processor.exe"
    CreateShortCut "$DESKTOP\${APPNAME}.lnk" "$INSTDIR\IDF-Processor.exe"
SectionEnd
```

### Enterprise Deployment

#### Network Shared Deployment

```bash
# Copy to network share
\\server\software\IDF-Processor\
├── IDF-Processor.exe
├── data\
├── examples\
└── documentation\

# Create batch file for users
@echo off
set IDFPROCESSOR_PATH=\\server\software\IDF-Processor
%IDFPROCESSOR_PATH%\IDF-Processor.exe
```

#### Centralized Management

```bash
# Group Policy deployment (Windows)
# - Deploy via software distribution
# - Centralized configuration
# - Automatic updates

# Configuration management
# - Ansible playbooks
# - Puppet manifests
# - Chef cookbooks
```

### Cloud Deployment

#### Web Service Deployment

```python
# Future: Flask/FastAPI web service
from flask import Flask, request, send_file
from processing_manager import ProcessingManager

app = Flask(__name__)

@app.route('/api/process-idf', methods=['POST'])
def process_idf_api():
    # Handle file upload
    # Process IDF file
    # Return generated reports
    pass

@app.route('/api/status/<job_id>')
def get_status(job_id):
    # Return processing status
    pass
```

#### Container Deployment

```dockerfile
# Dockerfile for containerized deployment
FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install EnergyPlus
RUN wget https://github.com/NREL/EnergyPlus/releases/download/v9.4.0/EnergyPlus-9.4.0-998c4b761e-Linux-Ubuntu18.04-x86_64.sh \
    && bash EnergyPlus-9.4.0-998c4b761e-Linux-Ubuntu18.04-x86_64.sh --skip-license \
    && rm EnergyPlus-9.4.0-998c4b761e-Linux-Ubuntu18.04-x86_64.sh

# Copy application
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Set environment variables
ENV ENERGYPLUS_DIR=/usr/local/EnergyPlus-9-4-0

EXPOSE 5000
CMD ["python", "app.py"]
```

## Configuration Management

### Environment Configuration

#### Development Configuration

```python
# config/development.py
class DevelopmentConfig:
    DEBUG = True
    ENERGYPLUS_PATH = "C:/EnergyPlusV9-4-0/energyplus.exe"
    DATA_DIR = "./data"
    LOG_LEVEL = "DEBUG"
    ENABLE_PROFILING = True
```

#### Production Configuration

```python
# config/production.py
class ProductionConfig:
    DEBUG = False
    ENERGYPLUS_PATH = "/usr/local/EnergyPlus-9-4-0/energyplus"
    DATA_DIR = "/opt/idf-processor/data"
    LOG_LEVEL = "INFO"
    ENABLE_PROFILING = False
```

#### Configuration Loading

```python
import os
from typing import Dict, Any

def load_config() -> Dict[str, Any]:
    """Load configuration based on environment."""
    env = os.getenv('IDF_PROCESSOR_ENV', 'development')

    if env == 'production':
        from config.production import ProductionConfig
        return ProductionConfig.__dict__
    else:
        from config.development import DevelopmentConfig
        return DevelopmentConfig.__dict__
```

### Settings Management

#### User Settings Storage

```python
# Cross-platform settings storage
import os
from pathlib import Path

def get_settings_path() -> Path:
    """Get platform-appropriate settings path."""
    if os.name == 'nt':  # Windows
        base = Path(os.getenv('APPDATA', ''))
    elif os.name == 'posix':  # Linux/macOS
        base = Path.home() / '.config'
    else:
        base = Path.home()

    return base / 'idf-processor' / 'settings.json'
```

#### Enterprise Settings

```python
# Enterprise configuration override
def load_enterprise_settings():
    """Load enterprise-wide settings."""
    enterprise_config_paths = [
        Path("\\\\server\\config\\idf-processor.json"),  # Windows
        Path("/etc/idf-processor/config.json"),          # Linux
        Path("/Library/Application Support/IDF-Processor/config.json")  # macOS
    ]

    for path in enterprise_config_paths:
        if path.exists():
            return json.loads(path.read_text())

    return {}
```

## Monitoring and Maintenance

### Logging Configuration

#### Production Logging

```python
import logging
import logging.handlers
from pathlib import Path

def setup_production_logging():
    """Configure logging for production deployment."""
    log_dir = Path("/var/log/idf-processor")  # Linux
    # log_dir = Path(os.getenv('APPDATA')) / "IDF-Processor" / "logs"  # Windows

    log_dir.mkdir(parents=True, exist_ok=True)

    # Main application log
    app_handler = logging.handlers.RotatingFileHandler(
        log_dir / "app.log",
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )

    # Error log
    error_handler = logging.handlers.RotatingFileHandler(
        log_dir / "error.log",
        maxBytes=10*1024*1024,
        backupCount=5
    )
    error_handler.setLevel(logging.ERROR)

    # Configure formatters
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    app_handler.setFormatter(formatter)
    error_handler.setFormatter(formatter)

    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(app_handler)
    logger.addHandler(error_handler)
```

#### Performance Monitoring

```python
import time
import psutil
from functools import wraps

def monitor_performance(func):
    """Decorator to monitor function performance."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        start_memory = psutil.Process().memory_info().rss

        try:
            result = func(*args, **kwargs)
            success = True
        except Exception as e:
            result = None
            success = False
            raise
        finally:
            end_time = time.time()
            end_memory = psutil.Process().memory_info().rss

            logging.info(f"Performance: {func.__name__}")
            logging.info(f"  Duration: {end_time - start_time:.2f}s")
            logging.info(f"  Memory delta: {(end_memory - start_memory) / 1024 / 1024:.2f}MB")
            logging.info(f"  Success: {success}")

        return result
    return wrapper
```

### Health Checks

#### Application Health Check

```python
def health_check() -> Dict[str, Any]:
    """Perform application health check."""
    health = {
        "status": "healthy",
        "timestamp": time.time(),
        "checks": {}
    }

    # Check EnergyPlus availability
    try:
        eplus_path = get_energyplus_path()
        health["checks"]["energyplus"] = {
            "status": "ok" if os.path.exists(eplus_path) else "error",
            "path": eplus_path
        }
    except Exception as e:
        health["checks"]["energyplus"] = {"status": "error", "error": str(e)}

    # Check data files
    try:
        data_dir = Path("data")
        required_files = ["countries-selection.csv", "2017_model.csv", "a.epw"]
        missing_files = [f for f in required_files if not (data_dir / f).exists()]

        health["checks"]["data_files"] = {
            "status": "ok" if not missing_files else "error",
            "missing_files": missing_files
        }
    except Exception as e:
        health["checks"]["data_files"] = {"status": "error", "error": str(e)}

    # Overall status
    if any(check["status"] == "error" for check in health["checks"].values()):
        health["status"] = "unhealthy"

    return health
```

### Update Management

#### Version Management

```python
__version__ = "1.0.0"

def get_version_info():
    """Get detailed version information."""
    return {
        "version": __version__,
        "build_date": "2024-01-01",
        "python_version": sys.version,
        "platform": platform.platform(),
        "dependencies": {
            "reportlab": reportlab.__version__,
            "eppy": eppy.__version__,
            # ... other dependencies
        }
    }
```

#### Automatic Updates (Future)

```python
def check_for_updates():
    """Check for application updates."""
    try:
        response = requests.get("https://api.idfprocessor.com/version")
        latest_version = response.json()["version"]

        if version.parse(latest_version) > version.parse(__version__):
            return {
                "update_available": True,
                "latest_version": latest_version,
                "download_url": response.json()["download_url"]
            }
    except Exception as e:
        logging.error(f"Failed to check for updates: {e}")

    return {"update_available": False}
```

## Troubleshooting Deployment Issues

### Common Issues and Solutions

#### EnergyPlus Integration Problems

```bash
# Issue: EnergyPlus not found
# Solution: Verify installation path
python -c "
import os
paths = [
    'C:/EnergyPlusV9-4-0/energyplus.exe',
    '/usr/local/EnergyPlus-9-4-0/energyplus',
    '/Applications/EnergyPlus-9-4-0/energyplus'
]
for path in paths:
    if os.path.exists(path):
        print(f'Found: {path}')
    else:
        print(f'Not found: {path}')
"
```

#### Hebrew Text Issues

```bash
# Issue: Hebrew text displays incorrectly
# Solution: Test Hebrew text processing
python -c "
from gui import fix_hebrew_text_display
test_text = 'תל אביב - יפו'
print(f'Original: {test_text}')
print(f'Fixed: {fix_hebrew_text_display(test_text)}')
print(f'Encoding: {test_text.encode()}')
"
```

#### Memory Issues

```bash
# Issue: Out of memory with large files
# Solution: Monitor memory usage
python -c "
import psutil
process = psutil.Process()
print(f'Memory usage: {process.memory_info().rss / 1024 / 1024:.2f} MB')
print(f'Available memory: {psutil.virtual_memory().available / 1024 / 1024:.2f} MB')
"
```

#### Permission Issues

```bash
# Issue: Cannot write to output directory
# Solution: Check permissions
python -c "
import os, tempfile
test_dir = 'test_output'
try:
    os.makedirs(test_dir, exist_ok=True)
    with open(os.path.join(test_dir, 'test.txt'), 'w') as f:
        f.write('test')
    print('Write permissions: OK')
    os.remove(os.path.join(test_dir, 'test.txt'))
    os.rmdir(test_dir)
except Exception as e:
    print(f'Write permissions: ERROR - {e}')
"
```

---

_This deployment guide ensures successful installation and operation of the IDF Report Generator across different environments and use cases._
