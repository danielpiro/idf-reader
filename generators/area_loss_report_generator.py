"""
Generates reports for area loss information extracted from IDF files.
"""
from typing import Dict, Any, List
from pathlib import Path
import datetime
import logging # Added for detailed error logging
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

logger = logging.getLogger(__name__) # Added logger instance

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
                             run_id: str = "N/A") -> bool:
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
                logger.info(f"Created output directory: {output_path}")
            except OSError as e:
                error_message = f"Error creating output directory '{output_path}': {e.strerror}"
                logger.error(error_message, exc_info=True)
                # No need to display to user here, caller (GUI) should handle status.
                return False
        elif not output_path.is_dir():
            error_message = f"Error: Output path '{output_path}' exists but is not a directory."
            logger.error(error_message)
            return False

        doc = SimpleDocTemplate(str(output_filename), pagesize=A4) # Ensure output_filename is string
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
        Report: Area Loss - Thermal Performance
        """
        story.append(Paragraph(header_text, header_style))
        story.append(Spacer(1, 5))

        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
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
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN', (2, 1), (3, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgrey]),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
        ])

        area_loss_table.setStyle(table_style)
        story.append(area_loss_table)

        doc.build(story)
        logger.info(f"Successfully generated Area Loss report: {output_filename}")
        return True
    except (IOError, OSError) as e:
        error_message = f"Error during file operation for Area Loss report '{output_filename}': {e.strerror}"
        logger.error(error_message, exc_info=True)
        return False
    except Exception as e: # Catch ReportLab specific errors or other unexpected issues
        # ReportLab errors can be varied. Logging them is key.
        error_message = f"An unexpected error occurred while generating Area Loss report '{output_filename}': {type(e).__name__} - {str(e)}"
        logger.error(error_message, exc_info=True)
        return False
    finally:
        # SimpleDocTemplate's build method should handle closing the file.
        # No explicit file resource to close here unless we were manually opening/writing.
        pass
