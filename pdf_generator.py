import os # For deleting temp files
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle # Added Table, TableStyle, removed Image
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.colors import navy, black, grey, blue, lightgrey
    from reportlab.lib.styles import ParagraphStyle # For custom styles
    # from timeline_plotter import plot_schedule_timeline # No longer needed
except ImportError:
    print("Error: reportlab library not found.")
    print("Please install it using: pip install reportlab")
    # You might want to exit or raise an error here depending on desired behavior
    # For now, we'll let it fail later if the user tries to run without it.
    canvas = None # Prevent further errors in this script if not imported

# Function to generate the settings PDF
def generate_settings_pdf(settings_data, output_filename="settings.pdf"):
    """
    Generates a PDF report from the extracted settings data.

    Args:
        settings_data (dict): Dictionary of extracted settings.
        output_filename (str): The name of the output PDF file.
    """
    if canvas is None:
        print("Cannot generate PDF because reportlab is not installed.")
        return False # Indicate failure

    c = canvas.Canvas(output_filename, pagesize=A4)
    width, height = A4 # width=21*cm, height=29.7*cm

    # Define margins
    margin_x = 2 * cm
    margin_y = 2 * cm
    content_width = width - 2 * margin_x
    current_y = height - margin_y

    # Styles
    styles = getSampleStyleSheet()
    title_style = styles['h1']
    title_style.textColor = navy
    section_title_style = styles['h2'] # Style for section titles
    section_title_style.spaceBefore = 0.5 * cm
    section_title_style.spaceAfter = 0.3 * cm
    schedule_name_style = ParagraphStyle( # Style for schedule names above plots
        name='ScheduleName',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        spaceBefore = 0.4*cm,
        spaceAfter=0.1*cm
    )
    # Custom Styles for better formatting
    setting_key_style = ParagraphStyle(
        name='SettingKey',
        parent=styles['Heading3'], # Inherit from H3
        fontName='Helvetica-Bold', # Make key bold
        spaceAfter=0.1*cm # Less space after key
    )
    setting_value_style = ParagraphStyle(
        name='SettingValue',
        parent=styles['Normal'],
        leftIndent=0.5*cm, # Indent normal values slightly
        spaceAfter=0.4*cm # Space after each setting block
    )
    setting_list_item_style = ParagraphStyle(
        name='SettingListItem',
        parent=styles['Normal'],
        leftIndent=1.0*cm, # Indent list items more
        spaceAfter=0.1*cm # Less space between list items
    )
    not_found_style = ParagraphStyle(
        name='NotFound',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique', # Italicize
        textColor=grey,
        leftIndent=0.5*cm,
        spaceAfter=0.4*cm
    )

    # --- Title ---
    title_text = "IDF Settings Report"
    p_title = Paragraph(title_text, title_style)
    p_title.wrapOn(c, content_width, margin_y) # Calculate height
    title_height = p_title.height
    p_title.drawOn(c, margin_x, current_y - title_height)
    current_y -= (title_height + 1 * cm) # Add extra space after title

    # --- Settings Data by Category ---
    for category, settings in settings_data.items():
        # Draw Category Header
        category_style = ParagraphStyle(
            'Category',
            parent=styles['Heading2'],
            textColor=navy,
            spaceBefore=1*cm,
            spaceAfter=0.5*cm,
            borderPadding=10,
            borderWidth=1,
            borderColor=navy,
            backColor=lightgrey
        )
        
        p_category = Paragraph(category, category_style)
        p_category.wrapOn(c, content_width, margin_y)
        category_height = p_category.height

        # Check for page break before category
        if current_y - category_height < margin_y:
            c.showPage()
            current_y = height - margin_y

        p_category.drawOn(c, margin_x, current_y - category_height)
        current_y -= (category_height + category_style.spaceAfter)

        # Process settings in this category
        for key, value in settings.items():
            # Draw Setting Key
            clean_key = key.replace(":", ": ")
            p_key = Paragraph(clean_key, setting_key_style)
            p_key.wrapOn(c, content_width, margin_y)
            key_height = p_key.height

            if current_y - key_height < margin_y:
                c.showPage()
                current_y = height - margin_y

            p_key.drawOn(c, margin_x, current_y - key_height)
            current_y -= key_height

            # Handle different value formats
            if value == "Not Found":
                p_value = Paragraph("<i>Not Found</i>", not_found_style)
                value_width = content_width - not_found_style.leftIndent
                p_value.wrapOn(c, value_width, margin_y)
                value_height = p_value.height

                if current_y - value_height < margin_y:
                    c.showPage()
                    current_y = height - margin_y
                    p_key.drawOn(c, margin_x, current_y - key_height)
                    current_y -= key_height

                p_value.drawOn(c, margin_x + not_found_style.leftIndent, current_y - value_height)
                current_y -= (value_height + not_found_style.spaceAfter)

            elif "\n" in str(value):
                # Handle multi-line formatted values (like temperature data)
                lines = value.split("\n")
                for line in lines:
                    if not line.strip():
                        current_y -= 0.2 * cm  # Add small space for empty lines
                        continue
                        
                    p_line = Paragraph(line, setting_value_style)
                    p_line.wrapOn(c, content_width - setting_value_style.leftIndent, margin_y)
                    line_height = p_line.height

                    if current_y - line_height < margin_y:
                        c.showPage()
                        current_y = height - margin_y

                    p_line.drawOn(c, margin_x + setting_value_style.leftIndent, current_y - line_height)
                    current_y -= (line_height + 0.1 * cm)  # Small space between lines

                current_y -= setting_value_style.spaceAfter  # Add final spacing after multi-line block

            else:
                # Handle regular string values
                value_text = value if value else "<i>(Empty value)</i>"
                p_value = Paragraph(value_text, setting_value_style)
                p_value.wrapOn(c, content_width - setting_value_style.leftIndent, margin_y)
                value_height = p_value.height

                if current_y - value_height < margin_y:
                    c.showPage()
                    current_y = height - margin_y
                    p_key.drawOn(c, margin_x, current_y - key_height)
                    current_y -= key_height

                p_value.drawOn(c, margin_x + setting_value_style.leftIndent, current_y - value_height)
                current_y -= (value_height + setting_value_style.spaceAfter)

        # Spacing is now handled by the spaceAfter property of the paragraph styles

    # Save the Settings PDF
    try:
        c.save()
        print(f"Successfully generated settings report: {output_filename}")
        return True # Indicate success
    except Exception as e:
        print(f"Error saving settings PDF file {output_filename}: {e}")
        return False # Indicate failure
    # Note: No finally block needed here as no temp files are created

# Function to generate the schedules PDF
def generate_schedules_pdf(schedule_data, output_filename="schedules.pdf"):
    """
    Generates a PDF report containing schedule definitions in a table format.

    Args:
        schedule_data (list): List of unique parsed schedule dictionaries.
        output_filename (str): The name of the output PDF file.
    """
    if canvas is None:
        print("Cannot generate PDF because reportlab is not installed.")
        return False
    # Removed matplotlib check as it's no longer used

    c = canvas.Canvas(output_filename, pagesize=A4)
    width, height = A4
    margin_x = 2 * cm
    margin_y = 2 * cm
    content_width = width - 2 * margin_x
    current_y = height - margin_y

    # Styles (redefine or reuse styles as needed)
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
    not_found_style = ParagraphStyle( # For plot errors
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

    # Proceed if there is schedule data
    # Define table style
    table_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), lightgrey), # Header row background
        ('TEXTCOLOR', (0, 0), (-1, 0), black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), # Header font
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('BACKGROUND', (0, 1), (-1, -1), '#EEEEEE'), # Body row background
        ('GRID', (0, 0), (-1, -1), 0.5, grey),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ])
    # Use normal style for table cell text
    cell_style = styles['Code'] # Use a monospaced font style if available
    cell_style.fontSize = 8
    cell_style.leading = 10

    try: # Wrap table generation in try block
        for schedule in schedule_data:
            schedule_name = schedule.get('name', 'Unknown Schedule')
            schedule_type = schedule.get('type', 'Unknown Type')
            raw_rules = schedule.get('raw_rules', [])

            # Draw Schedule Name and Type
            name_text = f"Schedule: {schedule_name} (Type: {schedule_type})"
            p_sched_name = Paragraph(name_text, schedule_name_style)
            p_sched_name.wrapOn(c, content_width, margin_y)
            name_height = p_sched_name.height

            # Prepare data for the table - just one column with the raw rules
            # Wrap each rule line in a Paragraph for better line breaking within cells
            table_data = [["Rule Field"]] # Header
            table_data.extend([[Paragraph(rule, cell_style)] for rule in raw_rules])

            # Create and style the table
            schedule_table = Table(table_data, colWidths=[content_width]) # Single column spanning content width
            schedule_table.setStyle(table_style)

            # Calculate table height
            table_width_actual, table_height = schedule_table.wrapOn(c, content_width, margin_y)

            # Check for page break before drawing name + table
            total_element_height = name_height + schedule_name_style.spaceAfter + table_height + 1*cm # Add space after table
            if current_y - total_element_height < margin_y:
                c.showPage()
                current_y = height - margin_y

            # Draw name
            p_sched_name.drawOn(c, margin_x, current_y - name_height)
            current_y -= (name_height + schedule_name_style.spaceAfter)

            # Draw table
            schedule_table.drawOn(c, margin_x, current_y - table_height)
            current_y -= (table_height + 1*cm) # Add space after table

        # Save the Schedules PDF
        c.save()
        print(f"Successfully generated schedules report: {output_filename}")
        return True # Indicate success

    except Exception as e:
        print(f"Error generating or saving schedules PDF file {output_filename}: {e}")
        return False # Indicate failure
    # No finally block needed as no temp files are created


if __name__ == '__main__':
    # Example usage for testing separate reports
    print("pdf_generator.py executed directly (intended for import).")
    # Example data
    test_settings = {"Version": ["9.5"], "Timestep": ["4"]}
    test_schedules = [
        {'name': 'Test Heating Schedule', 'type': 'Temperature',
         'raw_rules': ['Through: 31 Mar', 'For: AllDays', 'Until: 24:00, 20',
                       'Through: 30 Sep', 'For: AllDays', 'Until: 24:00, 18',
                       'Through: 31 Dec', 'For: AllDays', 'Until: 24:00, 21']},
        {'name': 'Test Lighting Schedule', 'type': 'Fraction',
         'raw_rules': ['Through: 31 Dec', 'For: Weekdays', 'Until: 08:00, 0.1', 'Until: 18:00, 0.9', 'Until: 24:00, 0.1',
                       'For: Weekends', 'Until: 24:00, 0.05']}
    ]
    print("Generating example separate PDF reports...")
    # No longer need matplotlib check here
    generate_settings_pdf(test_settings, "example_settings_report.pdf")
    generate_schedules_pdf(test_schedules, "example_schedules_report.pdf") # Test table generation