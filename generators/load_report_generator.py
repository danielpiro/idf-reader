"""
Generates PDF reports showing zone loads and their associated schedules.
"""
# Use platypus for automatic pagination
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, PageBreak
from reportlab.lib.pagesizes import A4, landscape, A3
from reportlab.lib.units import cm, inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import navy, black, grey, lightgrey, white
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import ast # Add import for literal_eval

def wrap_text(text, style):
    """Helper function to create wrapped text in a cell."""
    return Paragraph(str(text), style)

def create_cell_style(styles, is_header=False):
    """Create a cell style for wrapped text."""
    style = ParagraphStyle(
        'Cell',
        parent=styles['Normal'],
        fontSize=5, # Further reduced font size from 6 to 5
        leading=6, # Reduced leading accordingly
        spaceBefore=1,
        spaceAfter=1,
        fontName='Helvetica-Bold' if is_header else 'Helvetica',
        wordWrap='CJK',
        alignment=0
    )
    return style

def create_hierarchical_table_style():
    """Create table style for the main load table with hierarchical headers."""
    # Spans for the first header row (categories)
    # (start_col, start_row), (end_col, end_row)
    spans = [
        ('SPAN', (0, 0), (0, 1)),  # Zone spans both header rows
        ('SPAN', (1, 0), (3, 0)),  # Occupancy
        ('SPAN', (4, 0), (5, 0)),  # Lighting
        ('SPAN', (6, 0), (7, 0)),  # Non Fixed Equipment
        ('SPAN', (8, 0), (9, 0)),  # Fixed Equipment
        ('SPAN', (10, 0), (12, 0)), # Heating
        ('SPAN', (13, 0), (15, 0)), # Cooling
        ('SPAN', (16, 0), (17, 0)), # Infiltration
        ('SPAN', (18, 0), (19, 0))  # Ventilation
    ]

    # Basic styling + spans
    style = [
        # Header Row 1 (Categories) Styling
        ('BACKGROUND', (0, 0), (-1, 0), lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), black),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'), # Center align category headers
        ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 6), # Reduced category header font size
        ('BOTTOMPADDING', (0, 0), (-1, 0), 3), # Slightly reduce padding

        # Header Row 2 (Sub-columns) Styling
        ('BACKGROUND', (1, 1), (-1, 1), lightgrey),
        ('TEXTCOLOR', (1, 1), (-1, 1), black),
        ('ALIGN', (1, 1), (-1, 1), 'CENTER'),
        ('VALIGN', (1, 1), (-1, 1), 'MIDDLE'),
        ('FONTNAME', (1, 1), (-1, 1), 'Helvetica-Bold'),
        ('FONTSIZE', (1, 1), (-1, 1), 5), # Reduced sub-header font size
        ('TOPPADDING', (1, 1), (-1, 1), 1), # Reduce padding
        ('BOTTOMPADDING', (1, 1), (-1, 1), 1), # Reduce padding

        # Zone Header Cell Specific Styling (spanning both rows)
        ('ALIGN', (0, 0), (0, 1), 'CENTER'),
        ('VALIGN', (0, 0), (0, 1), 'MIDDLE'),

        # Data Rows Styling
        ('BACKGROUND', (0, 2), (-1, -1), white), # Data rows start from row 2
        ('TEXTCOLOR', (0, 2), (-1, -1), black),
        ('ALIGN', (0, 2), (-1, -1), 'LEFT'), # Left align data cells
        ('VALIGN', (0, 2), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 2), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 2), (-1, -1), 5), # Reduced data font size
        ('TOPPADDING', (0, 2), (-1, -1), 1), # Reduce padding
        ('BOTTOMPADDING', (0, 2), (-1, -1), 1), # Reduce padding

        # Grid lines for the entire table
        ('GRID', (0, 0), (-1, -1), 1, grey),

        # Padding for all cells
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3)
    ]

    return TableStyle(spans + style)

def extract_setpoint(schedule_values, setpoint_type, zone_name=None, all_schedules=None):
    """
    Extracts a specific setpoint value from Schedule:Compact data, considering availability.
    
    Args:
        schedule_values (list): The list of values from the Schedule:Compact object.
        setpoint_type (str): 'work' or 'non_work'.
        zone_name (str, optional): The name of the zone to get schedules for.
        all_schedules (dict, optional): Dictionary containing all schedules for the zone.
        
    Returns:
        str: The extracted setpoint value or '-' if not found/invalid.
    """
    # Check if schedule values available
    if not schedule_values:
        return '-'
        
    if not all_schedules:
        return '-'
        
    # Determine if we're working with heating or cooling setpoint
    schedule_name = all_schedules.get('name', '')
    
    is_heating = False
    is_cooling = False
    
    if 'heating' in schedule_name.lower() or 'heat' in schedule_name.lower():
        is_heating = True
    elif 'cooling' in schedule_name.lower() or 'cool' in schedule_name.lower() or 'sp sch' in schedule_name.lower():
        is_cooling = True
    
    # Find availability key by checking each key in all_schedules
    avail_key = None
    for key in all_schedules:
        if isinstance(key, str) and 'availability' in key.lower():
            if (is_heating and 'heat' in key.lower()) or (is_cooling and 'cool' in key.lower()):
                avail_key = key
                break
        
    # Find the availability schedule
    avail_schedule = None
    active_periods = []
    
    if avail_key and avail_key in all_schedules:
        avail_schedule = all_schedules[avail_key]
            
    # Process the availability schedule to find active periods
    if avail_schedule and isinstance(avail_schedule, dict) and 'schedule_values' in avail_schedule:
        avail_values = avail_schedule['schedule_values']
        
        # Track the current period being processed
        current_period = None
        for i, val in enumerate(avail_values):
            val_str = str(val).strip().lower()
            
            # Find period start
            if val_str.startswith('through:'):
                current_period = val_str.replace('through:', '').strip()
            # Find active value (1)
            elif val_str == '1' and current_period:
                # This is an active period
                active_periods.append(current_period)
    
    # Process setpoint values
    all_values = {}  # {period: {work: value, non_work: value}}
    active_values = {}  # {period: {work: value, non_work: value}}
    
    # Track the current period
    current_period = None
    for i, val in enumerate(schedule_values):
        val_str = str(val).strip().lower()
        
        # Find period start
        if val_str.startswith('through:'):
            current_period = val_str.replace('through:', '').strip()
            if current_period not in all_values:
                all_values[current_period] = {'work': None, 'non_work': None}
            
            # Check if this period is in the active periods list
            is_active = current_period in active_periods
            if is_active and current_period not in active_values:
                active_values[current_period] = {'work': None, 'non_work': None}
            
        # Find setpoint value after 'until:'
        elif current_period and val_str.startswith('until:'):
            time_str = val_str.replace('until:', '').strip()
            is_non_work = (time_str == '24:00')
            
            # Look for the temperature value (next item)
            if i+1 < len(schedule_values):
                try:
                    temp_val = float(str(schedule_values[i+1]).strip())
                    
                    # Filter appropriate temperatures based on heating/cooling
                    # For heating: keep if >= -10
                    # For cooling: keep if < 100 and > 10
                    is_valid_temp = False
                    if is_heating and temp_val >= -10:
                        is_valid_temp = True
                    elif is_cooling and temp_val < 100 and temp_val > 10:
                        is_valid_temp = True
                    
                    if is_valid_temp:
                        if is_non_work:
                            all_values[current_period]['non_work'] = temp_val
                            if current_period in active_values:
                                active_values[current_period]['non_work'] = temp_val
                        else:
                            all_values[current_period]['work'] = temp_val
                            if current_period in active_values:
                                active_values[current_period]['work'] = temp_val
                except (ValueError, TypeError):
                    pass
    
    # If we have active periods, use them for selection
    if active_values:
        # Collect all active work and non-work temps
        work_temps = []
        non_work_temps = []
        
        for period, temps in active_values.items():
            if temps['work'] is not None:
                work_temps.append(temps['work'])
            if temps['non_work'] is not None:
                non_work_temps.append(temps['non_work'])
        
        # For work setpoint (preferred)
        if setpoint_type == 'work':
            if work_temps:
                # Choose based on heating or cooling mode
                if is_heating:
                    return str(max(work_temps))  # Highest heating setpoint
                else:
                    return str(min(work_temps))  # Lowest cooling setpoint
            elif non_work_temps:
                # Fallback to non-work temps if no work temps found
                if is_heating:
                    return str(max(non_work_temps))
                else:
                    return str(min(non_work_temps))
        
        # For non-work setpoint
        elif setpoint_type == 'non_work' and non_work_temps:
            if is_heating:
                return str(max(non_work_temps))  # Highest heating setpoint
            else:
                return str(min(non_work_temps))  # Lowest cooling setpoint
    
    # If no active periods were found, fall back to using all temps
    work_temps = []
    non_work_temps = []
    
    for period, temps in all_values.items():
        if temps['work'] is not None:
            work_temps.append(temps['work'])
        if temps['non_work'] is not None:
            non_work_temps.append(temps['non_work'])
    
    # Select appropriate values based on mode
    if setpoint_type == 'work':
        if work_temps:
            if is_heating:
                return str(max(work_temps))
            else:
                return str(min(work_temps))
        elif non_work_temps:
            if is_heating:
                return str(max(non_work_temps))
            else:
                return str(min(non_work_temps))
    elif setpoint_type == 'non_work':
        if non_work_temps:
            if is_heating:
                return str(max(non_work_temps))
            else:
                return str(min(non_work_temps))
    
    return '-'

def generate_loads_report_pdf(zone_data, output_filename="output/loads.pdf"):
    """
    Generates a PDF report containing zone loads in a table format.

    Args:
        zone_data (dict): Dictionary of zone loads and schedules.
        output_filename (str): The name of the output PDF file.
    """
    # Use SimpleDocTemplate for automatic page layout
    # Use A3 Landscape with minimal margins to maximize table space
    left_margin = 0.5*cm
    right_margin = 0.5*cm
    top_margin = 1.0*cm
    bottom_margin = 1.0*cm
    page_size = landscape(A3)  # A3 gives much more space than A4
    
    doc = SimpleDocTemplate(output_filename, pagesize=page_size,
                            leftMargin=left_margin, rightMargin=right_margin,
                            topMargin=top_margin, bottomMargin=bottom_margin)
    story = []
    width, height = page_size
    content_width = width - left_margin - right_margin # Available content width

    # Styles
    styles = getSampleStyleSheet()
    cell_style = create_cell_style(styles)
    header_cell_style = create_cell_style(styles, is_header=True)
    title_style = styles['h1']
    title_style.textColor = navy
    title_style.alignment = TA_CENTER  # Center the title
    section_title_style = styles['h2']
    section_title_style.spaceBefore = 0.5 * cm
    section_title_style.spaceAfter = 0.3 * cm
    zone_name_style = ParagraphStyle(
        name='ZoneName', parent=styles['Normal'], fontName='Helvetica-Bold',
        fontSize=10, # Slightly larger for zone names
        spaceBefore = 0.4*cm, spaceAfter=0.1*cm
    )

    # --- Title ---
    title_text = "IDF Zone Loads Report"
    story.append(Paragraph(title_text, title_style))
    story.append(Spacer(1, 0.5*cm)) # Reduce space after title

    if not zone_data:
        story.append(Paragraph("No zones found or processed.", styles['Normal']))
        try:
            doc.build(story)
            print(f"Generated empty loads report: {output_filename}")
            return True
        except Exception as e:
            print(f"Error generating empty loads PDF file {output_filename}: {e}")
            return False

    # Create consistent cell style for data cells
    cell_style = create_cell_style(styles)

    try:
        # --- Consolidated Load Table ---
        table_data = []

        # Define Hierarchical Header Rows
        header_row1 = [
            "Zone", "Occupancy", "", "", "Lighting", "",
            "Non Fixed Equipment", "", "Fixed Equipment", "",
            "Heating", "", "", "Cooling", "", "",
            "Infiltration", "", "Ventilation", ""
        ]
        header_row2 = [
            "", # Spanned by Zone in row 1
            "people/\narea", "activity\nschedule\nw/person", "schedule\ntemplate\nname",
            "power\ndensity\n[w/m2]", "schedule\ntemplate\nname",
            "power\ndensity\n(W/m2)", "schedule\ntemplate\nname",
            "power\ndensity\n(W/m2)", "schedule\ntemplate\nname",
            "setpoint\n(C)", "setpoint\nnon work\ntime(C)", "equipment\nschedule\ntemplate\nname",
            "setpoint\n(C)", "setpoint\nnon work\ntime(C)", "equipment\nschedule\ntemplate\nname",
            "rate\n(ACH)", "schedule",
            "rate\n(ACH)", "schedule"
        ]

        # Apply styles to header cells
        styled_header_row1 = [wrap_text(h, header_cell_style) if h else "" for h in header_row1]
        styled_header_row2 = [wrap_text(h, header_cell_style) if h else "" for h in header_row2]

        table_data.append(styled_header_row1)
        table_data.append(styled_header_row2)

        # Populate Data Rows
        for zone_name, zone_info in zone_data.items():
            loads = zone_info.get('loads', {})
            schedules = zone_info.get('schedules', {})

            # Helper to safely get nested data or return default
            def get_load_data(load_type, key, default='-'):
                return loads.get(load_type, {}).get(key, default) or default

            def get_schedule_name(schedule_type, default='-'):
                 sched_info = schedules.get(schedule_type)
                 if isinstance(sched_info, dict):
                     return sched_info.get('name', default) or default
                 return sched_info or default # Fallback if not a dict

            # Extract data for each column
            people_density = get_load_data('people', 'people_per_area', 0.0)
            people_activity_sched = get_load_data('people', 'activity_schedule')
            people_sched = get_load_data('people', 'schedule')

            lights_density = get_load_data('lights', 'watts_per_area', 0.0)
            lights_sched = get_load_data('lights', 'schedule')

            non_fixed_density = get_load_data('non_fixed_equipment', 'watts_per_area', 0.0)
            non_fixed_sched = get_load_data('non_fixed_equipment', 'schedule')

            fixed_density = get_load_data('fixed_equipment', 'watts_per_area', 0.0)
            fixed_sched = get_load_data('fixed_equipment', 'schedule')

            heating_schedule_obj = schedules.get('heating')
            heating_sched_name = heating_schedule_obj.get('name', '-') if isinstance(heating_schedule_obj, dict) else '-'
            heating_sched_values = heating_schedule_obj.get('schedule_values', []) if isinstance(heating_schedule_obj, dict) else []
            heating_setpoint = extract_setpoint(heating_sched_values, 'work', zone_name, heating_schedule_obj)
            heating_setpoint_non_work = extract_setpoint(heating_sched_values, 'non_work', zone_name, heating_schedule_obj)

            cooling_schedule_obj = schedules.get('cooling')
            cooling_sched_name = cooling_schedule_obj.get('name', '-') if isinstance(cooling_schedule_obj, dict) else '-'
            cooling_sched_values = cooling_schedule_obj.get('schedule_values', []) if isinstance(cooling_schedule_obj, dict) else []
            cooling_setpoint = extract_setpoint(cooling_sched_values, 'work', zone_name, cooling_schedule_obj)
            cooling_setpoint_non_work = extract_setpoint(cooling_sched_values, 'non_work', zone_name, cooling_schedule_obj)

            infil_rate = get_load_data('infiltration', 'rate_ach', 0.0)
            infil_sched = get_load_data('infiltration', 'schedule')

            vent_rate = get_load_data('ventilation', 'rate_ach', 0.0)
            vent_sched = get_load_data('ventilation', 'schedule')

            # Format data for the row
            # Ensure all data is string before wrapping
            def to_str(val, precision=None):
                if val is None: return '-'
                if precision is not None:
                    try:
                        return f"{float(val):.{precision}f}"
                    except (ValueError, TypeError):
                        return str(val) # Fallback to string if formatting fails
                return str(val)

            row_data = [
                wrap_text(to_str(zone_name), cell_style),
                # Occupancy
                wrap_text(to_str(people_density, 2), cell_style),
                wrap_text(to_str(people_activity_sched), cell_style),
                wrap_text(to_str(people_sched), cell_style),
                # Lighting
                wrap_text(to_str(lights_density, 1), cell_style),
                wrap_text(to_str(lights_sched), cell_style),
                # Non Fixed Equipment
                wrap_text(to_str(non_fixed_density, 1), cell_style),
                wrap_text(to_str(non_fixed_sched), cell_style),
                # Fixed Equipment
                wrap_text(to_str(fixed_density, 1), cell_style),
                wrap_text(to_str(fixed_sched), cell_style),
                # Heating
                wrap_text(to_str(heating_setpoint), cell_style),
                wrap_text(to_str(heating_setpoint_non_work), cell_style),
                wrap_text(to_str(heating_sched_name), cell_style),
                # Cooling
                wrap_text(to_str(cooling_setpoint), cell_style),
                wrap_text(to_str(cooling_setpoint_non_work), cell_style),
                wrap_text(to_str(cooling_sched_name), cell_style),
                # Infiltration
                wrap_text(to_str(infil_rate, 2), cell_style),
                wrap_text(to_str(infil_sched), cell_style),
                # Ventilation
                wrap_text(to_str(vent_rate, 2), cell_style),
                wrap_text(to_str(vent_sched), cell_style),
            ]
            table_data.append(row_data)

        # Create and style the table
        if len(table_data) > 2: # Check if there's data beyond the two header rows
            # Optimize column widths based on content importance and available space
            # Calculate total available width and distribute proportionally
            available_width = content_width - 1*cm  # Allow some buffer
            
            # Define column width percentages (totaling 100%)
            col_percentages = [
                7.0,  # Zone - keep wider for zone names
                3.5,  # people/area - narrow numeric column
                5.5,  # activity schedule - medium width for text
                8.0,  # occupancy schedule name - wider for long names
                3.5,  # lighting density - narrow numeric column
                6.5,  # lighting schedule name - medium width for names
                3.5,  # non-fixed density - narrow numeric column
                6.5,  # non-fixed schedule name - medium width for names
                3.5,  # fixed density - narrow numeric column
                6.5,  # fixed schedule name - medium width for names
                3.0,  # heating setpoint - very narrow numeric column
                3.5,  # heating non-work setpoint - narrow numeric column
                8.0,  # heating schedule name - wider for long names
                3.0,  # cooling setpoint - very narrow numeric column
                3.5,  # cooling non-work setpoint - narrow numeric column
                8.0,  # cooling schedule name - wider for long names
                3.0,  # infil rate - very narrow numeric column
                5.0,  # infil schedule - medium width for names
                3.0,  # vent rate - very narrow numeric column
                5.0   # vent schedule - medium width for names
            ]
            
            # Calculate column widths based on percentages
            col_widths = [available_width * (p/100) for p in col_percentages]
            
            # Create the table with the calculated widths
            load_table = Table(table_data, colWidths=col_widths, hAlign='CENTER', repeatRows=2)
            load_table.setStyle(create_hierarchical_table_style())
            story.append(load_table)
        else:
            # Handle case where only header exists (e.g., zone_data was empty after filtering)
             story.append(Paragraph("No zone load data to display.", styles['Normal']))

        # Build the PDF document from the story
        doc.build(story)
        print(f"Successfully generated loads report: {output_filename}")
        return True

    except Exception as e:
        print(f"Error generating or saving loads PDF file {output_filename}: {e}")
        import traceback
        traceback.print_exc()  # Enable traceback for better debugging
        return False