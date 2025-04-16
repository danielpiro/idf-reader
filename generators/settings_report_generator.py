from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER

def wrap_text(text, style):
    """Helper function to wrap text for proper display in cells"""
    # Handle monthly data tables in ground temperature values
    if isinstance(text, str) and ("Jan" in text or "Feb" in text) and ("18.00" in text or any(month in text for month in ["Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])):
        # Format monthly data into a table-like structure with more line breaks
        lines = text.split('\n')
        result = ""
        for line in lines:
            # Add more breaks for monthly data
            line = line.replace("Jan ", "Jan<br/>").replace("Feb ", "Feb<br/>")
            line = line.replace("Mar ", "Mar<br/>").replace("Apr ", "Apr<br/>")
            line = line.replace("May ", "May<br/>").replace("Jun ", "Jun<br/>")
            line = line.replace("Jul ", "Jul<br/>").replace("Aug ", "Aug<br/>")
            line = line.replace("Sep ", "Sep<br/>").replace("Oct ", "Oct<br/>")
            line = line.replace("Nov ", "Nov<br/>").replace("Dec ", "Dec<br/>")
            result += line + "<br/>"
        return Paragraph(result, style)
    
    # Regular text wrapping for other content
    modified_text = str(text).replace('\n', '<br/>')
    return Paragraph(modified_text, style)

def generate_settings_report_pdf(settings_data, output_filename="output/settings.pdf"):
    """
    Generates a PDF report showing all extracted settings organized by category.

    Args:
        settings_data (dict): Dictionary of settings organized by category
                            {category: {setting_key: value}}
        output_filename (str): The name of the output PDF file.
    """
    # Use landscape orientation for more width to display tables
    doc = SimpleDocTemplate(output_filename, 
                           pagesize=landscape(A4),
                           leftMargin=1.5*cm,
                           rightMargin=1.5*cm,
                           topMargin=1.5*cm,
                           bottomMargin=1.5*cm)
    
    styles = getSampleStyleSheet()
    story = []

    # Add title with improved styling
    title_style = ParagraphStyle(
        name='CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        alignment=TA_CENTER,
        textColor=colors.navy,
        spaceBefore=0.5*cm,
        spaceAfter=1*cm
    )
    title = Paragraph("Energy Plus Settings Summary", title_style)
    story.append(title)

    # Create custom styles for cells with better wrapping
    header_style = ParagraphStyle(
        name='TableHeader',
        parent=styles['Normal'],
        fontSize=10,
        leading=12,
        fontName='Helvetica-Bold',
        alignment=TA_CENTER,
        textColor=colors.black
    )
    
    key_cell_style = ParagraphStyle(
        name='KeyCell',
        parent=styles['Normal'],
        fontSize=9,
        leading=11,
        spaceBefore=4,
        spaceAfter=4,
        wordWrap='CJK',  # Better word wrapping
        alignment=TA_LEFT
    )
    
    value_cell_style = ParagraphStyle(
        name='ValueCell',
        parent=styles['Normal'],
        fontSize=9,
        leading=11,
        spaceBefore=4,
        spaceAfter=4,
        wordWrap='CJK',  # Better word wrapping
        alignment=TA_LEFT
    )

    # Process each category
    for category, settings in settings_data.items():
        # Add category header with improved styling
        category_style = ParagraphStyle(
            name='CategoryHeader',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.darkblue,
            spaceBefore=0.5*cm,
            spaceAfter=0.3*cm
        )
        story.append(Paragraph(category, category_style))

        # Prepare table data for this category
        table_data = [
            [Paragraph('Setting', header_style), Paragraph('Value', header_style)]  # Styled header row
        ]

        # Add settings with properly wrapped text
        for key, value in settings.items():
            key_para = wrap_text(key, key_cell_style)
            value_para = wrap_text(value, value_cell_style)
            table_data.append([key_para, value_para])

        # Calculate column widths - give more space to values with complex data
        col_widths = [doc.width * 0.30, doc.width * 0.70]  # 30% for key, 70% for value

        # Define table style with improved readability
        style = TableStyle([
            # Header styles
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            
            # Data row styles
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('VALIGN', (0, 1), (-1, -1), 'TOP'),  # Align to top for multi-line content
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),
            ('ALIGN', (1, 1), (1, -1), 'LEFT'),
            
            # Cell padding for data rows
            ('LEFTPADDING', (0, 1), (-1, -1), 6),
            ('RIGHTPADDING', (0, 1), (-1, -1), 6),
            ('TOPPADDING', (0, 1), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
            
            # Grid and borders
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            
            # Alternate row colors for readability
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.whitesmoke])
        ])

        # Create and style the table
        table = Table(table_data, colWidths=col_widths, repeatRows=1)
        table.setStyle(style)
        story.append(table)
        story.append(Spacer(1, 0.8*cm))

    # Build PDF
    try:
        doc.build(story)
        print(f"Successfully generated settings report: {output_filename}")
        return True
    except Exception as e:
        print(f"Error building settings report PDF {output_filename}: {e}")
        import traceback
        traceback.print_exc()  # Enable traceback for better debugging
        return False