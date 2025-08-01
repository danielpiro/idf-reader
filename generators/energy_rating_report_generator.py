"""
Generates energy rating reports from processed energy consumption data.
"""
from utils.logging_config import get_logger
import os
import math
import datetime
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from utils.data_loader import get_energy_consumption, safe_float
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import black, Color
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
from utils.hebrew_text_utils import safe_format_header_text, get_hebrew_font_name, encode_hebrew_text
from utils.logo_utils import create_logo_image
from generators.shared_design_system import (
    COLORS, FONTS, FONT_SIZES, LAYOUT,
    create_multi_header_table_style, create_title_style, 
    create_header_info_style, create_standardized_header
)

from reportlab.lib.enums import TA_CENTER
from reportlab.graphics.shapes import Drawing, Rect, Polygon, String

logger = get_logger(__name__)

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

ENERGY_RATING_DATA_OFFICE = {
    "Zone A": [
        (46, "+A", 5), (40, "A", 4), (34, "B", 3), (28, "C", 2), (20, "D", 1),
        (10, "E", 0), (-float('inf'), "F", -1)
    ],
    "Zone B": [
        (52, "+A", 5), (44, "A", 4), (36, "B", 3), (28, "C", 2), (20, "D", 1),
        (10, "E", 0), (-float('inf'), "F", -1)
    ],
    "Zone C": [
        (52, "+A", 5), (44, "A", 4), (36, "B", 3), (28, "C", 2), (20, "D", 1),
        (10, "E", 0), (-float('inf'), "F", -1)
    ],
    "Zone D": [
        (46, "+A", 5), (40, "A", 4), (34, "B", 3), (28, "C", 2), (20, "D", 1),
        (10, "E", 0), (-float('inf'), "F", -1)
    ]
}

# 2023 uses a simplified rating system with universal thresholds
# Based on the image: A+=5, A=4, B=3, C=2, D=1, E=0, F=-1
# Thresholds: 40≥, 30≥, 20≥, 10≥, 0≥, -10≥, -20≥
ENERGY_RATING_DATA_2023 = [
    (40, "A+", 5), (30, "A", 4), (20, "B", 3), (10, "C", 2), (0, "D", 1),
    (-10, "E", 0), (-float('inf'), "F", -1)
]

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
        ('TEXTCOLOR', (0,1), (-1,1), COLORS['dark_gray']),
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
    if value is None:
        return '-'
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

def _get_numeric_area_score_for_group(group_sum_energy_components, group_sum_total_area, group_model_csv_area_desc, model_year, model_area_definition):
    """
    Calculates the numeric area score for a group based on its aggregated data.
    This function encapsulates logic similar to that in _energy_rating_table for determining area score.
    Returns an integer score or None.
    """


    numeric_energy_consumption = None
    calculated_improve_by_value = None  # Initialize at the beginning to avoid UnboundLocalError
    
    if group_model_csv_area_desc and model_year is not None and model_area_definition is not None:
        try:
            # Handle office model year differently
            if str(model_year).lower() == 'office' or (isinstance(model_year, str) and 'office' in model_year.lower()):
                iso_type_for_file_selection = "office"
            else:
                iso_type_for_file_selection = f"MODEL_YEAR_{model_year}"
            
            # For 2023 models, convert climate zone letters to numeric codes if needed
            area_def_for_lookup = model_area_definition
            if model_year == 2023 and model_area_definition in ['A', 'B', 'C', 'D']:
                # Map climate zones to numeric codes for 2023
                zone_to_numeric = {'A': '1', 'B': '2', 'C': '3', 'D': '4'}
                area_def_for_lookup = zone_to_numeric.get(model_area_definition, model_area_definition)
                logger.warning(f"_get_numeric_area_score_for_group: Converting 2023 climate zone '{model_area_definition}' to numeric code '{area_def_for_lookup}'")
            
            energy_value_raw = get_energy_consumption(
                iso_type_input=iso_type_for_file_selection,
                area_location_input=group_model_csv_area_desc,
                area_definition_input=area_def_for_lookup
            )
            numeric_energy_consumption = float(energy_value_raw)

        except Exception as e:
            logger.error(f"Error in _get_numeric_area_score_for_group getting energy consumption for '{group_model_csv_area_desc}': {e}")
    else:
        logger.warning(f"_get_numeric_area_score_for_group: Missing required parameters. group_model_csv_area_desc: {group_model_csv_area_desc}, model_year: {model_year}, model_area_definition: {model_area_definition}")
    
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
        elif model_year == 2023:
            # 2023 uses universal thresholds, no climate zone mapping needed
            thresholds = ENERGY_RATING_DATA_2023
            for min_ip, _, rating_score_val in thresholds:
                if calculated_improve_by_value >= min_ip:
                    return int(rating_score_val)
        elif str(model_year).lower() == 'office' or (isinstance(model_year, str) and 'office' in model_year.lower()):
            climate_zone_lookup_key = CLIMATE_ZONE_MAP.get(model_area_definition)

            if climate_zone_lookup_key and climate_zone_lookup_key in ENERGY_RATING_DATA_OFFICE:
                thresholds = ENERGY_RATING_DATA_OFFICE[climate_zone_lookup_key]
                for min_ip, _, rating_score_val in thresholds:
                    if calculated_improve_by_value >= min_ip:
                        return int(rating_score_val)
            elif not climate_zone_lookup_key:
                logger.warning(f"_get_numeric_area_score_for_group: Could not map model_area_definition '{model_area_definition}' to a known climate zone for office.")
            else:
                logger.warning(f"_get_numeric_area_score_for_group: Climate zone '{climate_zone_lookup_key}' not found in ENERGY_RATING_DATA_OFFICE for office buildings.")
        else:
            logger.warning(f"_get_numeric_area_score_for_group: Energy rating logic for model_year {model_year} not implemented (only 2017, 2023, and office).")
    return None

def _calculate_total_energy_rating(raw_table_data, model_year, model_area_definition):
    """
    Calculate the total energy rating using weighted area-based scoring.
    
    FINAL EQUATION:
    
    Final_Score = round(Σ(Area_i × Multiplier_i × Score_i) / Σ(Area_i × Multiplier_i))
    
    Where:
    - Area_i = zone area for group i (m²)
    - Multiplier_i = zone multiplier for group i (capped at 1.0 if >10 to prevent calculation errors)
    - Score_i = individual area score (-1 to 5) based on improvement percentage vs. reference consumption
    - Σ = summation over all area groups
    
    Score_i calculation:
    improvement_% = 100 × (reference_consumption - actual_consumption) / reference_consumption
    Score_i = threshold_lookup(improvement_%, model_year, climate_zone)
    
    Special cases:
    - Small areas (≤70 m²): reference_consumption × 1.18 (18% bonus)
    - 2023 models: Final_Score capped by lowest individual Score_i if any Score_i ≤ 0
    - Final bounds: -1 ≤ Final_Score ≤ 5
    
    Returns a tuple containing (numeric_score, letter_grade)
    """

    if not raw_table_data:
        logger.warning("_calculate_total_energy_rating: raw_table_data is empty or None.")
        return None, None

    def safe_float(value, default=0.0):
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    grouped_data = {}
    for row in raw_table_data:
        group_key = (str(row.get('floor_id_report', 'N/A')), str(row.get('area_id_report', 'N/A')))
        if group_key not in grouped_data:
            grouped_data[group_key] = {
                'sum_energy_components': 0.0,
                'sum_total_area': 0.0,
                'model_csv_area_description': row.get('model_csv_area_description'),
                'area_effective_for_numerator': 0.0,
                'raw_zone_area_sum_for_denominator': 0.0,                'calculated_score': None
            }

        zone_area = safe_float(row.get('total_area', 0))
        zone_multiplier = safe_float(row.get('multiplier', 1))

        # For 2023, exclude lighting from energy calculations
        # Note: Energy values are already per-zone (divided by multiplier in energy parser)
        if model_year == 2023:
            grouped_data[group_key]['sum_energy_components'] += safe_float(row.get('cooling', 0.0)) + \
                                                                  safe_float(row.get('heating', 0.0))
        else:
            grouped_data[group_key]['sum_energy_components'] += safe_float(row.get('lighting', 0.0)) + \
                                                                  safe_float(row.get('cooling', 0.0)) + \
                                                                  safe_float(row.get('heating', 0.0))
        grouped_data[group_key]['sum_total_area'] += zone_area
        grouped_data[group_key]['area_effective_for_numerator'] += zone_area * zone_multiplier
        grouped_data[group_key]['raw_zone_area_sum_for_denominator'] += zone_area * zone_multiplier

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

            # Validate that group_score is within valid range (-1 to 5)
            if group_score < -1 or group_score > 5:
                logger.error(f"_calculate_total_energy_rating: Group {group_key} has invalid score {group_score} (must be -1 to 5). Setting to 0.")
                group_score = 0

            term_numerator = group_effective_area * group_score
            weighted_score_sum_numerator += term_numerator
            total_raw_area_sum_denominator += group_raw_area_for_denom
            
            # Debug logging to track the calculation
            logger.debug(f"Group {group_key}: score={group_score}, effective_area={group_effective_area:.2f}, raw_area={group_raw_area_for_denom:.2f}, numerator_contribution={term_numerator:.2f}")

        else:
            logger.warning(f"_calculate_total_energy_rating: Group {group_key} has calculated_score as None, excluding from weighted calculation")

    if total_raw_area_sum_denominator > 0:
        raw_average = weighted_score_sum_numerator / total_raw_area_sum_denominator
        
        # Debug logging to understand the calculation
        logger.info(f"_calculate_total_energy_rating: weighted_sum_numerator={weighted_score_sum_numerator:.2f}, denominator={total_raw_area_sum_denominator:.2f}, raw_average={raw_average:.2f}")

        # For 2023: If any area gets E (0) or F (-1), cap the total rating accordingly
        if model_year == 2023:
            lowest_score = None
            for group_key, data_item in grouped_data.items():
                if data_item['calculated_score'] is not None:
                    score = data_item['calculated_score']
                    if lowest_score is None or score < lowest_score:
                        lowest_score = score
            
            # If any area got E (0) or F (-1), cap the total at that level
            if lowest_score is not None and lowest_score <= 0:
                final_score = min(lowest_score, math.floor(raw_average) if raw_average % 1 < 0.5 else math.ceil(raw_average))
            else:
                final_score = math.ceil(raw_average) if raw_average % 1 >= 0.5 else math.floor(raw_average)
        else:
            # For non-2023 models, use normal calculation
            final_score = math.ceil(raw_average) if raw_average % 1 >= 0.5 else math.floor(raw_average)

        # Ensure final score is within valid bounds (-1 to 5)
        if final_score < -1:
            logger.warning(f"_calculate_total_energy_rating: Final score {final_score} is below minimum (-1). Capping to -1.")
            final_score = -1
        elif final_score > 5:
            logger.warning(f"_calculate_total_energy_rating: Final score {final_score} is above maximum (5). Capping to 5.")
            final_score = 5

        letter_grade = _get_letter_grade_for_score(final_score)
        logger.info(f"_calculate_total_energy_rating: Calculated final_score = {final_score}, letter_grade = {letter_grade}")
        return final_score, letter_grade

    logger.warning("_calculate_total_energy_rating: total_raw_area_sum_denominator is 0 or less. Cannot calculate average.")
    return None, None

def _get_letter_grade_for_score(score):
    """Map a numeric score to its corresponding letter grade"""
    if score is None:
        return "N/A"
    
    # Handle scores within normal range
    if score >= 5:
        return "+A"
    elif score >= 4:
        return "A"
    elif score >= 3:
        return "B"
    elif score >= 2:
        return "C"
    elif score >= 1:
        return "D"
    elif score >= 0:
        return "E"
    else:
        # Any score below 0 is F (including negative scores from 2023 capping logic)
        return "F"

def _create_energy_rating_table_visual(total_score, letter_grade):
    """Create a professional energy rating table with chevron arrows."""
    elements = []
    
    if total_score is None or letter_grade == "N/A":
        styles = getSampleStyleSheet()
        no_data_style = styles['Normal']
        no_data_style.alignment = TA_CENTER
        no_data_style.fontName = get_hebrew_font_name()
        no_data_style.fontSize = FONT_SIZES['body']
        no_data_style.textColor = COLORS['medium_gray']
        elements.append(Paragraph("לא ניתן לחשב דירוג אנרגטי", no_data_style))
        return elements

    from reportlab.graphics.shapes import Drawing, Rect, String, Polygon

    # Professional dimensions
    drawing_width = 16 * cm
    base_bar_height = 0.7 * cm
    bar_spacing = 0.1 * cm
    chevron_width = 1.2 * cm
    
    # Define rating levels - REVERSED LENGTH (F longest, +A shortest) like in reference
    rating_levels = [
        {"grade": "+A", "label_he": "יהלום", "color": Color(0.0, 0.5, 0.0), "length_factor": 0.5},      # Best = shortest
        {"grade": "A", "label_he": "פלטינה", "color": Color(0.3, 0.7, 0.0), "length_factor": 0.58},
        {"grade": "B", "label_he": "זהב", "color": Color(0.6, 0.8, 0.0), "length_factor": 0.66},
        {"grade": "C", "label_he": "כסף", "color": Color(0.9, 0.9, 0.0), "length_factor": 0.74},
        {"grade": "D", "label_he": "ברונזה", "color": Color(1.0, 0.6, 0.0), "length_factor": 0.82},
        {"grade": "E", "label_he": "רמה בסיסית", "color": Color(1.0, 0.3, 0.0), "length_factor": 0.9},
        {"grade": "F", "label_he": "מתחת לבסיס", "color": Color(0.8, 0.0, 0.0), "length_factor": 1.0}  # Worst = longest
    ]

    drawing_height = (base_bar_height + bar_spacing) * len(rating_levels)
    drawing = Drawing(drawing_width, drawing_height)

    y_position = drawing_height - base_bar_height
    max_bar_width = drawing_width - chevron_width - 1*cm

    for level in rating_levels:
        # Calculate bar width (reverse order - worse ratings are longer)
        bar_width = max_bar_width * level["length_factor"]
        
        # Create the main bar rectangle
        bar_rect = Rect(0.5*cm, y_position, bar_width, base_bar_height)
        bar_rect.fillColor = level["color"]
        bar_rect.strokeColor = Color(0.2, 0.2, 0.2)
        bar_rect.strokeWidth = 0.5
        drawing.add(bar_rect)
        
        # Create simple chevron arrow end (no pointy tip)
        chevron_start_x = 0.5*cm + bar_width
        chevron_end_x = chevron_start_x + chevron_width
        chevron_mid_y = y_position + base_bar_height/2
        
        # Create simple chevron shape - just angled end
        chevron_points = [
            chevron_start_x, y_position,                    # bottom left
            chevron_end_x - 0.3*cm, y_position,            # bottom right (shorter)
            chevron_end_x, chevron_mid_y,                   # middle right (chevron point)
            chevron_end_x - 0.3*cm, y_position + base_bar_height,  # top right (shorter)
            chevron_start_x, y_position + base_bar_height,  # top left
        ]
        
        chevron = Polygon(chevron_points)
        chevron.fillColor = level["color"]
        chevron.strokeColor = Color(0.2, 0.2, 0.2)
        chevron.strokeWidth = 0.5
        drawing.add(chevron)

        # Add grade letter on the left side
        grade_label = String(0.8*cm, y_position + base_bar_height / 2.3, level["grade"])
        grade_label.fontName = get_hebrew_font_name()
        grade_label.fontSize = FONT_SIZES['heading']
        grade_label.textAnchor = 'start'
        grade_label.fillColor = COLORS['white']
        drawing.add(grade_label)

        # Add Hebrew label in the center
        hebrew_label_x = 0.5*cm + bar_width / 2
        hebrew_label = String(hebrew_label_x, y_position + base_bar_height / 2.3, encode_hebrew_text(level["label_he"]))
        hebrew_label.fontName = get_hebrew_font_name()
        hebrew_label.fontSize = FONT_SIZES['body']
        hebrew_label.textAnchor = 'middle'
        hebrew_label.fillColor = COLORS['white']
        drawing.add(hebrew_label)

        # Highlight the current rating with a chevron pointer
        if level["grade"] == letter_grade:
            # Position the pointer chevron to the right of the rating bar
            pointer_start_x = chevron_end_x + 0.3*cm
            pointer_tip_x = pointer_start_x + 0.8*cm
            pointer_mid_y = y_position + base_bar_height / 2
            
            # Create chevron pointer with EXACT same style as rating bars but pointing left
            pointer_end_x = pointer_start_x + chevron_width  # Use same chevron_width
            
            # Mirror the exact chevron structure from rating bars (lines 351-357)
            pointer_points = [
                pointer_end_x, y_position,                               # bottom right
                pointer_start_x + 0.3*cm, y_position,                   # bottom left (shorter)
                pointer_start_x, y_position + base_bar_height/2,        # left tip (chevron point)
                pointer_start_x + 0.3*cm, y_position + base_bar_height, # top left (shorter)
                pointer_end_x, y_position + base_bar_height,             # top right
            ]
            
            pointer_chevron = Polygon(pointer_points)
            pointer_chevron.fillColor = level["color"]
            pointer_chevron.strokeColor = Color(0.2, 0.2, 0.2)
            pointer_chevron.strokeWidth = 0.5
            drawing.add(pointer_chevron)
            
            # Add emphasis text next to the chevron
            emphasis_text = String(pointer_end_x + 0.2*cm, y_position + base_bar_height / 2.3, level["grade"])
            emphasis_text.fontName = get_hebrew_font_name()
            emphasis_text.fontSize = FONT_SIZES['heading']
            emphasis_text.textAnchor = 'start'
            emphasis_text.fillColor = level["color"]
            drawing.add(emphasis_text)

        y_position -= (base_bar_height + bar_spacing)

    elements.append(drawing)
    return elements

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
    right_arrow_width = 3.5 * cm  # Increased from 2.5 to 3.5 cm for even longer arrow
    right_arrow_height = bar_height * 1.3  # Increased height by 30% for bigger arrow

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
        eng_label.fontName = FONTS['table_header']  # Already bold
        eng_label.fontSize = FONT_SIZES['heading']  # Increased from table_body (8) to heading (12)
        eng_label.textAnchor = 'start'
        if level["grade"] in ["+A", "A", "B", "F"]:
            eng_label.fillColor = COLORS['white']
        else:
            eng_label.fillColor = COLORS['dark_gray']
        drawing.add(eng_label)

        # Move descriptive text (Diamond, Platinum, etc.) to center of bar and make it bold
        english_label_x_pos = left_arrow_width + label_offset_x + bar_width / 2
        eng_label_right = String(english_label_x_pos, y_position + bar_height / 2.5, level["label_en"])
        eng_label_right.fontName = FONTS['table_header']  # Changed to bold
        eng_label_right.fontSize = FONT_SIZES['body']  # Increased size
        eng_label_right.textAnchor = 'middle'  # Center the text
        if level["grade"] in ["+A", "A", "B", "F"]:
            eng_label_right.fillColor = COLORS['white']
        else:
            eng_label_right.fillColor = COLORS['dark_gray']
        drawing.add(eng_label_right)

        if level["grade"] == letter_grade:
            arrow_base_x = drawing_width - right_arrow_width - 0.2*cm
            arrow_tip_x = arrow_base_x - 0.5*cm  # Increased tip length from 0.3 to 0.5 cm

            # Adjust arrow positioning to account for increased height
            arrow_y_center = y_position + bar_height / 2
            arrow_half_height = right_arrow_height / 2

            arrow_points = [
                arrow_tip_x, arrow_y_center,  # Arrow tip (pointing left)
                arrow_base_x, arrow_y_center - arrow_half_height * 0.5,  # Upper notch
                arrow_base_x, arrow_y_center - arrow_half_height * 0.8,  # Upper body start
                arrow_base_x + right_arrow_width, arrow_y_center - arrow_half_height * 0.8,  # Upper right
                arrow_base_x + right_arrow_width, arrow_y_center + arrow_half_height * 0.8,  # Lower right
                arrow_base_x, arrow_y_center + arrow_half_height * 0.8,  # Lower body start
                arrow_base_x, arrow_y_center + arrow_half_height * 0.5   # Lower notch
            ]

            arrow = Polygon(arrow_points)
            arrow.fillColor = level["color"]
            arrow.strokeColor = Color(0.2, 0.2, 0.2)
            arrow.strokeWidth = 1.5  # Slightly thicker border
            drawing.add(arrow)

            arrow_label_x = arrow_base_x + right_arrow_width / 2
            arrow_label_y = arrow_y_center - FONT_SIZES['heading'] / 3  # Better vertical centering for larger font
            arrow_label = String(arrow_label_x, arrow_label_y, level["grade"])
            arrow_label.fontName = FONTS['table_header']  # Bold font
            arrow_label.fontSize = FONT_SIZES['heading']  # Increased from table_body (8) to heading (12)
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
        # Primary sort: Floor ID (numeric first, then alphabetic)
        floor_val = item.get('floor_id_report', '')
        try:
            floor_sort_val = int(floor_val)
        except ValueError:
            floor_sort_val = float('inf') if floor_val == '' else str(floor_val)

        # Secondary sort: Area ID (numeric first, then alphabetic)
        area_id_val = item.get('area_id_report', '')
        try:
            area_sort_val = int(area_id_val) if area_id_val else float('inf')
        except ValueError:
            area_sort_val = float('inf') if area_id_val == '' else str(area_id_val)

        # Tertiary sort: Zone ID for consistency
        zone_id_val = str(item.get('zone_id', ''))
        return (floor_sort_val, area_sort_val, zone_id_val)

    raw_table_data.sort(key=sort_key)

    header_row1 = [
        "Building Details", None, None, None, None,
        "Energy Consumption per Meter", None, None, None,
        "Summary and Calculation by 5282", None, None, None
    ]
    header_row2 = [
        "Floor", "Area id", "Zone id", "Zone area", "Zone multiplier",
        "Lighting", "Cooling", "Heating", "Sum",
        "Energy consumption", "Improve by %", "Energy rating", "Area score"    ]
    table_content = [header_row1, header_row2]

    span_commands = []
    pdf_data_start_row = 2

    group_sums_for_display = {}
    group_total_floor_areas = {}
    if raw_table_data:
        def safe_float(value, default=0.0):
            try:
                return float(value)
            except (ValueError, TypeError):
                return default

        for row_dict in raw_table_data:
            item_group_key_for_sum = (str(row_dict.get('floor_id_report','N/A')), str(row_dict.get('area_id_report','N/A')))
            # For 2023, exclude lighting from energy calculations
            if model_year == 2023:
                current_row_energy_sum = safe_float(row_dict.get('cooling', 0.0)) + \
                                         safe_float(row_dict.get('heating', 0.0))
            else:
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
            calculated_improve_by_value = None  # Initialize at the beginning to avoid UnboundLocalError
            display_energy_consump = "N/A"
            display_improve_by = ""
            display_energy_rating = ""
            display_area_rating = ""

            area_location_for_csv_lookup = row_dict.get('model_csv_area_description')

            if area_location_for_csv_lookup and model_year is not None and model_area_definition is not None:
                try:
                    # Handle office model year differently
                    if str(model_year).lower() == 'office' or (isinstance(model_year, str) and 'office' in model_year.lower()):
                        iso_type_for_file_selection = "office"
                    else:
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
                    else:                        logger.warning(f"ReportGen _energy_rating_table: Climate zone '{climate_zone_lookup_key}' (from model_area_definition '{model_area_definition}') not found in ENERGY_RATING_DATA_2017 for year {model_year}. Rating/Score will be N/A.")
                elif model_year == 2023:
                    # 2023 uses universal thresholds, no climate zone mapping needed
                    thresholds = ENERGY_RATING_DATA_2023
                    for min_ip, rating_letter, rating_score_val in thresholds:
                        if calculated_improve_by_value >= min_ip:
                            current_display_energy_rating = rating_letter
                            current_display_area_score = str(rating_score_val)
                            break
                elif str(model_year).lower() == 'office' or (isinstance(model_year, str) and 'office' in model_year.lower()):
                    climate_zone_lookup_key = CLIMATE_ZONE_MAP.get(model_area_definition)

                    if climate_zone_lookup_key and climate_zone_lookup_key in ENERGY_RATING_DATA_OFFICE:
                        thresholds = ENERGY_RATING_DATA_OFFICE[climate_zone_lookup_key]
                        for min_ip, rating_letter, rating_score_val in thresholds:
                            if calculated_improve_by_value >= min_ip:
                                current_display_energy_rating = rating_letter
                                current_display_area_score = str(rating_score_val)
                                break
                    elif not climate_zone_lookup_key:
                        logger.warning(f"ReportGen _energy_rating_table: Could not map model_area_definition '{model_area_definition}' to a known climate zone for office buildings. Rating/Score will be N/A.")
                    else:
                        logger.warning(f"ReportGen _energy_rating_table: Climate zone '{climate_zone_lookup_key}' (from model_area_definition '{model_area_definition}') not found in ENERGY_RATING_DATA_OFFICE for office buildings. Rating/Score will be N/A.")
                else:
                    logger.warning(f"ReportGen _energy_rating_table: Energy rating logic currently implemented for model_year 2017, 2023, and office buildings. Found {model_year}. Rating/Score will be N/A.")

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
            "-" if model_year == 2023 else _format_number(row_dict.get('lighting', 0)),
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

            # Add standardized header
            report_title = "Energy Rating"
            header_elements = create_standardized_header(
                doc=doc,
                project_name=self.project_name,
                run_id=self.run_id,
                city_name=self.selected_city_name or 'N/A',
                area_name=self.area_name,
                report_title=report_title
            )
            story.extend(header_elements)

            title_style = create_title_style(self.styles)
            story.append(Paragraph(f"{report_title} Report", title_style))
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

    def generate_total_energy_rating_report(self, output_filename="total-energy-rating.pdf", settings_extractor=None):
        """
        Generate Hebrew RTL total energy rating report with three sections:
        1. Header with project info
        2. Energy rating visual table
        3. Consultant information
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
            hebrew_font = get_hebrew_font_name()

            # Add standardized header with metadata
            report_title = "Total Energy Rating Report"
            header_elements = create_standardized_header(
                doc=doc,
                project_name=self.project_name,
                run_id=self.run_id,
                city_name=self.selected_city_name or 'N/A',
                area_name=self.area_name,
                report_title=report_title
            )
            story.extend(header_elements)

            # SECTION 1: Hebrew Header Information (simplified since standardized header is above)
            story.extend(self._create_hebrew_header_section(settings_extractor, hebrew_font, total_score, letter_grade))
            story.append(Spacer(1, LAYOUT['spacing']['small']))

            # SECTION 2: Energy Rating Visual Table
            story.extend(self._create_energy_rating_section(total_score, letter_grade, hebrew_font))
            story.append(Spacer(1, LAYOUT['spacing']['small']))

            # SECTION 3: Consultant Information
            story.extend(self._create_consultant_info_section(hebrew_font))

            doc.build(story)
            logger.info(f"Generated Hebrew total energy rating report: {output_path}")
            return output_path

        except Exception as e:
            error_message = f"Error generating total energy rating report: {e}"
            logger.error(error_message, exc_info=True)
            raise RuntimeError(error_message)

    def _get_raw_average_for_display(self, raw_table_data):
        """Calculate and return the raw average for display purposes"""
        try:
            if not raw_table_data:
                return None
            
            # Group the data (simplified version of the main calculation)
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

                # For 2023, exclude lighting from energy calculations
                if self.model_year == 2023:
                    grouped_data[group_key]['sum_energy_components'] += safe_float(row.get('cooling', 0.0)) + \
                                                                          safe_float(row.get('heating', 0.0))
                else:
                    grouped_data[group_key]['sum_energy_components'] += safe_float(row.get('lighting', 0.0)) + \
                                                                          safe_float(row.get('cooling', 0.0)) + \
                                                                          safe_float(row.get('heating', 0.0))
                grouped_data[group_key]['sum_total_area'] += zone_area
                grouped_data[group_key]['area_effective_for_numerator'] += zone_area * zone_multiplier
                grouped_data[group_key]['raw_zone_area_sum_for_denominator'] += zone_area * zone_multiplier

            # Calculate scores for each group
            for group_key, data_item in grouped_data.items():
                score = _get_numeric_area_score_for_group(
                    group_sum_energy_components=data_item['sum_energy_components'],
                    group_sum_total_area=data_item['sum_total_area'],
                    group_model_csv_area_desc=data_item['model_csv_area_description'],
                    model_year=self.model_year,
                    model_area_definition=self.model_area_definition
                )
                data_item['calculated_score'] = score

            # Calculate the raw average
            weighted_score_sum_numerator = 0.0
            total_raw_area_sum_denominator = 0.0

            for group_key, data_item in grouped_data.items():
                if data_item['calculated_score'] is not None:
                    group_score = safe_float(data_item['calculated_score'])
                    group_effective_area = data_item['area_effective_for_numerator']
                    group_raw_area_for_denom = data_item['raw_zone_area_sum_for_denominator']

                    # Validate that group_score is within valid range (-1 to 5)
                    if group_score < -1 or group_score > 5:
                        group_score = 0

                    term_numerator = group_effective_area * group_score
                    weighted_score_sum_numerator += term_numerator
                    total_raw_area_sum_denominator += group_raw_area_for_denom

            if total_raw_area_sum_denominator > 0:
                return weighted_score_sum_numerator / total_raw_area_sum_denominator
            return None
        except Exception as e:
            logger.error(f"Error calculating raw average for display: {e}")
            return None

    def _create_hebrew_header_section(self, settings_extractor, hebrew_font, total_score=None, letter_grade=None):
        """Create Section 1: Professional Hebrew header with project information"""
        elements = []
        
        # Add title (centered) - logo is already in standardized header above
        title_style = ParagraphStyle(
            'HebrewTitle',
            parent=self.styles['h1'],
            fontSize=20,
            fontName=hebrew_font,
            textColor=COLORS['primary_blue'],
            alignment=TA_CENTER,
            spaceAfter=0.3*cm
        )
        elements.append(Paragraph(encode_hebrew_text("דוח דירוג אנרגטי"), title_style))
        
        # Professional subtitle
        subtitle_style = ParagraphStyle(
            'HebrewSubtitle',
            parent=self.styles['Normal'],
            fontSize=14,
            fontName=hebrew_font,
            textColor=COLORS['dark_gray'],
            alignment=TA_CENTER,
            spaceAfter=0.3*cm
        )
        
        # Get area information - handle 2023 model area definitions
        area_value = self.area_name or "לא זמין"
        if settings_extractor:
            try:
                location_settings = settings_extractor.get_location_settings()
                if 'name' in location_settings and location_settings['name']:
                    area_value = str(location_settings['name'])
            except:
                pass
        
        # For 2023 models, use the model_area_definition directly (should be 1-8)
        # For other models, keep the existing logic
        if self.model_year == 2023 and self.model_area_definition:
            area_value = str(self.model_area_definition)
        elif self.model_area_definition and area_value == "לא זמין":
            area_value = str(self.model_area_definition)
        
        # Professional project information with RTL field:value order (value:field for Hebrew)
        iso_value = f"{self.model_year}" if self.model_year else "לא זמין"
        
        # Format calculation result - need to get the raw_average from the calculation
        if total_score is not None and letter_grade and letter_grade != "N/A":
            # Get the raw_average by recalculating just for display purposes
            raw_table_data = self.energy_rating_parser.get_energy_rating_table_data()
            raw_average = self._get_raw_average_for_display(raw_table_data)
            if raw_average is not None:
                calc_result = f"{raw_average:.3f}"
            else:
                calc_result = f"{total_score:.2f} ({letter_grade})"
        else:
            calc_result = "לא זמין"
            
        project_info = [
            # Header row
            [encode_hebrew_text("פרטי הפרויקט"), "", "", ""],
            # Data rows - switched order for Hebrew RTL (value:field)
            [encode_hebrew_text(self.project_name or "לא זמין"), encode_hebrew_text("שם הפרויקט:"),
             datetime.datetime.now().strftime('%d/%m/%Y'), encode_hebrew_text("תאריך הדוח:")],
            [encode_hebrew_text(self.selected_city_name or "לא זמין"), encode_hebrew_text("עיר:"),
             iso_value, encode_hebrew_text("תקן להסמכה:")],  # Moved ISO to right section
            [encode_hebrew_text(area_value), encode_hebrew_text("אזור אקלים:"),
             encode_hebrew_text(""), encode_hebrew_text("גוש:")],  # Area info and גוש
            [encode_hebrew_text(calc_result), encode_hebrew_text("תוצאת חישוב:"),
             encode_hebrew_text(""), encode_hebrew_text("חלקה:")]  # Calculation result and חלקה
        ]
        
        info_table = Table(project_info, colWidths=[4.5*cm, 3*cm, 4.5*cm, 3*cm])
        info_table.setStyle(TableStyle([
            # Header row styling
            ('FONTNAME', (0,0), (-1,0), hebrew_font),
            ('FONTSIZE', (0,0), (-1,0), 14),
            ('BACKGROUND', (0,0), (-1,0), COLORS['primary_blue']),
            ('TEXTCOLOR', (0,0), (-1,0), COLORS['white']),
            ('ALIGN', (0,0), (-1,0), 'CENTER'),
            ('SPAN', (0,0), (-1,0)),  # Merge header row
            
            # Data rows styling - all text aligned right for Hebrew RTL
            ('FONTNAME', (0,1), (-1,-1), hebrew_font),
            ('FONTSIZE', (0,1), (-1,-1), 11),
            ('ALIGN', (0,1), (-1,-1), 'RIGHT'),  # All cells aligned right
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TEXTCOLOR', (0,1), (-1,-1), COLORS['dark_gray']),
            ('BACKGROUND', (0,1), (-1,-1), Color(0.98, 0.98, 1.0)),  # Very light blue
            
            # Borders and styling
            ('BOX', (0,0), (-1,-1), 1, COLORS['primary_blue']),
            ('LINEBELOW', (0,0), (-1,0), 2, COLORS['primary_blue']),
            ('GRID', (0,1), (-1,-1), 0.5, COLORS['border_gray']),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('RIGHTPADDING', (0,0), (-1,-1), 10),
            ('LEFTPADDING', (0,0), (-1,-1), 10),
        ]))
        elements.append(info_table)
        
        return elements

    def _create_energy_rating_section(self, total_score, letter_grade, hebrew_font):
        """Create Section 2: Compact energy rating visual table"""
        elements = []
        
        # Section title - centered
        section_title_style = ParagraphStyle(
            'HebrewSectionTitle',
            parent=self.styles['h2'],
            fontSize=14,
            fontName=hebrew_font,
            textColor=COLORS['primary_blue'],
            alignment=TA_CENTER,
            spaceAfter=0.3*cm
        )
        elements.append(Paragraph(encode_hebrew_text("טבלת דירוג אנרגטי"), section_title_style))
        
        # Add the visual rating table (centered)
        from reportlab.platypus import KeepTogether
        rating_visual = _create_energy_rating_table_visual(total_score, letter_grade)
        
        # Center the rating table
        centered_table_style = ParagraphStyle(
            'CenteredTable',
            parent=self.styles['Normal'],
            alignment=TA_CENTER
        )
        
        # Wrap the drawing in a centered container
        if rating_visual:
            # Create a spacer to center the drawing
            elements.append(Spacer(1, 0.2*cm))
            for item in rating_visual:
                # Create a table with the drawing to center it
                centered_table = Table([[item]], colWidths=[16*cm])
                centered_table.setStyle(TableStyle([
                    ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ]))
                elements.append(centered_table)
        
        return elements

    def _create_consultant_info_section(self, hebrew_font):
        """Create Section 3: Two separate professional consultant tables"""
        elements = []
        
        # Professional section title with enhanced styling
        section_title_style = ParagraphStyle(
            'HebrewSectionTitle',
            parent=self.styles['h2'],
            fontSize=16,
            fontName=hebrew_font,
            textColor=COLORS['primary_blue'],
            alignment=TA_CENTER,
            spaceAfter=0.3*cm
        )
        elements.append(Paragraph(encode_hebrew_text("פרטי הצוות המקצועי"), section_title_style))
        
        # TABLE 1: Thermal Consultant
        consultant_data = [
            # Header
            [encode_hebrew_text("יועץ תרמי מוסמך"), ""],
            # Data rows - switched order for Hebrew RTL (value:field)
            [encode_hebrew_text("חברת ייעוץ תרמי בע\"מ"), encode_hebrew_text("חברה:")],
            [encode_hebrew_text("אבי כהן, מהנדס מכונות"), encode_hebrew_text("מהנדס אחראי:")],
            ["03-1234567", encode_hebrew_text("טלפון:")],
            ["avi.cohen@thermal.co.il", encode_hebrew_text("דוא\"ל:")]
        ]
        
        consultant_table = Table(consultant_data, colWidths=[8*cm, 4*cm])
        consultant_table.setStyle(TableStyle([
            # Header styling
            ('FONTNAME', (0,0), (-1,0), hebrew_font),
            ('FONTSIZE', (0,0), (-1,0), 12),
            ('BACKGROUND', (0,0), (-1,0), COLORS['primary_blue']),
            ('TEXTCOLOR', (0,0), (-1,0), COLORS['white']),
            ('ALIGN', (0,0), (-1,0), 'CENTER'),
            ('SPAN', (0,0), (-1,0)),  # Merge header
            
            # Body styling
            ('FONTNAME', (0,1), (-1,-1), hebrew_font),
            ('FONTSIZE', (0,1), (-1,-1), 10),
            ('ALIGN', (0,1), (-1,-1), 'RIGHT'),  # All cells aligned right
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TEXTCOLOR', (0,1), (-1,-1), COLORS['dark_gray']),
            ('BACKGROUND', (0,1), (-1,-1), Color(0.98, 0.98, 1.0)),
            
            # Borders and styling
            ('BOX', (0,0), (-1,-1), 1, COLORS['primary_blue']),
            ('LINEBELOW', (0,0), (-1,0), 2, COLORS['primary_blue']),
            ('GRID', (0,1), (-1,-1), 0.5, COLORS['border_gray']),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('RIGHTPADDING', (0,0), (-1,-1), 10),
            ('LEFTPADDING', (0,0), (-1,-1), 10),
        ]))
        elements.append(consultant_table)
        
        # Add spacing between tables
        elements.append(Spacer(1, 0.3*cm))
        
        # TABLE 2: Thermal Tester
        tester_data = [
            # Header
            [encode_hebrew_text("בודק תרמי מוסמך"), ""],
            # Data rows - switched order for Hebrew RTL (value:field)
            [encode_hebrew_text("מעבדת בדיקות תרמיות בע\"מ"), encode_hebrew_text("חברה:")],
            [encode_hebrew_text("שרה לוי, מהנדסת אזרחית"), encode_hebrew_text("בודק מוסמך:")],
            ["02-9876543", encode_hebrew_text("טלפון:")],
            ["sara.levy@thermal-lab.co.il", encode_hebrew_text("דוא\"ל:")]
        ]
        
        tester_table = Table(tester_data, colWidths=[8*cm, 4*cm])
        tester_table.setStyle(TableStyle([
            # Header styling
            ('FONTNAME', (0,0), (-1,0), hebrew_font),
            ('FONTSIZE', (0,0), (-1,0), 12),
            ('BACKGROUND', (0,0), (-1,0), COLORS['secondary_blue']),
            ('TEXTCOLOR', (0,0), (-1,0), COLORS['white']),
            ('ALIGN', (0,0), (-1,0), 'CENTER'),
            ('SPAN', (0,0), (-1,0)),  # Merge header
            
            # Body styling
            ('FONTNAME', (0,1), (-1,-1), hebrew_font),
            ('FONTSIZE', (0,1), (-1,-1), 10),
            ('ALIGN', (0,1), (-1,-1), 'RIGHT'),  # All cells aligned right
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TEXTCOLOR', (0,1), (-1,-1), COLORS['dark_gray']),
            ('BACKGROUND', (0,1), (-1,-1), Color(0.98, 0.98, 1.0)),
            
            # Borders and styling
            ('BOX', (0,0), (-1,-1), 1, COLORS['secondary_blue']),
            ('LINEBELOW', (0,0), (-1,0), 2, COLORS['secondary_blue']),
            ('GRID', (0,1), (-1,-1), 0.5, COLORS['border_gray']),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('RIGHTPADDING', (0,0), (-1,-1), 10),
            ('LEFTPADDING', (0,0), (-1,-1), 10),
        ]))
        elements.append(tester_table)
        
        return elements
