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

        # --- Combined Daylighting Table ---
        # self._story.append(Paragraph("Daylighting: Controls", self._styles['h2'])) # Removed Title
        # self._story.append(Spacer(1, 0.3*cm)) # Reduce space
        controls_data = self._data.get("controls", [])

        # Sort data by Zone Name
        controls_data.sort(key=lambda x: x.get("Zone", ""))

        if controls_data:
            # Define headers - Moved columns to the end and renamed one
            headers_controls = [
                "Zone", "Availability\nSchedule Name", "Lighting\nControl Type",
                "Stepped\nControl\nSteps", "Daylighting\nReference",
                "Lighting\nArea %", # Renamed from Fraction Controlled
                "Illuminance\nSetpoint\n(lux)", # Moved to end
                "Min Input\nPower\nFraction", # Moved to end
                "Min Light\nOutput\nFraction" # Moved to end
            ]

            # Wrap headers
            styled_headers_controls = [wrap_text(h, header_cell_style) for h in headers_controls]
            table_data_controls = [styled_headers_controls]

            # Helper to format numbers or return '-'
            def format_num(value, precision):
                if value is None: return '-'
                try:
                    # Format percentage for Lighting Area %
                    if headers_controls[row_values.index(value)] == "Lighting\nArea %": # Check header during formatting
                         return f"{float(value) * 100:.0f}%" # Format as percentage
                    return f"{float(value):.{precision}f}"
                except (ValueError, TypeError):
                    return str(value) # Fallback
                except IndexError: # Handle case where value might not be in row_values yet during check
                    return f"{float(value):.{precision}f}" # Fallback formatting


            # Populate data rows with wrapped text
            for entry in controls_data:
                # Temporary list to build row values before formatting percentage
                temp_row_values = [
                    entry.get("Zone", "-"),
                    entry.get("Availability Schedule Name", "-"),
                    entry.get("Lighting Control Type", "-"),
                    entry.get("Number of Stepped Control Steps", "-"),
                    entry.get("Daylighting Reference", "-"),
                    entry.get('Fraction of Zone Controlled'), # Get raw value first
                    entry.get('Illuminance Setpoint'), # Moved
                    entry.get("Minimum Input Power Fraction"), # Moved
                    entry.get("Minimum Light Output Fraction") # Moved
                ]

                # Now format with correct precision, handling percentage
                row_values = []
                precisions = [None, None, None, None, None, 0, 1, 2, 2] # Precision for each column
                for i, val in enumerate(temp_row_values):
                    header = headers_controls[i]
                    precision = precisions[i]
                    if val is None:
                        row_values.append('-')
                    elif header == "Lighting\nArea %":
                        try:
                            row_values.append(f"{float(val) * 100:.0f}%")
                        except (ValueError, TypeError):
                             row_values.append(str(val)) # Fallback
                    elif precision is not None:
                         try:
                            row_values.append(f"{float(val):.{precision}f}")
                         except (ValueError, TypeError):
                            row_values.append(str(val)) # Fallback
                    else:
                        row_values.append(str(val)) # No specific formatting


                # Wrap each cell value
                styled_row = [wrap_text(val, cell_style) for val in row_values]
                table_data_controls.append(styled_row)

            # Calculate proportional column widths (adjust for new structure)
            num_cols_controls = len(headers_controls) # Should be 9 now
            # Define approximate percentages (adjust as needed)
            col_percentages_controls = [14, 15, 10, 8, 15, 10, 10, 9, 9] # Adjusted for 9 columns

            total_percentage = sum(col_percentages_controls)
            # Ensure total percentage is close to 100 for safety
            if not (99.9 < total_percentage < 100.1):
                 print(f"Warning: Column percentages sum to {total_percentage}, adjusting to equal widths.")
                 col_percentages_controls = [100 / num_cols_controls] * num_cols_controls
                 total_percentage = 100

            col_widths_controls = [(p / total_percentage) * (doc.width - 1*cm) for p in col_percentages_controls] # Use available width

            # --- Add Spanning Logic for all columns based on Zone ---
            span_commands = []
            base_table_style_commands = table_style.getCommands() # Get base style commands

            # Iterate through data rows (skip header row index 0)
            # Apply to ALL columns (j iterates from 0 to num_cols_controls - 1)
            for j in range(num_cols_controls): # Iterate through each column
                start_row = 1 # Start checking from the first data row
                while start_row < len(table_data_controls):
                    # Ensure we don't access invalid index if table_data_controls is modified unexpectedly
                    if start_row >= len(table_data_controls) or j >= len(table_data_controls[start_row]):
                        break
                    current_val_obj = table_data_controls[start_row][j]
                    # Handle potential non-Paragraph objects if logic changes elsewhere
                    current_val = getattr(current_val_obj, 'text', str(current_val_obj))
                    current_zone_obj = table_data_controls[start_row][0] # Zone is always the first column (index 0)
                    current_zone = getattr(current_zone_obj, 'text', str(current_zone_obj))

                    count = 1
                    # Check subsequent rows
                    for i in range(start_row + 1, len(table_data_controls)):
                         # Ensure we don't access invalid index
                        if i >= len(table_data_controls) or j >= len(table_data_controls[i]) or 0 >= len(table_data_controls[i]):
                             break
                        next_val_obj = table_data_controls[i][j]
                        next_val = getattr(next_val_obj, 'text', str(next_val_obj))
                        next_zone_obj = table_data_controls[i][0]
                        next_zone = getattr(next_zone_obj, 'text', str(next_zone_obj))

                        # Span only if Zone and Value in the current column (j) match
                        if next_zone == current_zone and next_val == current_val:
                            count += 1
                            # Clear the text in the spanned cell below the first one for this column
                            # Check if it's already cleared to avoid overwriting Paragraph object with empty string
                            if getattr(table_data_controls[i][j], 'text', '') != "":
                                table_data_controls[i][j] = wrap_text("", cell_style)
                        else:
                            break # Stop counting if zone or value (in this column) changes

                    if count > 1:
                        # Add SPAN command for the current column (j)
                        # SPAN, (start_col, start_row), (end_col, end_row)
                        span_commands.append(('SPAN', (j, start_row), (j, start_row + count - 1)))
                        # Add commands to remove horizontal grid lines within the span for this column
                        for r in range(start_row, start_row + count - 1):
                             # Hide line below row r in column j
                             span_commands.append(('LINEBELOW', (j, r), (j, r), 0.5, colors.white))
                             # Also hide the line above the next row within the span to ensure clean merge
                             span_commands.append(('LINEABOVE', (j, r + 1), (j, r + 1), 0.5, colors.white))


                    start_row += count # Move to the next row after the potential span

            # Combine base style with span commands
            final_table_style = TableStyle(base_table_style_commands + span_commands)

            # Create and style the table with the final style including spans
            table_controls = Table(table_data_controls, colWidths=col_widths_controls, repeatRows=1)
            table_controls.setStyle(final_table_style)
            self._story.append(table_controls)
        else:
            self._story.append(Paragraph("No Daylighting data found.", self._styles['Normal']))

        # Removed PageBreak and Second Table (Daylighting:ReferencePoint)

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