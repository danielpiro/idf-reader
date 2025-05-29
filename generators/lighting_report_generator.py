"""
PDF Report generator for Daylighting data.
"""
from reportlab.lib.pagesizes import A3, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.colors import Color
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import datetime
import logging
from typing import Dict, List, Any
from pathlib import Path

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

def wrap_text(text, style):
    """Helper function to create wrapped text in a cell."""
    return Paragraph(str(text), style)

def create_cell_style(styles, is_header=False, font_size=6, leading=7):
    """Create a cell style for wrapped text."""
    style = ParagraphStyle(
        'Cell',
        parent=styles['Normal'],
        fontSize=font_size,
        leading=leading,
        spaceBefore=1,
        spaceAfter=1,
        fontName='Helvetica-Bold' if is_header else 'Helvetica',
        wordWrap='CJK',
        alignment=TA_LEFT
    )
    return style

def create_lighting_table_style(header_rows=1):
    """Create table style with modern blue/gray palette."""
    style = [
        ('BACKGROUND', (0, 0), (-1, header_rows - 1), COLORS['primary_blue']),
        ('TEXTCOLOR', (0, 0), (-1, header_rows - 1), COLORS['white']),
        ('ALIGN', (0, 0), (-1, header_rows - 1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, header_rows - 1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, header_rows - 1), FONTS['table_header']),
        ('FONTSIZE', (0, 0), (-1, header_rows - 1), FONT_SIZES['table_body']),
        ('BOTTOMPADDING', (0, 0), (-1, header_rows - 1), 4),
        ('TOPPADDING', (0, 0), (-1, header_rows - 1), 4),

        ('TEXTCOLOR', (0, header_rows), (-1, -1), COLORS['dark_gray']),
        ('ALIGN', (0, header_rows), (-1, -1), 'LEFT'),
        ('VALIGN', (0, header_rows), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, header_rows), (-1, -1), FONTS['table_body']),
        ('FONTSIZE', (0, header_rows), (-1, -1), FONT_SIZES['small']),
        ('TOPPADDING', (0, header_rows), (-1, -1), 2),
        ('BOTTOMPADDING', (0, header_rows), (-1, -1), 2),

        ('ROWBACKGROUNDS', (0, header_rows), (-1, -1), [COLORS['white'], COLORS['light_blue']]),

        ('GRID', (0, 0), (-1, -1), 0.5, COLORS['border_gray']),
        ('BOX', (0, 0), (-1, -1), 1, COLORS['medium_gray']),

        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4)
    ]
    return TableStyle(style)

def _format_lighting_row(entry, headers, precisions):
    row = []
    for i, header in enumerate(headers):
        val = entry.get(header.replace('\n', ' ').replace(' (lux)', '').replace(' %', '').replace('Fraction Controlled', 'Fraction of Zone Controlled').replace('Illuminance Setpoint', 'Illuminance Setpoint').replace('Min Input Power Fraction', 'Minimum Input Power Fraction').replace('Min Light Output Fraction', 'Minimum Light Output Fraction'), '-')
        precision = precisions[i]
        if header == "Lighting\nArea %":
            try:
                row.append(f"{float(val) * 100:.0f}%")
            except (ValueError, TypeError):
                row.append(str(val))
        elif precision is not None:
            try:
                row.append(f"{float(val):.{precision}f}")
            except (ValueError, TypeError):
                row.append(str(val))
        else:
            row.append(str(val))
    return row

def _span_table(table_data, col_idx):
    from reportlab.lib import colors
    span_cmds = []
    start_row = 1
    while start_row < len(table_data):
        current_val_obj = table_data[start_row][col_idx]
        current_val = getattr(current_val_obj, 'text', str(current_val_obj))
        count = 1
        for i in range(start_row + 1, len(table_data)):
            next_val_obj = table_data[i][col_idx]
            next_val = getattr(next_val_obj, 'text', str(next_val_obj))
            if next_val == current_val:
                count += 1
                if getattr(table_data[i][col_idx], 'text', '') != "":
                    table_data[i][col_idx] = wrap_text("", table_data[i][col_idx].style)
            else:
                break
        if count > 1:
            span_cmds.append(('SPAN', (col_idx, start_row), (col_idx, start_row + count - 1)))
            for r in range(start_row, start_row + count - 1):
                span_cmds.append(('LINEBELOW', (col_idx, r), (col_idx, r), 0.5, colors.white))
                span_cmds.append(('LINEABOVE', (col_idx, r + 1), (col_idx, r + 1), 0.5, colors.white))
        start_row += count
    return span_cmds

class LightingReportGenerator:
    """Generates a PDF report for parsed Daylighting data."""

    def __init__(self, data: Dict[str, List[Dict[str, Any]]], output_path: str,
                 project_name: str = "N/A", run_id: str = "N/A",
                 city_name: str = "N/A", area_name: str = "N/A"):
        """
        Initializes the LightingReportGenerator.

        Args:
            data: The parsed daylighting data from LightingParser.
            output_path: The path to save the generated PDF report.
            project_name: Name of the project for the header.
            run_id: Identifier for the current run for the header.        """
        self._data = data
        self._output_path = output_path
        self._project_name = project_name
        self._run_id = run_id
        self._city_name = city_name
        self._area_name = area_name
        self._styles = getSampleStyleSheet()
        self._story = []

    def _add_header_footer(self, canvas, doc):
        """Adds header and footer to each page."""
        canvas.saveState()
        now = datetime.datetime.now()
        header_text = f"Project: {self._project_name} | Run ID: {self._run_id} | Date: {now.strftime('%Y-%m-%d %H:%M:%S')} | City: {self._city_name} | Area: {self._area_name} | Report: Daylighting Summary"
        header_style = ParagraphStyle('HeaderStyle', parent=self._styles['Normal'], fontSize=8, alignment=TA_LEFT)
        p = Paragraph(header_text, header_style)
        w, h = p.wrap(doc.width, doc.topMargin)
        p.drawOn(canvas, doc.leftMargin, doc.height + doc.topMargin - h - 0.1*cm)

        footer_text = f"Page {doc.page}"
        footer_style = ParagraphStyle('FooterStyle', parent=self._styles['Normal'], fontSize=8, alignment=TA_CENTER)
        p = Paragraph(footer_text, footer_style)
        w, h = p.wrap(doc.width, doc.bottomMargin)
        p.drawOn(canvas, doc.leftMargin, h)

        canvas.restoreState()

    def generate_report(self) -> bool:
        """
        Generates the PDF report.

        Returns:
            bool: True if report generation was successful, False otherwise.
        """
        doc = None
        self._story = []
        try:
            output_file_path = Path(self._output_path)
            output_dir = output_file_path.parent
            if not output_dir.exists():
                try:
                    output_dir.mkdir(parents=True, exist_ok=True)
                except OSError as e:
                    error_message = f"Error creating output directory '{output_dir}' for lighting report: {e.strerror}"
                    logger.error(error_message, exc_info=True)
                    return False
            elif not output_dir.is_dir():
                error_message = f"Error: Output path '{output_dir}' for lighting report exists but is not a directory."
                logger.error(error_message)
                return False

            left_margin = 0.5*cm
            right_margin = 0.5*cm
            top_margin = 1.5*cm
            bottom_margin = 1.5*cm
            page_size = landscape(A3)

            doc = SimpleDocTemplate(str(self._output_path), pagesize=page_size,
                                    leftMargin=left_margin, rightMargin=right_margin,
                                    topMargin=top_margin, bottomMargin=bottom_margin)

            title_style = self._styles['h1']
            title_style.textColor = COLORS['primary_blue']
            title_style.fontName = FONTS['title']
            title_style.fontSize = FONT_SIZES['title']
            title_style.alignment = TA_CENTER
            self._story.append(Paragraph("Daylighting Report", title_style))
            self._story.append(Spacer(1, 0.5*cm))

            table_style = create_lighting_table_style()
            cell_style = create_cell_style(self._styles, font_size=5, leading=6)
            header_cell_style = create_cell_style(self._styles, is_header=True, font_size=6, leading=7)

            controls_data = self._data.get("controls", [])
            controls_data.sort(key=lambda x: x.get("Zone", ""))

            if controls_data:
                headers_controls = [
                    "Zone", "Availability\nSchedule Name", "Lighting\nControl Type",
                    "Stepped\nControl\nSteps", "Daylighting\nReference",
                    "Lighting\nArea %",
                    "Illuminance\nSetpoint\n(lux)",
                    "Min Input\nPower\nFraction",
                    "Min Light\nOutput\nFraction"
                ]
                styled_headers_controls = [wrap_text(h, header_cell_style) for h in headers_controls]
                table_data_controls = [styled_headers_controls]

                def format_num(value, precision, header_text_for_check):
                    if value is None or value == '-': return '-'
                    try:
                        if header_text_for_check == "Lighting\nArea %":
                             return f"{float(value) * 100:.0f}%"
                        return f"{float(value):.{precision}f}"
                    except (ValueError, TypeError):

                        return str(value)

                for entry in controls_data:
                    temp_row_values = [
                        entry.get("Zone", "-"),
                        entry.get("Availability Schedule Name", "-"),
                        entry.get("Lighting Control Type", "-"),
                        entry.get("Number of Stepped Control Steps", "-"),
                        entry.get("Daylighting Reference", "-"),
                        entry.get('Fraction of Zone Controlled'),
                        entry.get('Illuminance Setpoint'),
                        entry.get("Minimum Input Power Fraction"),
                        entry.get("Minimum Light Output Fraction")
                    ]
                    row_values = []
                    precisions = [None, None, None, None, None, 0, 1, 2, 2]
                    for i, val in enumerate(temp_row_values):
                        header_text = headers_controls[i]
                        precision = precisions[i]
                        row_values.append(format_num(val, precision, header_text))

                    styled_row = [wrap_text(val, cell_style) for val in row_values]
                    table_data_controls.append(styled_row)

                num_cols_controls = len(headers_controls)
                col_percentages_controls = [14, 15, 10, 8, 15, 10, 10, 9, 9]
                total_percentage = sum(col_percentages_controls)
                if not (99.9 < total_percentage < 100.1) or num_cols_controls == 0:
                    col_widths_controls = [(doc.width - 1*cm) / num_cols_controls if num_cols_controls > 0 else 0] * num_cols_controls
                else:
                    col_widths_controls = [(p / total_percentage) * (doc.width - 1*cm) for p in col_percentages_controls]

                span_commands_controls = []
                base_table_style_commands = table_style.getCommands()
                for j in range(num_cols_controls):
                    start_row = 1
                    while start_row < len(table_data_controls):
                        if not (start_row < len(table_data_controls) and j < len(table_data_controls[start_row])): break
                        current_val_obj = table_data_controls[start_row][j]
                        current_val = getattr(current_val_obj, 'text', str(current_val_obj))
                        if not (start_row < len(table_data_controls) and 0 < len(table_data_controls[start_row])): break
                        current_zone_obj = table_data_controls[start_row][0]
                        current_zone = getattr(current_zone_obj, 'text', str(current_zone_obj))

                        count = 1
                        for i in range(start_row + 1, len(table_data_controls)):
                            if not (i < len(table_data_controls) and j < len(table_data_controls[i]) and 0 < len(table_data_controls[i])): break
                            next_val_obj = table_data_controls[i][j]
                            next_val = getattr(next_val_obj, 'text', str(next_val_obj))
                            next_zone_obj = table_data_controls[i][0]
                            next_zone = getattr(next_zone_obj, 'text', str(next_zone_obj))

                            if next_zone == current_zone and next_val == current_val:
                                count += 1
                                if getattr(table_data_controls[i][j], 'text', '') != "":
                                    table_data_controls[i][j] = wrap_text("", cell_style)
                            else:
                                break
                        if count > 1:
                            span_commands_controls.append(('SPAN', (j, start_row), (j, start_row + count - 1)))
                            for r_idx in range(start_row, start_row + count - 1):
                                span_commands_controls.append(('LINEBELOW', (j, r_idx), (j, r_idx), 0.5, colors.white))
                                span_commands_controls.append(('LINEABOVE', (j, r_idx + 1), (j, r_idx + 1), 0.5, colors.white))
                        start_row += count

                final_controls_table_style = TableStyle(base_table_style_commands + span_commands_controls)
                table_controls = Table(table_data_controls, colWidths=col_widths_controls, repeatRows=1)
                table_controls.setStyle(final_controls_table_style)
                self._story.append(table_controls)
            else:
                self._story.append(Paragraph("No Daylighting Controls data found.", self._styles['Normal']))

            self._story.append(Spacer(1, 0.5*cm))

            self._story.append(Paragraph("Exterior Lights", self._styles['h2']))
            self._story.append(Spacer(1, 0.2*cm))
            exterior_lights_data = self._data.get("exterior_lights", [])
            exterior_lights_data.sort(key=lambda x: x.get("Name", ""))

            if exterior_lights_data:
                headers_ext_lights = ["Name", "Lighting SCHEDULE Name", "Design Equipment Level (W)"]
                styled_headers_ext_lights = [wrap_text(h, header_cell_style) for h in headers_ext_lights]
                table_data_ext_lights = [styled_headers_ext_lights]
                for entry in exterior_lights_data:
                    row_values = [
                        entry.get("Name", "-"),
                        entry.get("Lighting SCHEDULE Name", "-"),
                        f"{entry.get('Design Equipment Level (W)', 0.0):.2f}"
                    ]
                    styled_row = [wrap_text(val, cell_style) for val in row_values]
                    table_data_ext_lights.append(styled_row)

                num_cols_ext = len(headers_ext_lights)
                col_widths_ext = [(doc.width - 1*cm) / num_cols_ext if num_cols_ext > 0 else 0] * num_cols_ext
                table_ext_lights = Table(table_data_ext_lights, colWidths=col_widths_ext, repeatRows=1)
                table_ext_lights.setStyle(table_style)
                self._story.append(table_ext_lights)
            else:
                self._story.append(Paragraph("No Exterior Lights data found.", self._styles['Normal']))

            self._story.append(Spacer(1, 0.5*cm))

            self._story.append(Paragraph("Task Lights", self._styles['h2']))
            self._story.append(Spacer(1, 0.2*cm))
            task_lights_data = self._data.get("task_lights", [])
            task_lights_data.sort(key=lambda x: (x.get("Zone Name", ""), x.get("Lighting SCHEDULE Name", "")))

            if task_lights_data:
                headers_task_lights = ["Zone Name", "Lighting SCHEDULE Name"]
                styled_headers_task_lights = [wrap_text(h, header_cell_style) for h in headers_task_lights]
                table_data_task_lights = [styled_headers_task_lights]
                for entry in task_lights_data:
                    row_values = [
                        entry.get("Zone Name", "-"),
                        entry.get("Lighting SCHEDULE Name", "-")
                    ]
                    styled_row = [wrap_text(val, cell_style) for val in row_values]
                    table_data_task_lights.append(styled_row)

                num_cols_task = len(headers_task_lights)
                col_widths_task = [(doc.width - 1*cm) / num_cols_task if num_cols_task > 0 else 0] * num_cols_task

                task_table_style_commands = list(table_style.getCommands())
                span_commands_task = []
                start_row_task = 1
                while start_row_task < len(table_data_task_lights):
                    if not (start_row_task < len(table_data_task_lights) and 0 < len(table_data_task_lights[start_row_task])): break
                    current_zone_obj = table_data_task_lights[start_row_task][0]
                    current_zone = getattr(current_zone_obj, 'text', str(current_zone_obj))
                    count_task = 1
                    for i in range(start_row_task + 1, len(table_data_task_lights)):
                        if not (i < len(table_data_task_lights) and 0 < len(table_data_task_lights[i])): break
                        next_zone_obj = table_data_task_lights[i][0]
                        next_zone = getattr(next_zone_obj, 'text', str(next_zone_obj))
                        if next_zone == current_zone:
                            count_task += 1
                            if getattr(table_data_task_lights[i][0], 'text', '') != "":
                                 table_data_task_lights[i][0] = wrap_text("", cell_style)
                        else:
                            break
                    if count_task > 1:
                        span_commands_task.append(('SPAN', (0, start_row_task), (0, start_row_task + count_task - 1)))
                        for r_idx in range(start_row_task, start_row_task + count_task - 1):
                            span_commands_task.append(('LINEBELOW', (0, r_idx), (0, r_idx), 0.5, colors.white))
                            span_commands_task.append(('LINEABOVE', (0, r_idx + 1), (0, r_idx + 1), 0.5, colors.white))
                    start_row_task += count_task

                final_task_table_style = TableStyle(task_table_style_commands + span_commands_task)
                table_task_lights = Table(table_data_task_lights, colWidths=col_widths_task, repeatRows=1)
                table_task_lights.setStyle(final_task_table_style)
                self._story.append(table_task_lights)
            else:
                self._story.append(Paragraph("No Task Lights data found.", self._styles['Normal']))

            doc.build(self._story, onFirstPage=self._add_header_footer, onLaterPages=self._add_header_footer)
            return True
        except (IOError, OSError) as e:
            error_message = f"Error during file operation for Lighting report '{self._output_path}': {e.strerror}"
            logger.error(error_message, exc_info=True)
            return False
        except Exception as e:
            error_message = f"An unexpected error occurred while generating Lighting report '{self._output_path}': {type(e).__name__} - {str(e)}"
            logger.error(error_message, exc_info=True)
            return False
        finally:
            pass

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    dummy_data = {
        "controls": [
            {
                "Zone": "01:02XLIVING", "Availability Schedule Name": "Always On", "Lighting Control Type": "ContinuousOff",
                "Number of Stepped Control Steps": 1, "Daylighting Reference": "01:02XLIVING Ref Point 1",
                "Fraction of Zone Controlled": 1.0, "Illuminance Setpoint": 300.0,
                "Minimum Input Power Fraction": 0.1, "Minimum Light Output Fraction": 0.1
            },
        ],
        "reference_points": [
            {
                "Zone": "01:02XLIVING", "X-Coordinate": 10.123, "Y-Coordinate": 5.456, "Z-Coordinate": 0.8,
                "Daylighting Reference": "01:02XLIVING Ref Point 1", "Fraction of Zone Controlled": 1.0, "Illuminance Setpoint": 300.0,
                "Minimum Input Power Fraction": 0.1, "Minimum Light Output Fraction": 0.1
            },
        ],
        "exterior_lights": [
            {"Name": "EXTERIOR LIGHTING", "Lighting SCHEDULE Name": "On 24/7", "Design Equipment Level (W)": 100.0},
            {"Name": "GARAGE LIGHTS", "Lighting SCHEDULE Name": "Dusk to Dawn", "Design Equipment Level (W)": 75.5},
        ],
        "task_lights": [
            {"Zone Name": "02:03XMAMAD", "Lighting SCHEDULE Name": "8:00 - 18:00 Mon - Sat"},
            {"Zone Name": "02:03XMAMAD", "Lighting SCHEDULE Name": "Evening Study"},
            {"Zone Name": "01:01XSTUDY", "Lighting SCHEDULE Name": "Always On Task"},
        ]
    }
    generator = LightingReportGenerator(dummy_data, "lighting_report_styled.pdf",
                                        project_name="Test Project", run_id="Run_12345")
    generator.generate_report()
