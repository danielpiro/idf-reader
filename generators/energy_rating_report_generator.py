"""
Generates energy rating reports from processed energy consumption data.
"""
import logging
import os
import ast

from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from reportlab.lib.pagesizes import A4, landscape, A3
from reportlab.lib.units import cm, inch
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.colors import navy, black, grey, lightgrey, white, darkgray
from reportlab.lib.enums import TA_CENTER

logger = logging.getLogger(__name__)

def _get_table_style():
    return TableStyle([
        ('BACKGROUND', (0,0), (-1,0), lightgrey),
        ('TEXTCOLOR', (0,0), (-1,0), black),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('VALIGN', (0,0), (-1,0), 'MIDDLE'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 10),
        ('BACKGROUND', (0,1), (-1,1), lightgrey),
        ('TEXTCOLOR', (0,1), (-1,1), black),
        ('ALIGN', (0,1), (-1,1), 'CENTER'),
        ('VALIGN', (0,1), (-1,1), 'MIDDLE'),
        ('FONTNAME', (0,1), (-1,1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,1), (-1,1), 8),
        ('SPAN', (0,0), (4,0)),  # Building Details
        ('SPAN', (5,0), (8,0)),  # Energy Consumption per Meter
        ('SPAN', (9,0), (12,0)), # Summary and Calculation by 5282
        ('FONTNAME', (0,2), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,2), (-1,-1), 8),
        ('ALIGN', (0,2), (-1,-1), 'CENTER'),
        ('VALIGN', (0,2), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 1, grey),
        ('BOX', (0,0), (-1,-1), 1, black),
        ('LEFTPADDING', (0,0), (-1,-1), 3),
        ('RIGHTPADDING', (0,0), (-1,-1), 3),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
    ])

def _format_number(value):
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
    except Exception:
        return str(value)

def _energy_rating_table(energy_rating_parser):
    """
    Creates the energy rating table as a ReportLab Table object.
    Returns Table object or None if no data.
    """
    raw_table_data = energy_rating_parser.get_energy_rating_table_data()

    if not raw_table_data:
        return None

    def sort_key(item):
        floor_val = item.get('floor', '')
        try:
            floor_sort_val = int(floor_val) # Attempt to sort numerically if possible
        except ValueError:
            floor_sort_val = str(floor_val) # Fallback to string sort

        area_id_val = str(item.get('area_id', ''))
        zone_id_val = str(item.get('zone_id', '')) # Add zone_id for sorting
        return (floor_sort_val, area_id_val, zone_id_val)

    raw_table_data.sort(key=sort_key)

    header_row1 = [
        "Building Details", None, None, None, None,
        "Energy Consumption per Meter", None, None, None,
        "Summary and Calculation by 5282", None, None, None
    ]
    header_row2 = [
        "Floor", "Area id", "Zone id", "Zone area", "Zone multiplier",
        "Lighting", "Cooling", "Heating", "Sum",
        "Energy consumption", "Improve by %", "Energy rating", "Area rating"
    ]
    table_content = [header_row1, header_row2]

    for row_dict in raw_table_data:
        table_content.append([
            str(row_dict.get('floor_id_report', '')),       # "Floor"
            str(row_dict.get('area_id_report', '')),      # "Area id"
            str(row_dict.get('zone_name_report', '')),    # "Zone id" (maps to zone name part)
            _format_number(row_dict.get('total_area', 0)),  # "Zone area"
            str(row_dict.get('multiplier', '')),          # "Zone multiplier"
            _format_number(row_dict.get('lighting', 0)),
            _format_number(row_dict.get('cooling', 0)),
            _format_number(row_dict.get('heating', 0)),
            _format_number(row_dict.get('total', 0)),
            '',  # Placeholder for "Energy consumption"
            '',  # Placeholder for "Improve by %"
            '',  # Placeholder for "Energy rating"
            ''   # Placeholder for "Area rating"
        ])

    table = Table(table_content)
    table.setStyle(_get_table_style())
    return table

class EnergyRatingReportGenerator:
    """Generates PDF reports showing energy consumption and rating information."""
    def __init__(self, energy_rating_parser, output_dir="output/reports"):
        self.energy_rating_parser = energy_rating_parser
        self.output_dir = output_dir
        self.styles = getSampleStyleSheet()
        self.margin = 1 * cm

    def generate_report(self, output_filename="energy-rating.pdf"):
        """
        Generate energy rating report PDF using ReportLab.
        """
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        output_path = os.path.join(self.output_dir, output_filename)

        try:
            if not self.energy_rating_parser.processed:
                self.energy_rating_parser.process_output()

            doc = SimpleDocTemplate(output_path, pagesize=landscape(A4),
                                    leftMargin=self.margin, rightMargin=self.margin,
                                    topMargin=self.margin, bottomMargin=self.margin)
            story = []

            title_style = self.styles['h1']
            title_style.alignment = TA_CENTER
            title_style.textColor = navy
            story.append(Paragraph("Energy Rating Report", title_style))
            story.append(Spacer(1, 0.5*cm))

            energy_table = _energy_rating_table(self.energy_rating_parser)
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
            raise RuntimeError(f"Error generating energy rating report: {e}")
