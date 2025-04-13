"""
Generates PDF reports showing zone loads and their associated schedules.
"""
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph, Table, TableStyle, Spacer
from reportlab.lib.colors import navy, black, grey, lightgrey, white
def wrap_text(text, style):
    """Helper function to create wrapped text in a cell."""
    return Paragraph(str(text), style)

def create_cell_style(styles, is_header=False):
    """Create a cell style for wrapped text."""
    style = ParagraphStyle(
        'Cell',
        parent=styles['Normal'],
        fontSize=8,
        leading=9,
        spaceBefore=1,
        spaceAfter=1,
        fontName='Helvetica-Bold' if is_header else 'Helvetica',
        wordWrap='CJK',
        alignment=0
    )
    return style

def create_table_style():
    """Create a consistent table style for all tables in the report."""
    return TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('BACKGROUND', (0, 1), (-1, -1), white),
        ('GRID', (0, 0), (-1, -1), 1, grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4)
    ])

def generate_loads_report_pdf(zone_data, output_filename="output/loads.pdf"):
    """
    Generates a PDF report containing zone loads in a table format.

    Args:
        zone_data (dict): Dictionary of zone loads and schedules.
        output_filename (str): The name of the output PDF file.
    """
    if canvas is None:
        print("Cannot generate PDF because reportlab is not installed.")
        return False

    c = canvas.Canvas(output_filename, pagesize=A4)
    width, height = A4
    margin_x = 2 * cm
    margin_y = 2 * cm
    content_width = width - 2 * margin_x
    current_y = height - margin_y

    # Styles
    styles = getSampleStyleSheet()
    cell_style = create_cell_style(styles)
    title_style = styles['h1']
    title_style.textColor = navy
    section_title_style = styles['h2']
    section_title_style.spaceBefore = 0.5 * cm
    section_title_style.spaceAfter = 0.3 * cm
    zone_name_style = ParagraphStyle(
        name='ZoneName', parent=styles['Normal'], fontName='Helvetica-Bold',
        spaceBefore = 0.4*cm, spaceAfter=0.1*cm
    )

    # --- Title ---
    title_text = "IDF Zone Loads Report"
    p_title = Paragraph(title_text, title_style)
    p_title.wrapOn(c, content_width, margin_y)
    title_height = p_title.height
    p_title.drawOn(c, margin_x, current_y - title_height)
    current_y -= (title_height + 1 * cm)

    if not zone_data:
        p_empty = Paragraph("No zones found or processed.", styles['Normal'])
        p_empty.wrapOn(c, content_width, margin_y)
        p_empty.drawOn(c, margin_x, current_y - p_empty.height)
        c.save()
        print(f"Generated empty loads report: {output_filename}")
        return True

    # Create consistent cell style for data cells
    cell_style = create_cell_style(styles)

    try:
        for zone_name, zone_info in zone_data.items():
            # Check for page break
            if current_y < margin_y + 5*cm:
                c.showPage()
                current_y = height - margin_y

            # Zone Title
            zone_title = f"Zone: {zone_name}"
            p_zone = Paragraph(zone_title, zone_name_style)
            p_zone.wrapOn(c, content_width, margin_y)
            p_zone.drawOn(c, margin_x, current_y - p_zone.height)
            current_y -= (p_zone.height + 0.5*cm)

            # Zone Properties Table with word wrapping
            properties = zone_info['properties']
            prop_data = [
                [wrap_text("Property", create_cell_style(styles, True)),
                 wrap_text("Value", create_cell_style(styles, True)),
                 wrap_text("Units", create_cell_style(styles, True))],
                [wrap_text("Floor Area", cell_style), wrap_text(f"{properties['area']:.2f}", cell_style), wrap_text("m²", cell_style)],
                [wrap_text("Volume", cell_style), wrap_text(f"{properties['volume']:.2f}", cell_style), wrap_text("m³", cell_style)],
                [wrap_text("Zone Multiplier", cell_style), wrap_text(str(properties['multiplier']), cell_style), wrap_text("-", cell_style)]
            ]

            # Use consistent row height for all tables
            row_height = 0.6*cm
            prop_table = Table(
                prop_data,
                colWidths=[content_width*0.4, content_width*0.4, content_width*0.2],
                rowHeights=[row_height] * len(prop_data)
            )
            prop_table.setStyle(create_table_style())
            prop_width, prop_height = prop_table.wrapOn(c, content_width, margin_y)
            prop_table.drawOn(c, margin_x, current_y - prop_height)
            current_y -= (prop_height + 0.5*cm)

            # People Loads Section
            section_title = Paragraph("Occupancy Loads", section_title_style)
            section_title.wrapOn(c, content_width, margin_y)
            section_title.drawOn(c, margin_x, current_y - section_title.height)
            current_y -= (section_title.height + 0.3*cm)
            if zone_info['loads']['people']:
                people_data = [
                    [wrap_text("Description", create_cell_style(styles, True)),
                     wrap_text("Density", create_cell_style(styles, True)),
                     wrap_text("Activity Schedule", create_cell_style(styles, True)),
                     wrap_text("Occupancy Schedule", create_cell_style(styles, True))]
                ]
                for load in zone_info['loads']['people']:
                    name = load['name'].replace(zone_name + " ", "")
                    density = f"{load['value']:.3f} {load['calculation_method']}"
                    people_data.append([
                        wrap_text(name, cell_style),
                        wrap_text(density, cell_style),
                        wrap_text(load['activity_schedule'], cell_style),
                        wrap_text(load['schedule'], cell_style)
                    ])
                
                # Create table with fixed row heights
                row_height = 0.6*cm  # Consistent height for all tables
                people_table = Table(
                    people_data,
                    colWidths=[content_width*0.3, content_width*0.2, content_width*0.3, content_width*0.2],
                    rowHeights=[row_height] * len(people_data)
                )
                people_table.setStyle(create_table_style())
                people_width, people_height = people_table.wrapOn(c, content_width, margin_y)
                people_table.drawOn(c, margin_x, current_y - people_height)
                current_y -= (people_height + 0.5*cm)

            # Lighting Loads Section
            section_title = Paragraph("Lighting Loads", section_title_style)
            section_title.wrapOn(c, content_width, margin_y)
            section_title.drawOn(c, margin_x, current_y - section_title.height)
            current_y -= (section_title.height + 0.3*cm)
            if zone_info['loads']['lights']:
                lights_data = [
                    [wrap_text("Description", create_cell_style(styles, True)),
                     wrap_text("Load Density", create_cell_style(styles, True)),
                     wrap_text("Schedule", create_cell_style(styles, True)),
                     wrap_text("Category", create_cell_style(styles, True))]
                ]
                for load in zone_info['loads']['lights']:
                    name = load['name'].replace(zone_name + " ", "")
                    density = f"{load['watts_per_area']:.1f} W/m²"
                    lights_data.append([
                        wrap_text(name, cell_style),
                        wrap_text(density, cell_style),
                        wrap_text(load['schedule'], cell_style),
                        wrap_text("General Lighting", cell_style)
                    ])

                # Create table with fixed row heights and adjusted widths
                row_height = 0.7*cm
                lights_table = Table(
                    lights_data,
                    colWidths=[content_width*0.3, content_width*0.2, content_width*0.3, content_width*0.2],
                    rowHeights=[row_height] * len(lights_data)
                )
                lights_table.setStyle(create_table_style())
                lights_width, lights_height = lights_table.wrapOn(c, content_width, margin_y)
                lights_table.drawOn(c, margin_x, current_y - lights_height)
                current_y -= (lights_height + 0.3*cm)

            # Equipment Loads Section
            section_title = Paragraph("Equipment Loads", section_title_style)
            section_title.wrapOn(c, content_width, margin_y)
            section_title.drawOn(c, margin_x, current_y - section_title.height)
            current_y -= (section_title.height + 0.3*cm)
            if zone_info['loads']['equipment']:
                equip_data = [
                    [wrap_text("Description", create_cell_style(styles, True)),
                     wrap_text("Load Density", create_cell_style(styles, True)),
                     wrap_text("Schedule", create_cell_style(styles, True)),
                     wrap_text("Type", create_cell_style(styles, True))]
                ]
                for load in zone_info['loads']['equipment']:
                    name = load['name'].replace(zone_name + " ", "")
                    density = f"{load['watts_per_area']:.1f} W/m²"
                    equip_type = "Miscellaneous" if load.get('type') == 'misc' else "Fixed Equipment"
                    equip_data.append([
                        wrap_text(name, cell_style),
                        wrap_text(density, cell_style),
                        wrap_text(load['schedule'], cell_style),
                        wrap_text(equip_type, cell_style)
                    ])

                # Create table with fixed row heights and adjusted widths
                row_height = 0.7*cm
                equip_table = Table(
                    equip_data,
                    colWidths=[content_width*0.3, content_width*0.2, content_width*0.3, content_width*0.2],
                    rowHeights=[row_height] * len(equip_data)
                )
                equip_table.setStyle(create_table_style())
                equip_width, equip_height = equip_table.wrapOn(c, content_width, margin_y)
                equip_table.drawOn(c, margin_x, current_y - equip_height)
                current_y -= (equip_height + 0.3*cm)

            # Schedule Summary Section
            section_title = Paragraph("Schedule Summary", section_title_style)
            section_title.wrapOn(c, content_width, margin_y)
            section_title.drawOn(c, margin_x, current_y - section_title.height)
            current_y -= (section_title.height + 0.3*cm)
            schedules = zone_info['schedules']
            if any(schedules.values()):
                sched_data = [
                    [wrap_text("Schedule Type", create_cell_style(styles, True)),
                     wrap_text("Schedule Name", create_cell_style(styles, True))]
                ]
                
                for sched_type, sched_name in schedules.items():
                    if sched_name:
                        sched_data.append([
                            wrap_text(sched_type.capitalize(), cell_style),
                            wrap_text(sched_name, cell_style)
                        ])
                
                # Create table with fixed row heights
                row_height = 0.6*cm  # Consistent height for all tables
                sched_table = Table(
                    sched_data,
                    colWidths=[content_width*0.4, content_width*0.6],
                    rowHeights=[row_height] * len(sched_data)
                )
                sched_table.setStyle(create_table_style())
                sched_width, sched_height = sched_table.wrapOn(c, content_width, margin_y)
                sched_table.drawOn(c, margin_x, current_y - sched_height)
                current_y -= (sched_height + 0.5*cm)

        c.save()
        print(f"Successfully generated loads report: {output_filename}")
        return True

    except Exception as e:
        print(f"Error generating or saving loads PDF file {output_filename}: {e}")
        return False