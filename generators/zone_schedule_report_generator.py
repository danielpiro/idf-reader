from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.units import cm
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib import colors

def generate_schedules_report_pdf(schedules_by_zone, output_filename="output/schedules.pdf"):
    """
    Generates a PDF report showing schedules used in each zone.

    Args:
        schedules_by_zone (dict): Dictionary mapping zone IDs to sets of schedule names
                                 {zone_id: set(schedule_names)}
        output_filename (str): The name of the output PDF file.
    """
    if SimpleDocTemplate is None:
        print("Cannot generate PDF because reportlab is not installed.")
        return False

    doc = SimpleDocTemplate(output_filename, pagesize=landscape(A4))
    styles = getSampleStyleSheet()
    story = []

    # Add title
    title = Paragraph("Zone Schedules Summary", styles['h1'])
    story.append(title)
    story.append(Spacer(1, 0.5*cm))

    # Prepare table data
    table_data = [
        ['Zone', 'Associated Schedules']  # Header row
    ]

    # Add data rows
    for zone_id in sorted(schedules_by_zone.keys()):
        schedules = sorted(schedules_by_zone[zone_id])
        schedule_text = '\n'.join(schedules)
        table_data.append([zone_id, schedule_text])

    # Calculate column widths
    col_widths = [doc.width * 0.3, doc.width * 0.7]  # 30% for zone, 70% for schedules

    # Define table style
    style = TableStyle([
        # Header styles
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        
        # Data styles
        ('BACKGROUND', (0, 1), (-1, -1), colors.whitesmoke),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('ALIGN', (0, 1), (0, -1), 'LEFT'),  # Left align zone IDs
        ('ALIGN', (1, 1), (1, -1), 'LEFT'),  # Left align schedules
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        
        # Grid
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
    ])

    # Create and style the table
    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    table.setStyle(style)
    story.append(table)

    # Build PDF
    try:
        doc.build(story)
        print(f"Successfully generated schedules report: {output_filename}")
        return True
    except Exception as e:
        print(f"Error building schedules report PDF {output_filename}: {e}")
        return False