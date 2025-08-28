"""
Version management for IDF Reader application.
"""

__version__ = "1.1.16"
__version_info__ = (1, 1, 16)

# Update server configuration
UPDATE_SERVER_URL = "http://localhost:8000/api"  # Local development server
GITHUB_RELEASES_URL = "https://api.github.com/repos/danielpiro/idf-reader/releases/latest"  # GitHub releases

def get_version():
    """Get current application version."""
    return __version__

def get_version_info():
    """Get version as tuple for comparison."""
    return __version_info__

def compare_versions(version1, version2):
    """
    Compare two version strings.
    
    Args:
        version1: First version (e.g., "1.0.0")
        version2: Second version (e.g., "1.1.0")
    
    Returns:
        -1 if version1 < version2
         0 if version1 == version2
         1 if version1 > version2
    """
    def version_to_tuple(v):
        return tuple(map(int, v.split('.')))
    
    v1_tuple = version_to_tuple(version1)
    v2_tuple = version_to_tuple(version2)
    
    if v1_tuple < v2_tuple:
        return -1
    elif v1_tuple > v2_tuple:
        return 1
    else:
        return 0

















