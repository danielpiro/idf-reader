import os
try:
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.units import cm
    from reportlab.lib.pagesizes import landscape, A4
    from reportlab.lib import colors
except ImportError:
    print("Error: reportlab library not found.")
    print("Please install it using: pip install reportlab")
    SimpleDocTemplate = None # Flag missing library

def generate_loads_report_pdf(zone_ids, zone_data, output_filename="loads_report.pdf"):
    """
    Generates a PDF report summarizing zone load data in a table format.

    Args:
        zone_ids (list or set): A collection of unique zone IDs to include in the report.
        zone_data (dict): The dictionary returned by ZoneLoadDataExtractor.get_zone_load_data().
                          {zone_id: {param_key: value}}
        output_filename (str): The name of the output PDF file.
    """
    if SimpleDocTemplate is None:
        print("Cannot generate PDF because reportlab is not installed.")
        return False

    doc = SimpleDocTemplate(output_filename, pagesize=landscape(A4))
    styles = getSampleStyleSheet()
    story = []

    title = Paragraph("Zone Load Data Summary", styles['h1'])
    story.append(title)
    story.append(Spacer(1, 0.5*cm))

    # --- Define Table Structure ---
    # Header rows (complex with merged cells)
    header1 = [
        '', 'occupancy', '', '', 'lighting', '', 'non fixed equipment', '',
        'fixed equipment', '', 'heating', '', '', 'cooling', '', '',
        'infiltration', '', 'ventilation', ''
    ]
    header2 = [
        'zone', 'people/area', 'activity schedule w/person', 'schedule template name',
        'power density [w/m2]', 'schedule template name', 'power density(W/m2)', 'schedule template name',
        'power density(W/m2)', 'schedule template name', 'setpoint(C)', 'setpoint non work time(C)', 'equipment schedule template name',
        'setpoint(C)', 'setpoint non work time(C)', 'equipment schedule template name',
        'rate (ACH)', 'schedule', 'rate (ACH)', 'schedule'
    ]

    # Data rows
    table_data = [header1, header2]
    for zone_id in sorted(list(zone_ids)):
        data = zone_data.get(zone_id, {}) # Get data for this zone, or empty dict if missing

        # Helper to format None or numeric values
        def fmt(key, precision=2):
            val = data.get(key)
            if val is None:
                return '-'
            if isinstance(val, (int, float)):
                return f"{val:.{precision}f}"
            return str(val) # Return string representation otherwise

        row = [
            zone_id,
            fmt('occupancy_people_per_area', 2),
            fmt('occupancy_activity_schedule'), # Assuming this holds the W/person value? Needs clarification. Using schedule name for now.
            fmt('occupancy_schedule'), # Assuming this is the template name?
            fmt('lighting_watts_per_area', 1),
            fmt('lighting_schedule'),
            fmt('non_fixed_equip_watts_per_area', 1),
            fmt('non_fixed_equip_schedule'),
            fmt('fixed_equip_watts_per_area', 1),
            fmt('fixed_equip_schedule'),
            '-', # Heating Setpoint (Numeric value not extracted)
            '-', # Heating Setpoint Non Work (Numeric value not extracted)
            fmt('heating_setpoint_schedule'), # Schedule Name
            '-', # Cooling Setpoint (Numeric value not extracted)
            '-', # Cooling Setpoint Non Work (Numeric value not extracted)
            fmt('cooling_setpoint_schedule'), # Schedule Name
            fmt('infiltration_ach', 2),
            fmt('infiltration_schedule'),
            fmt('ventilation_ach', 2),
            fmt('ventilation_schedule')
        ]
        table_data.append(row)

    # --- Define Table Style ---
    # Calculate column widths (approximate for now)
    num_cols = len(header2)
    col_width = doc.width / num_cols * 0.95 # Adjust factor as needed
    col_widths = [col_width] * num_cols
    # Adjust first column width
    col_widths[0] = 2.5 * cm

    style = TableStyle([
        # Merged cells for header 1
        ('SPAN', (1, 0), (3, 0)),  # Occupancy
        ('SPAN', (4, 0), (5, 0)),  # Lighting
        ('SPAN', (6, 0), (7, 0)),  # Non Fixed Equip
        ('SPAN', (8, 0), (9, 0)),  # Fixed Equip
        ('SPAN', (10, 0), (12, 0)), # Heating
        ('SPAN', (13, 0), (15, 0)), # Cooling
        ('SPAN', (16, 0), (17, 0)), # Infiltration
        ('SPAN', (18, 0), (19, 0)), # Ventilation

        # Header styles
        ('BACKGROUND', (0, 0), (-1, 1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 1), colors.black),
        ('ALIGN', (0, 0), (-1, 1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, 1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, 1), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 1), 6),
        ('TOPPADDING', (0, 0), (-1, 1), 6),

        # Data styles
        ('BACKGROUND', (0, 2), (-1, -1), colors.whitesmoke),
        ('TEXTCOLOR', (0, 2), (-1, -1), colors.black),
        ('ALIGN', (0, 2), (0, -1), 'LEFT'), # Align first column left
        ('ALIGN', (1, 2), (-1, -1), 'CENTER'), # Align rest center
        ('VALIGN', (0, 2), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 2), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 8), # Smaller font size
        ('BOTTOMPADDING', (0, 2), (-1, -1), 4),
        ('TOPPADDING', (0, 2), (-1, -1), 4),

        # Grid lines
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
    ])

    # Create and style the table
    table = Table(table_data, colWidths=col_widths)
    table.setStyle(style)

    story.append(table)

    # --- Build PDF ---
    try:
        doc.build(story)
        print(f"Successfully generated loads report: {output_filename}")
        return True
    except Exception as e:
        print(f"Error building loads report PDF {output_filename}: {e}")
        return False

# Example usage placeholder
if __name__ == '__main__':
    print("loads_report_generator.py executed directly (intended for import).")
    # Example Data (replace with actual data from parser)
    # test_zone_ids = ['ZoneA', 'ZoneB']
    # test_zone_data = {
    #     'ZoneA': {'occupancy_people_per_area': 0.05, 'lighting_schedule': 'LightSched', 'infiltration_ach': 0.5},
    #     'ZoneB': {'occupancy_people_per_area': 0.10, 'lighting_watts_per_area': 8.0, 'ventilation_schedule': 'VentSched'}
    # }
    # generate_loads_report_pdf(test_zone_ids, test_zone_data, "example_loads_report.pdf")