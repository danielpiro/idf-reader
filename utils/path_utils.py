"""
Utility functions for handling file paths in both development and bundled (PyInstaller) environments.
"""
import os
import sys
from pathlib import Path

def get_data_file_path(filename: str) -> str:
    """
    Get the absolute path to a data file, working in both development and PyInstaller environments.
    
    Args:
        filename: Name of the file in the data folder (e.g., "countries-selection.csv", "a.epw")
    
    Returns:
        Absolute path to the data file
    
    Raises:
        FileNotFoundError: If the file cannot be found in any expected location
    """
    # List of possible base paths to try
    base_paths = []
    
    # PyInstaller bundle path (highest priority)
    if hasattr(sys, '_MEIPASS'):
        base_paths.append(os.path.join(sys._MEIPASS, 'data'))
    
    # Development environment paths
    # From current working directory
    base_paths.append(os.path.join(os.getcwd(), 'data'))
    
    # Relative to this utils module
    utils_dir = Path(__file__).resolve().parent
    base_paths.append(str(utils_dir.parent / 'data'))
    
    # Relative to the main application directory (where gui.py is)
    app_dir = utils_dir.parent
    base_paths.append(str(app_dir / 'data'))
    
    # Try each base path
    for base_path in base_paths:
        file_path = os.path.join(base_path, filename)
        if os.path.exists(file_path):
            return os.path.abspath(file_path)
    
    # If not found, provide detailed error message
    searched_paths = [os.path.join(bp, filename) for bp in base_paths]
    raise FileNotFoundError(
        f"Data file '{filename}' not found. Searched in:\n" + 
        "\n".join(f"  - {path}" for path in searched_paths)
    )

def get_data_directory() -> str:
    """
    Get the absolute path to the data directory.
    
    Returns:
        Absolute path to the data directory
    
    Raises:
        FileNotFoundError: If the data directory cannot be found
    """
    # List of possible data directory paths
    base_paths = []
    
    # PyInstaller bundle path (highest priority)
    if hasattr(sys, '_MEIPASS'):
        base_paths.append(os.path.join(sys._MEIPASS, 'data'))
    
    # Development environment paths
    # From current working directory
    base_paths.append(os.path.join(os.getcwd(), 'data'))
    
    # Relative to this utils module
    utils_dir = Path(__file__).resolve().parent
    base_paths.append(str(utils_dir.parent / 'data'))
    
    # Relative to the main application directory
    app_dir = utils_dir.parent
    base_paths.append(str(app_dir / 'data'))
    
    # Try each base path
    for base_path in base_paths:
        if os.path.exists(base_path) and os.path.isdir(base_path):
            return os.path.abspath(base_path)
    
    # If not found, provide detailed error message
    raise FileNotFoundError(
        f"Data directory not found. Searched in:\n" + 
        "\n".join(f"  - {path}" for path in base_paths)
    )

def list_data_files() -> list:
    """
    List all files in the data directory for debugging purposes.
    
    Returns:
        List of filenames in the data directory
    """
    try:
        data_dir = get_data_directory()
        return [f for f in os.listdir(data_dir) if os.path.isfile(os.path.join(data_dir, f))]
    except FileNotFoundError:
        return [] 