"""
Generates energy rating reports from processed energy consumption data.
"""
from typing import Dict, List, Any, Optional, Tuple, Union
import logging
import os
import datetime
import ast # Added import

from parsers.energy_rating_parser import EnergyRatingParser

# Use platypus for automatic pagination
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, PageBreak
from reportlab.lib.pagesizes import A4, landscape, A3 # Added A3
from reportlab.lib.units import cm, inch # Added inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import navy, black, grey, lightgrey, white, darkgray # Added darkgray
from reportlab.lib.enums import TA_CENTER, TA_LEFT

logger = logging.getLogger(__name__)
# --- Explicitly set logging level for this module ---
# logger.setLevel(logging.DEBUG) # Keep or remove as needed
# ---

class EnergyRatingReportGenerator:
    """
    Generates PDF reports showing energy consumption and rating information.
    Uses data from EnergyRatingParser and reportlab for PDF generation.
    """
    def __init__(self, energy_rating_parser: EnergyRatingParser, output_dir: str = "output/reports"):
        self.energy_rating_parser = energy_rating_parser
        self.output_dir = output_dir
        self.styles = getSampleStyleSheet()
        # Original margin was 10mm, converting to cm for reportlab
        self.margin = 1 * cm

    def _format_number(self, value: Union[float, int]) -> str:
        """
        Format number for display in the report.
        """
        try:
            if isinstance(value, (int, float)):
                if value == 0:
                    return "0"
                elif abs(value) < 0.01:
                    return "{:.4f}".format(value)
                elif abs(value) < 1:
                    return "{:.3f}".format(value)
                elif abs(value) < 10:
                    return "{:.2f}".format(value)
                elif abs(value) < 1000:
                    return "{:.1f}".format(value)
                else:
                    return "{:.0f}".format(value)
            return str(value)
        except:
            return str(value)

    def _add_energy_rating_table(self) -> Optional[Table]:
        """
        Creates the energy rating table as a ReportLab Table object.
        Returns Table object or None if no data.
        """
        raw_table_data = self.energy_rating_parser.get_energy_rating_table_data()

        if not raw_table_data:
            return None

        # Sort the raw_table_data
        def sort_key(item):
            floor_val = item.get('floor', '')
            try:
                # Attempt to convert floor to int for numeric sorting
                floor_sort_val = int(floor_val)
            except ValueError:
                # Fallback to string sorting if conversion fails
                floor_sort_val = str(floor_val)
            
            area_id_val = str(item.get('area_id', ''))
            return (floor_sort_val, area_id_val)

        raw_table_data.sort(key=sort_key)

        header_definitions = [
            ["Building Details", "Energy Consumption per Meter", "Energy Consumption by Model", "Summary and Calculation by 5282", "Multiplier"],
            ["Floor", "Area ID", "Total Area", "Location", "Lighting", "Heating", "Cooling", "Total", "", "Better %", "Energy Rating", "Amount"]
        ]

        # Prepare data for ReportLab Table
        # Header Row 1 (ReportLab data format for spans)
        header_row1_data = [
            header_definitions[0][0], None, None, None,  # Building Details (spans 4)
            header_definitions[0][1], None, None, None,  # Energy Consumption per Meter (spans 4)
            header_definitions[0][2],                    # Energy Consumption by Model (spans 1)
            header_definitions[0][3], None,              # Summary and Calculation by 5282 (spans 2)
            header_definitions[0][4]                     # Multiplier (spans 1)
        ]
        # Header Row 2
        header_row2_data = header_definitions[1]

        table_content = [header_row1_data, header_row2_data]

        # Add actual data rows
        for row_dict in raw_table_data:
            table_content.append([
                str(row_dict.get('floor', '')),
                str(row_dict.get('area_id', '')),
                self._format_number(row_dict.get('total_area', 0)),
                str(row_dict.get('location', '')),
                self._format_number(row_dict.get('lighting', 0)),
                self._format_number(row_dict.get('heating', 0)),
                self._format_number(row_dict.get('cooling', 0)),
                self._format_number(row_dict.get('total', 0)),
                str(row_dict.get('energy_consumption_model', '')),
                str(row_dict.get('better_percent', '')),
                str(row_dict.get('energy_rating', '')),
                str(row_dict.get('multiplier', ''))
            ])

        # Define column widths (12 columns). Let's distribute equally for now, can be adjusted.
        # Page width A4 landscape is 29.7cm. Margins 1cm each side. Available width = 27.7cm.
        # available_width = (29.7 * cm) - (2 * self.margin) # Using A4 landscape
        # col_width_val = available_width / 12
        # col_widths = [col_width_val] * 12
        # For simplicity, let ReportLab auto-size columns or set them more specifically if needed.

        table = Table(table_content) # colWidths=col_widths

        style = TableStyle([
            # Header Row 1 Style
            ('BACKGROUND', (0,0), (-1,0), lightgrey),
            ('TEXTCOLOR', (0,0), (-1,0), black),
            ('ALIGN', (0,0), (-1,0), 'CENTER'),
            ('VALIGN', (0,0), (-1,0), 'MIDDLE'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 10),

            # Header Row 2 Style
            ('BACKGROUND', (0,1), (-1,1), lightgrey),
            ('TEXTCOLOR', (0,1), (-1,1), black),
            ('ALIGN', (0,1), (-1,1), 'CENTER'),
            ('VALIGN', (0,1), (-1,1), 'MIDDLE'),
            ('FONTNAME', (0,1), (-1,1), 'Helvetica-Bold'),
            ('FONTSIZE', (0,1), (-1,1), 8),

            # Spans for the first header row
            ('SPAN', (0,0), (3,0)),  # Building Details
            ('SPAN', (4,0), (7,0)),  # Energy Consumption per Meter
            # Col 8 (Energy Consumption by Model) is a single cell, no span
            ('SPAN', (9,0), (10,0)), # Summary and Calculation by 5282
            # Col 11 (Multiplier) is a single cell, no span

            # Data Rows Style
            ('FONTNAME', (0,2), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,2), (-1,-1), 8),
            ('ALIGN', (0,2), (-1,-1), 'CENTER'), # As per original fpdf cell alignment
            ('VALIGN', (0,2), (-1,-1), 'MIDDLE'),

            # Grid for the entire table
            ('GRID', (0,0), (-1,-1), 1, grey),
            ('BOX', (0,0), (-1,-1), 1, black),

            # Padding
            ('LEFTPADDING', (0,0), (-1,-1), 3),
            ('RIGHTPADDING', (0,0), (-1,-1), 3),
            ('TOPPADDING', (0,0), (-1,-1), 2),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ])
        table.setStyle(style)
        return table

    def generate_report(self, output_filename: str = "energy-rating.pdf") -> str:
        """
        Generate energy rating report PDF using ReportLab.
        """
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        output_path = os.path.join(self.output_dir, output_filename)

        try:
            if not self.energy_rating_parser.processed:
                logger.info("Energy rating data not processed yet, processing now...")
                self.energy_rating_parser.process_output()

            doc = SimpleDocTemplate(output_path, pagesize=landscape(A4),
                                    leftMargin=self.margin, rightMargin=self.margin,
                                    topMargin=self.margin, bottomMargin=self.margin)
            story = []

            # Add report title
            title_style = self.styles['h1']
            title_style.alignment = TA_CENTER
            title_style.textColor = navy
            story.append(Paragraph("Energy Rating Report", title_style))
            story.append(Spacer(1, 0.5*cm))

            # Add energy rating table
            energy_table = self._add_energy_rating_table()
            if energy_table:
                story.append(energy_table)
            else:
                no_data_style = self.styles['Normal']
                no_data_style.alignment = TA_CENTER
                story.append(Paragraph("No energy rating data available.", no_data_style))

            doc.build(story)
            logger.info(f"Generated energy rating report: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Error generating energy rating report: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return ""
