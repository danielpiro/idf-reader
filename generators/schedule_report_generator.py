from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.colors import grey, Color
import datetime
import logging
from pathlib import Path
from utils.hebrew_text_utils import safe_format_header_text, get_hebrew_font_name

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

logger = logging.getLogger(__name__)

def parse_date_string(date_str: str) -> datetime.date:
    """
    Parses a 'DD/MM' date string into a datetime.date object (year 2000).
    Returns a default date (end of year) if parsing fails.
    """
    try:
        if not isinstance(date_str, str) or '/' not in date_str:
            raise ValueError("Date string must be in 'DD/MM' format.")
        day, month = map(int, date_str.split('/'))
        return datetime.date(2000, month, day)
    except (ValueError, AttributeError, TypeError) as e:
        logger.warning(f"Could not parse date string '{date_str}': {e}. Using default date.", exc_info=True)
        return datetime.date(2000, 12, 31)

def create_date_ranges(rule_blocks: list) -> list:
    """Creates date ranges for rule blocks. Returns empty list on error or no input."""
    if not rule_blocks:
        return []
    try:
        for block in rule_blocks:
            if not isinstance(block, dict) or 'through' not in block:
                logger.warning(f"Invalid rule block encountered (missing 'through' or not a dict): {block}")
                block.setdefault('through', '31/12')
            elif not isinstance(block.get('through'), str) or '/' not in block.get('through'):
                 logger.warning(f"Invalid 'through' date format in block: {block.get('through')}. Using default.")
                 block['through'] = '31/12'

        sorted_blocks = sorted(rule_blocks, key=lambda block: parse_date_string(block.get('through', '31/12')))

        first_date_str_in_sorted = sorted_blocks[0].get('through') if sorted_blocks else '31/12'
        first_range_start_date = '01/01' if parse_date_string(first_date_str_in_sorted) != parse_date_string('01/01') else None

        result_blocks = []

        for i, block in enumerate(sorted_blocks):
            current_date_str = block.get('through', '31/12')

            if i == 0:
                if first_range_start_date:
                    date_range = f"{first_range_start_date} -> {current_date_str}"
                else:
                    date_range = f"01/01 -> {current_date_str}"
            else:
                prev_block_date_str = sorted_blocks[i-1].get('through', '31/12')
                date_range = f"{prev_block_date_str} -> {current_date_str}"

            new_block = block.copy()
            new_block['date_range'] = date_range
            result_blocks.append(new_block)
        return result_blocks
    except Exception as e:
        logger.error(f"Error creating date ranges: {type(e).__name__} - {str(e)}", exc_info=True)
        return []

def create_hourly_schedule_table(rule_blocks: list, available_width: float) -> Table | None:
    """Creates a ReportLab Table for hourly schedules. Returns None on error or no input."""
    if not rule_blocks:
        return None
    try:
        rule_blocks_with_ranges = create_date_ranges(rule_blocks)
        if not rule_blocks_with_ranges:
            logger.warning("No valid date ranges could be created for schedule table.")
            return None

        period_col_width = 3.5 * cm
        num_hour_cols = 24
        if available_width <= period_col_width:
            logger.error(f"Available width ({available_width}) is too small for period column ({period_col_width}). Cannot create table.")
            return None
        hour_col_width = (available_width - period_col_width) / num_hour_cols
        col_widths = [period_col_width] + [hour_col_width] * num_hour_cols

        header = ["Date Ranges/Hours"] + [str(h + 1) for h in range(num_hour_cols)]
        table_data = [header]

        cell_style = getSampleStyleSheet()['Normal']
        cell_style.fontSize = 7
        cell_style.alignment = 1

        for block in rule_blocks_with_ranges:
            period_text = block.get('date_range', 'N/A')
            hourly_values = block.get('hourly_values', [''] * num_hour_cols)
            if len(hourly_values) < num_hour_cols:
                hourly_values.extend([''] * (num_hour_cols - len(hourly_values)))
            elif len(hourly_values) > num_hour_cols:
                hourly_values = hourly_values[:num_hour_cols]

            row_data = [period_text] + [str(val) if val is not None else '' for val in hourly_values]
            table_data.append(row_data)

        style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), COLORS['primary_blue']),
            ('TEXTCOLOR', (0, 0), (-1, 0), COLORS['dark_gray']),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), FONTS['table_header']),
            ('FONTSIZE', (0, 0), (-1, -1), FONT_SIZES['small']),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('TOPPADDING', (0, 0), (-1, 0), 6),

            ('FONTNAME', (0, 1), (-1, -1), FONTS['table_body']),
            ('TEXTCOLOR', (0, 1), (-1, -1), COLORS['dark_gray']),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [COLORS['white'], COLORS['light_blue']]),

            ('GRID', (0, 0), (-1, -1), 0.5, COLORS['border_gray']),
            ('BOX', (0, 0), (-1, -1), 1, COLORS['medium_gray']),

            ('ALIGN', (0, 1), (0, -1), 'LEFT'),
            ('LEFTPADDING', (0, 1), (0, -1), 6),

            ('TOPPADDING', (1, 1), (-1, -1), 4),
            ('BOTTOMPADDING', (1, 1), (-1, -1), 4),
            ('LEFTPADDING', (1, 1), (-1, -1), 3),
            ('RIGHTPADDING', (1, 1), (-1, -1), 3),
        ])
        schedule_table = Table(table_data, colWidths=col_widths)
        schedule_table.setStyle(style)
        return schedule_table
    except Exception as e:
        logger.error(f"Error creating hourly schedule table: {type(e).__name__} - {str(e)}", exc_info=True)
        return None

def generate_schedules_report_pdf(schedule_data: list, output_filename: str = "output/schedules.pdf",
                                  project_name: str = "N/A", run_id: str = "N/A", 
                                  city_name: str = "N/A", area_name: str = "N/A") -> bool:
    """
    Generates a PDF report containing schedule definitions, including a header.
    Returns:
        bool: True if report generation was successful, False otherwise.
    """

    try:
        output_file_path = Path(output_filename)
        output_dir = output_file_path.parent
        if not output_dir.exists():
            try:
                output_dir.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                error_message = f"Error creating output directory '{output_dir}' for schedules report: {e.strerror}"
                logger.error(error_message, exc_info=True)
                return False
        elif not output_dir.is_dir():
            error_message = f"Error: Output path '{output_dir}' for schedules report exists but is not a directory."
            logger.error(error_message)
            return False

        c = canvas.Canvas(str(output_file_path), pagesize=A4)
    except (IOError, OSError) as e:
        logger.error(f"Failed to create canvas for PDF '{output_filename}': {e.strerror}", exc_info=True)
        return False

    try:
        width, height = A4
        margin_x = 2 * cm
        margin_y = 2 * cm
        content_width = width - 2 * margin_x
        current_y = height - margin_y
        styles = getSampleStyleSheet()
        title_style = styles['h1']
        title_style.textColor = COLORS['primary_blue']
        title_style.fontName = FONTS['title']
        title_style.fontSize = FONT_SIZES['title']
        schedule_name_style = ParagraphStyle(
            name='ScheduleName', parent=styles['Normal'], fontName='Helvetica-Bold',
            spaceBefore=0.4*cm, spaceAfter=0.1*cm
        )
        not_found_style = ParagraphStyle(
            name='NotFound', parent=styles['Normal'], fontName='Helvetica-Oblique',
            textColor=grey, leftIndent=0.5*cm, spaceAfter=0.4*cm
        )
        hebrew_font = get_hebrew_font_name()
        header_info_style = ParagraphStyle(
            'HeaderInfo', parent=styles['Normal'], fontSize=9, fontName=hebrew_font, textColor=COLORS['dark_gray'], alignment=2        )
        now = datetime.datetime.now()
        header_text = safe_format_header_text(
            project_name=project_name,
            run_id=run_id,
            timestamp=now.strftime('%Y-%m-%d %H:%M:%S'),
            city_name=city_name,
            area_name=area_name,
            report_title="Unique Schedule Definitions"
        )
        p_header = Paragraph(header_text, header_info_style)
        header_width_actual, header_height = p_header.wrapOn(c, content_width, margin_y)
        p_header.drawOn(c, width - margin_x - header_width_actual, height - margin_y - header_height)
        current_y -= (header_height + 0.2*cm)

        title_text = "IDF Unique Schedule Definitions"
        p_title = Paragraph(title_text, title_style)
        p_title.wrapOn(c, content_width, margin_y)
        title_height = p_title.height
        p_title.drawOn(c, margin_x, current_y - title_height)
        current_y -= (title_height + 1 * cm)

        if not schedule_data:
            p_empty = Paragraph("No relevant schedules found or extracted.", styles['Normal'])
            p_empty.wrapOn(c, content_width, margin_y)
            p_empty.drawOn(c, margin_x, current_y - p_empty.height)
            c.save()
            return True

        space_after_table = 0.8 * cm
        for schedule_item in schedule_data:
            if not isinstance(schedule_item, dict):
                logger.warning(f"Skipping invalid schedule item (not a dict): {schedule_item}")
                continue

            raw_schedule_type = schedule_item.get('type', 'Unknown Type')
            schedule_type_lower = raw_schedule_type.lower()
            if "activity" in schedule_type_lower or "clothing" in schedule_type_lower:
                parts = raw_schedule_type.split(" ")
                schedule_type = f"{parts[0]} Schedule" if len(parts) > 1 else f"{raw_schedule_type} Schedule"
            elif "heating" in schedule_type_lower or "cooling" in schedule_type_lower:
                parts = raw_schedule_type.split(" ")
                if len(parts) > 2: schedule_type = f"{parts[1]} {parts[2]} Schedule"
                elif len(parts) > 1: schedule_type = f"{parts[0]} Schedule"
                else: schedule_type = f"{raw_schedule_type} Schedule"
            else:
                schedule_type = raw_schedule_type

            rule_blocks = schedule_item.get('rule_blocks', [])

            generic_name_map = {
                "activity": "People", "clothing": "People", "occupancy": "People",
                "heating": "Temperature", "cooling": "Temperature",
                "ventilation": "Ventilation", "lighting": "Lighting",
                "shading": "Shading", "equipment": "Equipment"
            }
            determined_schedule_name = None
            for key, val_name in generic_name_map.items():
                if key in schedule_type.lower():
                    determined_schedule_name = val_name
                    break

            name_text = f"{schedule_type} [{determined_schedule_name}]" if determined_schedule_name else f"{schedule_type}"
            p_sched_name = Paragraph(name_text, schedule_name_style)
            p_sched_name.wrapOn(c, content_width, margin_y)
            name_height = p_sched_name.height

            schedule_table_obj = create_hourly_schedule_table(rule_blocks, content_width)

            if schedule_table_obj:
                table_width_actual_content, table_height = schedule_table_obj.wrapOn(c, content_width, margin_y)
                total_element_height = name_height + schedule_name_style.spaceAfter + table_height + space_after_table

                if current_y - total_element_height < margin_y:
                    c.showPage()
                    current_y = height - margin_y
                    p_header.drawOn(c, width - margin_x - header_width_actual, height - margin_y - header_height)

                p_sched_name.drawOn(c, margin_x, current_y - name_height)
                current_y -= (name_height + schedule_name_style.spaceAfter)
                schedule_table_obj.drawOn(c, margin_x, current_y - table_height)
                current_y -= (table_height + space_after_table)
            else:
                logger.warning(f"No table generated for schedule: {name_text}")
                no_data_message_height_approx = styles['Normal'].leading * 2

                if current_y - (name_height + schedule_name_style.spaceAfter + no_data_message_height_approx + space_after_table) < margin_y:
                    c.showPage()
                    current_y = height - margin_y
                    p_header.drawOn(c, width - margin_x - header_width_actual, height - margin_y - header_height)

                p_sched_name.drawOn(c, margin_x, current_y - name_height)
                current_y -= (name_height + schedule_name_style.spaceAfter)
                p_no_data = Paragraph("No rule data available or error in generating hourly table.", not_found_style)
                p_no_data.wrapOn(c, content_width, margin_y)
                no_data_actual_height = p_no_data.height
                p_no_data.drawOn(c, margin_x, current_y - no_data_actual_height)
                current_y -= (no_data_actual_height + space_after_table)

        c.save()
        return True
    except (IOError, OSError) as e:
        logger.error(f"File operation error during schedules report generation for '{output_filename}': {e.strerror}", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred while generating Schedules report '{output_filename}': {type(e).__name__} - {str(e)}", exc_info=True)
        if 'c' in locals() and hasattr(c, '_filename') and c._filename:
            try:
                if not c._saved: c.save()
            except Exception as save_err:
                logger.error(f"Could not save PDF {output_filename} even after an error during generation: {save_err}", exc_info=True)
        return False
