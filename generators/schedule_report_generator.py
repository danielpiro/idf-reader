from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph, Table, TableStyle # Re-added Table, TableStyle
from reportlab.lib import colors # Import colors module
from reportlab.lib.colors import navy, black, grey, lightgrey, white # Removed unused colors

# --- Helper Functions (Removed timeline helpers) ---

# --- Table Creation Function ---

def create_hourly_schedule_table(rule_blocks: list, available_width: float) -> Table:
    """
    Creates a ReportLab Table object for displaying hourly schedule values.

    Args:
        rule_blocks: List of rule block dictionaries from the parser.
                     Each dict has 'through', 'for_days', 'hourly_values'.
        available_width: The width available for the table.

    Returns:
        A ReportLab Table object, or None if rule_blocks is empty.
    """
    if not rule_blocks:
        return None

    # Define column widths to match reference structure (Period + 24 hours)
    # Adjust column widths again for better fit, make first column wider
    period_col_width = 3.5 * cm
    num_hour_cols = 24
    # Calculate width for each hourly column
    hour_col_width = (available_width - period_col_width) / num_hour_cols

    col_widths = [period_col_width] + [hour_col_width] * num_hour_cols

    # Prepare table data - matching reference structure
    # Using a placeholder "Period" label, actual content from 'For:' field
    # Update header to match reference (using double backslash for literal)
    header = ["Months/Hours"] + [str(h+1) for h in range(num_hour_cols)] # Hours 1-24
    table_data = [header]

    # Use a base style for cells, can be overridden by TableStyle
    cell_style = getSampleStyleSheet()['Normal']
    cell_style.fontSize = 7
    cell_style.alignment = 1 # Center

    for block in rule_blocks:
        # Use cleaned 'Through:' field as the period identifier
        period_text = block.get('through', '').replace('Through:', '').strip()
        hourly_values = block.get('hourly_values', [''] * num_hour_cols) # Ensure 24 values

        # Create row data with period identifier + 24 hourly values
        # Using raw strings for simplicity as requested
        row_data = [period_text] + [str(val) if val is not None else '' for val in hourly_values]
        table_data.append(row_data)

    # Create TableStyle - simplified to match reference structure (no background colors)
    style = TableStyle([
        # ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey), # REMOVED Header background
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),     # Header text color (keep)
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),           # Center align all cells
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),          # Middle align all cells
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), # Header font bold
        ('FONTSIZE', (0, 0), (-1, -1), 7),               # General font size
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),           # Header bottom padding
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),    # Grid lines (keep)
        # ('BACKGROUND', (0, 1), (0, -1), colors.Color(red=(220/255), green=(240/255), blue=(220/255))), # REMOVED First column background
    ])

    # Remove alternating row color logic
    # for i, row in enumerate(table_data):
    #     if i % 2 == 0 and i != 0:
    #          style.add('BACKGROUND', (0, i), (-1, i), colors.whitesmoke)


    # Create Table
    schedule_table = Table(table_data, colWidths=col_widths)
    schedule_table.setStyle(style)

    return schedule_table


# --- Main PDF Generation Function ---

def generate_schedules_report_pdf(schedule_data, output_filename="output/schedules.pdf"):
    """
    Generates a PDF report containing schedule definitions visualized as hourly tables.

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

    # Removed timeline settings

    space_after_table = 0.8 * cm

    try:
        for schedule in schedule_data:
            schedule_type = schedule.get('type', 'Unknown Type')
            # Keep type normalization logic
            if ("activity" in schedule_type.lower() or "clothing" in schedule_type.lower()):
                 schedule_type = schedule_type.split(" ")[0] + " Schedule"
            elif ("heating" in schedule_type.lower() or "cooling" in schedule_type.lower()):
                 schedule_type = schedule_type.split(" ")[1] + " " + schedule_type.split(" ")[2] + " Schedule"

            rule_blocks = schedule.get('rule_blocks', []) # Get the parsed hourly data

            # Draw Schedule Name and Type
            name_text = f"Schedule: {schedule_type} (Name: {schedule.get('name', 'N/A')})" # Include original name
            p_sched_name = Paragraph(name_text, schedule_name_style)
            p_sched_name.wrapOn(c, content_width, margin_y)
            name_height = p_sched_name.height

            # Create the hourly table for this schedule
            schedule_table = create_hourly_schedule_table(rule_blocks, content_width)

            if schedule_table:
                # Calculate table height
                table_width_actual, table_height = schedule_table.wrapOn(c, content_width, margin_y)

                # Calculate total height needed for name + table + spacing
                total_element_height = name_height + schedule_name_style.spaceAfter + table_height + space_after_table

                # Check for page break before drawing name + table
                if current_y - total_element_height < margin_y:
                    c.showPage()
                    current_y = height - margin_y # Reset Y to top margin

                # Draw name
                p_sched_name.drawOn(c, margin_x, current_y - name_height)
                current_y -= (name_height + schedule_name_style.spaceAfter)

                # Draw table
                schedule_table.drawOn(c, margin_x, current_y - table_height)
                current_y -= (table_height + space_after_table) # Add space after table
            else:
                 # Handle case where table couldn't be created (e.g., no rule blocks)
                 # Check for page break just for the name
                 if current_y - (name_height + schedule_name_style.spaceAfter + 1*cm) < margin_y:
                     c.showPage()
                     current_y = height - margin_y
                 # Draw name
                 p_sched_name.drawOn(c, margin_x, current_y - name_height)
                 current_y -= (name_height + schedule_name_style.spaceAfter)
                 # Draw a note that no data was available for table
                 p_no_data = Paragraph("No rule data available to generate hourly table.", not_found_style)
                 p_no_data.wrapOn(c, content_width, margin_y)
                 p_no_data.drawOn(c, margin_x, current_y - p_no_data.height)
                 current_y -= (p_no_data.height + space_after_table)


        # Save the Schedules PDF
        c.save()
        print(f"Successfully generated schedules report: {output_filename}")
        return True

    except Exception as e:
        print(f"Error generating or saving schedules PDF file {output_filename}: {e}")
        return False