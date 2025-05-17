"""
Generates energy rating reports from processed energy consumption data.
"""
import logging
import os

from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from utils.data_loader import get_energy_consumption
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.colors import navy, black, grey, lightgrey
from reportlab.lib.enums import TA_CENTER

logger = logging.getLogger(__name__)

ENERGY_RATING_DATA_2017 = {
    "אזור א": [
        (35, "+A", 5), (30, "A", 4), (25, "B", 3), (20, "C", 2), (10, "D", 1),
        (0, "E", 0), (-float('inf'), "F", -1)
    ],
    "אזור ב": [
        (35, "+A", 5), (30, "A", 4), (25, "B", 3), (20, "C", 2), (10, "D", 1),
        (0, "E", 0), (-float('inf'), "F", -1)
    ],
    "אזור ג": [
        (40, "+A", 5), (34, "A", 4), (27, "B", 3), (20, "C", 2), (10, "D", 1),
        (0, "E", 0), (-float('inf'), "F", -1)
    ],
    "אזור ד": [
        (29, "+A", 5), (26, "A", 4), (23, "B", 3), (20, "C", 2), (10, "D", 1),
        (0, "E", 0), (-float('inf'), "F", -1)
    ]
}

CLIMATE_ZONE_MAP = {
    "a": "אזור א", "A": "אזור א", "אזור א": "אזור א",
    "b": "אזור ב", "B": "אזור ב", "אזור ב": "אזור ב",
    "c": "אזור ג", "C": "אזור ג", "אזור ג": "אזור ג",
    "d": "אזור ד", "D": "אזור ד", "אזור ד": "אזור ד",
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

def _energy_rating_table(energy_rating_parser, model_year: int, model_area_definition: str, selected_city_name: str):
    """
    Creates the energy rating table as a ReportLab Table object.
    Returns Table object or None if no data.
    """
    raw_table_data = energy_rating_parser.get_energy_rating_table_data()

    if not raw_table_data:
        return None

    def sort_key(item):
        floor_val = item.get('floor', '')
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
