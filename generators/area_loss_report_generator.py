"""
Generates reports for area loss information extracted from IDF files.
"""
from typing import Dict, Any, List
from pathlib import Path
import datetime
import logging
from reportlab.lib import colors
from reportlab.lib.colors import Color
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

# Modern Blue/Gray Color Palette
COLORS = {
    'primary_blue': Color(0.2, 0.4, 0.7),      # #3366B2 - Primary blue
    'secondary_blue': Color(0.4, 0.6, 0.85),   # #6699D9 - Secondary blue
    'light_blue': Color(0.9, 0.94, 0.98),      # #E6F0FA - Light blue background
    'dark_gray': Color(0.2, 0.2, 0.2),         # #333333 - Dark gray text
    'medium_gray': Color(0.5, 0.5, 0.5),       # #808080 - Medium gray
    'light_gray': Color(0.9, 0.9, 0.9),        # #E6E6E6 - Light gray
    'white': Color(1, 1, 1),                   # #FFFFFF - White
    'border_gray': Color(0.8, 0.8, 0.8),       # #CCCCCC - Border gray
}

# Typography Settings
FONTS = {
    'title': 'Helvetica-Bold',
    'heading': 'Helvetica-Bold',
    'body': 'Helvetica',
    'table_header': 'Helvetica-Bold',
    'table_body': 'Helvetica',
}

FONT_SIZES = {
    'title': 16,
    'heading': 12,
    'body': 10,
    'table_header': 9,
    'table_body': 8,
    'small': 7,
}

logger = logging.getLogger(__name__)

def _compatibility_color(compatible: str) -> colors.Color:
    """Returns green if compatible is 'Yes', otherwise red."""
    return colors.green if compatible == "Yes" else colors.red

def _area_loss_table_data(area_loss_data, cell_style, compatibility_style):
    table_data = [[
        Paragraph("Area", cell_style),
        Paragraph("Location", cell_style),
        Paragraph("H-Value", cell_style),
        Paragraph("H-Needed", cell_style),
        Paragraph("Compatible", cell_style)
    ]]
    sorted_rows = sorted(area_loss_data, key=lambda x: x.get('area_id', ''))
    for row in sorted_rows:
        area_id = row.get('area_id', 'Unknown')
        location = row.get('location', 'Unknown')
        h_value = row.get('h_value', 0.0)
        h_needed = row.get('h_needed', 0.0)
        compatible = row.get('compatible', 'No')
        h_value_formatted = f"{h_value:.3f}"
        h_needed_formatted = f"{h_needed:.3f}"
        color = _compatibility_color(compatible)
        table_data.append([
            Paragraph(area_id, cell_style),
            Paragraph(location, cell_style),
            h_value_formatted,
            h_needed_formatted,
            Paragraph(f"<font color={color}>{compatible}</font>", compatibility_style)
        ])
    return table_data

def generate_area_loss_report_pdf(area_loss_data: List[Dict[str, Any]],
                             output_filename: str,
                             project_name: str = "N/A", 
                             run_id: str = "N/A",
                             city_name: str = "N/A",
                             area_name: str = "N/A") -> bool:
    """
    Generate a PDF report with area loss information, including H-values.

    Args:
        area_loss_data (List[Dict[str, Any]]): List of area loss data rows.
        output_filename (str): Path where to save the PDF report.
        project_name (str): Name of the project.
        run_id (str): Identifier for the current run.

    Returns:
        bool: True if report generation was successful, False otherwise.
    """
    doc = None
    try:
        output_path = Path(output_filename).parent
        if not output_path.exists():
            try:
                output_path.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                error_message = f"Error creating output directory '{output_path}': {e.strerror}"
                logger.error(error_message, exc_info=True)
                return False
        elif not output_path.is_dir():
            error_message = f"Error: Output path '{output_path}' exists but is not a directory."
            logger.error(error_message)
            return False

        doc = SimpleDocTemplate(str(output_filename), pagesize=A4)
        styles = getSampleStyleSheet()
        story = []

        now = datetime.datetime.now()
        header_style = ParagraphStyle(
            'HeaderInfo',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.black,
            alignment=2
        )
        header_text = f"""
        Project: {project_name}<br/>
        Run ID: {run_id}<br/>
        Date: {now.strftime('%Y-%m-%d %H:%M:%S')}<br/>
        City: {city_name}<br/>
        Area: {area_name}<br/>
        Report: Area Loss - Thermal Performance
        """
        story.append(Paragraph(header_text, header_style))
        story.append(Spacer(1, 5))

        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=FONT_SIZES['title'],
            fontName=FONTS['title'],
            textColor=COLORS['primary_blue'],
            spaceAfter=20
        )
        story.append(Paragraph("Area Loss - Thermal Performance Report", title_style))

        cell_style = ParagraphStyle(
            'CellStyle',
            parent=styles['Normal'],
            fontSize=9,
            leading=10,
            spaceBefore=0,
            spaceAfter=0
        )

        compatibility_style = ParagraphStyle(
            'CompatibilityStyle',
            parent=styles['Normal'],
            fontSize=9,
            leading=10,
            spaceBefore=0,
            spaceAfter=0
        )

        headers = [
            Paragraph("Area", cell_style),
            Paragraph("Location", cell_style),
            Paragraph("H-Value", cell_style),
            Paragraph("H-Needed", cell_style),
            Paragraph("Compatible", cell_style)
        ]

        table_data = _area_loss_table_data(area_loss_data, cell_style, compatibility_style)

        col_widths = [
            3.0*cm,
            5.0*cm,
            3.0*cm,
            3.0*cm,
            3.0*cm
        ]

        area_loss_table = Table(table_data, colWidths=col_widths, repeatRows=1)

        table_style = TableStyle([
            # Header row styling - primary blue background
            ('BACKGROUND', (0, 0), (-1, 0), COLORS['primary_blue']),
            ('TEXTCOLOR', (0, 0), (-1, 0), COLORS['white']),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), FONTS['table_header']),
            ('FONTSIZE', (0, 0), (-1, 0), FONT_SIZES['table_header']),
            ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
            
            # Data rows styling
            ('FONTNAME', (0, 1), (-1, -1), FONTS['table_body']),
            ('FONTSIZE', (0, 1), (-1, -1), FONT_SIZES['table_body']),
            ('TEXTCOLOR', (0, 1), (-1, -1), COLORS['dark_gray']),
            ('ALIGN', (2, 1), (3, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            
            # Zebra striping for data rows
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [COLORS['white'], COLORS['light_blue']]),
            
            # Borders - subtle gray lines
            ('GRID', (0, 0), (-1, -1), 0.5, COLORS['border_gray']),
            ('BOX', (0, 0), (-1, -1), 1, COLORS['medium_gray']),
            
            # Padding for better readability
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ])

        area_loss_table.setStyle(table_style)
        story.append(area_loss_table)

        doc.build(story)
        return True
    except (IOError, OSError) as e:
        error_message = f"Error during file operation for Area Loss report '{output_filename}': {e.strerror}"
        logger.error(error_message, exc_info=True)
        return False
    except Exception as e:
        error_message = f"An unexpected error occurred while generating Area Loss report '{output_filename}': {type(e).__name__} - {str(e)}"
        logger.error(error_message, exc_info=True)
        return False
    finally:
        pass
