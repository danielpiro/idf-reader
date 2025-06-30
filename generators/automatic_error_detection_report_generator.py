"""
Automatic Error Detection Report Generator
Generates PDF reports for automatic error detection data.
"""
from typing import Dict, List, Any
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER
from utils.hebrew_text_utils import safe_format_header_text, get_hebrew_font_name
from utils.logo_utils import create_logo_image
import logging
import os
from datetime import datetime
from pathlib import Path

# Color scheme - matching other report generators
COLORS = {
    'primary_blue': colors.Color(0.2, 0.4, 0.7),
    'secondary_blue': colors.Color(0.4, 0.6, 0.85),
    'light_blue': colors.Color(0.9, 0.94, 0.98),
    'dark_gray': colors.Color(0.2, 0.2, 0.2),
    'medium_gray': colors.Color(0.5, 0.5, 0.5),
    'light_gray': colors.Color(0.9, 0.9, 0.9),
    'white': colors.Color(1, 1, 1),
    'border_gray': colors.Color(0.8, 0.8, 0.8),
    'error_red': colors.Color(0.8, 0.2, 0.2),
    'warning_orange': colors.Color(0.9, 0.6, 0.2),
}

# Font definitions - matching other report generators
FONTS = {
    'title': 'Helvetica-Bold',
    'heading': 'Helvetica-Bold',
    'body': 'Helvetica',
    'table_header': 'Helvetica-Bold',
    'table_body': 'Helvetica',
}

# Font sizes - matching other report generators
FONT_SIZES = {
    'title': 16,
    'heading': 12,
    'body': 10,
    'table_header': 9,
    'table_body': 8,
    'small': 7,
}

logger = logging.getLogger(__name__)

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

def create_error_detection_table_style():
    """Create table style for automatic error detection table."""
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
        ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # Center align zone name column
        ('VALIGN', (0, 1), (-1, -1), 'MIDDLE'),
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

def _get_remark_color(remark: str) -> colors.Color:
    """Get color based on remark severity."""
    remark_lower = remark.lower()
    if 'not allowed' in remark_lower:
        return COLORS['error_red']
    elif 'not correct' in remark_lower:
        return COLORS['warning_orange']
    elif 'need to change' in remark_lower:
        return COLORS['warning_orange']
    else:
        return COLORS['dark_gray']

def _create_error_detection_table_data(error_data: List[Dict[str, Any]], styles) -> List[List]:
    """Create table data for the automatic error detection table."""
    
    # Create cell styles
    header_style = create_cell_style(styles, is_header=True)
    cell_style = create_cell_style(styles, is_header=False)
    center_cell_style = create_cell_style(styles, is_header=False, center_align=True)
    
    # Create header row
    table_data = [
        [
            wrap_text("Zone Name", header_style),
            wrap_text("Category", header_style),
            wrap_text("Current Model Value", header_style),
            wrap_text("Recommended Standard Value", header_style),
            wrap_text("Remark", header_style)
        ]
    ]
    
    # Add data rows
    for row in error_data:
        zone_name = str(row.get('zone_name', ''))
        category = str(row.get('category', ''))
        current_value = str(row.get('current_model_value', ''))
        recommended_value = str(row.get('recommended_standard_value', ''))
        remark = str(row.get('remark', ''))
        
        # Create colored remark based on severity
        remark_color = _get_remark_color(remark)
        remark_style = ParagraphStyle(
            'RemarkCell',
            parent=styles['Normal'],
            fontSize=FONT_SIZES['small'],
            leading=8,
            spaceBefore=2,
            spaceAfter=2,
            fontName=FONTS['table_body'],
            wordWrap='CJK',
            alignment=0,
            textColor=remark_color
        )
        
        table_data.append([
            wrap_text(zone_name, center_cell_style),
            wrap_text(category, cell_style),
            wrap_text(current_value, center_cell_style),
            wrap_text(recommended_value, center_cell_style),
            wrap_text(remark, remark_style)
        ])
    
    return table_data

def generate_automatic_error_detection_report(error_detection_data: List[Dict[str, Any]], 
                                            output_path: str, 
                                            project_name: str, 
                                            run_id: str,
                                            city_name: str = "",
                                            area_name: str = "") -> bool:
    """
    Generate a PDF report for automatic error detection data.
    
    Args:
        error_detection_data: List containing error detection data
        output_path: Path where the PDF report will be saved
        project_name: Name of the project
        run_id: Unique identifier for this run
        city_name: Name of the city (optional)
        area_name: Name of the area (optional)
        
    Returns:
        bool: True if report generation was successful, False otherwise
    """
    try:
        # Ensure output directory exists
        output_dir = Path(output_path).parent
        if not output_dir.exists():
            output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Starting automatic validation report generation: {output_path}")

        # Create document
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            topMargin=2*cm,
            bottomMargin=2*cm,
            leftMargin=2*cm,
            rightMargin=2*cm
        )
        
        styles = getSampleStyleSheet()
        story = []

        # Add logo if available
        logo_image = create_logo_image(max_width=3*cm, max_height=1.5*cm)
        if logo_image:
            # Create a table to position logo on the left
            logo_table_data = [[logo_image, ""]]
            logo_table = Table(logo_table_data, colWidths=[4*cm, doc.width - 4*cm])
            logo_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (0, 0), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ]))
            story.append(logo_table)
            story.append(Spacer(1, 10))

        # Add header information
        now = datetime.now()
        hebrew_font = get_hebrew_font_name()
        header_style = ParagraphStyle(
            'HeaderInfo',
            parent=styles['Normal'],
            fontSize=9,
            fontName=hebrew_font,
            textColor=COLORS['dark_gray'],
            alignment=2
        )
        
        header_text = safe_format_header_text(
            project_name=project_name,
            run_id=run_id,
            timestamp=now.strftime('%Y-%m-%d %H:%M:%S'),
            city_name=city_name,
            area_name=area_name,
            report_title="Automatic Error Detection"
        )
        story.append(Paragraph(header_text, header_style))
        story.append(Spacer(1, 15))

        # Add title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=FONT_SIZES['title'],
            fontName=FONTS['title'],
            textColor=COLORS['primary_blue'],
            spaceAfter=20,
            alignment=TA_CENTER
        )
        story.append(Paragraph("Automatic Error Detection Report", title_style))
        story.append(Spacer(1, 10))

        # Create error detection table
        if error_detection_data:
            table_data = _create_error_detection_table_data(error_detection_data, styles)
            
            # Define column widths
            col_widths = [
                3.5*cm,  # Zone Name
                3.5*cm,  # Category
                3.5*cm,  # Current Model Value
                4.0*cm,  # Recommended Standard Value
                4.5*cm   # Remark
            ]
            
            table = Table(table_data, colWidths=col_widths, repeatRows=1)
            table.setStyle(create_error_detection_table_style())
            
            story.append(table)
        else:
            # No data message
            no_data_style = ParagraphStyle(
                'NoData',
                parent=styles['Normal'],
                fontSize=FONT_SIZES['body'],
                fontName=FONTS['body'],
                textColor=COLORS['medium_gray'],
                alignment=TA_CENTER,
                spaceAfter=20
            )
            story.append(Paragraph("No error detection data available.", no_data_style))

        # Build PDF
        doc.build(story)
        logger.info(f"Automatic error detection report generated successfully: {output_path}")
        return True

    except Exception as e:
        logger.error(f"Error generating automatic error detection report: {str(e)}", exc_info=True)
        return False 