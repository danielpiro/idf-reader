"""
Utilities for handling Hebrew text in PDF reports.
"""
import html
import logging
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os

logger = logging.getLogger(__name__)

def register_hebrew_font():
    """
    Register a font that supports Hebrew characters for PDF generation.
    Falls back to system fonts if available.
    """
    try:
        # Try to register Arial Unicode MS or a similar font that supports Hebrew
        system_fonts = [
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/calibri.ttf",
            "C:/Windows/Fonts/tahoma.ttf",
            "/System/Library/Fonts/Arial.ttf",  # macOS
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Linux
        ]
        
        for font_path in system_fonts:
            if os.path.exists(font_path):
                try:
                    pdfmetrics.registerFont(TTFont('HebrewFont', font_path))
                    logger.info(f"Successfully registered Hebrew font: {font_path}")
                    return 'HebrewFont'
                except Exception as e:
                    logger.debug(f"Could not register font {font_path}: {e}")
                    continue
        
        # If no system font found, log warning but continue
        logger.warning("No Hebrew-compatible font found. Hebrew text may not display correctly.")
        return 'Helvetica'  # Fallback to default
        
    except Exception as e:
        logger.warning(f"Error registering Hebrew font: {e}")
        return 'Helvetica'

def encode_hebrew_text(text):
    """
    Properly encode Hebrew text for PDF generation with Unicode support.
    Reverses Hebrew text to display correctly in RTL format for PDF generation.
    
    Args:
        text: String that may contain Hebrew characters
        
    Returns:
        str: Properly encoded Hebrew text for PDF generation with RTL support
    """
    if not text or text == "N/A":
        return text
    
    try:
        # Ensure proper Unicode encoding for Hebrew text
        if isinstance(text, str):
            # Normalize the text and ensure proper Unicode encoding
            normalized_text = text.strip()
            
            # Check if text contains Hebrew characters
            contains_hebrew = any('\u0590' <= char <= '\u05FF' for char in normalized_text)
            
            if contains_hebrew:
                # For Hebrew text, reverse the text for proper RTL display
                try:
                    # Split by words and reverse the order for RTL display
                    words = normalized_text.split()
                    hebrew_words = []
                    non_hebrew_words = []
                    
                    for word in words:
                        if any('\u0590' <= char <= '\u05FF' for char in word):
                            # Hebrew word - reverse it
                            hebrew_words.append(word[::-1])
                        else:
                            # Non-Hebrew word - keep as is
                            non_hebrew_words.append(word)
                    
                    # If we have Hebrew words, reverse their order and combine
                    if hebrew_words:
                        # Reverse the order of Hebrew words for RTL reading
                        reversed_hebrew = ' '.join(reversed(hebrew_words))
                        if non_hebrew_words:
                            # Combine with non-Hebrew words (non-Hebrew words stay in original order)
                            encoded_text = reversed_hebrew + ' ' + ' '.join(non_hebrew_words)
                        else:
                            encoded_text = reversed_hebrew
                    else:
                        encoded_text = normalized_text
                    
                    return encoded_text.encode('utf-8').decode('utf-8')
                except UnicodeError:
                    # If encoding fails, escape the text
                    return html.escape(normalized_text, quote=False)
            else:
                # For non-Hebrew text, just escape HTML entities
                return html.escape(normalized_text, quote=False)
        
        return html.escape(str(text), quote=False)
        
    except Exception as e:
        logger.warning(f"Error encoding Hebrew text '{text}': {e}")
        # Fallback: return the original text with HTML escaping
        return html.escape(str(text) if text else "N/A", quote=False)

def safe_format_header_text(project_name, run_id, timestamp, city_name, area_name, report_title, version="Alpha"):
    """
    Safely format header text preserving Hebrew characters with proper encoding.
    
    Args:
        project_name: Project name
        run_id: Run identifier
        timestamp: Formatted timestamp string
        city_name: City name (may contain Hebrew)
        area_name: Area name (may contain Hebrew)
        report_title: Report title
        version: Version identifier (defaults to "Alpha")
        
    Returns:
        str: Properly formatted header text with Hebrew support
    """
    safe_city_name = encode_hebrew_text(city_name)
    safe_area_name = encode_hebrew_text(area_name)
    
    return f"""
    Project: {html.escape(str(project_name), quote=False)}<br/>
    Run ID: {html.escape(str(run_id), quote=False)}<br/>
    Date: {timestamp}<br/>
    Version: {html.escape(str(version), quote=False)}<br/>
    City: {safe_city_name}<br/>
    Area: {safe_area_name}<br/>
    """

def get_hebrew_font_name():
    """
    Get the name of the registered Hebrew font, registering it if needed.
    
    Returns:
        str: Font name to use for Hebrew text
    """
    try:
        # Check if HebrewFont is already registered
        registered_fonts = pdfmetrics.getRegisteredFontNames()
        if 'HebrewFont' in registered_fonts:
            return 'HebrewFont'
        else:
            return register_hebrew_font()
    except Exception as e:
        logger.warning(f"Error getting Hebrew font: {e}")
        return 'Helvetica'