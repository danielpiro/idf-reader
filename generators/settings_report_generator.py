from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, inch # Import inch
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER
import datetime # Add datetime import

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

def generate_settings_report_pdf(settings_data, output_filename="output/settings.pdf",
                                 project_name: str = "N/A", run_id: str = "N/A"):
    """
    Generates a PDF report showing all extracted settings, including a header.

    Args:
        settings_data (dict): Dictionary of settings organized by category.
        output_filename (str): The name of the output PDF file.
        project_name (str): Name of the project.
        run_id (str): Identifier for the current run.
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

    # Header Information
    now = datetime.datetime.now()
    header_style = ParagraphStyle(
        'HeaderInfo',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.black, # Changed from darkgrey to black
        alignment=2 # Right aligned
    )
    header_text = f"""
    Project: {project_name}<br/>
    Run ID: {run_id}<br/>
    Date: {now.strftime('%Y-%m-%d %H:%M:%S')}<br/>
    Report: Settings Summary
    """
    story.append(Paragraph(header_text, header_style))
    story.append(Spacer(1, 5)) # Add some space after header

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

    # Function to format dictionary values
    def format_dict_value(value_dict):
        if not value_dict:
            return "Not specified"
        
        # Monthly temperature values (ground temps, reflectance)
        if isinstance(value_dict, dict) and any(key in ['January', 'February', 'March'] for key in value_dict.keys()):
            formatted_lines = []
            # Sort months in calendar order
            month_order = [
                'January', 'February', 'March', 'April', 'May', 'June',
                'July', 'August', 'September', 'October', 'November', 'December'
            ]
            for month in month_order:
                if month in value_dict:
                    formatted_lines.append(f"{month}: {value_dict[month]}")
            return "<br/>".join(formatted_lines)
            
        # For RunPeriod nested data
        if isinstance(value_dict, dict) and any(key in ['start_month', 'end_month', 'location'] for key in value_dict.keys()):
            formatted_lines = []
            # Format start/end dates
            if 'start_month' in value_dict and 'start_day' in value_dict:
                formatted_lines.append(f"Start Date: {value_dict['start_month']}/{value_dict['start_day']}")
            if 'end_month' in value_dict and 'end_day' in value_dict:
                formatted_lines.append(f"End Date: {value_dict['end_month']}/{value_dict['end_day']}")
            if 'location' in value_dict:
                formatted_lines.append(f"Location: {value_dict['location']}")
                
            # Format weather options
            for k, v in value_dict.items():
                if k not in ['start_month', 'start_day', 'end_month', 'end_day', 'location'] and v is not None:
                    formatted_name = k.replace('_', ' ').title()
                    formatted_lines.append(f"{formatted_name}: {v}")
                    
            return "<br/>".join(formatted_lines)
            
        # For daylight saving
        if isinstance(value_dict, dict) and any(key in ['start', 'end'] for key in value_dict.keys()):
            formatted_lines = []
            if 'start' in value_dict:
                formatted_lines.append(f"Start: {value_dict['start']}")
            if 'end' in value_dict:
                formatted_lines.append(f"End: {value_dict['end']}")
            return "<br/>".join(formatted_lines)
            
        # For snow modifiers
        if isinstance(value_dict, dict) and any(key in ['ground', 'daylighting'] for key in value_dict.keys()):
            formatted_lines = []
            if 'ground' in value_dict:
                formatted_lines.append(f"Ground Reflected: {value_dict['ground']}")
            if 'daylighting' in value_dict:
                formatted_lines.append(f"Daylighting: {value_dict['daylighting']}")
            return "<br/>".join(formatted_lines)
            
        # Default formatting for other dictionary values
        return "<br/>".join([f"{k}: {v}" for k, v in value_dict.items()])

# --- Add DesignBuilder Metadata Section ---
    if 'designbuilder' in settings_data:
        designbuilder_data = settings_data.pop('designbuilder') # Extract and remove
        if designbuilder_data and any(designbuilder_data.values()):
            story.append(Paragraph("DesignBuilder Metadata", ParagraphStyle(name='CategoryHeader', parent=styles['Heading2'], fontSize=14, textColor=colors.darkblue, spaceBefore=0.5*cm, spaceAfter=0.3*cm)))

            db_table_data = [
                [Paragraph('Parameter', header_style), Paragraph('Value', header_style)]
            ]
            db_param_map = {
                'version': "DesignBuilder Version",
                'date': "File Generation Date",
                'time': "File Generation Time",
                'geometry_convention': "Geometry Convention",
                'zone_geometry_surface_areas': "Zone Geometry Surface Areas",
                'zone_volume_calculation': "Zone Volume Calculation",
                'zone_floor_area_calculation': "Zone Floor Area Calculation",
                'window_wall_ratio': "Window to Wall Ratio Method"
            }

            for key, display_name in db_param_map.items():
                value = designbuilder_data.get(key)
                if value is not None and value != '':
                    db_table_data.append([
                        Paragraph(display_name, key_cell_style),
                        Paragraph(str(value), value_cell_style)
                    ])

            if len(db_table_data) > 1: # Only add table if there's data
                db_col_widths = [doc.width * 0.30, doc.width * 0.70]
                db_table_style = TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                    ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                    ('TOPPADDING', (0, 0), (-1, 0), 8),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                    ('VALIGN', (0, 1), (-1, -1), 'TOP'),
                    ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
                    ('LEFTPADDING', (0, 1), (-1, -1), 6),
                    ('RIGHTPADDING', (0, 1), (-1, -1), 6),
                    ('TOPPADDING', (0, 1), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('BOX', (0, 0), (-1, -1), 1, colors.black),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.whitesmoke])
                ])
                db_table = Table(db_table_data, colWidths=db_col_widths, repeatRows=1)
                db_table.setStyle(db_table_style)
                story.append(db_table)
                story.append(Spacer(1, 0.8*cm))
            else:
                 story.append(Paragraph("No DesignBuilder metadata found.", value_cell_style))
                 story.append(Spacer(1, 0.8*cm))
        else:
            story.append(Paragraph("No DesignBuilder metadata found.", value_cell_style))
            story.append(Spacer(1, 0.8*cm))
    # --- End DesignBuilder Metadata Section ---
    # Process each category
    for category_name, settings in settings_data.items():
        # Capitalize category name for display
        display_category = category_name.replace('_', ' ').title()
        
        # Add category header with improved styling
        category_style = ParagraphStyle(
            name='CategoryHeader',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.darkblue,
            spaceBefore=0.5*cm,
            spaceAfter=0.3*cm
        )
        story.append(Paragraph(display_category, category_style))

        # Prepare table data for this category
        table_data = [
            [Paragraph('Setting', header_style), Paragraph('Value', header_style)]  # Styled header row
        ]

        # Add settings with properly wrapped text
        for key, value in settings.items():
            # Format the key for display
            display_key = key.replace('_', ' ').title()
            
            # Format different types of values
            if isinstance(value, dict):
                # Handle nested dictionary values
                formatted_value = format_dict_value(value)
                value_para = Paragraph(formatted_value, value_cell_style)
            elif value is None:
                # Handle None values
                value_para = Paragraph("Not specified", value_cell_style)
            else:
                # Handle regular values
                value_para = Paragraph(str(value), value_cell_style)
                
            key_para = Paragraph(display_key, key_cell_style)
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