"""
PDF Report generator for Daylighting data.
"""
from reportlab.lib.pagesizes import A3, landscape # Changed to A3
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle # Added ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT # Added alignments
import datetime # Added datetime
from typing import Dict, List, Any

# Helper functions similar to load_report_generator
def wrap_text(text, style):
    """Helper function to create wrapped text in a cell."""
    return Paragraph(str(text), style)

def create_cell_style(styles, is_header=False, font_size=6, leading=7): # Adjusted default font size
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
        alignment=TA_LEFT # Default to left alignment for data
    )
    return style

def create_lighting_table_style(header_rows=1):
    """Create table style similar to load report but simpler header."""
    style = [
        # Header Row Styling
        ('BACKGROUND', (0, 0), (-1, header_rows - 1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, header_rows - 1), colors.black),
        ('ALIGN', (0, 0), (-1, header_rows - 1), 'CENTER'), # Center align headers
        ('VALIGN', (0, 0), (-1, header_rows - 1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, header_rows - 1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, header_rows - 1), 6), # Header font size
        ('BOTTOMPADDING', (0, 0), (-1, header_rows - 1), 3),

        # Data Rows Styling (start from header_rows index)
        ('BACKGROUND', (0, header_rows), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, header_rows), (-1, -1), colors.black),
        ('ALIGN', (0, header_rows), (-1, -1), 'LEFT'), # Left align data cells
        ('VALIGN', (0, header_rows), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, header_rows), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, header_rows), (-1, -1), 5), # Data font size
        ('TOPPADDING', (0, header_rows), (-1, -1), 1),
        ('BOTTOMPADDING', (0, header_rows), (-1, -1), 1),

        # Grid lines for the entire table
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),

        # Padding for all cells
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3)
    ]
    return TableStyle(style)


class LightingReportGenerator:
    """Generates a PDF report for parsed Daylighting data, styled like the load report."""

    # Added project_name and run_id
    def __init__(self, data: Dict[str, List[Dict[str, Any]]], output_path: str,
                 project_name: str = "N/A", run_id: str = "N/A"):
        """
        Initializes the LightingReportGenerator.

        Args:
            data: The parsed daylighting data from LightingParser.
            output_path: The path to save the generated PDF report.
            project_name: Name of the project for the header.
            run_id: Identifier for the current run for the header.
        """
        self._data = data
        self._output_path = output_path
        self._project_name = project_name
        self._run_id = run_id
        self._styles = getSampleStyleSheet()
        self._story = []

    def _add_header_footer(self, canvas, doc):
        """Adds header and footer to each page."""
        canvas.saveState()
        # Header (similar to load report, but simpler content for now)
        now = datetime.datetime.now()
        header_text = f"Project: {self._project_name} | Run ID: {self._run_id} | Date: {now.strftime('%Y-%m-%d %H:%M:%S')} | Report: Daylighting Summary"
        header_style = ParagraphStyle('HeaderStyle', parent=self._styles['Normal'], fontSize=8, alignment=TA_LEFT)
        p = Paragraph(header_text, header_style)
        w, h = p.wrap(doc.width, doc.topMargin)
        p.drawOn(canvas, doc.leftMargin, doc.height + doc.topMargin - h - 0.1*cm) # Adjust position slightly

        # Footer (Page Number)
        footer_text = f"Page {doc.page}"
        footer_style = ParagraphStyle('FooterStyle', parent=self._styles['Normal'], fontSize=8, alignment=TA_CENTER)
        p = Paragraph(footer_text, footer_style)
        w, h = p.wrap(doc.width, doc.bottomMargin)
        p.drawOn(canvas, doc.leftMargin, h) # Position at bottom

        canvas.restoreState()


    def generate_report(self):
        """Generates the PDF report."""
        # Use A3 Landscape with minimal margins
        left_margin = 0.5*cm
        right_margin = 0.5*cm
        top_margin = 1.5*cm # Increased top margin for header
        bottom_margin = 1.5*cm # Increased bottom margin for footer
        page_size = landscape(A3)

        doc = SimpleDocTemplate(self._output_path, pagesize=page_size,
                                leftMargin=left_margin, rightMargin=right_margin,
                                topMargin=top_margin, bottomMargin=bottom_margin)

        # --- Title ---
        title_style = self._styles['h1']
        title_style.textColor = colors.navy # Match load report title color
        title_style.alignment = TA_CENTER
        self._story.append(Paragraph("Daylighting Report", title_style))
        self._story.append(Spacer(1, 0.5*cm)) # Reduce space after title

        # --- Table Styles ---
        table_style = create_lighting_table_style()
        cell_style = create_cell_style(self._styles, font_size=5, leading=6) # Use smaller font for data
        header_cell_style = create_cell_style(self._styles, is_header=True, font_size=6, leading=7) # Slightly larger for headers

        # --- Table 1: Daylighting:Controls ---
        self._story.append(Paragraph("Daylighting: Controls", self._styles['h2']))
        self._story.append(Spacer(1, 0.3*cm)) # Reduce space
        controls_data = self._data.get("controls", [])
        if controls_data:
            # Define headers - check if conditional columns are needed
            headers_controls = [
                "Zone", "Availability\nSchedule Name", "Lighting\nControl Type",
                "Stepped\nControl\nSteps", "Daylighting\nReference",
                "Fraction\nControlled", "Illuminance\nSetpoint\n(lux)"
            ]
            # Check if any entry has non-None conditional values
            has_continuous_fields = any(
                entry.get("Minimum Input Power Fraction") is not None for entry in controls_data
            )
            if has_continuous_fields:
                 # Insert conditional headers at the correct position
                 headers_controls.insert(3, "Min Input\nPower\nFraction")
                 headers_controls.insert(4, "Min Light\nOutput\nFraction")

            # Wrap headers
            styled_headers_controls = [wrap_text(h, header_cell_style) for h in headers_controls]
            table_data_controls = [styled_headers_controls]

            # Helper to format numbers or return '-'
            def format_num(value, precision):
                if value is None: return '-'
                try:
                    return f"{float(value):.{precision}f}"
                except (ValueError, TypeError):
                    return str(value) # Fallback

            # Populate data rows with wrapped text
            for entry in controls_data:
                row_values = [
                    entry.get("Zone", "-"),
                    entry.get("Availability Schedule Name", "-"),
                    entry.get("Lighting Control Type", "-"),
                    entry.get("Number of Stepped Control Steps", "-"),
                    entry.get("Daylighting Reference", "-"),
                    format_num(entry.get('Fraction of Zone Controlled'), 2),
                    format_num(entry.get('Illuminance Setpoint'), 1)
                ]
                if has_continuous_fields:
                    min_power = entry.get("Minimum Input Power Fraction")
                    min_output = entry.get("Minimum Light Output Fraction")
                    row_values.insert(3, format_num(min_power, 2))
                    row_values.insert(4, format_num(min_output, 2))

                # Wrap each cell value
                styled_row = [wrap_text(val, cell_style) for val in row_values]
                table_data_controls.append(styled_row)

            # Calculate proportional column widths
            num_cols_controls = len(headers_controls)
            # Define approximate percentages (adjust as needed)
            # Example: Give Zone, Schedule, Reference more width
            if num_cols_controls == 7: # No continuous fields
                 col_percentages_controls = [15, 18, 12, 8, 18, 12, 17]
            elif num_cols_controls == 9: # With continuous fields
                 col_percentages_controls = [14, 15, 10, 8, 8, 8, 15, 10, 12]
            else: # Fallback to equal width
                 col_percentages_controls = [100 / num_cols_controls] * num_cols_controls

            total_percentage = sum(col_percentages_controls)
            col_widths_controls = [(p / total_percentage) * (doc.width - 1*cm) for p in col_percentages_controls] # Use available width

            # Create and style the table
            table_controls = Table(table_data_controls, colWidths=col_widths_controls, repeatRows=1) # Repeat header row
            table_controls.setStyle(table_style)
            self._story.append(table_controls)
        else:
            self._story.append(Paragraph("No Daylighting:Controls data found.", self._styles['Normal']))

        self._story.append(PageBreak())

        # --- Table 2: Daylighting:ReferencePoint ---
        self._story.append(Paragraph("Daylighting: Reference Points", self._styles['h2']))
        self._story.append(Spacer(1, 0.3*cm)) # Reduce space
        ref_points_data = self._data.get("reference_points", [])
        if ref_points_data:
            # Define headers - check if conditional columns are needed
            headers_ref_points = [
                "Zone", "X-Coord\n(m)", "Y-Coord\n(m)", "Z-Coord\n(m)",
                "Daylighting\nReference", "Fraction\nControlled", "Illuminance\nSetpoint\n(lux)"
            ]
            # Check if any entry has non-None conditional values
            has_continuous_fields_ref = any(
                entry.get("Minimum Input Power Fraction") is not None for entry in ref_points_data
            )
            if has_continuous_fields_ref:
                 # Append conditional headers
                 headers_ref_points.append("Min Input\nPower\nFraction")
                 headers_ref_points.append("Min Light\nOutput\nFraction")

            # Wrap headers
            styled_headers_ref_points = [wrap_text(h, header_cell_style) for h in headers_ref_points]
            table_data_ref_points = [styled_headers_ref_points]

            # Use the same formatter as above
            # Populate data rows with wrapped text
            for entry in ref_points_data:
                row_values = [
                    entry.get("Zone", "-"),
                    format_num(entry.get('X-Coordinate'), 3),
                    format_num(entry.get('Y-Coordinate'), 3),
                    format_num(entry.get('Z-Coordinate'), 1),
                    entry.get("Daylighting Reference", "-"),
                    format_num(entry.get('Fraction of Zone Controlled'), 2),
                    format_num(entry.get('Illuminance Setpoint'), 1)
                ]
                if has_continuous_fields_ref:
                    min_power = entry.get("Minimum Input Power Fraction")
                    min_output = entry.get("Minimum Light Output Fraction")
                    row_values.append(format_num(min_power, 2))
                    row_values.append(format_num(min_output, 2))

                # Wrap each cell value
                styled_row = [wrap_text(val, cell_style) for val in row_values]
                table_data_ref_points.append(styled_row)

            # Calculate proportional column widths
            num_cols_ref = len(headers_ref_points)
            # Define approximate percentages (adjust as needed)
            if num_cols_ref == 7: # No continuous fields
                 col_percentages_ref = [15, 10, 10, 10, 20, 15, 20]
            elif num_cols_ref == 9: # With continuous fields
                 col_percentages_ref = [14, 8, 8, 8, 18, 12, 14, 9, 9]
            else: # Fallback to equal width
                 col_percentages_ref = [100 / num_cols_ref] * num_cols_ref

            total_percentage_ref = sum(col_percentages_ref)
            col_widths_ref = [(p / total_percentage_ref) * (doc.width - 1*cm) for p in col_percentages_ref] # Use available width

            # Create and style the table
            table_ref_points = Table(table_data_ref_points, colWidths=col_widths_ref, repeatRows=1) # Repeat header row
            table_ref_points.setStyle(table_style)
            self._story.append(table_ref_points)
        else:
            self._story.append(Paragraph("No Daylighting:ReferencePoint data found.", self._styles['Normal']))


        # Build the PDF with header/footer
        try:
            # Use onFirstPage and onLaterPages arguments for header/footer
            doc.build(self._story, onFirstPage=self._add_header_footer, onLaterPages=self._add_header_footer)
            print(f"Successfully generated Lighting report: {self._output_path}")
            return True # Indicate success
        except Exception as e:
            print(f"Error generating Lighting report PDF file {self._output_path}: {e}")
            return False # Indicate failure

# Example Usage (if you want to test this generator directly)
# Updated to include project_name and run_id
if __name__ == '__main__':
    # Dummy data matching the parser output structure
    # Dummy data matching the parser output structure
    dummy_data = {
        "controls": [
            {
                "Zone": "01:02XLIVING", "Availability Schedule Name": "Always On", "Lighting Control Type": "ContinuousOff",
                "Number of Stepped Control Steps": 1, "Daylighting Reference": "01:02XLIVING Ref Point 1",
                "Fraction of Zone Controlled": 1.0, "Illuminance Setpoint": 300.0,
                "Minimum Input Power Fraction": 0.1, "Minimum Light Output Fraction": 0.1
            },
             { # Example for Stepped control
                "Zone": "02:03XMAMAD", "Availability Schedule Name": "Work Hours", "Lighting Control Type": "Stepped",
                "Number of Stepped Control Steps": 3, "Daylighting Reference": "02:03XMAMAD Ref Point 1",
                "Fraction of Zone Controlled": 0.8, "Illuminance Setpoint": 500.0,
                 "Minimum Input Power Fraction": None, "Minimum Light Output Fraction": None
            },
             { # Example for a second ref point from the same control object
                "Zone": "02:03XMAMAD", "Availability Schedule Name": "Work Hours", "Lighting Control Type": "Stepped",
                "Number of Stepped Control Steps": 3, "Daylighting Reference": "02:03XMAMAD Ref Point 2",
                "Fraction of Zone Controlled": 0.2, "Illuminance Setpoint": 400.0,
                 "Minimum Input Power Fraction": None, "Minimum Light Output Fraction": None
            },
        ],
        "reference_points": [
            { # Linked to ContinuousOff control
                "Zone": "01:02XLIVING", "X-Coordinate": 10.123, "Y-Coordinate": 5.456, "Z-Coordinate": 0.8,
                "Daylighting Reference": "01:02XLIVING Ref Point 1", "Fraction of Zone Controlled": 1.0, "Illuminance Setpoint": 300.0,
                "Minimum Input Power Fraction": 0.1, "Minimum Light Output Fraction": 0.1
            },
            { # Linked to Stepped control (point 1)
                "Zone": "02:03XMAMAD", "X-Coordinate": 67.788, "Y-Coordinate": -32.073, "Z-Coordinate": 0.7,
                "Daylighting Reference": "02:03XMAMAD Ref Point 1", "Fraction of Zone Controlled": 0.8, "Illuminance Setpoint": 500.0,
                 "Minimum Input Power Fraction": None, "Minimum Light Output Fraction": None
            },
             { # Linked to Stepped control (point 2)
                "Zone": "02:03XMAMAD", "X-Coordinate": 70.0, "Y-Coordinate": -30.0, "Z-Coordinate": 0.7,
                "Daylighting Reference": "02:03XMAMAD Ref Point 2", "Fraction of Zone Controlled": 0.2, "Illuminance Setpoint": 400.0,
                 "Minimum Input Power Fraction": None, "Minimum Light Output Fraction": None
            }
        ]
    }
    # Pass project name and run ID to the constructor
    generator = LightingReportGenerator(dummy_data, "lighting_report_styled.pdf",
                                        project_name="Test Project", run_id="Run_12345")
    generator.generate_report()