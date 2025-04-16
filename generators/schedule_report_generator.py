from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.lib.colors import navy, black, grey, lightgrey

def generate_schedules_report_pdf(schedule_data, output_filename="output/schedules.pdf"):
    """
    Generates a PDF report containing schedule definitions in a table format.

    Args:
        schedule_data (list): List of unique parsed schedule dictionaries.
        output_filename (str): The name of the output PDF file.
    """
    if canvas is None:
        print("Cannot generate PDF because reportlab is not installed.")
        return False

    c = canvas.Canvas(output_filename, pagesize=A4)
    width, height = A4
    margin_x = 2 * cm
    margin_y = 2 * cm
    content_width = width - 2 * margin_x
    current_y = height - margin_y

    # Styles
    styles = getSampleStyleSheet()
    title_style = styles['h1']
    title_style.textColor = navy
    section_title_style = styles['h2']
    section_title_style.spaceBefore = 0.5 * cm
    section_title_style.spaceAfter = 0.3 * cm
    schedule_name_style = ParagraphStyle(
        name='ScheduleName', parent=styles['Normal'], fontName='Helvetica-Bold',
        spaceBefore = 0.4*cm, spaceAfter=0.1*cm
    )
    not_found_style = ParagraphStyle(
        name='NotFound', parent=styles['Normal'], fontName='Helvetica-Oblique',
        textColor=grey, leftIndent=0.5*cm, spaceAfter=0.4*cm
    )

    # --- Title ---
    title_text = "IDF Unique Schedule Definitions"
    p_title = Paragraph(title_text, title_style)
    p_title.wrapOn(c, content_width, margin_y)
    title_height = p_title.height
    p_title.drawOn(c, margin_x, current_y - title_height)
    current_y -= (title_height + 1 * cm)

    # --- Schedule Timelines Section ---
    if not schedule_data:
        p_empty = Paragraph("No relevant schedules found or extracted.", styles['Normal'])
        p_empty.wrapOn(c, content_width, margin_y)
        p_empty.drawOn(c, margin_x, current_y - p_empty.height)
        # Save the PDF even if empty
        try:
            c.save()
            print(f"Generated empty schedules report: {output_filename}")
            return True
        except Exception as e:
            print(f"Error saving empty schedules PDF file {output_filename}: {e}")
            return False

    # Define table style
    table_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), lightgrey),  # Header row background
        ('TEXTCOLOR', (0, 0), (-1, 0), black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),  # Header font
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('BACKGROUND', (0, 1), (-1, -1), '#EEEEEE'),  # Body row background
        ('GRID', (0, 0), (-1, -1), 0.5, grey),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ])

    # Use normal style for table cell text
    cell_style = styles['Code']  # Use a monospaced font style
    cell_style.fontSize = 8
    cell_style.leading = 10

    try:
        for schedule in schedule_data:
            schedule_type = schedule.get('type', 'Unknown Type')
            if ("activity" in schedule_type.lower() or "clothing" in schedule_type.lower()):
                schedule_type = schedule_type.split(" ")[0] + " Schedule"
            elif ("heating" in schedule_type.lower() or "cooling" in schedule_type.lower()):
                schedule_type = schedule_type.split(" ")[1] + " " + schedule_type.split(" ")[2] + " Schedule"
            raw_rules = schedule.get('raw_rules', [])

            # Draw Schedule Name and Type
            name_text = f"Schedule: {schedule_type}"
            p_sched_name = Paragraph(name_text, schedule_name_style)
            p_sched_name.wrapOn(c, content_width, margin_y)
            name_height = p_sched_name.height

            # Prepare data for the table - just one column with the raw rules
            table_data = [["Rule Field"]]  # Header
            table_data.extend([[Paragraph(rule, cell_style)] for rule in raw_rules])

            # Create and style the table
            schedule_table = Table(table_data, colWidths=[content_width])
            schedule_table.setStyle(table_style)

            # Calculate table height
            table_width_actual, table_height = schedule_table.wrapOn(c, content_width, margin_y)

            # Check for page break before drawing name + table
            total_element_height = name_height + schedule_name_style.spaceAfter + table_height + 1*cm
            if current_y - total_element_height < margin_y:
                c.showPage()
                current_y = height - margin_y

            # Draw name
            p_sched_name.drawOn(c, margin_x, current_y - name_height)
            current_y -= (name_height + schedule_name_style.spaceAfter)

            # Draw table
            schedule_table.drawOn(c, margin_x, current_y - table_height)
            current_y -= (table_height + 1*cm)  # Add space after table

        # Save the Schedules PDF
        c.save()
        print(f"Successfully generated schedules report: {output_filename}")
        return True

    except Exception as e:
        print(f"Error generating or saving schedules PDF file {output_filename}: {e}")
        return False