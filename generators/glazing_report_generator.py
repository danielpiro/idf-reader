from typing import Dict, Any
import pandas as pd
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
from generators.base_report_generator import BaseReportGenerator, handle_report_errors, StandardPageSizes
from generators.shared_design_system import (
    COLORS, FONTS, FONT_SIZES, LAYOUT,
    create_standard_table_style, create_cell_style, wrap_text, create_title_style
)
from generators.utils.formatting_utils import ValueFormatter



class GlazingReportGenerator(BaseReportGenerator):
    """Generates a PDF report summarizing glazing constructions using ReportLab."""
    def __init__(self, parsed_glazing_data, project_name="N/A", run_id="N/A", city_name="N/A", area_name="N/A"):
        super().__init__(project_name, run_id, city_name, area_name)
        self.glazing_data = parsed_glazing_data
        self.formatter = ValueFormatter()
        self.cell_style = create_cell_style(self.styles, is_header=False, font_size=FONT_SIZES['table_body'])
        self.header_style = create_cell_style(self.styles, is_header=True, center_align=True, font_size=FONT_SIZES['table_header'])
        self.subheader_style = create_cell_style(self.styles, is_header=False, font_size=FONT_SIZES['table_body'])

    @handle_report_errors("Glazing")
    def generate_report_pdf(self, output_filename):
        if not self.glazing_data:
            return False
            
        # Get standard page configuration
        page_config = StandardPageSizes.get_config('glazing')
        
        # Create document
        doc = self.create_document(
            output_filename,
            page_size=page_config['page_size'],
            orientation=page_config['orientation']
        )
        
        # Build story
        story = []
        report_title = "Glazing"
        
        # Add standardized header
        header_elements = self.add_standardized_header(doc, report_title)
        story.extend(header_elements)
        title_style = create_title_style(self.styles)
        story.append(Paragraph(f"{report_title} Report", title_style))
        story.append(Spacer(1, LAYOUT['spacing']['standard']))
        
        # Create separate tables for each construction
        if self.glazing_data:
            for construction_id, data in self.glazing_data.items():
                # Add construction heading
                sub_heading_style = ParagraphStyle(
                    'SubHeading',
                    parent=self.styles['h3'],
                    textColor=COLORS['primary_blue'],
                    alignment=TA_CENTER
                )
                story.append(Paragraph(f"Construction: {construction_id}", sub_heading_style))
                story.append(Spacer(1, LAYOUT['spacing']['small']))
                
                # Create table for this construction
                construction_table = self._create_construction_table(construction_id, data)
                if construction_table:
                    story.append(construction_table)
                    story.append(Spacer(1, LAYOUT['spacing']['section']))
        else:
            # Fallback message if no data
            story.append(Paragraph("No glazing data available.", self.styles['Normal']))
        
        # Build document
        return self.build_document(doc, story)

    def _create_construction_table(self, construction_id, data):
        """Create a table for a single construction with improved spacing."""
        # Table headers - simplified and better spaced for A3 landscape
        headers = [
            "Type", "Name/ID", "Type", "Thickness\n(m)", 
            "Conductivity\n(W/mK)", "U-Value\n(W/m²K)", "VT\n(Visible Trans.)", 
            "SHGC\n(Solar Heat Gain)", "ST\n(Solar Trans.)", "Transmittance", 
            "Reflectivity", "Position"
        ]
        
        table_data = [[wrap_text(h, self.header_style) for h in headers]]
        
        # Add system details
        system_details = data.get('system_details', {})
        if system_details:
            row = [
                wrap_text("Window", self.cell_style),
                wrap_text(system_details.get('Name', '-'), self.cell_style),
                wrap_text(system_details.get('Type', '-'), self.cell_style),
                wrap_text(self.formatter.format_number(system_details.get('Thickness'), precision=4), self.cell_style),
                wrap_text("-", self.cell_style),
                wrap_text(self.formatter.format_number(system_details.get('U-Value')), self.cell_style),
                wrap_text(self.formatter.format_number(system_details.get('VT')), self.cell_style),
                wrap_text(self.formatter.format_number(system_details.get('SHGC')), self.cell_style),
                wrap_text("-", self.cell_style),
                wrap_text("-", self.cell_style),
                wrap_text("-", self.cell_style),
                wrap_text("-", self.cell_style)
            ]
            table_data.append(row)
        
        # Add glazing layers
        glazing_layers = data.get('glazing_layers', [])
        for i, layer in enumerate(glazing_layers):
            row = [
                wrap_text(f"Layer {i+1}", self.cell_style),
                wrap_text(layer.get('Name', '-'), self.cell_style),
                wrap_text(layer.get('Type', '-'), self.cell_style),
                wrap_text(self.formatter.format_number(layer.get('Thickness'), precision=4), self.cell_style),
                wrap_text(self.formatter.format_number(layer.get('Conductivity')), self.cell_style),
                wrap_text("-", self.cell_style),
                wrap_text(self.formatter.format_number(layer.get('VT')), self.cell_style),
                wrap_text("-", self.cell_style),
                wrap_text(self.formatter.format_number(layer.get('ST')), self.cell_style),
                wrap_text("-", self.cell_style),
                wrap_text("-", self.cell_style),
                wrap_text("Glass layer", self.cell_style)
            ]
            table_data.append(row)
        
        # Add shading layers
        shading_layers = data.get('shading_layers', [])
        for i, layer in enumerate(shading_layers):
            row = [
                wrap_text(f"Shading Layer {i+1}", self.cell_style),
                wrap_text(layer.get('Name', '-'), self.cell_style),
                wrap_text("-", self.cell_style),
                wrap_text(self.formatter.format_number(layer.get('Thickness'), precision=4), self.cell_style),
                wrap_text(self.formatter.format_number(layer.get('Conductivity')), self.cell_style),
                wrap_text("-", self.cell_style),
                wrap_text("-", self.cell_style),
                wrap_text("-", self.cell_style),
                wrap_text("-", self.cell_style),
                wrap_text(self.formatter.format_number(layer.get('Transmittance')), self.cell_style),
                wrap_text(self.formatter.format_number(layer.get('Reflectivity')), self.cell_style),
                wrap_text(layer.get('Position', '-'), self.cell_style)
            ]
            table_data.append(row)
        
        # Add frame details
        frame_details = data.get('frame_details')
        if frame_details:
            frame_width = self.formatter.format_number(frame_details.get('frame_width'), precision=4)
            frame_conductance = self.formatter.format_number(frame_details.get('frame_conductance'))
            row = [
                wrap_text("Frame", self.cell_style),
                wrap_text(frame_details.get('id', '-'), self.cell_style),
                wrap_text("-", self.cell_style),
                wrap_text(f"{frame_width} m", self.cell_style),
                wrap_text(f"{frame_conductance} W/mK", self.cell_style),
                wrap_text("-", self.cell_style),
                wrap_text("-", self.cell_style),
                wrap_text("-", self.cell_style),
                wrap_text("-", self.cell_style),
                wrap_text("-", self.cell_style),
                wrap_text("-", self.cell_style),
                wrap_text("-", self.cell_style)
            ]
            table_data.append(row)
        
        if len(table_data) <= 1:  # Only headers
            return None
            
        # Define column widths optimized for A3 landscape (42cm - 2.8cm margins = ~39cm usable)
        col_widths = [3.5*cm, 4.5*cm, 3*cm, 2.5*cm, 3*cm, 3*cm, 3*cm, 3.5*cm, 2.5*cm, 3*cm, 3*cm, 4.5*cm]
        
        table = Table(table_data, colWidths=col_widths)
        style = create_standard_table_style()
        
        # Right-align numeric columns
        style.add('ALIGN', (3, 1), (10, -1), 'RIGHT')
        
        table.setStyle(style)
        return table

def generate_glazing_report_pdf(parsed_glazing_data, output_filename, project_name="N/A", run_id="N/A",
                               city_name="N/A", area_name="N/A"):
    generator = GlazingReportGenerator(parsed_glazing_data, project_name=project_name, run_id=run_id, 
                                      city_name=city_name, area_name=area_name)
    return generator.generate_report_pdf(output_filename)
