"""
Utility functions for handling file paths in both development and bundled (PyInstaller) environments.
Includes support for Unicode/Hebrew characters in paths.
"""
import os
import sys
import tempfile
import shutil
from utils.logging_config import get_logger
from pathlib import Path

logger = get_logger(__name__)

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

def contains_non_ascii(path_str):
    """
    Check if a path contains non-ASCII characters (like Hebrew).
    
    Args:
        path_str: Path string to check
        
    Returns:
        bool: True if path contains non-ASCII characters
    """
    try:
        path_str.encode('ascii')
        return False
    except UnicodeEncodeError:
        return True

def create_safe_path_for_energyplus(original_path, temp_dir=None):
    """
    Create a safe ASCII-only path for EnergyPlus compatibility.
    EnergyPlus has issues with Unicode/Hebrew characters in file paths.
    
    Args:
        original_path: The original path that may contain Unicode characters
        temp_dir: Optional temporary directory to use
        
    Returns:
        tuple: (safe_path, cleanup_function)
            safe_path: ASCII-only path safe for EnergyPlus
            cleanup_function: Function to call to clean up temporary files (or None)
    """
    if not contains_non_ascii(original_path):
        # Path is already ASCII-safe
        return original_path, None
    
    logger.info(f"Creating ASCII-safe copy for Unicode path: {original_path}")
    
    # Create a temporary ASCII-safe copy
    if temp_dir is None:
        temp_dir = tempfile.mkdtemp(prefix="eplus_safe_")
    
    # Create a safe filename using only ASCII characters
    original_name = os.path.basename(original_path)
    file_ext = os.path.splitext(original_name)[1]
    safe_name = f"input_file{file_ext}"  # Use a simple ASCII name with original extension
    
    safe_path = os.path.join(temp_dir, safe_name)
    
    try:
        # Copy the file to the safe location with proper encoding handling
        shutil.copy2(original_path, safe_path)
        logger.info(f"Created ASCII-safe copy at: {safe_path}")
    except (OSError, IOError) as e:
        logger.error(f"Failed to create safe copy of {original_path}: {e}")
        raise
    
    def cleanup():
        try:
            if os.path.exists(safe_path):
                os.remove(safe_path)
                logger.debug(f"Cleaned up temporary file: {safe_path}")
            if os.path.exists(temp_dir) and not os.listdir(temp_dir):
                os.rmdir(temp_dir)
                logger.debug(f"Cleaned up temporary directory: {temp_dir}")
        except OSError as e:
            logger.warning(f"Could not clean up temporary file {safe_path}: {e}")
    
    return safe_path, cleanup

def create_safe_output_dir_for_energyplus(original_output_dir):
    """
    Create a safe ASCII-only output directory for EnergyPlus.
    
    Args:
        original_output_dir: The original output directory that may contain Unicode
        
    Returns:
        tuple: (safe_output_dir, needs_move_back)
            safe_output_dir: ASCII-only directory safe for EnergyPlus
            needs_move_back: Boolean indicating if files need to be moved back
    """
    if not contains_non_ascii(original_output_dir):
        # Path is already ASCII-safe
        return original_output_dir, False
    
    logger.info(f"Creating ASCII-safe output directory for Unicode path: {original_output_dir}")
    
    # Create a temporary ASCII-safe directory
    temp_dir = tempfile.mkdtemp(prefix="eplus_output_")
    logger.info(f"Created temporary ASCII-safe output directory: {temp_dir}")
    
    return temp_dir, True

def move_simulation_files_back(temp_output_dir, original_output_dir):
    """
    Move simulation output files from temporary ASCII directory back to original Unicode directory.
    
    Args:
        temp_output_dir: Temporary ASCII-safe directory containing simulation outputs
        original_output_dir: Original Unicode directory where files should be moved
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logger.info(f"Moving simulation files from {temp_output_dir} to {original_output_dir}")
        
        # Ensure the original output directory exists
        os.makedirs(original_output_dir, exist_ok=True)
        
        # Move all files from temp directory to original location
        moved_files = []
        for filename in os.listdir(temp_output_dir):
            src = os.path.join(temp_output_dir, filename)
            dst = os.path.join(original_output_dir, filename)
            if os.path.isfile(src):
                shutil.move(src, dst)
                moved_files.append(filename)
                logger.debug(f"Moved file: {filename}")
        
        logger.info(f"Successfully moved {len(moved_files)} files to {original_output_dir}")
        
        # Clean up temp directory
        try:
            shutil.rmtree(temp_output_dir)
            logger.debug(f"Cleaned up temporary directory: {temp_output_dir}")
        except OSError as e:
            logger.warning(f"Could not remove temporary output directory {temp_output_dir}: {e}")
        
        return True
        
    except (OSError, IOError) as e:
        logger.error(f"Failed to move simulation files back: {e}")
        return False

def normalize_path_for_energyplus(path_str):
    """
    Normalize a path string for EnergyPlus compatibility.
    Converts forward slashes to backslashes on Windows and ensures proper encoding.
    
    Args:
        path_str: Path string to normalize
        
    Returns:
        str: Normalized path string
    """
    if not path_str:
        return path_str
    
    # Convert to Path object for proper handling
    path_obj = Path(path_str)
    
    # Convert to absolute path with proper separators for the OS
    normalized = str(path_obj.resolve())
    
    # On Windows, ensure backslashes are used (EnergyPlus prefers this)
    if os.name == 'nt':
        normalized = normalized.replace('/', '\\')
    
    return normalized