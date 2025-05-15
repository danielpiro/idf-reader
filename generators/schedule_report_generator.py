from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.colors import navy, black, grey, lightgrey, white
import datetime

def parse_date_string(date_str):
    try:
        day, month = map(int, date_str.split('/'))
        return datetime.date(2000, month, day)
    except (ValueError, AttributeError):
        return datetime.date(2000, 12, 31)

def create_date_ranges(rule_blocks):
    if not rule_blocks:
        return []
    sorted_blocks = sorted(rule_blocks, key=lambda block: parse_date_string(block.get('through', '31/12')))
    first_date = '01/01' if sorted_blocks and sorted_blocks[0].get('through') != '01/01' else None
    result_blocks = []
    prev_date = first_date
    for i, block in enumerate(sorted_blocks):
        current_date = block.get('through', '31/12')
        if '/' not in current_date:
            continue
        if i == 0 and first_date:
            date_range = f"{first_date} -> {current_date}"
        elif i > 0:
            prev_date = sorted_blocks[i-1].get('through', '31/12')
            date_range = f"{prev_date} -> {current_date}"
        else:
            date_range = f"01/01 -> {current_date}"
        new_block = block.copy()
        new_block['date_range'] = date_range
        result_blocks.append(new_block)
    return result_blocks

def create_hourly_schedule_table(rule_blocks, available_width):
    if not rule_blocks:
        return None
    rule_blocks_with_ranges = create_date_ranges(rule_blocks)
    period_col_width = 3.5 * cm
    num_hour_cols = 24
    hour_col_width = (available_width - period_col_width) / num_hour_cols
    col_widths = [period_col_width] + [hour_col_width] * num_hour_cols
    header = ["Date Ranges/Hours"] + [str(h+1) for h in range(num_hour_cols)]
    table_data = [header]
    cell_style = getSampleStyleSheet()['Normal']
    cell_style.fontSize = 7
    cell_style.alignment = 1
    for block in rule_blocks_with_ranges:
        period_text = block.get('date_range', 'N/A')
        hourly_values = block.get('hourly_values', [''] * num_hour_cols)
        row_data = [period_text] + [str(val) if val is not None else '' for val in hourly_values]
        table_data.append(row_data)
    style = TableStyle([
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
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

def generate_schedules_report_pdf(schedule_data, output_filename="output/schedules.pdf", project_name: str = "N/A", run_id: str = "N/A"):
    """
    Generates a PDF report containing schedule definitions, including a header.
    """
    if canvas is None:
        return False
    c = canvas.Canvas(output_filename, pagesize=A4)
    width, height = A4
    margin_x = 2 * cm
    margin_y = 2 * cm
    content_width = width - 2 * margin_x
    current_y = height - margin_y
    styles = getSampleStyleSheet()
    title_style = styles['h1']
    title_style.textColor = navy
    section_title_style = styles['h2']
    section_title_style.spaceBefore = 0.5 * cm
    section_title_style.spaceAfter = 0.3 * cm
    schedule_name_style = ParagraphStyle(
        name='ScheduleName', parent=styles['Normal'], fontName='Helvetica-Bold',
        spaceBefore=0.4*cm, spaceAfter=0.1*cm
    )
    not_found_style = ParagraphStyle(
        name='NotFound', parent=styles['Normal'], fontName='Helvetica-Oblique',
        textColor=grey, leftIndent=0.5*cm, spaceAfter=0.4*cm
    )
    header_info_style = ParagraphStyle(
        'HeaderInfo', parent=styles['Normal'], fontSize=9, textColor=colors.black, alignment=2
    )
    now = datetime.datetime.now()
    header_text = f"""
    Project: {project_name}<br/>
    Run ID: {run_id}<br/>
    Date: {now.strftime('%Y-%m-%d %H:%M:%S')}<br/>
    Report: Unique Schedule Definitions
    """
    p_header = Paragraph(header_text, header_info_style)
    header_width, header_height = p_header.wrapOn(c, content_width, margin_y)
    p_header.drawOn(c, width - margin_x - header_width, height - margin_y - header_height)
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
        try:
            c.save()
            return True
        except Exception:
            return False
    space_after_table = 0.8 * cm
    try:
        for schedule in schedule_data:
            schedule_type = schedule.get('type', 'Unknown Type')
            if ("activity" in schedule_type.lower() or "clothing" in schedule_type.lower()):
                schedule_type = schedule_type.split(" ")[0] + " Schedule"
            elif ("heating" in schedule_type.lower() or "cooling" in schedule_type.lower()):
                schedule_type = schedule_type.split(" ")[1] + " " + schedule_type.split(" ")[2] + " Schedule"
            rule_blocks = schedule.get('rule_blocks', [])
            schedule_name = None
            if any(x in schedule_type.lower() for x in ["activity", "clothing", "occupancy"]):
                schedule_name = "People"
            elif any(x in schedule_type.lower() for x in ["heating", "cooling"]):
                schedule_name = "Temperature"
            elif "ventilation" in schedule_type.lower():
                schedule_name = "Ventilation"
            elif "lighting" in schedule_type.lower():
                schedule_name = "Lighting"
            elif "shading" in schedule_type.lower():
                schedule_name = "Shading"
            elif "equipment" in schedule_type.lower():
                schedule_name = "Equipment"
            name_text = f"{schedule_type} [{schedule_name}]" if schedule_name else f"{schedule_type}"
            p_sched_name = Paragraph(name_text, schedule_name_style)
            p_sched_name.wrapOn(c, content_width, margin_y)
            name_height = p_sched_name.height
            schedule_table = create_hourly_schedule_table(rule_blocks, content_width)
            if schedule_table:
                table_width_actual, table_height = schedule_table.wrapOn(c, content_width, margin_y)
                total_element_height = name_height + schedule_name_style.spaceAfter + table_height + space_after_table
                if current_y - total_element_height < margin_y:
                    c.showPage()
                    current_y = height - margin_y
                p_sched_name.drawOn(c, margin_x, current_y - name_height)
                current_y -= (name_height + schedule_name_style.spaceAfter)
                schedule_table.drawOn(c, margin_x, current_y - table_height)
                current_y -= (table_height + space_after_table)
            else:
                if current_y - (name_height + schedule_name_style.spaceAfter + 1*cm) < margin_y:
                    c.showPage()
                    current_y = height - margin_y
                p_sched_name.drawOn(c, margin_x, current_y - name_height)
                current_y -= (name_height + schedule_name_style.spaceAfter)
                p_no_data = Paragraph("No rule data available to generate hourly table.", not_found_style)
                p_no_data.wrapOn(c, content_width, margin_y)
                p_no_data.drawOn(c, margin_x, current_y - p_no_data.height)
                current_y -= (p_no_data.height + space_after_table)
        c.save()
        return True
    except Exception:
        return False