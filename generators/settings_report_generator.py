from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.units import cm
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors

def generate_settings_report_pdf(settings_data, output_filename="output/settings.pdf"):
    """
    Generates a PDF report showing all extracted settings organized by category.

    Args:
        settings_data (dict): Dictionary of settings organized by category
                            {category: {setting_key: value}}
        output_filename (str): The name of the output PDF file.
    """
    if SimpleDocTemplate is None:
        print("Cannot generate PDF because reportlab is not installed.")
        return False

    doc = SimpleDocTemplate(output_filename, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    # Add title
    title = Paragraph("Energy Plus Settings Summary", styles['h1'])
    story.append(title)
    story.append(Spacer(1, 0.5*cm))

    # Create a custom style for multi-line cell content
    styles.add(ParagraphStyle(
        name='TableCell',
        parent=styles['Normal'],
        fontSize=9,
        leading=11,
        spaceBefore=6,
        spaceAfter=6
    ))

    # Process each category
    for category, settings in settings_data.items():
        # Add category header
        story.append(Paragraph(category, styles['h2']))
        story.append(Spacer(1, 0.3*cm))

        # Prepare table data for this category
        table_data = [
            ['Setting', 'Value']  # Header row
        ]

        # Add settings
        for key, value in settings.items():
            # Convert value to Paragraph for proper multi-line display
            value_para = Paragraph(value.replace('\n', '<br/>'), styles['TableCell'])
            table_data.append([key, value_para])

        # Calculate column widths
        col_widths = [doc.width * 0.35, doc.width * 0.65]  # 35% for key, 65% for value

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
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),  # Left align keys
            ('ALIGN', (1, 1), (1, -1), 'LEFT'),  # Left align values
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
        story.append(Spacer(1, 0.5*cm))

    # Build PDF
    try:
        doc.build(story)
        print(f"Successfully generated settings report: {output_filename}")
        return True
    except Exception as e:
        print(f"Error building settings report PDF {output_filename}: {e}")
        return False