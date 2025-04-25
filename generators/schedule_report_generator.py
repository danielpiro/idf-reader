from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph, Table, TableStyle # Re-added Table, TableStyle
from reportlab.lib import colors # Import colors module
from reportlab.lib.colors import navy, black, grey, lightgrey, white # Removed unused colors
import datetime

# --- Helper Functions ---

def parse_date_string(date_str):
    """
    Parse date string in "DD/MM" format to a datetime.date object.
    For sorting purposes, assume current year.
    """
    try:
        day, month = map(int, date_str.split('/'))
        # Use a fixed year since we're just concerned with month/day order
        return datetime.date(2000, month, day)
    except (ValueError, AttributeError):
        # Default value for invalid dates
        return datetime.date(2000, 12, 31)

def create_date_ranges(rule_blocks):
    """
    Process rule blocks to create date ranges.
    
    Transforms single dates like "31/12" into ranges like "01/01 -> 31/12"
    and connects consecutive dates.
    
    Args:
        rule_blocks: List of rule block dictionaries from the parser.
        
    Returns:
        List of rule blocks with 'through' field replaced by 'date_range'
    """
    if not rule_blocks:
        return []
        
    # Sort the blocks by their date
    sorted_blocks = sorted(rule_blocks, key=lambda block: parse_date_string(block.get('through', '31/12')))
    
    # Add a special first block for 01/01 if needed
    if sorted_blocks and sorted_blocks[0].get('through') != '01/01':
        first_date = '01/01'
    else:
        first_date = None
        
    # Create the date ranges
    result_blocks = []
    prev_date = first_date
    
    for i, block in enumerate(sorted_blocks):
        current_date = block.get('through', '31/12')
        
        # Skip if can't parse date properly
        if '/' not in current_date:
            continue
            
        # For the first block with a special start date
        if i == 0 and first_date:
            date_range = f"{first_date} -> {current_date}"
        # For subsequent blocks, use previous block's date as start
        elif i > 0:
            prev_date = sorted_blocks[i-1].get('through', '31/12')
            date_range = f"{prev_date} -> {current_date}"
        # For first block without special start
        else:
            date_range = f"01/01 -> {current_date}"
            
        # Create a new block with date range
        new_block = block.copy()
        new_block['date_range'] = date_range
        result_blocks.append(new_block)
    
    return result_blocks

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

    # Process the rule blocks to create date ranges
    rule_blocks_with_ranges = create_date_ranges(rule_blocks)
    
    # Define column widths to match reference structure (Period + 24 hours)
    # Adjust column widths for better fit
    period_col_width = 3.5 * cm  # Reduced width for date ranges to give more space to hour cells
    num_hour_cols = 24
    # Calculate width for each hourly column with more space for values
    hour_col_width = (available_width - period_col_width) / num_hour_cols

    col_widths = [period_col_width] + [hour_col_width] * num_hour_cols

    # Prepare table data - matching reference structure
    # Using a placeholder "Period" label, actual content from 'For:' field
    # Update header to match reference (using double backslash for literal)
    header = ["Date Ranges/Hours"] + [str(h+1) for h in range(num_hour_cols)] # Hours 1-24
    table_data = [header]

    # Use a base style for cells, can be overridden by TableStyle
    cell_style = getSampleStyleSheet()['Normal']
    cell_style.fontSize = 7
    cell_style.alignment = 1 # Center

    for block in rule_blocks_with_ranges:
        # Use the created date range instead of just 'through' date
        period_text = block.get('date_range', 'N/A')
        hourly_values = block.get('hourly_values', [''] * num_hour_cols) # Ensure 24 values

        # Create row data with period identifier + 24 hourly values
        row_data = [period_text] + [str(val) if val is not None else '' for val in hourly_values]
        table_data.append(row_data)

    # Add left alignment for the date column to improve readability
    style = TableStyle([
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),     # Header text color
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),           # Center align all cells
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),          # Middle align all cells
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), # Header font bold
        ('FONTSIZE', (0, 0), (-1, -1), 7),               # General font size
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),           # Header bottom padding
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),    # Grid lines
        ('ALIGN', (0, 1), (0, -1), 'LEFT'),              # Left align date column 
        ('LEFTPADDING', (0, 1), (0, -1), 6),             # Add padding for dates
        ('TOPPADDING', (1, 1), (-1, -1), 4),             # Add top padding for hour cells
        ('BOTTOMPADDING', (1, 1), (-1, -1), 4),          # Add bottom padding for hour cells
        ('LEFTPADDING', (1, 1), (-1, -1), 3),            # Add left padding for hour cells
        ('RIGHTPADDING', (1, 1), (-1, -1), 3),           # Add right padding for hour cells
    ])

    # Create Table
    schedule_table = Table(table_data, colWidths=col_widths)
    schedule_table.setStyle(style)

    return schedule_table


# --- Main PDF Generation Function ---

def generate_schedules_report_pdf(schedule_data, output_filename="output/schedules.pdf",
                                  project_name: str = "N/A", run_id: str = "N/A"):
    """
    Generates a PDF report containing schedule definitions, including a header.

    Args:
        schedule_data (list): List of unique parsed schedule dictionaries.
        output_filename (str): The name of the output PDF file.
        project_name (str): Name of the project.
        run_id (str): Identifier for the current run.
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
    header_info_style = ParagraphStyle(
        'HeaderInfo',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.black, # Changed from darkgrey to black
        alignment=2 # Right aligned
    )

    # --- Header ---
    now = datetime.datetime.now()
    header_text = f"""
    Project: {project_name}<br/>
    Run ID: {run_id}<br/>
    Date: {now.strftime('%Y-%m-%d %H:%M:%S')}<br/>
    Report: Unique Schedule Definitions
    """
    p_header = Paragraph(header_text, header_info_style)
    header_width, header_height = p_header.wrapOn(c, content_width, margin_y)
    p_header.drawOn(c, width - margin_x - header_width, height - margin_y - header_height)
    # Adjust starting Y position slightly below the header
    current_y -= (header_height + 0.2*cm)


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
            schedule_name = None
            if "activity" in schedule_type.lower() or "clothing" in schedule_type.lower() or "occupancy" in schedule_type.lower():
                schedule_name = "People"
            elif "heating" in schedule_type.lower() or "cooling" in schedule_type.lower():
                schedule_name = "Temperature"
            elif "ventilation" in schedule_type.lower():
                schedule_name = "Ventilation"
            elif "lighting" in schedule_type.lower():
                schedule_name = "Lighting"
            elif "shading" in schedule_type.lower():
                schedule_name = "Shading"
            elif "equipment" in schedule_type.lower():
                schedule_name = "Equipment"
            
            if schedule_name is not None:
                name_text = f"{schedule_type} [{schedule_name}]"
            else:
                name_text = f"{schedule_type}"
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