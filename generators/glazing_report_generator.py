# generators/glazing_report_generator.py
from typing import Dict, Any, List
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from reportlab.lib.colors import navy, black, grey, lightgrey, white
import pandas as pd # Keep pandas for potential internal use if needed, but output is PDF
import datetime # Add datetime import

# --- Reportlab Helper Functions (similar to other generators) ---

def wrap_text(text, style):
    """Helper function to create wrapped text in a cell."""
    return Paragraph(str(text), style)

def create_cell_style(styles, is_header=False, is_subheader=False, align=TA_LEFT):
    """Create a cell style for wrapped text."""
    parent_style = styles['Normal']
    font_name = 'Helvetica'
    if is_header:
        font_name = 'Helvetica-Bold'
    elif is_subheader:
        font_name = 'Helvetica-Oblique'

    style = ParagraphStyle(
        'CellStyle',
        parent=parent_style,
        fontSize=8,
        leading=10,
        spaceBefore=2,
        spaceAfter=2,
        fontName=font_name,
        wordWrap='CJK', # Allow wrapping
        alignment=align
    )
    return style

def create_base_table_style():
    """Create a consistent base table style."""
    return TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ])

def apply_header_style(table_style, row_index=0):
    """Apply header styling to a TableStyle."""
    table_style.add('BACKGROUND', (0, row_index), (-1, row_index), lightgrey)
    table_style.add('TEXTCOLOR', (0, row_index), (-1, row_index), black)
    table_style.add('ALIGN', (0, row_index), (-1, row_index), 'CENTER')
    table_style.add('FONTNAME', (0, row_index), (-1, row_index), 'Helvetica-Bold')
    return table_style

# Helper function to safely format values for the report
def format_value(value, precision=3, na_rep='-'):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return na_rep
    try:
        # Attempt to format as float with specified precision
        return f"{float(value):.{precision}f}"
    except (ValueError, TypeError):
        # If not floatable, return as string
        return str(value)

# --- Main Generator Class ---

class GlazingReportGenerator:
    """Generates a PDF report summarizing glazing constructions using ReportLab."""

    def __init__(self, parsed_glazing_data: Dict[str, Dict[str, Any]],
                 project_name: str = "N/A", run_id: str = "N/A"):
        """
        Initializes the generator with parsed glazing data and header info.

        Args:
            parsed_glazing_data: The output dictionary from GlazingParser.parse_glazing_data().
            project_name (str): Name of the project.
            run_id (str): Identifier for the current run.
        """
        self.glazing_data = parsed_glazing_data
        self.project_name = project_name
        self.run_id = run_id
        self.styles = getSampleStyleSheet()
        self.cell_style = create_cell_style(self.styles)
        self.header_style = create_cell_style(self.styles, is_header=True, align=TA_CENTER)
        self.subheader_style = create_cell_style(self.styles, is_subheader=True)

    def generate_report_pdf(self, output_filename: str):
        """
        Generates the full glazing report as a PDF file.

        Args:
            output_filename: Path to save the generated PDF file.
        """
        if not self.glazing_data:
            print("Warning: No glazing data provided for PDF report generation.")
            # Optionally create a PDF saying "No data"
            # doc = SimpleDocTemplate(output_filename, pagesize=A4)
            # story = [Paragraph("No glazing constructions found or processed.", self.styles['Normal'])]
            # doc.build(story)
            return False

        try:
            page_size = landscape(A4) # Use landscape A4
            doc = SimpleDocTemplate(output_filename, pagesize=page_size,
                                    leftMargin=1.5*cm, rightMargin=1.5*cm,
                                    topMargin=1.5*cm, bottomMargin=1.5*cm)
            story = []

            # --- Header ---
            now = datetime.datetime.now()
            header_info_style = ParagraphStyle(
                'HeaderInfo',
                parent=self.styles['Normal'],
                fontSize=9,
                textColor=black,
                alignment=2 # Right aligned
            )
            header_text = f"""
            Project: {self.project_name}<br/>
            Run ID: {self.run_id}<br/>
            Date: {now.strftime('%Y-%m-%d %H:%M:%S')}<br/>
            Report: Glazing Constructions
            """
            story.append(Paragraph(header_text, header_info_style))
            story.append(Spacer(1, 5)) # Add some space after header

            # Title (using h3 for smaller size)
            title_style = self.styles['h3'] # Changed from h2 to h3
            title_style.alignment = TA_CENTER
            title_style.textColor = navy
            story.append(Paragraph("Glazing Constructions Report", title_style))
            story.append(Spacer(1, 0.5*cm))

            # Iterate through each construction
            for construction_id, data in self.glazing_data.items():
                # Construction Sub-heading (using h3)
                sub_heading_style = self.styles['h3'] # Changed from h2 to h3
                story.append(Paragraph(f"Construction: {construction_id}", sub_heading_style))
                story.append(Spacer(1, 0.2*cm))

                # --- 1. Glazing System Table ---
                system_table = self._create_system_table(data.get('system_details', {}))
                if system_table:
                    # Place title and table side-by-side
                    title_p = Paragraph("Glazing System", self.styles['h3'])
                    # Outer table to hold title and data table
                    outer_data = [[title_p, system_table]]
                    # Adjust colWidths: Title width + Table width (None lets it fill)
                    # Ensure title column width + table width fits page width minus margins
                    available_width = landscape(A4)[0] - 3*cm # Page width - margins
                    title_col_width = 3.5*cm
                    table_col_width = available_width - title_col_width - 0.5*cm # Small gap
                    # Check if system_table._colWidths sum exceeds table_col_width and adjust if needed (complex, skip for now)

                    outer_table = Table(outer_data, colWidths=[title_col_width, None]) # Let table column auto-size
                    outer_style = TableStyle([
                        ('VALIGN', (0, 0), (-1, -1), 'TOP'), # Align title top
                        ('LEFTPADDING', (0, 0), (0, 0), 0), # No padding left of title
                        ('RIGHTPADDING', (0, 0), (0, 0), 0.2*cm), # Padding between title and table
                        ('LEFTPADDING', (1, 0), (1, 0), 0), # No padding left of table cell
                        ('RIGHTPADDING', (1, 0), (1, 0), 0), # No padding right of table cell
                    ])
                    outer_table.setStyle(outer_style)
                    story.append(outer_table)
                    story.append(Spacer(1, 0.4*cm))

                # --- 2. Glazing Details Table ---
                details_table = self._create_details_table(data.get('glazing_layers', []))
                if details_table:
                    # Place title and table side-by-side
                    title_p = Paragraph("Glazing Details (Layers)", self.styles['h3'])
                    outer_data = [[title_p, details_table]]
                    title_col_width = 3.5*cm # Consistent width
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

                # --- 3. Shading Table ---
                shading_table = self._create_shading_table(data.get('shading_layers', []))
                if shading_table:
                    # Place title and table side-by-side
                    title_p = Paragraph("Shading", self.styles['h3'])
                    outer_data = [[title_p, shading_table]]
                    title_col_width = 3.5*cm # Consistent width
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

                # Add a separator line or larger spacer between constructions
                story.append(Spacer(1, 0.6*cm)) # Larger spacer

            # Build the PDF
            doc.build(story)
            print(f"Successfully generated glazing report: {output_filename}")
            return True

        except Exception as e:
            print(f"Error generating glazing PDF report: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _create_system_table(self, system_details: Dict[str, Any]) -> Table | None:
        """Creates the ReportLab Table for Glazing System."""
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

        # Define column widths (adjust as needed)
        col_widths = [3*cm, 3*cm, 2.5*cm, 3*cm, 2*cm, 2*cm] # Example widths

        table = Table(data, colWidths=col_widths)
        style = create_base_table_style()
        apply_header_style(style)
        table.setStyle(style)
        return table

    def _create_details_table(self, glazing_layers: List[Dict[str, Any]]) -> Table | None:
        """Creates the ReportLab Table for Glazing Details."""
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
                wrap_text(format_value(layer.get('ST')), self.cell_style) # Solar Transmittance
            ])

        # Define column widths (adjust as needed)
        col_widths = [4*cm, 3*cm, 2.5*cm, 3*cm, 2*cm, 2*cm] # Example widths

        table = Table(data, colWidths=col_widths)
        style = create_base_table_style()
        apply_header_style(style)
        table.setStyle(style)
        return table

    def _create_shading_table(self, shading_layers: List[Dict[str, Any]]) -> Table | None:
        """Creates the ReportLab Table for Shading."""
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
                # Use the 'Position' key from the parser, fallback to '-' if missing/empty
                wrap_text(layer.get('Position') or '-', self.cell_style)
            ])

        # Define column widths (adjust as needed)
        col_widths = [4*cm, 2.5*cm, 3*cm, 2.5*cm, 2.5*cm, 2.5*cm] # Example widths

        table = Table(data, colWidths=col_widths)
        style = create_base_table_style()
        apply_header_style(style)
        table.setStyle(style)
        return table

# --- Standalone Function for PDF Generation (called from outside) ---
def generate_glazing_report_pdf(parsed_glazing_data: Dict[str, Dict[str, Any]], output_filename: str,
                                project_name: str = "N/A", run_id: str = "N/A"):
    """
    Convenience function to instantiate the generator and create the PDF report.

    Args:
        parsed_glazing_data: The data obtained from GlazingParser.
        output_filename: The path where the PDF report should be saved.
        project_name (str): Name of the project.
        run_id (str): Identifier for the current run.
    """
    generator = GlazingReportGenerator(parsed_glazing_data, project_name=project_name, run_id=run_id)
    return generator.generate_report_pdf(output_filename)


# Example Usage (if run directly or for testing)
if __name__ == '__main__':
    # Example parsed data (similar to parser output)
    mock_parsed_data = {
        "Exterior Window Simple": {
            'id': "Exterior Window Simple", 'name': "Exterior Window Simple", 'type': 'Simple',
            'system_details': {'Name': "Exterior Window Simple", 'Type': 'Simple Glazing', 'Thickness': None, 'U-Value': 2.5, 'VT': 0.7, 'SHGC': 0.6},
            'glazing_layers': [], 'shading_layers': []
        },
        "Exterior Window Detailed": {
            'id': "Exterior Window Detailed", 'name': "Exterior Window Detailed", 'type': 'Detailed',
            'system_details': {'Name': "Exterior Window Detailed", 'Type': 'Detailed Glazing', 'Thickness': 0.0187, 'U-Value': None, 'VT': None, 'SHGC': None},
            'glazing_layers': [
                {'Name': 'Glass Layer 1', 'Type': 'Glazing', 'Thickness': 0.003, 'Conductivity': 1.0, 'VT': 0.8, 'ST': 0.7},
                {'Name': 'Air Gap', 'Type': 'Gas (Air)', 'Thickness': 0.0127, 'Conductivity': None, 'VT': None, 'ST': None},
                {'Name': 'Glass Layer 2', 'Type': 'Glazing', 'Thickness': 0.003, 'Conductivity': 1.0, 'VT': 0.8, 'ST': 0.7}
            ],
            'shading_layers': [
                 {'Name': 'Interior Shade Material', 'Thickness': 0.001, 'Conductivity': 0.1, 'Transmittance': 0.2, 'Reflectivity': 0.5, 'Position': 'Unknown'}
            ]
        }
    }

    output_pdf = "test_glazing_report.pdf"
    generate_glazing_report_pdf(mock_parsed_data, output_pdf)
    print(f"Test PDF generated: {output_pdf}")