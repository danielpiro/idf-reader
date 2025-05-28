"""
Generates PDF reports showing zone loads and their associated schedules.
"""
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, Spacer
from reportlab.lib.pagesizes import landscape, A3
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import navy, black, lightgrey, white, grey, Color
from reportlab.lib.enums import TA_CENTER
import datetime
from reportlab.platypus import TableStyle

# Modern Blue/Gray Color Palette
COLORS = {
    'primary_blue': Color(0.2, 0.4, 0.7),      # #3366B2 - Primary blue
    'secondary_blue': Color(0.4, 0.6, 0.85),   # #6699D9 - Secondary blue
    'light_blue': Color(0.9, 0.94, 0.98),      # #E6F0FA - Light blue background
    'dark_gray': Color(0.2, 0.2, 0.2),         # #333333 - Dark gray text
    'medium_gray': Color(0.5, 0.5, 0.5),       # #808080 - Medium gray
    'light_gray': Color(0.9, 0.9, 0.9),        # #E6E6E6 - Light gray
    'white': Color(1, 1, 1),                   # #FFFFFF - White
    'border_gray': Color(0.8, 0.8, 0.8),       # #CCCCCC - Border gray
}

# Typography Settings
FONTS = {
    'title': 'Helvetica-Bold',
    'heading': 'Helvetica-Bold',
    'body': 'Helvetica',
    'table_header': 'Helvetica-Bold',
    'table_body': 'Helvetica',
}

FONT_SIZES = {
    'title': 16,
    'heading': 12,
    'body': 10,
    'table_header': 9,
    'table_body': 8,
    'small': 7,
}

def wrap_text(text, style):
    """Helper function to create wrapped text in a cell."""
    return Paragraph(str(text), style)

def create_cell_style(styles, is_header=False):
    """Create a cell style for wrapped text."""
    style = ParagraphStyle(
        'Cell',
        parent=styles['Normal'],
        fontSize=5,
        leading=6,
        spaceBefore=1,
        spaceAfter=1,
        fontName='Helvetica-Bold' if is_header else 'Helvetica',
        wordWrap='CJK',
        alignment=0
    )
    return style

def create_hierarchical_table_style():
    """Create table style for the main load table with hierarchical headers."""
    spans = [
        ('SPAN', (0, 0), (0, 1)),
        ('SPAN', (1, 0), (3, 0)),
        ('SPAN', (4, 0), (5, 0)),
        ('SPAN', (6, 0), (7, 0)),
        ('SPAN', (8, 0), (9, 0)),
        ('SPAN', (10, 0), (12, 0)),
        ('SPAN', (13, 0), (15, 0)),
        ('SPAN', (16, 0), (17, 0)),
        ('SPAN', (18, 0), (19, 0)),
        ('SPAN', (20, 0), (21, 0))
    ]

    style = [
        # Primary header row styling - primary blue background
        ('BACKGROUND', (0, 0), (-1, 0), COLORS['primary_blue']),
        ('TEXTCOLOR', (0, 0), (-1, 0), COLORS['white']),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, 0), FONTS['table_header']),
        ('FONTSIZE', (0, 0), (-1, 0), FONT_SIZES['table_body']),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 4),
        ('TOPPADDING', (0, 0), (-1, 0), 4),

        # Secondary header row styling - secondary blue background
        ('BACKGROUND', (1, 1), (-1, 1), COLORS['secondary_blue']),
        ('TEXTCOLOR', (1, 1), (-1, 1), COLORS['white']),
        ('ALIGN', (1, 1), (-1, 1), 'CENTER'),
        ('VALIGN', (1, 1), (-1, 1), 'MIDDLE'),
        ('FONTNAME', (1, 1), (-1, 1), FONTS['table_header']),
        ('FONTSIZE', (1, 1), (-1, 1), FONT_SIZES['small']),
        ('TOPPADDING', (1, 1), (-1, 1), 2),
        ('BOTTOMPADDING', (1, 1), (-1, 1), 2),

        # Zone column spans both header rows
        ('ALIGN', (0, 0), (0, 1), 'CENTER'),
        ('VALIGN', (0, 0), (0, 1), 'MIDDLE'),

        # Data rows styling
        ('TEXTCOLOR', (0, 2), (-1, -1), COLORS['dark_gray']),
        ('ALIGN', (0, 2), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 2), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 2), (-1, -1), FONTS['table_body']),
        ('FONTSIZE', (0, 2), (-1, -1), FONT_SIZES['small']),
        ('TOPPADDING', (0, 2), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 2), (-1, -1), 2),

        # Zebra striping for data rows
        ('ROWBACKGROUNDS', (0, 2), (-1, -1), [COLORS['white'], COLORS['light_blue']]),

        # Borders - subtle gray lines
        ('GRID', (0, 0), (-1, -1), 0.5, COLORS['border_gray']),
        ('BOX', (0, 0), (-1, -1), 1, COLORS['medium_gray']),

        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4)
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
    if not schedule_values:
        return '-'

    if not all_schedules:
        return '-'

    schedule_name = all_schedules.get('name', '')

    is_heating = False
    is_cooling = False

    if 'heating' in schedule_name.lower() or 'heat' in schedule_name.lower():
        is_heating = True
    elif 'cooling' in schedule_name.lower() or 'cool' in schedule_name.lower() or 'sp sch' in schedule_name.lower():
        is_cooling = True

    avail_key = None
    for key in all_schedules:
        if isinstance(key, str) and 'availability' in key.lower():
            if (is_heating and 'heat' in key.lower()) or (is_cooling and 'cool' in key.lower()):
                avail_key = key
                break

    avail_schedule = None
    active_periods = []

    if avail_key and avail_key in all_schedules:
        avail_schedule = all_schedules[avail_key]

    if avail_schedule and isinstance(avail_schedule, dict) and 'schedule_values' in avail_schedule:
        avail_values = avail_schedule['schedule_values']

        current_period = None
        for i, val in enumerate(avail_values):
            val_str = str(val).strip().lower()

            if val_str.startswith('through:'):
                current_period = val_str.replace('through:', '').strip()
            elif val_str == '1' and current_period:
                active_periods.append(current_period)

    all_values = {}
    active_values = {}

    current_period = None
    for i, val in enumerate(schedule_values):
        val_str = str(val).strip().lower()

        if val_str.startswith('through:'):
            current_period = val_str.replace('through:', '').strip()
            if current_period not in all_values:
                all_values[current_period] = {'work': None, 'non_work': None}

            is_active = current_period in active_periods
            if is_active and current_period not in active_values:
                active_values[current_period] = {'work': None, 'non_work': None}

        elif current_period and val_str.startswith('until:'):
            time_str = val_str.replace('until:', '').strip()
            is_non_work = (time_str == '24:00')

            if i+1 < len(schedule_values):
                try:
                    temp_val = float(str(schedule_values[i+1]).strip())

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

    if active_values:
        work_temps = []
        non_work_temps = []

        for period, temps in active_values.items():
            if temps['work'] is not None:
                work_temps.append(temps['work'])
            if temps['non_work'] is not None:
                non_work_temps.append(temps['non_work'])

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

        elif setpoint_type == 'non_work' and non_work_temps:
            if is_heating:
                return str(max(non_work_temps))
            else:
                return str(min(non_work_temps))

    work_temps = []
    non_work_temps = []

    for period, temps in all_values.items():
        if temps['work'] is not None:
            work_temps.append(temps['work'])
        if temps['non_work'] is not None:
            non_work_temps.append(temps['non_work'])

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

def _get_load_data(loads, load_type, key, default='-'):
    return loads.get(load_type, {}).get(key, default) or default

def _get_schedule_name(schedules, schedule_type, default='-'):
    sched_info = schedules.get(schedule_type)
    if isinstance(sched_info, dict):
        return sched_info.get('name', default) or default
    return sched_info or default

def _to_str(val, precision=None):
    if val is None:
        return '-'
    if precision is not None:
        try:
            return f"{float(val):.{precision}f}"
        except (ValueError, TypeError):
            return str(val)
    return str(val)

def generate_loads_report_pdf(zone_data, output_filename="output/loads.pdf", project_name="N/A", run_id="N/A", 
                             city_name="N/A", area_name="N/A"):
    """
    Generates a PDF report containing zone loads, including a header.

    Args:
        zone_data (dict): Dictionary of zone loads and schedules.
        output_filename (str): The name of the output PDF file.
        project_name (str): Name of the project.
        run_id (str): Identifier for the current run.

    Returns:
        bool: True if report generated successfully, False otherwise.
    """
    left_margin = right_margin = 0.5 * cm
    top_margin = bottom_margin = 1.0 * cm
    page_size = landscape(A3)
    doc = SimpleDocTemplate(output_filename, pagesize=page_size,
                            leftMargin=left_margin, rightMargin=right_margin,
                            topMargin=top_margin, bottomMargin=bottom_margin)
    story = []
    width, _ = page_size
    content_width = width - left_margin - right_margin
    styles = getSampleStyleSheet()
    cell_style = create_cell_style(styles)
    header_cell_style = create_cell_style(styles, is_header=True)
    title_style = styles['h1']
    title_style.textColor = COLORS['primary_blue']
    title_style.fontName = FONTS['title']
    title_style.fontSize = FONT_SIZES['title']
    title_style.alignment = TA_CENTER
    header_info_style = ParagraphStyle(        'HeaderInfo', parent=styles['Normal'], fontSize=9, textColor=black, alignment=2)
    now = datetime.datetime.now()
    header_text = f"""
    Project: {project_name}<br/>
    Run ID: {run_id}<br/>
    Date: {now.strftime('%Y-%m-%d %H:%M:%S')}<br/>
    City: {city_name}<br/>
    Area: {area_name}<br/>
    Report: Zone Loads Summary
    """
    story.append(Paragraph(header_text, header_info_style))
    story.append(Spacer(1, 5))
    story.append(Paragraph("IDF Zone Loads Report", title_style))
    story.append(Spacer(1, 0.5 * cm))
    if not zone_data:
        story.append(Paragraph("No zones found or processed.", styles['Normal']))
        try:
            doc.build(story)
            return True
        except Exception as e:
            raise RuntimeError(f"Error generating empty loads PDF file {output_filename}: {e}")
    try:
        table_data = []
        header_row1 = [
            "Zone", "Occupancy", "", "", "Lighting", "",
            "Non Fixed Equipment", "", "Fixed Equipment", "",
            "Heating", "", "", "Cooling", "", "",
            "Infiltration", "", "Ventilation", "", "Mechanical Ventilation", ""
        ]
        header_row2 = [
            "", "people/\narea", "activity\nschedule\nw/person", "schedule\ntemplate\nname",
            "power\ndensity\n[w/m2]", "schedule\ntemplate\nname",
            "power\ndensity\n(W/m2)", "schedule\ntemplate\nname",
            "power\ndensity\n(W/m2)", "schedule\ntemplate\nname",
            "setpoint\n(C)", "setpoint\nnon work\ntime(C)", "equipment\nschedule\ntemplate\nname",
            "setpoint\n(C)", "setpoint\nnon work\ntime(C)", "equipment\nschedule\ntemplate\nname",
            "rate\n(ACH)", "schedule", "rate\n(ACH)", "schedule",
            "Outdoor Air\nFlow per Person\n{m3/s}", "Outdoor Air\nFlow Rate Fraction\nSchedule Name"
        ]
        styled_header_row1 = [wrap_text(h, header_cell_style) if h else "" for h in header_row1]
        styled_header_row2 = [wrap_text(h, header_cell_style) if h else "" for h in header_row2]
        table_data.append(styled_header_row1)
        table_data.append(styled_header_row2)
        for zone_name, zone_info in zone_data.items():
            loads = zone_info.get('loads', {})
            schedules = zone_info.get('schedules', {})
            people_density = _get_load_data(loads, 'people', 'people_per_area', 0.0)
            people_activity_sched = _get_load_data(loads, 'people', 'activity_schedule')
            people_sched = _get_load_data(loads, 'people', 'schedule')
            lights_density = _get_load_data(loads, 'lights', 'watts_per_area', 0.0)
            lights_sched = _get_load_data(loads, 'lights', 'schedule')
            non_fixed_density = _get_load_data(loads, 'non_fixed_equipment', 'watts_per_area', 0.0)
            non_fixed_sched = _get_load_data(loads, 'non_fixed_equipment', 'schedule')
            fixed_density = _get_load_data(loads, 'fixed_equipment', 'watts_per_area', 0.0)
            fixed_sched = _get_load_data(loads, 'fixed_equipment', 'schedule')
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
            infil_rate = _get_load_data(loads, 'infiltration', 'rate_ach', 0.0)
            infil_sched = _get_load_data(loads, 'infiltration', 'schedule')
            vent_rate = _get_load_data(loads, 'ventilation', 'rate_ach', 0.0)
            vent_sched = _get_load_data(loads, 'ventilation', 'schedule')
            mech_vent_flow_per_person = _get_load_data(loads, 'mechanical_ventilation', 'outdoor_air_flow_per_person', 0.0)
            mech_vent_sched = _get_load_data(loads, 'mechanical_ventilation', 'schedule')
            row_data = [
                wrap_text(_to_str(zone_name), cell_style),
                wrap_text(_to_str(people_density, 2), cell_style),
                wrap_text(_to_str(people_activity_sched), cell_style),
                wrap_text(_to_str(people_sched), cell_style),
                wrap_text(_to_str(lights_density, 1), cell_style),
                wrap_text(_to_str(lights_sched), cell_style),
                wrap_text(_to_str(non_fixed_density, 1), cell_style),
                wrap_text(_to_str(non_fixed_sched), cell_style),
                wrap_text(_to_str(fixed_density, 1), cell_style),
                wrap_text(_to_str(fixed_sched), cell_style),
                wrap_text(_to_str(heating_setpoint), cell_style),
                wrap_text(_to_str(heating_setpoint_non_work), cell_style),
                wrap_text(_to_str(heating_sched_name), cell_style),
                wrap_text(_to_str(cooling_setpoint), cell_style),
                wrap_text(_to_str(cooling_setpoint_non_work), cell_style),
                wrap_text(_to_str(cooling_sched_name), cell_style),
                wrap_text(_to_str(infil_rate, 2), cell_style),
                wrap_text(_to_str(infil_sched), cell_style),
                wrap_text(_to_str(vent_rate, 2), cell_style),
                wrap_text(_to_str(vent_sched), cell_style),
                wrap_text(_to_str(mech_vent_flow_per_person, 3), cell_style),
                wrap_text(_to_str(mech_vent_sched), cell_style),
            ]
            table_data.append(row_data)
        if len(table_data) > 2:
            available_width = content_width - 1 * cm
            col_percentages = [
                6.5, 3.0, 5.0, 7.5, 3.0, 6.0, 3.0, 6.0, 3.0, 6.0, 2.5, 3.0, 7.5, 2.5, 3.0, 7.5, 2.5, 4.5, 2.5, 4.5, 3.5, 6.5
            ]
            col_widths = [available_width * (p / 100) for p in col_percentages]
            load_table = Table(table_data, colWidths=col_widths, hAlign='CENTER', repeatRows=2)
            load_table.setStyle(create_hierarchical_table_style())
            story.append(load_table)
        else:
            story.append(Paragraph("No zone load data to display.", styles['Normal']))
        doc.build(story)
        return True
    except Exception as e:
        raise RuntimeError(f"Error generating or saving loads PDF file {output_filename}: {e}")
