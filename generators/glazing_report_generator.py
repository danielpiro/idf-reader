from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.colors import Color
import datetime
import pandas as pd
from utils.hebrew_text_utils import safe_format_header_text, get_hebrew_font_name
from utils.logo_utils import create_logo_image

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

def wrap_text(text, style):
    return Paragraph(str(text), style)

def create_cell_style(styles, is_header=False, is_subheader=False, align=TA_LEFT):
    parent_style = styles['Normal']
    font_name = 'Helvetica-Bold' if is_header else 'Helvetica-Oblique' if is_subheader else 'Helvetica'
    return ParagraphStyle(
        'CellStyle',
        parent=parent_style,
        fontSize=8,
        leading=10,
        spaceBefore=2,
        spaceAfter=2,
        fontName=font_name,
        textColor=COLORS['white'] if is_header else COLORS['dark_gray'],
        wordWrap='CJK',
        alignment=align
    )

def create_base_table_style():
    return TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, COLORS['border_gray']),
        ('BOX', (0, 0), (-1, -1), 1, COLORS['medium_gray']),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [COLORS['white'], COLORS['light_blue']]),
        ('FONTNAME', (0, 1), (-1, -1), FONTS['table_body']),
        ('FONTSIZE', (0, 1), (-1, -1), FONT_SIZES['table_body']),
        ('TEXTCOLOR', (0, 1), (-1, -1), COLORS['dark_gray']),
    ])

def apply_header_style(table_style, row_index=0):
    table_style.add('BACKGROUND', (0, row_index), (-1, row_index), COLORS['primary_blue'])
    table_style.add('TEXTCOLOR', (0, row_index), (-1, row_index), COLORS['white'])
    table_style.add('ALIGN', (0, row_index), (-1, row_index), 'CENTER')
    table_style.add('FONTNAME', (0, row_index), (-1, row_index), FONTS['table_header'])
    table_style.add('FONTSIZE', (0, row_index), (-1, row_index), FONT_SIZES['table_header'])
    return table_style

def format_value(value, precision=3, na_rep='-'):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return na_rep
    try:
        return f"{float(value):.{precision}f}"
    except (ValueError, TypeError):
        return str(value)

class GlazingReportGenerator:
    """Generates a PDF report summarizing glazing constructions using ReportLab."""
    def __init__(self, parsed_glazing_data, project_name="N/A", run_id="N/A", city_name="N/A", area_name="N/A"):
        self.glazing_data = parsed_glazing_data
        self.project_name = project_name
        self.run_id = run_id
        self.city_name = city_name
        self.area_name = area_name        
        self.styles = getSampleStyleSheet()
        self.cell_style = create_cell_style(self.styles)
        self.header_style = create_cell_style(self.styles, is_header=True, align=TA_CENTER)
        self.subheader_style = create_cell_style(self.styles, is_subheader=True)

    def generate_report_pdf(self, output_filename):
        if not self.glazing_data:
            return False
        try:
            page_size = landscape(A4)
            doc = SimpleDocTemplate(output_filename, pagesize=page_size,
                                    leftMargin=1.5*cm, rightMargin=1.5*cm,
                                    topMargin=1.5*cm, bottomMargin=1.5*cm)
            story = []
            
            # Add logo if available
            logo_image = create_logo_image(max_width=4*cm, max_height=2*cm)
            if logo_image:
                # Create a table to position logo on the left
                logo_table_data = [[logo_image, ""]]
                logo_table = Table(logo_table_data, colWidths=[5*cm, doc.width - 5*cm])
                logo_table.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (0, 0), 'LEFT'),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 0),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                    ('TOPPADDING', (0, 0), (-1, -1), 0),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
                ]))
                story.append(logo_table)
                story.append(Spacer(1, 10))
            
            now = datetime.datetime.now()
            hebrew_font = get_hebrew_font_name()
            header_info_style = ParagraphStyle(
                'HeaderInfo',
                parent=self.styles['Normal'],
                fontSize=9,
                fontName=hebrew_font,
                textColor=COLORS['dark_gray'],
                alignment=2
            )
            report_title = "Glazing Constructions"
            header_text = safe_format_header_text(
                project_name=self.project_name,
                run_id=self.run_id,
                timestamp=now.strftime('%Y-%m-%d %H:%M:%S'),
                city_name=self.city_name,
                area_name=self.area_name,
                report_title=report_title
            )
            story.append(Paragraph(header_text, header_info_style))
            story.append(Spacer(1, 5))
            title_style = self.styles['h3']
            title_style.alignment = TA_CENTER
            title_style.textColor = COLORS['primary_blue']
            title_style.fontName = FONTS['title']
            title_style.fontSize = FONT_SIZES['title']
            story.append(Paragraph(f"{report_title} Report", title_style))
            story.append(Spacer(1, 0.5*cm))
            for construction_id, data in self.glazing_data.items():
                sub_heading_style = ParagraphStyle(
                    'SubHeading',
                    parent=self.styles['h3'],
                    textColor=COLORS['primary_blue'],
                    alignment=TA_CENTER
                )
                story.append(Paragraph(f"Construction: {construction_id}", sub_heading_style))
                story.append(Spacer(1, 0.2*cm))
                system_table = self._create_system_table(data.get('system_details', {}))
                if system_table:
                    glazing_system_style = ParagraphStyle(
                        'GlazingSystemStyle',
                        parent=self.styles['h3'],
                        textColor=COLORS['primary_blue'],
                        alignment=TA_CENTER
                    )
                    title_p = Paragraph("Glazing System", glazing_system_style)
                    outer_data = [[title_p, system_table]]
                    landscape(A4)[0] - 3*cm
                    title_col_width = 3.5*cm
                    outer_table = Table(outer_data, colWidths=[title_col_width, None])
                    outer_style = TableStyle([
                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                        ('LEFTPADDING', (0, 0), (0, 0), 0),
                        ('RIGHTPADDING', (0, 0), (0, 0), 0.2*cm),
                        ('LEFTPADDING', (1, 0), (1, 0), 0),
                        ('RIGHTPADDING', (1, 0), (1, 0), 0),
                    ])
                    outer_table.setStyle(outer_style)
                    story.append(outer_table)
                    story.append(Spacer(1, 0.4*cm))
                details_table = self._create_details_table(data.get('glazing_layers', []))
                if details_table:
                    glazing_details_style = ParagraphStyle(
                        'GlazingDetailsStyle',
                        parent=self.styles['h3'],
                        textColor=COLORS['primary_blue'],
                        alignment=TA_CENTER
                    )
                    title_p = Paragraph("Glazing Details (Layers)", glazing_details_style)
                    outer_data = [[title_p, details_table]]
                    title_col_width = 3.5*cm
                    outer_table = Table(outer_data, colWidths=[title_col_width, None])
                    outer_style = TableStyle([
                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                        ('LEFTPADDING', (0, 0), (0, 0), 0),
                        ('RIGHTPADDING', (0, 0), (0, 0), 0.2*cm),
                        ('LEFTPADDING', (1, 0), (1, 0), 0),
                        ('RIGHTPADDING', (1, 0), (1, 0), 0),
                    ])
                    outer_table.setStyle(outer_style)
                    story.append(outer_table)
                    story.append(Spacer(1, 0.4*cm))
                shading_table = self._create_shading_table(data.get('shading_layers', []))
                if shading_table:
                    shading_style = ParagraphStyle(
                        'ShadingStyle',
                        parent=self.styles['h3'],
                        textColor=COLORS['primary_blue'],
                        alignment=TA_CENTER
                    )
                    title_p = Paragraph("Shading", shading_style)
                    outer_data = [[title_p, shading_table]]
                    title_col_width = 3.5*cm
                    outer_table = Table(outer_data, colWidths=[title_col_width, None])
                    outer_style = TableStyle([
                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                        ('LEFTPADDING', (0, 0), (0, 0), 0),
                        ('RIGHTPADDING', (0, 0), (0, 0), 0.2*cm),
                        ('LEFTPADDING', (1, 0), (1, 0), 0),
                        ('RIGHTPADDING', (1, 0), (1, 0), 0),
                    ])
                    outer_table.setStyle(outer_style)
                    story.append(outer_table)
                    story.append(Spacer(1, 0.4*cm))
                frame_table = self._create_frame_table(data.get('frame_details'))
                if frame_table:
                    frame_style = ParagraphStyle(
                        'FrameStyle',
                        parent=self.styles['h3'],
                        textColor=COLORS['primary_blue'],
                        alignment=TA_CENTER
                    )
                    title_p = Paragraph("Frame", frame_style)
                    outer_data = [[title_p, frame_table]]
                    title_col_width = 3.5*cm
                    outer_table = Table(outer_data, colWidths=[title_col_width, None])
                    outer_style = TableStyle([
                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                        ('LEFTPADDING', (0, 0), (0, 0), 0),
                        ('RIGHTPADDING', (0, 0), (0, 0), 0.2*cm),
                        ('LEFTPADDING', (1, 0), (1, 0), 0),
                        ('RIGHTPADDING', (1, 0), (1, 0), 0),
                    ])
                    outer_table.setStyle(outer_style)
                    story.append(outer_table)
                    story.append(Spacer(1, 0.4*cm))
                story.append(Spacer(1, 0.6*cm))
            doc.build(story)
            return True
        except Exception as e:
            raise RuntimeError(f"Error generating glazing PDF report: {e}")

    def _create_system_table(self, system_details):
        if not system_details:
            return None
        headers = ["Name", "Type", "Thickness (m)", "U-Value (W/m²K)", "VT", "SHGC"]
        data = [
            [wrap_text(h, self.header_style) for h in headers],
            [
                wrap_text(system_details.get('Name', '-'), self.cell_style),
                wrap_text(system_details.get('Type', '-'), self.cell_style),
                wrap_text(format_value(system_details.get('Thickness'), precision=4), self.cell_style),
                wrap_text(format_value(system_details.get('U-Value')), self.cell_style),
                wrap_text(format_value(system_details.get('VT')), self.cell_style),
                wrap_text(format_value(system_details.get('SHGC')), self.cell_style)
            ]
        ]
        col_widths = [3*cm, 3*cm, 2.5*cm, 3*cm, 2*cm, 2*cm]
        table = Table(data, colWidths=col_widths)
        style = create_base_table_style()
        apply_header_style(style)
        style.add('ALIGN', (2, 1), (-1, -1), 'RIGHT')
        table.setStyle(style)
        return table

    def _create_details_table(self, glazing_layers):
        if not glazing_layers:
            return None
        headers = ["Name", "Type", "Thickness (m)", "Conductivity (W/mK)", "VT", "ST"]
        data = [[wrap_text(h, self.header_style) for h in headers]]
        for layer in glazing_layers:
            data.append([
                wrap_text(layer.get('Name', '-'), self.cell_style),
                wrap_text(layer.get('Type', '-'), self.cell_style),
                wrap_text(format_value(layer.get('Thickness'), precision=4), self.cell_style),
                wrap_text(format_value(layer.get('Conductivity')), self.cell_style),
                wrap_text(format_value(layer.get('VT')), self.cell_style),
                wrap_text(format_value(layer.get('ST')), self.cell_style)
            ])
        col_widths = [4*cm, 3*cm, 2.5*cm, 3*cm, 2*cm, 2*cm]
        table = Table(data, colWidths=col_widths)
        style = create_base_table_style()
        apply_header_style(style)
        style.add('ALIGN', (2, 1), (-1, -1), 'RIGHT')
        table.setStyle(style)
        return table

    def _create_shading_table(self, shading_layers):
        if not shading_layers:
            return None
        headers = ["Name", "Thickness (m)", "Conductivity (W/mK)", "Transmittance", "Reflectivity", "Position"]
        data = [[wrap_text(h, self.header_style) for h in headers]]
        for layer in shading_layers:
            data.append([
                wrap_text(layer.get('Name', '-'), self.cell_style),
                wrap_text(format_value(layer.get('Thickness'), precision=4), self.cell_style),
                wrap_text(format_value(layer.get('Conductivity')), self.cell_style),
                wrap_text(format_value(layer.get('Transmittance')), self.cell_style),
                wrap_text(format_value(layer.get('Reflectivity')), self.cell_style),
                wrap_text(layer.get('Position') or '-', self.cell_style)
            ])
        col_widths = [4*cm, 2.5*cm, 3*cm, 2.5*cm, 2.5*cm, 2.5*cm]
        table = Table(data, colWidths=col_widths)
        style = create_base_table_style()
        apply_header_style(style)
        style.add('ALIGN', (1, 1), (4, -1), 'RIGHT')
        table.setStyle(style)
        return table

    def _create_frame_table(self, frame_details):
        if not frame_details:
            return None
        headers = ["ID", "Width (m)", "Conductance (W/mK)"]
        data = [
            [wrap_text(h, self.header_style) for h in headers],
            [
                wrap_text(frame_details.get('id', '-'), self.cell_style),
                wrap_text(format_value(frame_details.get('frame_width'), precision=4), self.cell_style),
                wrap_text(format_value(frame_details.get('frame_conductance')), self.cell_style)
            ]
        ]
        col_widths = [4*cm, 3*cm, 3*cm]
        table = Table(data, colWidths=col_widths)
        style = create_base_table_style()
        apply_header_style(style)
        style.add('ALIGN', (1, 1), (-1, -1), 'RIGHT')
        table.setStyle(style)
        return table

def generate_glazing_report_pdf(parsed_glazing_data, output_filename, project_name="N/A", run_id="N/A",
                               city_name="N/A", area_name="N/A"):
    generator = GlazingReportGenerator(parsed_glazing_data, project_name=project_name, run_id=run_id, 
                                      city_name=city_name, area_name=area_name)
    return generator.generate_report_pdf(output_filename)
