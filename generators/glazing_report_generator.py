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
from generators.shared_design_system import (
    COLORS, FONTS, FONT_SIZES, LAYOUT,
    create_standard_table_style, create_cell_style, wrap_text, 
    create_title_style, create_header_info_style
)


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
        self.cell_style = create_cell_style(self.styles, is_header=False, font_size=FONT_SIZES['table_body'])
        self.header_style = create_cell_style(self.styles, is_header=True, center_align=True, font_size=FONT_SIZES['table_header'])
        self.subheader_style = create_cell_style(self.styles, is_header=False, font_size=FONT_SIZES['table_body'])

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
            logo_image = create_logo_image(max_width=LAYOUT['logo']['max_width'], max_height=LAYOUT['logo']['max_height'])
            if logo_image:
                # Create a table to position logo on the left
                logo_table_data = [[logo_image, ""]]
                logo_table = Table(logo_table_data, colWidths=[LAYOUT['logo']['table_width'], doc.width - LAYOUT['logo']['table_width']])
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
            header_info_style = create_header_info_style(self.styles)
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
            story.append(Spacer(1, LAYOUT['spacing']['small']))
            title_style = create_title_style(self.styles)
            story.append(Paragraph(f"{report_title} Report", title_style))
            story.append(Spacer(1, LAYOUT['spacing']['standard']))
            for construction_id, data in self.glazing_data.items():
                sub_heading_style = ParagraphStyle(
                    'SubHeading',
                    parent=self.styles['h3'],
                    textColor=COLORS['primary_blue'],
                    alignment=TA_CENTER
                )
                story.append(Paragraph(f"Construction: {construction_id}", sub_heading_style))
                story.append(Spacer(1, LAYOUT['spacing']['small']))
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
                    story.append(Spacer(1, LAYOUT['spacing']['small']))
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
                    story.append(Spacer(1, LAYOUT['spacing']['small']))
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
                    story.append(Spacer(1, LAYOUT['spacing']['small']))
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
                    story.append(Spacer(1, LAYOUT['spacing']['small']))
                story.append(Spacer(1, LAYOUT['spacing']['section']))
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
        style = create_standard_table_style()
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
        style = create_standard_table_style()
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
        style = create_standard_table_style()
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
        style = create_standard_table_style()
        style.add('ALIGN', (1, 1), (-1, -1), 'RIGHT')
        table.setStyle(style)
        return table

def generate_glazing_report_pdf(parsed_glazing_data, output_filename, project_name="N/A", run_id="N/A",
                               city_name="N/A", area_name="N/A"):
    generator = GlazingReportGenerator(parsed_glazing_data, project_name=project_name, run_id=run_id, 
                                      city_name=city_name, area_name=area_name)
    return generator.generate_report_pdf(output_filename)
