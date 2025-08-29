"""
Consolidated ReportLab imports for all PDF generators.
This module provides a centralized location for all common ReportLab imports
to reduce redundancy and improve maintenance.
"""

# Core ReportLab imports
from reportlab.lib.colors import Color, black, lightgrey, grey
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, A3, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm, inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Table, TableStyle, 
    Spacer, Image, PageBreak
)

# Graphics imports
from reportlab.graphics.shapes import Drawing, Rect, Polygon, String

# Re-export everything for easy access
__all__ = [
    # Colors
    'Color', 'black', 'lightgrey', 'grey', 'colors',
    
    # Enums
    'TA_CENTER', 'TA_LEFT', 'TA_RIGHT',
    
    # Page sizes
    'A4', 'A3', 'landscape',
    
    # Styles
    'getSampleStyleSheet', 'ParagraphStyle',
    
    # Units
    'cm', 'mm', 'inch',
    
    # Document elements
    'SimpleDocTemplate', 'Paragraph', 'Table', 'TableStyle', 
    'Spacer', 'Image', 'PageBreak',
    
    # Graphics
    'Drawing', 'Rect', 'Polygon', 'String'
]