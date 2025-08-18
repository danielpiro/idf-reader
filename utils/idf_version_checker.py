"""
IDF Version Checker and Updater
Handles checking IDF file versions and updating them using IDFVersionUpdater.
"""
import os
import re
import subprocess
from pathlib import Path
from typing import Optional, Tuple
from utils.logging_config import get_logger

logger = get_logger(__name__)

class IDFVersionChecker:
    """Utility class for checking and updating IDF file versions."""
    
    def __init__(self, energyplus_path: Optional[str] = None):
        """
        Initialize the IDF Version Checker.
        
        Args:
            energyplus_path: Path to EnergyPlus installation directory
        """
        self.energyplus_path = energyplus_path
        self.target_version = "24.1.0"
        
    def get_idf_version(self, idf_path: str) -> Optional[str]:
        """
        Extract version from IDF file header.
        
        Args:
            idf_path: Path to the IDF file
            
        Returns:
            Version string (e.g., "9.6.0") or None if not found
        """
        try:
            with open(idf_path, 'r', encoding='utf-8', errors='ignore') as f:
                # Read first 50 lines to find version
                for i, line in enumerate(f):
                    if i > 50:  # Limit search to first 50 lines
                        break
                    
                    line = line.strip()
                    if line.upper().startswith('VERSION,'):
                        # Extract version number from "Version,9.6.0;" format
                        version_match = re.search(r'VERSION,\s*([0-9]+\.[0-9]+\.[0-9]+)', line.upper())
                        if version_match:
                            version = version_match.group(1)
                            logger.info(f"Found IDF version: {version} in file: {idf_path}")
                            return version
                        else:
                            # Try alternative format without comma
                            version_match = re.search(r'([0-9]+\.[0-9]+\.[0-9]+)', line)
                            if version_match:
                                version = version_match.group(1)
                                logger.info(f"Found IDF version: {version} in file: {idf_path}")
                                return version
                                
        except Exception as e:
            logger.error(f"Error reading IDF file {idf_path}: {e}")
            
        logger.warning(f"Could not find version in IDF file: {idf_path}")
        return None
    
    def compare_versions(self, version1: str, version2: str) -> int:
        """
        Compare two version strings.
        
        Args:
            version1: First version string
            version2: Second version string
            
        Returns:
            -1 if version1 < version2
             0 if version1 == version2
             1 if version1 > version2
        """
        try:
            # Split versions into parts and convert to integers
            v1_parts = [int(x) for x in version1.split('.')]
            v2_parts = [int(x) for x in version2.split('.')]
            
            # Pad shorter version with zeros
            max_len = max(len(v1_parts), len(v2_parts))
            v1_parts.extend([0] * (max_len - len(v1_parts)))
            v2_parts.extend([0] * (max_len - len(v2_parts)))
            
            # Compare each part
            for v1, v2 in zip(v1_parts, v2_parts):
                if v1 < v2:
                    return -1
                elif v1 > v2:
                    return 1
            
            return 0
            
        except ValueError as e:
            logger.error(f"Error comparing versions {version1} and {version2}: {e}")
            return 0
    
    def needs_update(self, idf_path: str) -> bool:
        """
        Check if IDF file needs to be updated to target version.
        
        Args:
            idf_path: Path to the IDF file
            
        Returns:
            True if file needs updating, False otherwise
        """
        current_version = self.get_idf_version(idf_path)
        if not current_version:
            logger.warning(f"Cannot determine version for {idf_path}, assuming update needed")
            return True
            
        comparison = self.compare_versions(current_version, self.target_version)
        needs_update = comparison < 0
        
        if needs_update:
            logger.info(f"IDF file {idf_path} version {current_version} is older than target {self.target_version}")
        else:
            logger.info(f"IDF file {idf_path} version {current_version} is up to date")
            
        return needs_update
    
    def find_energyplus_installation(self) -> Optional[str]:
        """
        Try to find EnergyPlus installation path automatically.
        
        Returns:
            Path to EnergyPlus installation or None if not found
        """
        if self.energyplus_path and os.path.exists(self.energyplus_path):
            return self.energyplus_path
            
        # Common installation paths on Windows
        common_paths = [
            f"C:\\EnergyPlusV{self.target_version.replace('.', '-')}",
            f"C:\\EnergyPlusV24-1-0",
            "C:\\EnergyPlusV24-1-0",
            "C:\\Program Files\\EnergyPlusV24-1-0",
            "C:\\Program Files (x86)\\EnergyPlusV24-1-0"
        ]
        
        for path in common_paths:
            if os.path.exists(path):
                logger.info(f"Found EnergyPlus installation at: {path}")
                self.energyplus_path = path
                return path
                
        logger.error("Could not find EnergyPlus installation. Please provide energyplus_path.")
        return None
    
    def get_version_updater_path(self) -> Optional[str]:
        """
        Get the path to IDFVersionUpdater directory.
        
        Returns:
            Path to IDFVersionUpdater directory or None if not found
        """
        energyplus_path = self.find_energyplus_installation()
        if not energyplus_path:
            return None
            
        updater_path = os.path.join(energyplus_path, "PreProcess", "IDFVersionUpdater")
        if os.path.exists(updater_path):
            logger.info(f"Found IDFVersionUpdater at: {updater_path}")
            return updater_path
        else:
            logger.error(f"IDFVersionUpdater not found at: {updater_path}")
            return None
    
    def update_idf_version(self, idf_path: str, backup: bool = True) -> Tuple[bool, str]:
        """
        Update IDF file to target version using IDFVersionUpdater.
        
        Args:
            idf_path: Path to the IDF file to update
            backup: Whether to create a backup of the original file
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Check if update is needed
            if not self.needs_update(idf_path):
                return True, f"File {idf_path} is already up to date"
            
            # Find IDFVersionUpdater
            updater_path = self.get_version_updater_path()
            if not updater_path:
                return False, "Could not find IDFVersionUpdater"
            
            # Create backup if requested
            if backup:
                backup_path = f"{idf_path}.backup"
                import shutil
                shutil.copy2(idf_path, backup_path)
                logger.info(f"Created backup: {backup_path}")
            
            # Get current version to determine which updater to use
            current_version = self.get_idf_version(idf_path)
            if not current_version:
                return False, "Could not determine current IDF version"
            
            # Find appropriate transition executable
            transition_exe = self._find_transition_executable(updater_path, current_version)
            if not transition_exe:
                return False, f"Could not find transition executable for version {current_version}"
            
            # Run the version updater
            logger.info(f"Updating {idf_path} from version {current_version} to {self.target_version}")
            result = subprocess.run(
                [transition_exe, idf_path],
                cwd=updater_path,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode == 0:
                logger.info(f"Successfully updated {idf_path} to version {self.target_version}")
                return True, f"Successfully updated to version {self.target_version}"
            else:
                error_msg = f"IDFVersionUpdater failed: {result.stderr}"
                logger.error(error_msg)
                return False, error_msg
                
        except subprocess.TimeoutExpired:
            return False, "IDFVersionUpdater timed out"
        except Exception as e:
            error_msg = f"Error updating IDF version: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def _find_transition_executable(self, updater_path: str, current_version: str) -> Optional[str]:
        """
        Find the appropriate transition executable for the current version.
        
        Args:
            updater_path: Path to IDFVersionUpdater directory
            current_version: Current IDF version
            
        Returns:
            Path to transition executable or None if not found
        """
        # Look for transition executables in the updater directory
        for file in os.listdir(updater_path):
            if file.startswith("Transition") and file.endswith(".exe"):
                # Extract version from filename like "Transition-V9-6-0-to-V24-1-0.exe"
                version_match = re.search(r'V(\d+)-(\d+)-(\d+)-to-V(\d+)-(\d+)-(\d+)', file)
                if version_match:
                    from_version = f"{version_match.group(1)}.{version_match.group(2)}.{version_match.group(3)}"
                    to_version = f"{version_match.group(4)}.{version_match.group(5)}.{version_match.group(6)}"
                    
                    # Check if this is the right transition for our current version
                    if from_version == current_version or self.compare_versions(from_version, current_version) <= 0:
                        transition_path = os.path.join(updater_path, file)
                        logger.info(f"Found transition executable: {transition_path}")
                        return transition_path
        
        # If no specific transition found, try the generic IDFVersionUpdater
        generic_updater = os.path.join(updater_path, "IDFVersionUpdater.exe")
        if os.path.exists(generic_updater):
            logger.info(f"Using generic IDFVersionUpdater: {generic_updater}")
            return generic_updater
            
        logger.error(f"No suitable transition executable found for version {current_version}")
        return None
    
    def batch_update_directory(self, directory_path: str, file_pattern: str = "*.idf") -> dict:
        """
        Update all IDF files in a directory.
        
        Args:
            directory_path: Path to directory containing IDF files
            file_pattern: File pattern to match (default: "*.idf")
            
        Returns:
            Dictionary with results for each file
        """
        results = {}
        directory = Path(directory_path)
        
        if not directory.exists():
            logger.error(f"Directory does not exist: {directory_path}")
            return results
        
        # Find all matching files
        idf_files = list(directory.glob(file_pattern))
        logger.info(f"Found {len(idf_files)} IDF files to process in {directory_path}")
        
        for idf_file in idf_files:
            try:
                success, message = self.update_idf_version(str(idf_file))
                results[str(idf_file)] = {
                    'success': success,
                    'message': message
                }
                logger.info(f"Processed {idf_file}: {message}")
            except Exception as e:
                error_msg = f"Error processing {idf_file}: {str(e)}"
                results[str(idf_file)] = {
                    'success': False,
                    'message': error_msg
                }
                logger.error(error_msg)
        
        return results