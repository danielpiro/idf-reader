"""
Natural Ventilation Report Generator
Generates PDF reports for natural ventilation data from ZoneVentilation:DesignFlowRate objects.
"""
from typing import Dict, List, Any
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER
from utils.hebrew_text_utils import safe_format_header_text, get_hebrew_font_name
import logging
import os
import re
from datetime import datetime

# Color scheme - matching load_report_generator.py
COLORS = {
    'primary_blue': colors.Color(0.2, 0.4, 0.7),
    'secondary_blue': colors.Color(0.4, 0.6, 0.85),
    'light_blue': colors.Color(0.9, 0.94, 0.98),
    'dark_gray': colors.Color(0.2, 0.2, 0.2),
    'medium_gray': colors.Color(0.5, 0.5, 0.5),
    'light_gray': colors.Color(0.9, 0.9, 0.9),
    'white': colors.Color(1, 1, 1),
    'border_gray': colors.Color(0.8, 0.8, 0.8),
}

# Font definitions - matching load_report_generator.py
FONTS = {
    'title': 'Helvetica-Bold',
    'heading': 'Helvetica-Bold',
    'body': 'Helvetica',
    'table_header': 'Helvetica-Bold',
    'table_body': 'Helvetica',
}

# Font sizes - matching load_report_generator.py
FONT_SIZES = {
    'title': 16,
    'heading': 12,
    'body': 10,
    'table_header': 9,
    'table_body': 8,
    'small': 7,
}

logger = logging.getLogger(__name__)

# Regex for extracting area ID
AREA_ID_REGEX = re.compile(r"^\d{2}")

def wrap_text(text, style):
    """Helper function to create wrapped text in a cell."""
    return Paragraph(str(text), style)

def create_cell_style(styles, is_header=False, center_align=False):
    """Create a cell style for wrapped text."""
    if is_header:
        style = ParagraphStyle(
            'HeaderCell',
            parent=styles['Normal'],
            fontSize=FONT_SIZES['small'],
            leading=8,
            spaceBefore=4,
            spaceAfter=4,
            fontName=FONTS['table_header'],
            textColor=COLORS['white'],
            wordWrap='CJK',
            alignment=1  # Center alignment
        )
    else:
        if center_align:
            style = ParagraphStyle(
                'CenteredCell',
                parent=styles['Normal'],
                fontSize=FONT_SIZES['small'],
                leading=8,
                spaceBefore=2,
                spaceAfter=2,
                fontName=FONTS['table_body'],
                wordWrap='CJK',
                alignment=1  # Center alignment
            )
        else:
            style = ParagraphStyle(
                'Cell',
                parent=styles['Normal'],
                fontSize=FONT_SIZES['small'],
                leading=8,
                spaceBefore=2,
                spaceAfter=2,
                fontName=FONTS['table_body'],
                wordWrap='CJK',
                alignment=0  # Left alignment for data
            )
    return style

def create_natural_ventilation_table_style():
    """Create table style for natural ventilation table."""
    style = [
        # Header row styling
        ('BACKGROUND', (0, 0), (-1, 0), COLORS['primary_blue']),
        ('TEXTCOLOR', (0, 0), (-1, 0), COLORS['white']),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, 0), FONTS['table_header']),
        ('FONTSIZE', (0, 0), (-1, 0), FONT_SIZES['table_body']),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),

        # Data rows styling
        ('TEXTCOLOR', (0, 1), (-1, -1), COLORS['dark_gray']),
        ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
        ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # Center align zone column
        ('VALIGN', (0, 1), (-1, -1), 'MIDDLE'),
        ('VALIGN', (0, 1), (0, -1), 'MIDDLE'),  # Ensure zone column is vertically centered
        ('FONTNAME', (0, 1), (-1, -1), FONTS['table_body']),
        ('FONTSIZE', (0, 1), (-1, -1), FONT_SIZES['small']),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),

        # Alternating row colors
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [COLORS['white'], COLORS['light_blue']]),

        # Grid and borders
        ('GRID', (0, 0), (-1, -1), 0.5, COLORS['border_gray']),
        ('BOX', (0, 0), (-1, -1), 1, COLORS['medium_gray']),

        # Padding
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6)
    ]

    return TableStyle(style)

def _extract_area_id(zone_id: str) -> str:
    """Extract area_id from a zone_id string."""
    split = zone_id.split(":", 1)
    if len(split) > 1 and split[1]:
        if AREA_ID_REGEX.match(split[1]):
            return split[1][:2]
        return split[1]
    return ""

def _extract_zone_prefix(zone_id: str) -> str:
    """Extract the prefix (part before colon) from a zone_id string."""
    split = zone_id.split(":", 1)
    return split[0] if split else zone_id

def _sort_zones_key(zone_name: str) -> tuple:
    """
    Create a sort key for zone names.
    Sort by area_id first (e.g., '01'), then by prefix (e.g., '00').
    """
    area_id = _extract_area_id(zone_name)
    prefix = _extract_zone_prefix(zone_name)
    
    # Convert to integers for proper numeric sorting, default to high values for non-numeric
    try:
        area_id_num = int(area_id) if area_id else 999
    except ValueError:
        area_id_num = 999
    
    try:
        prefix_num = int(prefix) if prefix else 999
    except ValueError:
        prefix_num = 999
    
    return (area_id_num, prefix_num, zone_name)

def _to_str(val, precision=None):
    """Convert value to string with optional precision."""
    if val is None:
        return '-'
    if precision is not None:
        try:
            return f"{float(val):.{precision}f}"
        except (ValueError, TypeError):
            return str(val)
    return str(val)

def generate_natural_ventilation_report(ventilation_data: Dict[str, List[Dict[str, Any]]], 
                                       output_path: str, 
                                       project_name: str, 
                                       run_id: str,
                                       city_name: str = "",
                                       area_name: str = "") -> bool:
    """
    Generate a PDF report for natural ventilation data.
    
    Args:
        ventilation_data: Dictionary containing natural ventilation data for each zone
        output_path: Path where the PDF report will be saved
        project_name: Name of the project
        run_id: Unique identifier for this run
        city_name: Name of the city (optional)
        area_name: Name of the area (optional)
        
    Returns:
        bool: True if report generated successfully, False otherwise
    """
    try:
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Set up page layout - matching load_report_generator.py
        left_margin = right_margin = 0.5 * cm
        top_margin = bottom_margin = 1.0 * cm
        page_size = landscape(A4)
        
        # Create PDF document
        doc = SimpleDocTemplate(output_path, pagesize=page_size,
                                leftMargin=left_margin, rightMargin=right_margin,
                                topMargin=top_margin, bottomMargin=bottom_margin)
        story = []
        
        width, _ = page_size
        content_width = width - left_margin - right_margin
        
        # Get styles
        styles = getSampleStyleSheet()
        
        # Create cell styles
        cell_style = create_cell_style(styles)
        centered_cell_style = create_cell_style(styles, center_align=True)
        header_cell_style = create_cell_style(styles, is_header=True)
        
        # Create title style - matching load_report_generator.py
        title_style = styles['h1']
        title_style.textColor = COLORS['primary_blue']
        title_style.fontName = FONTS['title']
        title_style.fontSize = FONT_SIZES['title']
        title_style.alignment = TA_CENTER
        
        # Create header info style - matching load_report_generator.py
        hebrew_font = get_hebrew_font_name()
        header_info_style = ParagraphStyle('HeaderInfo', parent=styles['Normal'], 
                                         fontSize=9, fontName=hebrew_font, 
                                         textColor=COLORS['dark_gray'], alignment=2)
        
        # Add header - matching load_report_generator.py format
        now = datetime.now()
        header_text = safe_format_header_text(
            project_name=project_name,
            run_id=run_id,
            timestamp=now.strftime('%Y-%m-%d %H:%M:%S'),
            city_name=city_name,
            area_name=area_name,
            report_title="Natural Ventilation Summary"
        )
        story.append(Paragraph(header_text, header_info_style))
        story.append(Spacer(1, 5))
        
        # Add title
        story.append(Paragraph("Natural Ventilation Report", title_style))
        story.append(Spacer(1, 0.5 * cm))
        
        # Check if we have data
        if not ventilation_data or all(not vent_list for vent_list in ventilation_data.values()):
            story.append(Paragraph("No natural ventilation data found in the IDF file.", styles['Normal']))
            doc.build(story)
            logger.info(f"Natural ventilation report generated successfully (no data): {output_path}")
            return True
        
        # Prepare table data
        table_data = []
        
        # Header row
        headers = [
            "Zone", "Schedule Name", "Design Flow Rate\n(m³/s)", "Ventilation Type", 
            "Min Indoor Temp\n(°C)", "Max Indoor Temp\n(°C)", "Max Temp Difference\n(°C)",
            "Min Outdoor Temp\n(°C)", "Max Outdoor Temp\n(°C)", "Max Wind Speed\n(m/s)"
        ]
        
        styled_headers = [wrap_text(h, header_cell_style) for h in headers]
        table_data.append(styled_headers)
        
        # Sort zones by area_id first, then by prefix
        sorted_zones = sorted(ventilation_data.keys(), key=_sort_zones_key)
        
        # Add ventilation data to table in sorted order
        for zone_name in sorted_zones:
            ventilation_list = ventilation_data[zone_name]
            for vent_data in ventilation_list:
                row_data = [
                    wrap_text(zone_name, cell_style),
                    wrap_text(vent_data.get('schedule_name', ''), cell_style),
                    wrap_text(_to_str(vent_data.get('design_flow_rate', 0.0), 3), centered_cell_style),
                    wrap_text(vent_data.get('ventilation_type', ''), cell_style),
                    wrap_text(_to_str(vent_data.get('min_indoor_temp', 0.0), 1), centered_cell_style),
                    wrap_text(_to_str(vent_data.get('max_indoor_temp', 0.0), 1), centered_cell_style),
                    wrap_text(_to_str(vent_data.get('max_temp_difference', 0.0), 1), centered_cell_style),
                    wrap_text(_to_str(vent_data.get('min_outdoor_temp', 0.0), 1), centered_cell_style),
                    wrap_text(_to_str(vent_data.get('max_outdoor_temp', 0.0), 1), centered_cell_style),
                    wrap_text(_to_str(vent_data.get('max_wind_speed', 0.0), 1), centered_cell_style)
                ]
                table_data.append(row_data)
        
        # Create table with proper column widths
        if len(table_data) > 1:  # Has data beyond headers
            # Use 95% of content width to match load_report_generator.py
            table_width = content_width * 0.95
            
            # Column widths for 10 columns
            col_widths = [
                table_width * 0.12,  # Zone
                table_width * 0.15,  # Schedule Name
                table_width * 0.08,  # Design Flow Rate
                table_width * 0.12,  # Ventilation Type
                table_width * 0.08,  # Min Indoor Temp
                table_width * 0.08,  # Max Indoor Temp
                table_width * 0.08,  # Max Temp Difference
                table_width * 0.08,  # Min Outdoor Temp
                table_width * 0.08,  # Max Outdoor Temp
                table_width * 0.08   # Max Wind Speed
            ]
            
            table = Table(table_data, colWidths=col_widths, hAlign='CENTER', repeatRows=1)
            table.setStyle(create_natural_ventilation_table_style())
            
            story.append(table)
            story.append(Spacer(1, 0.4 * cm))
        
        # Build PDF
        doc.build(story)
        logger.info(f"Natural ventilation report generated successfully: {output_path}")
        return True
        
    except Exception as e:
        logger.error(f"An unexpected error occurred while generating Natural Ventilation report '{output_path}': {type(e).__name__} - {str(e)}", exc_info=True)
        return False 