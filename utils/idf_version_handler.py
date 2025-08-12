"""
IDF Version Handler for EnergyPlus files.

This module provides functionality to check and modify IDF file versions
to ensure compatibility with EnergyPlus 9.4.0.002.
"""

import re
from utils.logging_config import get_logger

logger = get_logger(__name__)

TARGET_VERSION = "9.4.0.002"


def check_idf_version(idf_file_path: str) -> str:
    """
    Check the version of an IDF file.
    
    Args:
        idf_file_path: Path to the IDF file
        
    Returns:
        Current version string from the IDF file, or None if not found
        
    Raises:
        FileNotFoundError: If the IDF file doesn't exist
        IOError: If there's an error reading the file
    """
    try:
        with open(idf_file_path, 'r', encoding='utf-8') as file:
            content = file.read()
            
        # Look for Version objects in the IDF file
        # More comprehensive pattern to handle various formats
        version_pattern = r'Version,\s*(?:\n\s*)?([^;]+);[^\n]*'
        matches = re.findall(version_pattern, content, re.IGNORECASE | re.MULTILINE)
        
        if matches:
            # If multiple versions found, warn and return the first one
            if len(matches) > 1:
                logger.warning(f"Found {len(matches)} Version objects in IDF file. Using the first one.")
                logger.info(f"All versions found: {[v.strip() for v in matches]}")
            
            version = matches[0].strip()
            logger.info(f"Found IDF version: {version}")
            return version
        else:
            logger.warning("No Version object found in IDF file")
            return None
            
    except FileNotFoundError:
        logger.error(f"IDF file not found: {idf_file_path}")
        raise
    except IOError as e:
        logger.error(f"Error reading IDF file {idf_file_path}: {e}")
        raise


def update_idf_version(idf_file_path: str, target_version: str = TARGET_VERSION) -> bool:
    """
    Update the version in an IDF file to the target version.
    
    Args:
        idf_file_path: Path to the IDF file
        target_version: Version to set (default: 9.4.0.002)
        
    Returns:
        True if version was successfully updated, False otherwise
        
    Raises:
        FileNotFoundError: If the IDF file doesn't exist
        IOError: If there's an error reading/writing the file
    """
    try:
        with open(idf_file_path, 'r', encoding='utf-8') as file:
            content = file.read()
            
        # Pattern to match complete Version objects (including newlines)
        # This handles both single-line and multi-line Version formats
        version_pattern = r'Version,\s*(?:\n\s*)?[^;]+;[^\n]*(?:\n)?'
        
        # Find all version objects and remove them
        original_content = content
        new_content = re.sub(version_pattern, '', content, flags=re.IGNORECASE | re.MULTILINE)
        
        # Count how many were removed
        version_count = len(re.findall(version_pattern, original_content, re.IGNORECASE | re.MULTILINE))
        
        if version_count > 0:
            # Clean up any extra empty lines left behind
            new_content = re.sub(r'\n\s*\n\s*\n', '\n\n', new_content)
            
            # Find the right place to insert the new version
            lines = new_content.split('\n')
            insert_pos = 0
            
            # Find first non-comment, non-empty line
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped and not stripped.startswith('!'):
                    insert_pos = i
                    break
            
            # Insert version object
            version_object = f"Version,\n    {target_version};                !- Version Identifier"
            lines.insert(insert_pos, version_object)
            new_content = '\n'.join(lines)
            logger.info(f"Replaced {version_count} existing version object(s) with {target_version}")
        else:
            # Add version object at the beginning after any initial comments
            lines = content.split('\n')
            insert_pos = 0
            
            # Find first non-comment, non-empty line
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped and not stripped.startswith('!'):
                    insert_pos = i
                    break
            
            # Insert version object
            version_object = f"Version,\n    {target_version};                !- Version Identifier\n"
            lines.insert(insert_pos, version_object)
            new_content = '\n'.join(lines)
            logger.info(f"Added new version object with version {target_version}")
        
        # Write the updated content back to file
        with open(idf_file_path, 'w', encoding='utf-8') as file:
            file.write(new_content)
            
        logger.info(f"Successfully updated IDF version to {target_version} in {idf_file_path}")
        return True
        
    except FileNotFoundError:
        logger.error(f"IDF file not found: {idf_file_path}")
        raise
    except IOError as e:
        logger.error(f"Error updating IDF file {idf_file_path}: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error updating IDF version: {e}")
        return False


def ensure_idf_version_compatibility(idf_file_path: str, target_version: str = TARGET_VERSION) -> bool:
    """
    Ensure IDF file has the target version. If not, update it.
    
    Args:
        idf_file_path: Path to the IDF file
        target_version: Required version (default: 9.4.0.002)
        
    Returns:
        True if file already has target version or was successfully updated
        
    Raises:
        FileNotFoundError: If the IDF file doesn't exist
        IOError: If there's an error reading/writing the file
    """
    try:
        # Read the file content to check for multiple version objects
        with open(idf_file_path, 'r', encoding='utf-8') as file:
            content = file.read()
            
        # Check for all version objects
        version_pattern = r'Version,\s*(?:\n\s*)?([^;]+);'
        all_versions = re.findall(version_pattern, content, re.IGNORECASE | re.MULTILINE)
        
        current_version = check_idf_version(idf_file_path)
        
        # If multiple versions exist or no version found, always update
        if len(all_versions) > 1:
            logger.warning(f"Found {len(all_versions)} Version objects in IDF file. Consolidating to single target version.")
            return update_idf_version(idf_file_path, target_version)
        elif current_version is None:
            logger.warning("No version found in IDF file, adding target version")
            return update_idf_version(idf_file_path, target_version)
        elif current_version.strip() == target_version.strip():
            logger.info(f"IDF file already has target version {target_version}")
            return True
        else:
            logger.info(f"IDF version mismatch: current={current_version}, target={target_version}")
            logger.info("Updating IDF version to target version")
            return update_idf_version(idf_file_path, target_version)
            
    except Exception as e:
        logger.error(f"Error ensuring IDF version compatibility: {e}")
        raise