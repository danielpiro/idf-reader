"""
Generates reports for area loss information extracted from IDF files.
"""
from typing import Dict, Any, List
from pathlib import Path
import datetime
from colorama import Fore, Style, init
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

# Initialize colorama
init(autoreset=True)

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
    try:
        # Ensure output directory exists
        output_path = Path(output_filename).parent
        output_path.mkdir(exist_ok=True, parents=True)
        
        # Create PDF document
        doc = SimpleDocTemplate(output_filename, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []
        
        # Header Information
        now = datetime.datetime.now()
        header_style = ParagraphStyle(
            'HeaderInfo',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.black,
            alignment=2  # Right aligned
        )
        header_text = f"""
        Project: {project_name}<br/>
        Run ID: {run_id}<br/>
        Date: {now.strftime('%Y-%m-%d %H:%M:%S')}<br/>
        Report: Area Loss - Thermal Performance
        """
        story.append(Paragraph(header_text, header_style))
        story.append(Spacer(1, 5))  # Add some space after header

        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=20
        )
        story.append(Paragraph("Area Loss - Thermal Performance Report", title_style))
        
        # Create cell styles for better formatting
        cell_style = ParagraphStyle(
            'CellStyle',
            parent=styles['Normal'],
            fontSize=9,
            leading=10,
            spaceBefore=0,
            spaceAfter=0
        )
        
        header_style = ParagraphStyle(
            'HeaderStyle',
            parent=styles['Heading4'],
            fontSize=10,
            alignment=1,  # Center alignment
            textColor=colors.whitesmoke
        )
        
        compatibility_style = ParagraphStyle(
            'CompatibilityStyle',
            parent=styles['Normal'],
            fontSize=9,
            leading=10,
            spaceBefore=0,
            spaceAfter=0
        )
        
        # Header row for the table as Paragraphs for consistent styling
        headers = [
            Paragraph("Area", header_style),
            Paragraph("Location", header_style),
            Paragraph("H-Value", header_style),
            Paragraph("H-Needed", header_style),
            Paragraph("Compatible", header_style)
        ]
        
        # Prepare table data
        table_data = [headers]
        
        # Sort rows by area_id for better readability
        sorted_rows = sorted(area_loss_data, key=lambda x: x.get('area_id', ''))
        
        # Format values and add to table
        for row in sorted_rows:
            area_id = row.get('area_id', 'Unknown')
            location = row.get('location', 'Unknown')
            h_value = row.get('h_value', 0.0)
            h_needed = row.get('h_needed', 0.0)
            compatible = row.get('compatible', 'No')
            
            # Format numeric values with proper precision
            h_value_formatted = f"{h_value:.3f}"
            h_needed_formatted = f"{h_needed:.3f}"
            
            # Determine compatibility color based on the status
            compatibility_color = colors.green if compatible == "Yes" else colors.red
            
            # Add row to the table
            table_data.append([
                Paragraph(area_id, cell_style),
                Paragraph(location, cell_style),
                h_value_formatted,
                h_needed_formatted,
                Paragraph(f"<font color={compatibility_color}>{compatible}</font>", compatibility_style)
            ])
        
        # Create the table with carefully adjusted column widths
        col_widths = [
            3.0*cm,  # Area
            5.0*cm,  # Location
            3.0*cm,  # H-Value
            3.0*cm,  # H-Needed
            3.0*cm   # Compatible
        ]
        
        # Create table with data and column widths
        area_loss_table = Table(table_data, colWidths=col_widths, repeatRows=1)
        
        # Style the table
        table_style = TableStyle([
            # Header style
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            # Data rows - numbers right aligned
            ('ALIGN', (2, 1), (3, -1), 'RIGHT'),
            # Grid style
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            # Enhanced cell padding for better spacing
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            # Alternating row colors
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgrey]),
            # Extra - adjust vertical alignment
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
        ])
        
        area_loss_table.setStyle(table_style)
        story.append(area_loss_table)
        
        # Build the document
        doc.build(story)
        return True
        
    except Exception as e:
        print(f"{Fore.RED}Error generating area loss report PDF: {e}{Style.RESET_ALL}")
        import traceback
        traceback.print_exc()
        return False