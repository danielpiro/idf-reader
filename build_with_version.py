"""
Enhanced build script with automatic version management.
"""

import os
import sys
import shutil
import subprocess
import json
import time
from pathlib import Path
from datetime import datetime

def get_current_version():
    """Get current version from version.py."""
    try:
        with open("version.py", 'r', encoding='utf-8') as f:
            content = f.read()
            for line in content.split('\n'):
                if line.strip().startswith('__version__'):
                    # Extract version string
                    version = line.split('=')[1].strip().strip('"').strip("'")
                    return version
    except Exception as e:
        print(f"Error reading version: {e}")
        return "1.0.0"

def update_version(new_version):
    """Update version in version.py."""
    try:
        # Parse version to tuple
        version_tuple = tuple(map(int, new_version.split('.')))
        
        # Read current file
        with open("version.py", 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Replace version lines
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if line.strip().startswith('__version__'):
                lines[i] = f'__version__ = "{new_version}"'
            elif line.strip().startswith('__version_info__'):
                lines[i] = f'__version_info__ = {version_tuple}'
        
        # Write back
        with open("version.py", 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        
        print(f"Updated version to {new_version}")
        return True
        
    except Exception as e:
        print(f"Error updating version: {e}")
        return False

def increment_version(current_version, increment_type='patch'):
    """Increment version number."""
    try:
        major, minor, patch = map(int, current_version.split('.'))
        
        if increment_type == 'major':
            major += 1
            minor = 0
            patch = 0
        elif increment_type == 'minor':
            minor += 1
            patch = 0
        elif increment_type == 'patch':
            patch += 1
        
        return f"{major}.{minor}.{patch}"
    except Exception as e:
        print(f"Error incrementing version: {e}")
        return current_version

def create_build_info(version, build_type='release'):
    """Create build information file."""
    build_info = {
        "version": version,
        "build_type": build_type,
        "build_date": datetime.now().isoformat(),
        "build_timestamp": int(time.time()),
        "platform": sys.platform,
        "python_version": sys.version
    }
    
    with open("build_info.json", 'w', encoding='utf-8') as f:
        json.dump(build_info, f, indent=4, ensure_ascii=False)
    
    print(f"Created build_info.json for version {version}")

def run_pyinstaller(version):
    """Run PyInstaller to create executable."""
    print("Building executable with PyInstaller...")
    
    # PyInstaller command
    cmd = [
        'pyinstaller',
        '--onefile',
        '--windowed',
        '--name', f'idf-reader-{version}',
        '--icon=data/logo.ico',
        '--add-data', 'data;data',
        '--add-data', 'version.py;.',
        '--add-data', 'build_info.json;.',
        '--add-data', '.env;.',
        '--hidden-import', 'flet',
        '--hidden-import', 'reportlab',
        'main.py'
    ]
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("PyInstaller completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"PyInstaller failed: {e}")
        print(f"STDOUT: {e.stdout}")
        print(f"STDERR: {e.stderr}")
        return False

def create_release_package(version):
    """Create release package with version."""
    try:
        dist_dir = Path("dist")
        if not dist_dir.exists():
            print("No dist directory found")
            return False
        
        # Find the executable
        exe_files = list(dist_dir.glob(f"idf-reader-{version}.exe"))
        if not exe_files:
            print(f"No executable found for version {version}")
            return False
        
        exe_file = exe_files[0]
        
        # Create releases directory
        releases_dir = Path("releases")
        releases_dir.mkdir(exist_ok=True)
        
        # Copy executable to releases
        release_exe = releases_dir / f"idf-reader-{version}.exe"
        shutil.copy2(exe_file, release_exe)
        
        print(f"Created release package: {release_exe}")
        
        # Create release info
        release_info = {
            "version": version,
            "filename": release_exe.name,
            "size": release_exe.stat().st_size,
            "release_date": datetime.now().isoformat(),
            "changelog": [
                "שיפור ביצועים",
                "תיקון באגים",
                "תכונות חדשות"
            ]
        }
        
        release_info_file = releases_dir / f"release-{version}.json"
        with open(release_info_file, 'w', encoding='utf-8') as f:
            json.dump(release_info, f, indent=4, ensure_ascii=False)
        
        print(f"Created release info: {release_info_file}")
        return True
        
    except Exception as e:
        print(f"Error creating release package: {e}")
        return False

def clean_build_artifacts():
    """Clean build artifacts."""
    dirs_to_clean = ["build", "dist", "__pycache__"]
    files_to_clean = ["*.spec", "build_info.json"]
    
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"Cleaned {dir_name}")
    
    import glob
    for pattern in files_to_clean:
        for file in glob.glob(pattern):
            os.remove(file)
            print(f"Cleaned {file}")

def main():
    """Main build function."""
    if len(sys.argv) < 2:
        print("Usage: python build_with_version.py <increment_type> [new_version]")
        print("increment_type: major, minor, patch, or custom")
        print("new_version: required if increment_type is 'custom'")
        sys.exit(1)
    
    increment_type = sys.argv[1].lower()
    
    # Get current version
    current_version = get_current_version()
    print(f"Current version: {current_version}")
    
    # Determine new version
    if increment_type == 'custom':
        if len(sys.argv) < 3:
            print("Error: new_version required for custom increment")
            sys.exit(1)
        new_version = sys.argv[2]
    else:
        new_version = increment_version(current_version, increment_type)
    
    print(f"Building version: {new_version}")
    
    # Update version
    if not update_version(new_version):
        print("Failed to update version")
        sys.exit(1)
    
    try:
        # Create build info
        create_build_info(new_version)
        
        # Run build
        if not run_pyinstaller(new_version):
            print("Build failed")
            sys.exit(1)
        
        # Create release package
        if not create_release_package(new_version):
            print("Failed to create release package")
            sys.exit(1)
        
        print(f"\nBuild completed successfully!")
        print(f"Version: {new_version}")
        print(f"Executable: releases/idf-reader-{new_version}.exe")
        
        # Ask if user wants to clean build artifacts
        response = input("\nClean build artifacts? (y/N): ").strip().lower()
        if response == 'y':
            clean_build_artifacts()
            print("Build artifacts cleaned")
        
    except Exception as e:
        print(f"Build error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()