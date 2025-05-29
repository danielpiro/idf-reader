"""
Generates energy rating reports from processed energy consumption data.
"""
import logging
import os
import math
import datetime
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from utils.data_loader import get_energy_consumption
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.colors import black, Color

COLORS = {
    'primary_blue': Color(0.2, 0.4, 0.7),
    'secondary_blue': Color(0.4, 0.6, 0.85),
    'light_blue': Color(0.9, 0.94, 0.98),
    'dark_gray': Color(0.2, 0.2, 0.2),
    'medium_gray': Color(0.5, 0.5, 0.5),
    'light_gray': Color(0.9, 0.9, 0.9),
    'white': Color(1, 1, 1),
    'border_gray': Color(0.8, 0.8, 0.8),
}

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
from reportlab.lib.enums import TA_CENTER
from reportlab.graphics.shapes import Drawing, Rect, Polygon, String

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
        ('BACKGROUND', (0,0), (-1,0), COLORS['primary_blue']),
        ('TEXTCOLOR', (0,0), (-1,0), COLORS['white']),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('VALIGN', (0,0), (-1,0), 'MIDDLE'),
        ('FONTNAME', (0,0), (-1,0), FONTS['table_header']),
        ('FONTSIZE', (0,0), (-1,0), FONT_SIZES['table_header']),

        ('BACKGROUND', (0,1), (-1,1), COLORS['secondary_blue']),
        ('TEXTCOLOR', (0,1), (-1,1), COLORS['white']),
        ('ALIGN', (0,1), (-1,1), 'CENTER'),
        ('VALIGN', (0,1), (-1,1), 'MIDDLE'),
        ('FONTNAME', (0,1), (-1,1), FONTS['table_header']),
        ('FONTSIZE', (0,1), (-1,1), FONT_SIZES['table_body']),

        ('SPAN', (0,0), (4,0)),
        ('SPAN', (5,0), (8,0)),
        ('SPAN', (9,0), (12,0)),

        ('FONTNAME', (0,2), (-1,-1), FONTS['table_body']),
        ('FONTSIZE', (0,2), (-1,-1), FONT_SIZES['table_body']),
        ('ALIGN', (0,2), (-1,-1), 'CENTER'),
        ('VALIGN', (0,2), (-1,-1), 'MIDDLE'),
        ('TEXTCOLOR', (0,2), (-1,-1), COLORS['dark_gray']),

        ('ROWBACKGROUNDS', (0,2), (-1,-1), [COLORS['white'], COLORS['light_blue']]),

        ('LINEBELOW', (0,0), (-1,0), 1, COLORS['border_gray']),
        ('LINEBELOW', (0,1), (-1,1), 1, COLORS['border_gray']),
        ('GRID', (0,2), (-1,-1), 0.5, COLORS['border_gray']),
        ('BOX', (0,0), (-1,-1), 1, COLORS['medium_gray']),

        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
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

        except Exception as e:
            logger.error(f"Error in _get_numeric_area_score_for_group getting energy consumption for '{group_model_csv_area_desc}': {e}")
    else:
        logger.warning(f"_get_numeric_area_score_for_group: Missing required parameters. group_model_csv_area_desc: {group_model_csv_area_desc}, model_year: {model_year}, model_area_definition: {model_area_definition}")

    calculated_improve_by_value = None
    if numeric_energy_consumption is not None:

        if group_sum_total_area <= 70:
            adjusted_target_ec = 1.18 * numeric_energy_consumption

            if adjusted_target_ec != 0:
                calculated_improve_by_value = 100 * (adjusted_target_ec - group_sum_energy_components) / adjusted_target_ec
            else:
                logger.warning(f"_get_numeric_area_score_for_group: adjusted_target_ec is 0, cannot calculate improve_by_value for area <= 70")

        else:
            if numeric_energy_consumption != 0:
                calculated_improve_by_value = 100 * (numeric_energy_consumption - group_sum_energy_components) / numeric_energy_consumption
            else:
                logger.warning(f"_get_numeric_area_score_for_group: numeric_energy_consumption is 0, cannot calculate improve_by_value for area > 70")

    else:
        logger.warning(f"_get_numeric_area_score_for_group: numeric_energy_consumption is None, cannot calculate improve_by_value")

    if calculated_improve_by_value is not None:
        if model_year == 2017:
            climate_zone_lookup_key = CLIMATE_ZONE_MAP.get(model_area_definition)

            if climate_zone_lookup_key and climate_zone_lookup_key in ENERGY_RATING_DATA_2017:
                thresholds = ENERGY_RATING_DATA_2017[climate_zone_lookup_key]
                for min_ip, _, rating_score_val in thresholds:
                    if calculated_improve_by_value >= min_ip:

                        return int(rating_score_val)
            elif not climate_zone_lookup_key:
                logger.warning(f"_get_numeric_area_score_for_group: Could not map model_area_definition '{model_area_definition}' to a known climate zone.")
            else:
                logger.warning(f"_get_numeric_area_score_for_group: Climate zone '{climate_zone_lookup_key}' not found in ENERGY_RATING_DATA_2017 for year {model_year}.")
        else:
            logger.warning(f"_get_numeric_area_score_for_group: Energy rating logic for model_year {model_year} not implemented (only 2017).")

    return None

def _calculate_total_energy_rating(raw_table_data, model_year, model_area_definition):
    """
    Calculate the total energy rating.
    Formula: sum(for each area | zone area * zone multiplier * area score) / sum(for all areas zone area)
    Returns a tuple containing (numeric_score, letter_grade)
    """

    if not raw_table_data:
        logger.warning("_calculate_total_energy_rating: raw_table_data is empty or None.")
        return None, None

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

    weighted_score_sum_numerator = 0.0
    total_raw_area_sum_denominator = 0.0

    for group_key, data_item in grouped_data.items():
        if data_item['calculated_score'] is not None:
            group_score = safe_float(data_item['calculated_score'])
            group_effective_area = data_item['area_effective_for_numerator']
            group_raw_area_for_denom = data_item['raw_zone_area_sum_for_denominator']

            term_numerator = group_effective_area * group_score
            weighted_score_sum_numerator += term_numerator
            total_raw_area_sum_denominator += group_raw_area_for_denom

        else:
            logger.warning(f"_calculate_total_energy_rating: Group {group_key} has calculated_score as None, excluding from weighted calculation")

    if total_raw_area_sum_denominator > 0:
        raw_average = weighted_score_sum_numerator / total_raw_area_sum_denominator

        if raw_average % 1 >= 0.5:
            final_score = math.ceil(raw_average)

        else:
            final_score = math.floor(raw_average)

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

    if total_score is None or letter_grade == "N/A":
        styles = getSampleStyleSheet()
        no_data_style = styles['Normal']
        no_data_style.alignment = TA_CENTER
        no_data_style.fontName = FONTS['body']
        no_data_style.fontSize = FONT_SIZES['body']
        no_data_style.textColor = COLORS['medium_gray']
        elements.append(Paragraph("Cannot calculate total energy rating.", no_data_style))
        return elements

    drawing_width = 18 * cm
    bar_height = 0.8 * cm
    bar_spacing = 0.3 * cm
    label_offset_x = 0.5 * cm
    hebrew_label_offset_x = 4 * cm
    left_arrow_width = 0.5 * cm
    right_arrow_width = 1.5 * cm
    right_arrow_height = bar_height

    rating_levels = [
        { "grade": "+A", "label_en": "Diamond", "color": Color(0.0157, 0.4549, 0.7686) },
        { "grade": "A",  "label_en": "Platinum", "color": Color(0.1059, 0.5059, 0.2353) },
        { "grade": "B",  "label_en": "Gold", "color": Color(0.1608, 0.6824, 0.3098) },
        { "grade": "C",  "label_en": "Silver", "color": Color(0.2000, 0.8000, 0.2000) },
        { "grade": "D",  "label_en": "Bronze", "color": Color(1.0000, 0.8000, 0.0000) },
        { "grade": "E",  "label_en": "Base Level", "color": Color(0.9843, 0.3961, 0.0000) },
        { "grade": "F",  "label_en": "Below Base", "color": Color(0.3451, 0.3451, 0.3451) }
    ]

    drawing_height = (bar_height + bar_spacing) * len(rating_levels)
    drawing = Drawing(drawing_width, drawing_height)

    y_position = drawing_height - bar_height 

    for level in rating_levels:
        bar_width = drawing_width - (left_arrow_width + label_offset_x + hebrew_label_offset_x + right_arrow_width + 1*cm)
        bar = Rect(left_arrow_width + label_offset_x, y_position, bar_width, bar_height)
        bar.fillColor = level["color"]
        bar.strokeColor = COLORS['border_gray']
        bar.strokeWidth = 0.5
        drawing.add(bar)

        eng_label = String(left_arrow_width + label_offset_x * 2, y_position + bar_height / 2.5, level["grade"])
        eng_label.fontName = FONTS['table_header']
        eng_label.fontSize = FONT_SIZES['table_body']
        eng_label.textAnchor = 'start'
        if level["grade"] in ["+A", "A", "B", "F"]:
            eng_label.fillColor = COLORS['white']
        else:
            eng_label.fillColor = COLORS['dark_gray']
        drawing.add(eng_label)

        english_label_x_pos = left_arrow_width + label_offset_x + bar_width + 0.2*cm
        eng_label_right = String(english_label_x_pos, y_position + bar_height / 2.5, level["label_en"])
        eng_label_right.fontName = FONTS['body']
        eng_label_right.fontSize = FONT_SIZES['table_body']
        eng_label_right.textAnchor = 'start'
        eng_label_right.fillColor = COLORS['dark_gray']
        drawing.add(eng_label_right)

        if level["grade"] == letter_grade:
            arrow_base_x = drawing_width - right_arrow_width - 0.2*cm
            arrow_tip_x = arrow_base_x - 0.3*cm

            arrow_points = [
                arrow_tip_x, y_position + right_arrow_height / 2,
                arrow_base_x, y_position + right_arrow_height * 0.25,
                arrow_base_x, y_position + right_arrow_height * 0.4,
                arrow_base_x + right_arrow_width, y_position + right_arrow_height * 0.4,
                arrow_base_x + right_arrow_width, y_position + right_arrow_height * 0.6,
                arrow_base_x, y_position + right_arrow_height * 0.6,
                arrow_base_x, y_position + right_arrow_height * 0.75
            ]

            arrow = Polygon(arrow_points)
            arrow.fillColor = level["color"]
            arrow.strokeColor = Color(0.2, 0.2, 0.2)
            arrow.strokeWidth = 1
            drawing.add(arrow)

            arrow_label_x = arrow_base_x + right_arrow_width / 2
            arrow_label_y = y_position + right_arrow_height / 2.5
            arrow_label = String(arrow_label_x, arrow_label_y, level["grade"])
            arrow_label.fontName = FONTS['table_header']
            arrow_label.fontSize = FONT_SIZES['table_body']
            arrow_label.textAnchor = 'middle'
            if level["grade"] in ["+A", "A", "B", "F"]:
                arrow_label.fillColor = COLORS['white']
            else:
                arrow_label.fillColor = COLORS['dark_gray']
            drawing.add(arrow_label)

        y_position -= (bar_height + bar_spacing)

    elements.append(drawing)

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
        floor_val = item.get('floor_id_report', '')
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
            calculated_improve_by_value = None
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
                 selected_city_name: str = None, project_name: str = "N/A", 
                 run_id: str = "N/A", area_name: str = "N/A"):
        self.energy_rating_parser = energy_rating_parser
        self.output_dir = output_dir
        self.model_year = model_year
        self.model_area_definition = model_area_definition
        self.selected_city_name = selected_city_name
        self.project_name = project_name
        self.run_id = run_id
        self.area_name = area_name
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

            from reportlab.lib.styles import ParagraphStyle
            from reportlab.lib.enums import TA_RIGHT
            header_info_style = ParagraphStyle(
                'HeaderInfo', 
                parent=self.styles['Normal'], 
                fontSize=9, 
                textColor=COLORS['white'], 
                alignment=TA_RIGHT
            )
            now = datetime.datetime.now()
            header_text = f"""
            Project: {self.project_name}<br/>
            Run ID: {self.run_id}<br/>
            Date: {now.strftime('%Y-%m-%d %H:%M:%S')}<br/>
            City: {self.selected_city_name or 'N/A'}<br/>
            Area: {self.area_name}<br/>
            Report: Energy Rating Report
            """
            story.append(Paragraph(header_text, header_info_style))
            story.append(Spacer(1, 5))

            title_style = self.styles['h1']
            title_style.alignment = TA_CENTER
            title_style.textColor = COLORS['primary_blue']
            title_style.fontName = FONTS['title']
            title_style.fontSize = FONT_SIZES['title']
            story.append(Paragraph("Energy Rating Report", title_style))
            story.append(Spacer(1, 0.7*cm))

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
                no_data_style.fontName = FONTS['body']
                no_data_style.fontSize = FONT_SIZES['body']
                no_data_style.textColor = COLORS['medium_gray']
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

            raw_table_data = self.energy_rating_parser.get_energy_rating_table_data()

            total_score, letter_grade = _calculate_total_energy_rating(
                raw_table_data,
                self.model_year,
                self.model_area_definition
            )
            doc = SimpleDocTemplate(output_path, pagesize=A4,
                                   leftMargin=self.margin, rightMargin=self.margin,
                                   topMargin=self.margin, bottomMargin=self.margin)
            story = []

            from reportlab.lib.styles import ParagraphStyle
            from reportlab.lib.enums import TA_RIGHT
            header_info_style = ParagraphStyle(
                'HeaderInfo', 
                parent=self.styles['Normal'], 
                fontSize=9, 
                textColor=COLORS['white'], 
                alignment=TA_RIGHT
            )
            now = datetime.datetime.now()
            header_text = f"""
            Project: {self.project_name}<br/>
            Run ID: {self.run_id}<br/>
            Date: {now.strftime('%Y-%m-%d %H:%M:%S')}<br/>
            City: {self.selected_city_name or 'N/A'}<br/>
            Area: {self.area_name}<br/>
            Report: Total Energy Rating Report
            """
            story.append(Paragraph(header_text, header_info_style))
            story.append(Spacer(1, 5))

            title_style = self.styles['h1']
            title_style.alignment = TA_CENTER
            title_style.textColor = COLORS['primary_blue']
            title_style.fontName = FONTS['title']
            title_style.fontSize = FONT_SIZES['title']
            story.append(Paragraph("Total Energy Rating Report", title_style))
            story.append(Spacer(1, 1*cm))

            if total_score is not None and letter_grade != "N/A":
                rating_table = _create_total_energy_rating_table(total_score, letter_grade)
                if rating_table:
                    story.append(Spacer(1, 1*cm))
                    story.extend(rating_table)
            else:
                styles = getSampleStyleSheet()
                unavailable_style = styles['Normal']
                unavailable_style.alignment = TA_CENTER
                unavailable_style.fontName = FONTS['body']
                unavailable_style.fontSize = FONT_SIZES['body']
                unavailable_style.textColor = COLORS['medium_gray']
                story.append(Paragraph("Total energy rating not available.", unavailable_style))

            doc.build(story)
            logger.info(f"Generated total energy rating report: {output_path}")
            return output_path

        except Exception as e:
            error_message = f"Error generating total energy rating report: {e}"
            logger.error(error_message, exc_info=True)
            raise RuntimeError(error_message)
