"""
Generates PDF reports showing zone loads and their associated schedules.
"""
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, Spacer, TableStyle
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet
import datetime
from utils.hebrew_text_utils import safe_format_header_text
from utils.logo_utils import create_logo_image
from generators.shared_design_system import (
    COLORS, FONTS, FONT_SIZES, LAYOUT,
    create_multi_header_table_style, create_cell_style, 
    create_title_style, create_header_info_style, wrap_text,
    create_standardized_header
)


def create_table1_style():
    """Create table style for table 1 (Zone, Occupancy, Lighting, Non Fixed Equipment, Fixed Equipment)."""
    spans = [
        ('SPAN', (1, 0), (3, 0)),  # Occupancy
        ('SPAN', (4, 0), (5, 0)),  # Lighting
        ('SPAN', (6, 0), (7, 0)),  # Non Fixed Equipment
        ('SPAN', (8, 0), (9, 0))   # Fixed Equipment
    ]
    return create_multi_header_table_style(header_rows=2, spans=spans)

def create_table2_style():
    """Create table style for table 2 (Zone, Heating, Cooling, Infiltration, Natural Ventilation, Mechanical Ventilation)."""
    spans = [
        ('SPAN', (1, 0), (3, 0)),  # Heating
        ('SPAN', (4, 0), (6, 0)),  # Cooling
        ('SPAN', (7, 0), (8, 0)),  # Infiltration
        ('SPAN', (9, 0), (10, 0)), # Natural Ventilation
        ('SPAN', (11, 0), (12, 0)) # Mechanical Ventilation
    ]
    return create_multi_header_table_style(header_rows=2, spans=spans)

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
    
    # Determine if this is heating or cooling schedule
    is_heating = False
    is_cooling = False
    
    if 'heating' in schedule_name.lower() or 'heat' in schedule_name.lower():
        is_heating = True
    elif 'cooling' in schedule_name.lower() or 'cool' in schedule_name.lower() or 'sp sch' in schedule_name.lower():
        is_cooling = True
    
    # Get availability schedule if it exists
    avail_schedule = None
    avail_key = None
    for key in all_schedules:
        if isinstance(key, str) and 'availability' in key.lower():
            if (is_heating and 'heat' in key.lower()) or (is_cooling and 'cool' in key.lower()):
                avail_key = key
                avail_schedule = all_schedules[avail_key]
                break
    
    # Parse availability schedule to find periods and their availability status
    period_availability = {}
    if avail_schedule and isinstance(avail_schedule, dict) and 'schedule_values' in avail_schedule:
        avail_values = avail_schedule['schedule_values']
        current_period = None
        
        for i, val in enumerate(avail_values):
            val_str = str(val).strip().lower()
            
            if val_str.startswith('through:'):
                current_period = val_str.replace('through:', '').strip()
            elif val_str in ['0', '1'] and current_period:
                period_availability[current_period] = val_str == '1'
    
    # Parse setpoint schedule to extract temperatures by period
    period_temps = {}
    
    current_period = None
    for i, val in enumerate(schedule_values):
        val_str = str(val).strip().lower()
        
        if val_str.startswith('through:'):
            current_period = val_str.replace('through:', '').strip()
            period_temps[current_period] = []
        
        elif current_period and val_str.startswith('until:'):
            # Look for temperature value after the Until: statement
            if i + 1 < len(schedule_values):
                try:
                    temp_val = float(str(schedule_values[i + 1]).strip())
                    period_temps[current_period].append(temp_val)
                except (ValueError, TypeError):
                    pass
    
    # Check if we have availability schedule and if any periods are available
    if period_availability:
        # Check if any periods have availability = 1 (system is available)
        has_available_periods = any(period_availability.values())
        
        if not has_available_periods:
            # No periods are available, return '-'
            return '-'
        
        # Find which periods are available and get their temperatures
        available_temps = []
        unavailable_temps = []
        
        for period, temps in period_temps.items():
            if not temps:
                continue
            
            # Get representative temperature for this period
            period_temp = temps[0] if len(temps) == 1 else max(temps) if is_heating else min(temps)
            
            # Check if this period is available
            is_available = period_availability.get(period, False)
            
            if is_available:
                # Validate temperature (filter out extreme values that indicate "off" mode)
                is_valid_temp = False
                if is_heating and period_temp > 5:  # Valid heating setpoint
                    is_valid_temp = True
                elif is_cooling and 15 <= period_temp <= 35:  # Valid cooling setpoint
                    is_valid_temp = True
                
                if is_valid_temp:
                    available_temps.append(period_temp)
            else:
                unavailable_temps.append(period_temp)
        
        # Return appropriate setpoint based on request type
        if setpoint_type == 'work':
            # Work setpoint: use available period temperatures
            if available_temps:
                if is_heating:
                    return str(max(available_temps))  # Highest heating setpoint during available periods
                else:
                    return str(min(available_temps))  # Lowest cooling setpoint during available periods
            else:
                return '-'  # No available periods with valid temperatures
        
        elif setpoint_type == 'non_work':
            # Non-work setpoint: check if unavailable periods have meaningful temperatures
            if unavailable_temps:
                # Check if unavailable periods have valid temperatures (not extreme values)
                valid_unavailable_temps = []
                for temp in unavailable_temps:
                    if is_heating and temp > 5:  # Valid heating setpoint
                        valid_unavailable_temps.append(temp)
                    elif is_cooling and 15 <= temp <= 35:  # Valid cooling setpoint
                        valid_unavailable_temps.append(temp)
                
                if valid_unavailable_temps:
                    if is_heating:
                        return str(max(valid_unavailable_temps))
                    else:
                        return str(min(valid_unavailable_temps))
                else:
                    # Unavailable periods have extreme values, return '-'
                    return '-'
            else:
                # No unavailable periods or only available periods exist
                # For non-work time, if system is not available, return '-'
                return '-'
    
    else:
        # No availability schedule found, use original logic
        # Parse setpoint schedule to extract temperatures by period
        active_temps = []
        inactive_temps = []
        
        for period, temps in period_temps.items():
            if not temps:
                continue
                
            # Get representative temperature for this period (usually just one value per period)
            period_temp = temps[0] if len(temps) == 1 else max(temps) if is_heating else min(temps)
            
            # Validate temperature (filter out extreme values that indicate "off" mode)
            is_valid_active_temp = False
            if is_heating and period_temp > 5:  # Valid heating setpoint
                is_valid_active_temp = True
            elif is_cooling and 15 <= period_temp <= 35:  # Valid cooling setpoint
                is_valid_active_temp = True
                
            if is_valid_active_temp:
                active_temps.append(period_temp)
            else:
                inactive_temps.append(period_temp)
        
        # Return appropriate setpoint based on request type
        if setpoint_type == 'work':
            # Work setpoint: use active period temperatures
            if active_temps:
                if is_heating:
                    return str(max(active_temps))  # Highest heating setpoint during active periods
                else:
                    return str(min(active_temps))  # Lowest cooling setpoint during active periods
            else:
                return '-'
        
        elif setpoint_type == 'non_work':
            # Non-work setpoint: for seasonal schedules, this could mean inactive periods
            # or a different interpretation based on the schedule structure
            
            # If we have both active and inactive periods, use inactive for non-work
            if active_temps and inactive_temps:
                # Use inactive period temperatures for non-work
                if is_heating:
                    return str(max(inactive_temps))
                else:
                    return str(min(inactive_temps))
            
            # If we only have active periods, look for time-based variations within periods
            elif active_temps:
                # For seasonal schedules with only active periods, work and non-work might be similar
                # Try to find a slightly different setpoint for energy savings
                if len(active_temps) > 1:
                    sorted_temps = sorted(active_temps)
                    if is_heating:
                        # Non-work heating: slightly lower for energy savings
                        return str(sorted_temps[0]) if len(sorted_temps) > 1 else str(sorted_temps[0] - 2)
                    else:
                        # Non-work cooling: slightly higher for energy savings
                        return str(sorted_temps[-1]) if len(sorted_temps) > 1 else str(sorted_temps[0] + 2)
                else:
                    # Only one active temperature, apply offset for energy savings
                    base_temp = active_temps[0]
                    if is_heating:
                        return str(base_temp - 2)  # Lower heating setpoint for non-work
                    else:
                        return str(base_temp + 2)  # Higher cooling setpoint for non-work
            
            # Fallback to inactive periods or extreme values
            elif inactive_temps:
                if is_heating:
                    return str(max(inactive_temps))
                else:
                    return str(min(inactive_temps))
    
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
    # Use standardized layout settings
    margins = LAYOUT['margins']['default']
    page_size = landscape(A4)
    doc = SimpleDocTemplate(output_filename, pagesize=page_size,
                            leftMargin=margins, rightMargin=margins,
                            topMargin=margins, bottomMargin=margins)
    story = []
    width, _ = page_size
    content_width = width - (margins * 2)
    styles = getSampleStyleSheet()
    
    # Create standardized styles
    cell_style = create_cell_style(styles, font_size=FONT_SIZES['small'])
    header_cell_style = create_cell_style(styles, is_header=True, font_size=FONT_SIZES['small'])
    title_style = create_title_style(styles)
    header_info_style = create_header_info_style(styles)
    
    # Add standardized header
    header_elements = create_standardized_header(
        doc=doc,
        project_name=project_name,
        run_id=run_id,
        city_name=city_name,
        area_name=area_name,
        report_title="Zone Loads Summary"
    )
    story.extend(header_elements)
    story.append(Paragraph("IDF Zone Loads Report", title_style))
    story.append(Spacer(1, LAYOUT['spacing']['standard']))
    if not zone_data:
        story.append(Paragraph("No zones found or processed.", styles['Normal']))
        try:
            doc.build(story)
            return True
        except Exception as e:
            raise RuntimeError(f"Error generating empty loads PDF file {output_filename}: {e}")
    try:
        # Create Table 1: Zone, Occupancy, Lighting, Non Fixed Equipment, Fixed Equipment
        table1_data = []
        table1_header_row1 = [
            "", "Occupancy", "", "", "Lighting", "",
            "Non Fixed Equipment", "", "Fixed Equipment", ""
        ]
        table1_header_row2 = [
            "Zone", "people/\narea", "activity\nschedule\nw/person", "schedule\ntemplate\nname",
            "power\ndensity\n[w/m2]", "schedule\ntemplate\nname",
            "power\ndensity\n(W/m2)", "schedule\ntemplate\nname",
            "power\ndensity\n(W/m2)", "schedule\ntemplate\nname"
        ]
        styled_table1_header_row1 = [wrap_text(h, header_cell_style) if h else "" for h in table1_header_row1]
        styled_table1_header_row2 = [wrap_text(h, header_cell_style) if h else "" for h in table1_header_row2]
        table1_data.append(styled_table1_header_row1)
        table1_data.append(styled_table1_header_row2)

        # Create Table 2: Zone, Heating, Cooling, Infiltration, Natural Ventilation, Mechanical Ventilation
        table2_data = []
        table2_header_row1 = [
            "", "Heating", "", "", "Cooling", "", "",
            "Infiltration", "", "Natural Ventilation", "", "Mechanical Ventilation", ""
        ]
        table2_header_row2 = [
            "Zone", "setpoint\n(C)", "setpoint\nnon work\ntime(C)", "equipment\nschedule\ntemplate\nname",
            "setpoint\n(C)", "setpoint\nnon work\ntime(C)", "equipment\nschedule\ntemplate\nname",
            "rate\n(ACH)", "schedule", "rate\n(ACH)", "schedule",
            "Outdoor Air\nFlow per Person\n{m3/s}", "Outdoor Air\nFlow Rate Fraction\nSchedule Name"
        ]
        styled_table2_header_row1 = [wrap_text(h, header_cell_style) if h else "" for h in table2_header_row1]
        styled_table2_header_row2 = [wrap_text(h, header_cell_style) if h else "" for h in table2_header_row2]
        table2_data.append(styled_table2_header_row1)
        table2_data.append(styled_table2_header_row2)

        for zone_name, zone_info in zone_data.items():
            loads = zone_info.get('loads', {})
            schedules = zone_info.get('schedules', {})
            
            # Extract data for both tables
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
            
            # Table 1 row data
            table1_row_data = [
                wrap_text(_to_str(zone_name), cell_style),
                wrap_text(_to_str(people_density, 2), cell_style),
                wrap_text(_to_str(people_activity_sched), cell_style),
                wrap_text(_to_str(people_sched), cell_style),
                wrap_text(_to_str(lights_density, 1), cell_style),
                wrap_text(_to_str(lights_sched), cell_style),
                wrap_text(_to_str(non_fixed_density, 1), cell_style),
                wrap_text(_to_str(non_fixed_sched), cell_style),
                wrap_text(_to_str(fixed_density, 1), cell_style),
                wrap_text(_to_str(fixed_sched), cell_style)
            ]
            table1_data.append(table1_row_data)
            
            # Table 2 row data
            table2_row_data = [
                wrap_text(_to_str(zone_name), cell_style),
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
                wrap_text(_to_str(mech_vent_sched), cell_style)
            ]
            table2_data.append(table2_row_data)

        if len(table1_data) > 2:  # Has data beyond headers
            # Use 95% of content width for both tables to match Table 2's perfect fit
            table1_width = content_width * 0.95
            table2_width = content_width * 0.95
            
            # Table 1 column widths (10 columns) - reduced to match Table 2's compact sizing
            table1_col_widths = [
                table1_width * 0.11,  # Zone (same as Table 2)
                table1_width * 0.06,  # people/area
                table1_width * 0.05,  # activity schedule w/person
                table1_width * 0.16,  # schedule template name
                table1_width * 0.06,  # power density [w/m2]
                table1_width * 0.14,  # schedule template name
                table1_width * 0.06,  # power density (W/m2)
                table1_width * 0.14,  # schedule template name
                table1_width * 0.06,  # power density (W/m2)
                table1_width * 0.14   # schedule template name
            ]
            table1 = Table(table1_data, colWidths=table1_col_widths, hAlign='CENTER', repeatRows=2)
            table1.setStyle(create_table1_style())
            story.append(table1)
            
            # Add spacing between tables
            story.append(Spacer(1, LAYOUT['spacing']['section']))
            
            # Table 2 column widths (13 columns) - reduced to fit A4 width
            table2_col_widths = [
                table2_width * 0.11,  # Zone (slightly smaller to accommodate more columns)
                table2_width * 0.05,  # setpoint (C)
                table2_width * 0.05,  # setpoint non work time(C)
                table2_width * 0.14,  # equipment schedule template name
                table2_width * 0.05,  # setpoint (C)
                table2_width * 0.05,  # setpoint non work time(C)
                table2_width * 0.14,  # equipment schedule template name
                table2_width * 0.05,  # rate (ACH)
                table2_width * 0.09,  # schedule
                table2_width * 0.05,  # rate (ACH)
                table2_width * 0.09,  # schedule
                table2_width * 0.06,  # Outdoor Air Flow per Person {m3/s}
                table2_width * 0.11   # Outdoor Air Flow Rate Fraction Schedule Name
            ]
            table2 = Table(table2_data, colWidths=table2_col_widths, hAlign='CENTER', repeatRows=2)
            table2.setStyle(create_table2_style())
            
            story.append(table2)
            story.append(Spacer(1, LAYOUT['spacing']['standard']))
        else:
            story.append(Paragraph("No zone load data to display.", styles['Normal']))
        doc.build(story)
        return True
    except Exception as e:
        raise RuntimeError(f"Error generating or saving loads PDF file {output_filename}: {e}")
