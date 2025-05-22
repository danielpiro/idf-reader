"""
Generates energy rating reports from processed energy consumption data.
"""
import logging
import os
import math
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from utils.data_loader import get_energy_consumption
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.colors import navy, black, grey, lightgrey, blue, green, limegreen, yellow, orange, darkgrey, Color # Added Color
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.graphics.shapes import Drawing, Rect, Polygon, String # Added Polygon and String
import math # Ensure math is imported
import logging # Ensure logging is imported
import os # Ensure os is imported

logger = logging.getLogger(__name__)

ENERGY_RATING_DATA_2017 = {
    "Zone A": [
        (35, "+A", 5), (30, "A", 4), (25, "B", 3), (20, "C", 2), (10, "D", 1),
        (0, "E", 0), (-float('inf'), "F", -1)
    ],
    "Zone B": [
        (35, "+A", 5), (30, "A", 4), (25, "B", 3), (20, "C", 2), (10, "D", 1),
        (0, "E", 0), (-float('inf'), "F", -1)
    ],
    "Zone C": [
        (40, "+A", 5), (34, "A", 4), (27, "B", 3), (20, "C", 2), (10, "D", 1),
        (0, "E", 0), (-float('inf'), "F", -1)
    ],
    "Zone D": [
        (29, "+A", 5), (26, "A", 4), (23, "B", 3), (20, "C", 2), (10, "D", 1),
        (0, "E", 0), (-float('inf'), "F", -1)
    ]
}

CLIMATE_ZONE_MAP = {
    "a": "Zone A", "A": "Zone A", "אזור א": "Zone A",
    "b": "Zone B", "B": "Zone B", "אזור ב": "Zone B",
    "c": "Zone C", "C": "Zone C", "אזור ג": "Zone C",
    "d": "Zone D", "D": "Zone D", "אזור ד": "Zone D",
}

def _get_table_style():
    return TableStyle([
        ('BACKGROUND', (0,0), (-1,0), lightgrey),
        ('TEXTCOLOR', (0,0), (-1,0), black),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('VALIGN', (0,0), (-1,0), 'MIDDLE'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 10),
        ('BACKGROUND', (0,1), (-1,1), lightgrey),
        ('TEXTCOLOR', (0,1), (-1,1), black),
        ('ALIGN', (0,1), (-1,1), 'CENTER'),
        ('VALIGN', (0,1), (-1,1), 'MIDDLE'),
        ('FONTNAME', (0,1), (-1,1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,1), (-1,1), 8),
        ('SPAN', (0,0), (4,0)),
        ('SPAN', (5,0), (8,0)),
        ('SPAN', (9,0), (12,0)),
        ('FONTNAME', (0,2), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,2), (-1,-1), 8),
        ('ALIGN', (0,2), (-1,-1), 'CENTER'),
        ('VALIGN', (0,2), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 1, grey),
        ('BOX', (0,0), (-1,-1), 1, black),
        ('LEFTPADDING', (0,0), (-1,-1), 3),
        ('RIGHTPADDING', (0,0), (-1,-1), 3),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
    ])

def _format_number(value):
    """
    Format number for display in the report.
    """
    try:
        if isinstance(value, (int, float)):
            if value == 0:
                return "0"
            elif abs(value) < 0.01:
                return "{:.4f}".format(value)
            elif abs(value) < 1:
                return "{:.3f}".format(value)
            elif abs(value) < 10:
                return "{:.2f}".format(value)
            elif abs(value) < 1000:
                return "{:.1f}".format(value)
            else:
                return "{:.0f}".format(value)
        return str(value)
    except Exception:
        return str(value)

def safe_float(value, default=0.0):
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

def _get_numeric_area_score_for_group(group_sum_energy_components, group_sum_total_area, group_model_csv_area_desc, model_year, model_area_definition):
    """
    Calculates the numeric area score for a group based on its aggregated data.
    This function encapsulates logic similar to that in _energy_rating_table for determining area score.
    Returns an integer score or None.
    """
    logger.debug(f"Attempting to get score for group. Inputs: group_sum_energy_components={group_sum_energy_components}, group_sum_total_area={group_sum_total_area}, group_model_csv_area_desc='{group_model_csv_area_desc}', model_year={model_year}, model_area_definition='{model_area_definition}'")
    numeric_energy_consumption = None
    if group_model_csv_area_desc and model_year is not None and model_area_definition is not None:
        try:
            iso_type_for_file_selection = f"MODEL_YEAR_{model_year}"
            energy_value_raw = get_energy_consumption(
                iso_type_input=iso_type_for_file_selection,
                area_location_input=group_model_csv_area_desc,
                area_definition_input=model_area_definition
            )
            numeric_energy_consumption = float(energy_value_raw)
            logger.debug(f"Retrieved numeric_energy_consumption: {numeric_energy_consumption} for '{group_model_csv_area_desc}'")
        except Exception as e:
            logger.error(f"Error in _get_numeric_area_score_for_group getting energy consumption for '{group_model_csv_area_desc}': {e}")
            # numeric_energy_consumption remains None
    else:
        logger.debug(f"Skipping energy consumption lookup for group '{group_model_csv_area_desc}' due to missing inputs (model_year, model_area_definition, or desc).")


    calculated_improve_by_value = None
    if numeric_energy_consumption is not None:
        logger.debug(f"Calculating improve_by_value: numeric_energy_consumption={numeric_energy_consumption}, group_sum_total_area={group_sum_total_area}, group_sum_energy_components={group_sum_energy_components}")
        if group_sum_total_area <= 70:
            adjusted_target_ec = 1.18 * numeric_energy_consumption
            logger.debug(f"Area <= 70. adjusted_target_ec = {adjusted_target_ec}")
            if adjusted_target_ec != 0:
                calculated_improve_by_value = 100 * (adjusted_target_ec - group_sum_energy_components) / adjusted_target_ec
            else:
                logger.debug("adjusted_target_ec is 0, cannot calculate improve_by_value.")
        else:
            logger.debug("Area > 70.")
            if numeric_energy_consumption != 0:
                calculated_improve_by_value = 100 * (numeric_energy_consumption - group_sum_energy_components) / numeric_energy_consumption
            else:
                logger.debug("numeric_energy_consumption is 0, cannot calculate improve_by_value.")
        logger.debug(f"Calculated_improve_by_value: {calculated_improve_by_value}")
    else:
        logger.debug("numeric_energy_consumption is None, cannot calculate improve_by_value.")

    
    if calculated_improve_by_value is not None:
        if model_year == 2017:
            climate_zone_lookup_key = CLIMATE_ZONE_MAP.get(model_area_definition)
            logger.debug(f"Model year 2017. Climate zone lookup key for '{model_area_definition}': '{climate_zone_lookup_key}'")
            if climate_zone_lookup_key and climate_zone_lookup_key in ENERGY_RATING_DATA_2017:
                thresholds = ENERGY_RATING_DATA_2017[climate_zone_lookup_key]
                for min_ip, _, rating_score_val in thresholds:
                    if calculated_improve_by_value >= min_ip:
                        logger.debug(f"Found score: {rating_score_val} (improve_by {calculated_improve_by_value} >= min_ip {min_ip})")
                        return int(rating_score_val)
            elif not climate_zone_lookup_key:
                logger.warning(f"_get_numeric_area_score_for_group: Could not map model_area_definition '{model_area_definition}' to a known climate zone.")
            else:
                logger.warning(f"_get_numeric_area_score_for_group: Climate zone '{climate_zone_lookup_key}' not found in ENERGY_RATING_DATA_2017 for year {model_year}.")
        else:
            logger.warning(f"_get_numeric_area_score_for_group: Energy rating logic for model_year {model_year} not implemented (only 2017).")
    
    logger.debug(f"Returning None for score for group '{group_model_csv_area_desc}'.")
    return None

def _calculate_total_energy_rating(raw_table_data, model_year, model_area_definition):
    """
    Calculate the total energy rating.
    Formula: sum(for each area | zone area * zone multiplier * area score) / sum(for all areas zone area)
    Returns a tuple containing (numeric_score, letter_grade)
    """
    logger.debug(f"_calculate_total_energy_rating received raw_table_data (count: {len(raw_table_data) if raw_table_data else 0}), model_year: {model_year}, model_area_definition: {model_area_definition}")
    if not raw_table_data:
        logger.warning("_calculate_total_energy_rating: raw_table_data is empty or None.")
        return None, None

    # Step 1: Aggregate data per group from raw_table_data (zones)
    # grouped_data[group_key] will store:
    #   'sum_energy_components': sum of (lighting+cooling+heating) for the group
    #   'sum_total_area': sum of 'total_area' for the group
    #   'model_csv_area_description': from one of the zones in the group
    #   'area_effective_for_numerator': sum of (zone_area * zone_multiplier)
    #   'raw_zone_area_sum_for_denominator': sum of (zone_area)
    #   'calculated_score': to be filled in Step 2
    grouped_data = {}
    for row in raw_table_data:
        group_key = (str(row.get('floor_id_report', 'N/A')), str(row.get('area_id_report', 'N/A')))
        if group_key not in grouped_data:
            grouped_data[group_key] = {
                'sum_energy_components': 0.0,
                'sum_total_area': 0.0,
                'model_csv_area_description': row.get('model_csv_area_description'),
                'area_effective_for_numerator': 0.0,
                'raw_zone_area_sum_for_denominator': 0.0,
                'calculated_score': None
            }
        
        zone_area = safe_float(row.get('total_area', 0))
        zone_multiplier = safe_float(row.get('multiplier', 1))
        
        grouped_data[group_key]['sum_energy_components'] += safe_float(row.get('lighting', 0.0)) + \
                                                              safe_float(row.get('cooling', 0.0)) + \
                                                              safe_float(row.get('heating', 0.0))
        grouped_data[group_key]['sum_total_area'] += zone_area
        grouped_data[group_key]['area_effective_for_numerator'] += zone_area * zone_multiplier
        grouped_data[group_key]['raw_zone_area_sum_for_denominator'] += zone_area

    logger.debug(f"_calculate_total_energy_rating: grouped_data after aggregation: {grouped_data}")

    # Step 2: Calculate score for each group
    for group_key, data_item in grouped_data.items():
        score = _get_numeric_area_score_for_group(
            group_sum_energy_components=data_item['sum_energy_components'],
            group_sum_total_area=data_item['sum_total_area'],
            group_model_csv_area_desc=data_item['model_csv_area_description'],
            model_year=model_year,
            model_area_definition=model_area_definition
        )
        data_item['calculated_score'] = score
        if score is None:
            logger.warning(f"Score calculation for group {group_key} resulted in None.")


    logger.debug(f"_calculate_total_energy_rating: grouped_data after score calculation: {grouped_data}")
    
    # Step 3: Calculate final weighted average using the calculated scores
    weighted_score_sum_numerator = 0.0
    total_raw_area_sum_denominator = 0.0
    
    for group_key, data_item in grouped_data.items():
        if data_item['calculated_score'] is not None:
            group_score = safe_float(data_item['calculated_score'])
            group_effective_area = data_item['area_effective_for_numerator']
            # Denominator uses raw zone area of groups that have a score
            group_raw_area_for_denom = data_item['raw_zone_area_sum_for_denominator']

            term_numerator = group_effective_area * group_score
            weighted_score_sum_numerator += term_numerator
            total_raw_area_sum_denominator += group_raw_area_for_denom
            logger.debug(f"  Group {group_key}: score={group_score}, effective_area={group_effective_area}, raw_area_for_denom={group_raw_area_for_denom}. Adding {term_numerator} to numerator, {group_raw_area_for_denom} to denominator.")
        else:
            logger.debug(f"  Group {group_key}: score is None. Skipping from weighted average.")
            
    logger.debug(f"_calculate_total_energy_rating: final weighted_score_sum_numerator = {weighted_score_sum_numerator}, final total_raw_area_sum_denominator = {total_raw_area_sum_denominator}")
            
    if total_raw_area_sum_denominator > 0:
        raw_average = weighted_score_sum_numerator / total_raw_area_sum_denominator
        logger.debug(f"Calculated raw_average: {raw_average} ({weighted_score_sum_numerator}/{total_raw_area_sum_denominator})")
        
        if raw_average % 1 >= 0.5:
            final_score = math.ceil(raw_average)
            logger.debug(f"Rounding up: final_score = {final_score}")
        else:
            final_score = math.floor(raw_average)
            logger.debug(f"Rounding down: final_score = {final_score}")
        
        letter_grade = _get_letter_grade_for_score(final_score)
        logger.info(f"_calculate_total_energy_rating: Calculated final_score = {final_score}, letter_grade = {letter_grade}")
        return final_score, letter_grade
    
    logger.warning("_calculate_total_energy_rating: total_raw_area_sum_denominator is 0 or less. Cannot calculate average.")
    return None, None

def _get_letter_grade_for_score(score):
    """Map a numeric score to its corresponding letter grade"""
    score_to_grade = {
        5: "+A",
        4: "A",
        3: "B",
        2: "C",
        1: "D",
        0: "E",
        -1: "F"
    }
    return score_to_grade.get(score, "N/A")

def _create_total_energy_rating_table(total_score, letter_grade):
    """Create a graphical representation of the total energy rating."""
    elements = []
    styles = getSampleStyleSheet()
    title_style = styles['h2']
    title_style.alignment = TA_CENTER
    title_style.textColor = navy
    elements.append(Paragraph("Total Energy Rating", title_style))
    elements.append(Spacer(1, 0.5 * cm))

    if total_score is None or letter_grade == "N/A":
        no_data_style = styles['Normal']
        no_data_style.alignment = TA_CENTER
        elements.append(Paragraph("Cannot calculate total energy rating.", no_data_style))
        return elements

    drawing_width = 18 * cm
    bar_height = 0.8 * cm
    bar_spacing = 0.3 * cm
    label_offset_x = 0.5 * cm
    hebrew_label_offset_x = 4 * cm # Adjusted for longer Hebrew text
    arrow_width = 0.5 * cm
    arrow_height = bar_height
    
    # Define rating levels, colors (approximated from image), and Hebrew labels
    rating_levels = [
        { "grade": "+A", "label_en": "Diamond", "color": Color(0/255, 114/255, 198/255) }, # Blue
        { "grade": "A",  "label_en": "Platinum", "color": Color(34/255, 139/255, 34/255) },  # Forest Green
        { "grade": "B",  "label_en": "Gold", "color": Color(50/255, 205/255, 50/255) },   # Lime Green
        { "grade": "C",  "label_en": "Silver", "color": Color(154/255, 205/255, 50/255) },  # Yellow Green (approximated)
        { "grade": "D",  "label_en": "Bronze", "color": Color(255/255, 215/255, 0/255) },   # Gold (Yellow)
        { "grade": "E",  "label_en": "Base Level", "color": Color(255/255, 165/255, 0/255) }, # Orange
        { "grade": "F",  "label_en": "Below Base", "color": Color(105/255, 105/255, 105/255) } # Dim Gray, shortened label
    ]

    drawing_height = (bar_height + bar_spacing) * len(rating_levels)
    drawing = Drawing(drawing_width, drawing_height)

    y_position = drawing_height - bar_height 

    for level in rating_levels:
        # Bar
        # Adjusted width calculation for right label space: drawing_width - (arrow_width + label_offset_x (for left grade) + space_for_right_label + arrow_space_if_on_right)
        # Let's allocate more space for the right label by reducing the constant subtracted.
        # Old: drawing_width - (arrow_width + label_offset_x + label_offset_x + 2*cm)
        # New: drawing_width - (arrow_width + label_offset_x + hebrew_label_offset_x + 0.5*cm) # Using hebrew_label_offset_x as it was intended for longer text
        bar_width = drawing_width - (arrow_width + label_offset_x + hebrew_label_offset_x + 0.5*cm)
        bar = Rect(arrow_width + label_offset_x, y_position, bar_width, bar_height)
        bar.fillColor = level["color"]
        bar.strokeColor = black
        bar.strokeWidth = 0.5
        drawing.add(bar)

        # English Label
        eng_label = String(arrow_width + label_offset_x * 2, y_position + bar_height / 4, level["grade"])
        eng_label.fontName = "Helvetica" # Ensure this font supports the characters
        eng_label.fontSize = 10
        eng_label.textAnchor = 'start'
        drawing.add(eng_label)
        
        # English Label (aligned to the right of the bar)
        # For ReportLab, positive X is right, positive Y is up.
        # We position the text using textAnchor = 'end' relative to a point to the right of the bar.
        # The x-position for the right label should be to the right of the bar.
        # Bar ends at: arrow_width + label_offset_x + bar_width
        # Place label slightly after that.
        english_label_x_pos = arrow_width + label_offset_x + bar_width + 0.2*cm # Position for start of text
        eng_label_right = String(english_label_x_pos, y_position + bar_height / 4, level["label_en"])
        eng_label_right.fontName = "Helvetica"
        eng_label_right.fontSize = 9 # Reduced font size slightly for "Below Base"
        eng_label_right.textAnchor = 'start'
        drawing.add(eng_label_right)


        # Arrow if this is the current grade
        if level["grade"] == letter_grade:
            # Arrow pointing right, to the left of the bar
            arrow_tip_x = arrow_width + label_offset_x - 0.2*cm # Tip slightly before the bar starts
            arrow_base_x = label_offset_x # Base further left
            
            arrow_points = [
                arrow_tip_x, y_position + arrow_height / 2,     # Tip
                arrow_base_x, y_position + arrow_height,        # Top left base
                arrow_base_x, y_position                        # Bottom left base
            ]
            arrow = Polygon(arrow_points)
            arrow.fillColor = black
            arrow.strokeColor = black
            drawing.add(arrow)

        y_position -= (bar_height + bar_spacing)

    elements.append(drawing)
    
    # Display the score and letter grade textually below the graphic
    score_text = f"Score: {total_score} ({letter_grade})"
    score_paragraph_style = styles['Normal']
    score_paragraph_style.alignment = TA_CENTER
    score_paragraph_style.fontName = "Helvetica" # Ensure this font supports Hebrew for the grade
    elements.append(Spacer(1, 0.5 * cm))
    elements.append(Paragraph(score_text, score_paragraph_style))

    return elements

def _energy_rating_table(energy_rating_parser, model_year: int, model_area_definition: str, selected_city_name: str):
    """
    Creates the energy rating table as a ReportLab Table object.
    Returns Table object or None if no data.
    """
    raw_table_data = energy_rating_parser.get_energy_rating_table_data()

    if not raw_table_data:
        return None

    def sort_key(item):
        floor_val = item.get('floor_id_report', '') # Changed from 'floor' to 'floor_id_report'
        try:
            floor_sort_val = int(floor_val)
        except ValueError:
            floor_sort_val = str(floor_val)

        area_id_val = str(item.get('area_id', ''))
        zone_id_val = str(item.get('zone_id', ''))
        return (floor_sort_val, area_id_val, zone_id_val)

    raw_table_data.sort(key=sort_key)

    header_row1 = [
        "Building Details", None, None, None, None,
        "Energy Consumption per Meter", None, None, None,
        "Summary and Calculation by 5282", None, None, None
    ]
    header_row2 = [
        "Floor", "Area id", "Zone id", "Zone area", "Zone multiplier",
        "Lighting", "Cooling", "Heating", "Sum",
        "Energy consumption", "Improve by %", "Energy rating", "Area score"
    ]
    table_content = [header_row1, header_row2]

    span_commands = []
    pdf_data_start_row = 2

    group_sums_for_display = {}
    group_total_floor_areas = {}
    if raw_table_data:
        for row_dict in raw_table_data:
            item_group_key_for_sum = (str(row_dict.get('floor_id_report','N/A')), str(row_dict.get('area_id_report','N/A')))
            current_row_energy_sum = safe_float(row_dict.get('lighting', 0.0)) + \
                                     safe_float(row_dict.get('cooling', 0.0)) + \
                                     safe_float(row_dict.get('heating', 0.0))
            group_sums_for_display[item_group_key_for_sum] = group_sums_for_display.get(item_group_key_for_sum, 0.0) + current_row_energy_sum
            group_total_floor_areas[item_group_key_for_sum] = group_total_floor_areas.get(item_group_key_for_sum, 0.0) + safe_float(row_dict.get('total_area', 0.0))

    current_group_key = None
    group_start_pdf_row_index_in_table_content = -1

    for i, row_dict in enumerate(raw_table_data):
        item_group_key = (str(row_dict.get('floor_id_report','N/A')), str(row_dict.get('area_id_report','N/A')))

        display_sum_for_row = ""
        display_energy_consump = ""
        display_improve_by = ""
        display_energy_rating = ""
        display_area_rating = ""
        display_floor_id = str(row_dict.get('floor_id_report', ''))
        display_area_id = str(row_dict.get('area_id_report', ''))

        if item_group_key != current_group_key:
            if current_group_key is not None:
                num_rows_in_prev_group = i - group_start_pdf_row_index_in_table_content
                if num_rows_in_prev_group > 1:
                    start_span_pdf_row = pdf_data_start_row + group_start_pdf_row_index_in_table_content
                    end_span_pdf_row = pdf_data_start_row + i - 1
                    columns_to_span = [0, 1] + list(range(8, 13))
                    for col_idx in columns_to_span:
                        span_commands.append(('SPAN', (col_idx, start_span_pdf_row), (col_idx, end_span_pdf_row)))
                        span_commands.append(('VALIGN', (col_idx, start_span_pdf_row), (col_idx, end_span_pdf_row), 'MIDDLE'))

            current_group_key = item_group_key
            group_start_pdf_row_index_in_table_content = i

            current_group_actual_sum = group_sums_for_display.get(current_group_key, 0.0)
            display_sum_for_row = _format_number(current_group_actual_sum)

            numeric_energy_consumption = None
            display_energy_consump = "N/A"
            display_improve_by = ""
            display_energy_rating = ""
            display_area_rating = ""

            area_location_for_csv_lookup = row_dict.get('model_csv_area_description')

            if area_location_for_csv_lookup and model_year is not None and model_area_definition is not None:
                try:
                    iso_type_for_file_selection = f"MODEL_YEAR_{model_year}"

                    energy_value_raw = get_energy_consumption(
                        iso_type_input=iso_type_for_file_selection,
                        area_location_input=area_location_for_csv_lookup,
                        area_definition_input=model_area_definition
                    )
                    numeric_energy_consumption = float(energy_value_raw)
                    display_energy_consump = _format_number(numeric_energy_consumption)
                except FileNotFoundError as e_fnf:
                    logger.error(f"ReportGen _energy_rating_table: FileNotFoundError. AreaDesc='{area_location_for_csv_lookup}', Year='{model_year}', AreaDef='{model_area_definition}'. Error: {e_fnf}")
                    display_energy_consump = "FNF Error"
                except KeyError as e_key:
                    logger.error(f"ReportGen _energy_rating_table: KeyError. AreaDesc='{area_location_for_csv_lookup}', Year='{model_year}', AreaDef='{model_area_definition}'. Error: {e_key}")
                    display_energy_consump = "Key Error"
                except ValueError as e_val:
                    logger.error(f"ReportGen _energy_rating_table: ValueError. AreaDesc='{area_location_for_csv_lookup}', Year='{model_year}', AreaDef='{model_area_definition}'. Error: {e_val}")
                    display_energy_consump = "Val Error"
                except Exception as e_gen:
                    logger.error(f"ReportGen _energy_rating_table: Exception. AreaDesc='{area_location_for_csv_lookup}', Year='{model_year}', AreaDef='{model_area_definition}'. Error: {e_gen}", exc_info=True)
                    display_energy_consump = "Exc Error"
            else:
                if not area_location_for_csv_lookup:
                    logger.warning(f"ReportGen _energy_rating_table: 'model_csv_area_description' (for area_location_input) is missing or empty in row_dict for group {current_group_key}. display_energy_consump remains N/A.")
                if model_year is None:
                    logger.warning(f"ReportGen _energy_rating_table: model_year is None (for CSV lookup for group {current_group_key}). display_energy_consump remains N/A.")
                if model_area_definition is None:
                    logger.warning(f"ReportGen _energy_rating_table: model_area_definition is None (for CSV lookup for group {current_group_key}). display_energy_consump remains N/A.")

            if numeric_energy_consumption is not None:
                current_group_total_area_val = group_total_floor_areas.get(current_group_key, 0.0)
                calculated_improve_by_value = None

                if current_group_total_area_val <= 70:
                    adjusted_target_ec = 1.18 * numeric_energy_consumption
                    if adjusted_target_ec != 0:
                        calculated_improve_by_value = 100 * (adjusted_target_ec - current_group_actual_sum) / adjusted_target_ec
                    else:
                        display_improve_by = "N/A (Div0 Adj)"
                else:
                    if numeric_energy_consumption != 0:
                        calculated_improve_by_value = 100 * (numeric_energy_consumption - current_group_actual_sum) / numeric_energy_consumption
                    else:
                        display_improve_by = "N/A (Div0 EC)"

                if calculated_improve_by_value is not None:
                    display_improve_by = _format_number(calculated_improve_by_value)
            else:
                display_improve_by = "N/A (No EC)"

            current_display_energy_rating = "N/A"
            current_display_area_score = "N/A"

            if calculated_improve_by_value is not None:
                if model_year == 2017:
                    climate_zone_lookup_key = CLIMATE_ZONE_MAP.get(model_area_definition)

                    if climate_zone_lookup_key and climate_zone_lookup_key in ENERGY_RATING_DATA_2017:
                        thresholds = ENERGY_RATING_DATA_2017[climate_zone_lookup_key]
                        for min_ip, rating_letter, rating_score_val in thresholds:
                            if calculated_improve_by_value >= min_ip:
                                current_display_energy_rating = rating_letter
                                current_display_area_score = str(rating_score_val)
                                break
                    elif not climate_zone_lookup_key:
                        logger.warning(f"ReportGen _energy_rating_table: Could not map model_area_definition '{model_area_definition}' to a known climate zone. Rating/Score will be N/A.")
                    else:
                        logger.warning(f"ReportGen _energy_rating_table: Climate zone '{climate_zone_lookup_key}' (from model_area_definition '{model_area_definition}') not found in ENERGY_RATING_DATA_2017 for year {model_year}. Rating/Score will be N/A.")
                else:
                    logger.warning(f"ReportGen _energy_rating_table: Energy rating logic currently implemented for model_year 2017. Found {model_year}. Rating/Score will be N/A.")

            display_energy_rating = current_display_energy_rating
            display_area_rating = current_display_area_score

            if isinstance(calculated_improve_by_value, (int, float)):
                 display_improve_by = _format_number(calculated_improve_by_value)


        else:
            display_floor_id = ""
            display_area_id = ""
            display_sum_for_row = ""
            display_energy_consump = ""
            display_improve_by = ""
            display_energy_rating = ""
            display_area_rating = ""

        table_content.append([
            display_floor_id,
            display_area_id,
            str(row_dict.get('zone_name_report', '')),
            _format_number(row_dict.get('total_area', 0)),
            str(row_dict.get('multiplier', '')),
            _format_number(row_dict.get('lighting', 0)),
            _format_number(row_dict.get('cooling', 0)),
            _format_number(row_dict.get('heating', 0)),
            display_sum_for_row,
            display_energy_consump,
            display_improve_by,
            display_energy_rating,
            display_area_rating
        ])

    if current_group_key is not None and raw_table_data:
        num_rows_in_last_group = len(raw_table_data) - group_start_pdf_row_index_in_table_content
        if num_rows_in_last_group > 1:
            start_span_pdf_row = pdf_data_start_row + group_start_pdf_row_index_in_table_content
            end_span_pdf_row = pdf_data_start_row + len(raw_table_data) - 1
            columns_to_span = [0, 1] + list(range(8, 13))
            for col_idx in columns_to_span:
                span_commands.append(('SPAN', (col_idx, start_span_pdf_row), (col_idx, end_span_pdf_row)))
                span_commands.append(('VALIGN', (col_idx, start_span_pdf_row), (col_idx, end_span_pdf_row), 'MIDDLE'))

    table = Table(table_content)
    style = _get_table_style()
    for cmd in span_commands:
        style.add(*cmd)
    table.setStyle(style)
    return table

class EnergyRatingReportGenerator:
    """Generates PDF reports showing energy consumption and rating information."""
    def __init__(self, energy_rating_parser, output_dir="output/reports",
                 model_year: int = None, model_area_definition: str = None,
                 selected_city_name: str = None):
        self.energy_rating_parser = energy_rating_parser
        self.output_dir = output_dir
        self.model_year = model_year
        self.model_area_definition = model_area_definition
        self.selected_city_name = selected_city_name
        self.styles = getSampleStyleSheet()
        self.margin = 1 * cm
        if self.selected_city_name:
            pass
        else:
            logger.warning(f"EnergyRatingReportGenerator initialized WITHOUT city. Year: {self.model_year}, AreaDef: '{self.model_area_definition}'")

    def generate_report(self, output_filename="energy-rating.pdf"):
        """
        Generate energy rating report PDF using ReportLab.
        """
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        output_path = os.path.join(self.output_dir, output_filename)

        try:
            if not self.energy_rating_parser.processed:
                self.energy_rating_parser.process_output()

            doc = SimpleDocTemplate(output_path, pagesize=landscape(A4),
                                    leftMargin=self.margin, rightMargin=self.margin,
                                    topMargin=self.margin, bottomMargin=self.margin)
            story = []

            title_style = self.styles['h1']
            title_style.alignment = TA_CENTER
            title_style.textColor = navy
            story.append(Paragraph("Energy Rating Report", title_style))
            story.append(Spacer(1, 0.5*cm))

            energy_table = _energy_rating_table(
                self.energy_rating_parser,
                self.model_year,
                self.model_area_definition,
                self.selected_city_name
            )
            if energy_table:
                story.append(energy_table)
            else:
                no_data_style = self.styles['Normal']
                no_data_style.alignment = TA_CENTER
                story.append(Paragraph("No energy rating data available.", no_data_style))

            doc.build(story)
            return output_path

        except Exception as e:
            raise RuntimeError(f"Error generating energy rating report: {e}")
            
    def generate_total_energy_rating_report(self, output_filename="total_energy_rating.pdf"):
        """
        Generate total energy rating report PDF using ReportLab.
        The total rating is a weighted average of area scores based on each area's size.
        """
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        output_path = os.path.join(self.output_dir, output_filename)

        try:
            if not self.energy_rating_parser.processed:
                self.energy_rating_parser.process_output()
                
            # Get the table data which contains area scores
            raw_table_data = self.energy_rating_parser.get_energy_rating_table_data()
            
            # Calculate the total energy rating (numeric score and letter grade)
            total_score, letter_grade = _calculate_total_energy_rating(
                raw_table_data,
                self.model_year,
                self.model_area_definition
            )
            
            # Create the PDF document
            doc = SimpleDocTemplate(output_path, pagesize=A4,
                                   leftMargin=self.margin, rightMargin=self.margin,
                                   topMargin=self.margin, bottomMargin=self.margin)
            story = []

            # Add title
            title_style = self.styles['h1']
            title_style.alignment = TA_CENTER
            title_style.textColor = navy
            story.append(Paragraph("Total Energy Rating Report", title_style))
            story.append(Spacer(1, 1*cm))
            
            # Add project information
            info_style = self.styles['Normal']
            if self.selected_city_name:
                story.append(Paragraph(f"City: {self.selected_city_name}", info_style))
            if self.model_year:
                story.append(Paragraph(f"Model Year: {self.model_year}", info_style))
            if self.model_area_definition:
                climate_zone = CLIMATE_ZONE_MAP.get(self.model_area_definition, self.model_area_definition)
                story.append(Paragraph(f"Climate Zone: {climate_zone}", info_style))
            story.append(Spacer(1, 1*cm))
            
            # Create and add the total rating table
            if total_score is not None and letter_grade != "N/A":
                rating_table = _create_total_energy_rating_table(total_score, letter_grade)
                if rating_table:
                    story.append(Spacer(1, 1*cm))
                    story.extend(rating_table) # Changed append to extend
            else:
                styles = getSampleStyleSheet()
                unavailable_style = styles['Normal']
                unavailable_style.alignment = TA_CENTER
                story.append(Paragraph("Total energy rating not available.", unavailable_style))

            # Build the PDF
            doc.build(story)
            logger.info(f"Generated total energy rating report: {output_path}")
            return output_path

        except Exception as e:
            error_message = f"Error generating total energy rating report: {e}"
            logger.error(error_message, exc_info=True)
            raise RuntimeError(error_message)
