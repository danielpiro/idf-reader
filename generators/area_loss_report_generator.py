"""
Generates reports for area loss information extracted from IDF files.
"""
from typing import Dict, Any, List
from utils.logging_config import get_logger
from generators.reportlab_commons import colors, ParagraphStyle, cm, Paragraph, Table
from generators.base_report_generator import BaseReportGenerator, handle_report_errors, StandardPageSizes
from generators.shared_design_system import (
    COLORS, FONTS, create_standard_table_style, create_title_style
)
from generators.utils.formatting_utils import ValueFormatter


logger = get_logger(__name__)

class AreaLossReportGenerator(BaseReportGenerator):
    """Area Loss Report Generator using the refactored architecture."""
    
    def __init__(self, project_name="N/A", run_id="N/A", city_name="N/A", area_name="N/A"):
        super().__init__(project_name, run_id, city_name, area_name)
        self.formatter = ValueFormatter()
    
    @handle_report_errors("Area Loss")
    def generate_report(self, area_loss_data: List[Dict[str, Any]], output_filename: str) -> bool:
        """Generate area loss PDF report."""
        # Get standard page configuration
        page_config = StandardPageSizes.get_config('area_loss')
        
        # Create document
        doc = self.create_document(
            output_filename,
            page_size=page_config['page_size'],
            orientation=page_config['orientation']
        )
        
        # Build story
        story = []
        report_title = "Area Loss"
        
        # Add standardized header
        header_elements = self.add_standardized_header(doc, report_title)
        story.extend(header_elements)
        
        # Add title
        title_style = create_title_style(self.styles)
        story.append(Paragraph(f"{report_title} Report", title_style))
        
        # Create and add table
        if area_loss_data:
            table = self._create_area_loss_table(area_loss_data)
            story.append(table)
        else:
            no_data_paragraph = Paragraph("No area loss data available.", self.styles['Normal'])
            story.append(no_data_paragraph)
        
        # Build document
        return self.build_document(doc, story)
    
    def _create_area_loss_table(self, area_loss_data: List[Dict[str, Any]]) -> Table:
        """Create area loss table with standardized styling."""
        # Create styles
        cell_style = ParagraphStyle(
            'CellStyle',
            parent=self.styles['Normal'],
            fontSize=9,
            leading=10,
            spaceBefore=0,
            spaceAfter=0
        )
        
        header_style = ParagraphStyle(
            'HeaderStyle',
            parent=self.styles['Normal'],
            fontSize=9,
            leading=10,
            spaceBefore=0,
            spaceAfter=0,
            fontName=FONTS['table_header'],
            textColor=COLORS['white']
        )
        
        compatibility_style = ParagraphStyle(
            'CompatibilityStyle',
            parent=self.styles['Normal'],
            fontSize=9,
            leading=10,
            spaceBefore=0,
            spaceAfter=0
        )
        
        # Create table data
        table_data = self._prepare_table_data(area_loss_data, cell_style, compatibility_style, header_style)
        
        # Define column widths
        col_widths = [3.0*cm, 5.0*cm, 3.0*cm, 3.0*cm, 3.0*cm]
        
        # Create table
        table = Table(table_data, colWidths=col_widths, repeatRows=1)
        
        # Apply styling
        table_style = create_standard_table_style(header_rows=1)
        table_style.add('ALIGN', (2, 1), (3, -1), 'RIGHT')  # Right align H-Value and H-Needed
        table.setStyle(table_style)
        
        return table
    
    def _prepare_table_data(self, area_loss_data, cell_style, compatibility_style, header_style):
        """Prepare table data with headers and formatted content."""
        # Header row
        table_data = [[
            Paragraph("Area", header_style),
            Paragraph("Location", header_style),
            Paragraph("H-Value", header_style),
            Paragraph("H-Needed", header_style),
            Paragraph("Compatible", header_style)
        ]]
        
        # Sort data
        sorted_rows = sorted(area_loss_data, key=lambda x: x.get('area_id', ''))
        
        # Data rows
        for row in sorted_rows:
            area_id = self.formatter.safe_string(row.get('area_id', 'Unknown'))
            location = self.formatter.safe_string(row.get('location', 'Unknown'))
            h_value = self.formatter.format_number(row.get('h_value'), precision=3)
            h_needed = self.formatter.format_number(row.get('h_needed'), precision=3)
            compatible = row.get('compatible', 'No')
            
            # Color-code compatibility
            color = "green" if compatible == "Yes" else "red"
            compatible_cell = Paragraph(f"<font color={color}>{compatible}</font>", compatibility_style)
            
            table_data.append([
                Paragraph(area_id, cell_style),
                Paragraph(location, cell_style),
                h_value,
                h_needed,
                compatible_cell
            ])
        
        return table_data

# Backward compatibility function
@handle_report_errors("Area Loss")
def generate_area_loss_report_pdf(area_loss_data: List[Dict[str, Any]],
                                 output_filename: str,
                                 project_name: str = "N/A", 
                                 run_id: str = "N/A",
                                 city_name: str = "N/A",
                                 area_name: str = "N/A") -> bool:
    """
    Generate a PDF report with area loss information, including H-values.
    
    This function provides backward compatibility while using the new refactored architecture.

    Args:
        area_loss_data (List[Dict[str, Any]]): List of area loss data rows.
        output_filename (str): Path where to save the PDF report.
        project_name (str): Name of the project.
        run_id (str): Identifier for the current run.
        city_name (str): City name.
        area_name (str): Area name.

    Returns:
        bool: True if report generation was successful, False otherwise.
    """
    generator = AreaLossReportGenerator(
        project_name=project_name,
        run_id=run_id,
        city_name=city_name,
        area_name=area_name
    )
    
    return generator.generate_report(area_loss_data, output_filename)
