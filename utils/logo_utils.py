"""
Utility functions for handling logo assets in the IDF Reader application.
Provides consistent logo handling across GUI and PDF reports.
"""
import os
import logging
from pathlib import Path
from reportlab.platypus import Image
from reportlab.lib.units import cm
from utils.path_utils import get_data_file_path

logger = logging.getLogger(__name__)

def get_logo_path(logo_type='jpg'):
    """
    Get the path to the logo file.
    
    Args:
        logo_type (str): Type of logo file ('jpg' for reports, 'ico' for GUI)
    
    Returns:
        str or None: Path to the logo file, None if not found
    """
    try:
        if logo_type.lower() == 'ico':
            return get_data_file_path('logo.ico')
        else:
            return get_data_file_path('logo.png')
    except FileNotFoundError:
        logger.warning(f"Logo file (logo.{logo_type}) not found in data directory")
        return None
    except Exception as e:
        logger.error(f"Error getting logo path: {e}")
        return None

def create_logo_image(logo_path=None, width=None, height=None, max_width=4*cm, max_height=2*cm):
    """
    Create a ReportLab Image object for the logo with proper sizing.
    
    Args:
        logo_path (str, optional): Path to logo file. If None, auto-detected.
        width (float, optional): Desired width in ReportLab units
        height (float, optional): Desired height in ReportLab units
        max_width (float): Maximum width constraint
        max_height (float): Maximum height constraint
    
    Returns:
        Image or None: ReportLab Image object, None if logo not available
    """
    try:
        if logo_path is None:
            logo_path = get_logo_path('jpg')
        
        if not logo_path or not os.path.exists(logo_path):
            logger.warning("Logo file not available for report generation")
            return None
        
        # Create the Image object
        if width and height:
            # Use specified dimensions
            logo_image = Image(logo_path, width=width, height=height)
        else:
            # Auto-size with constraints
            logo_image = Image(logo_path)
            
            # Get original dimensions
            img_width, img_height = logo_image.drawWidth, logo_image.drawHeight
            
            # Calculate scaling to fit within max constraints
            width_scale = max_width / img_width if img_width > max_width else 1
            height_scale = max_height / img_height if img_height > max_height else 1
            scale = min(width_scale, height_scale)
            
            # Apply scaling
            logo_image.drawWidth = img_width * scale
            logo_image.drawHeight = img_height * scale
        
        return logo_image
        
    except Exception as e:
        logger.error(f"Error creating logo image: {e}")
        return None

def get_gui_logo_path():
    """
    Get the logo path specifically for GUI window icon.
    
    Returns:
        str or None: Path to the .ico logo file, None if not found
    """
    return get_logo_path('ico')

def has_logo():
    """
    Check if logo files are available.
    
    Returns:
        dict: Dictionary with availability status for different logo types
    """
    return {
        'jpg': get_logo_path('jpg') is not None,
        'ico': get_logo_path('ico') is not None
    }