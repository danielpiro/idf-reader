"""
Generates PDF reports showing zone loads and their associated schedules.
"""
# Use platypus for automatic pagination
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, PageBreak
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
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
    # Use SimpleDocTemplate for automatic page layout
    doc = SimpleDocTemplate(output_filename, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    story = []
    width, height = A4 # Used for calculating column widths relative to page
    content_width = width - 2*cm - 2*cm # Available width after margins

    # Styles
    styles = getSampleStyleSheet()
    cell_style = create_cell_style(styles)
    header_cell_style = create_cell_style(styles, is_header=True)
    title_style = styles['h1']
    title_style.textColor = navy
    section_title_style = styles['h2']
    section_title_style.spaceBefore = 0.5 * cm
    section_title_style.spaceAfter = 0.3 * cm
    zone_name_style = ParagraphStyle(
        name='ZoneName', parent=styles['Normal'], fontName='Helvetica-Bold',
        fontSize=10, # Slightly larger for zone names
        spaceBefore = 0.4*cm, spaceAfter=0.1*cm
    )

    # --- Title ---
    title_text = "IDF Zone Loads Report"
    story.append(Paragraph(title_text, title_style))
    story.append(Spacer(1, 1*cm)) # Add space after title

    if not zone_data:
        story.append(Paragraph("No zones found or processed.", styles['Normal']))
        try:
            doc.build(story)
            print(f"Generated empty loads report: {output_filename}")
            return True
        except Exception as e:
            print(f"Error generating empty loads PDF file {output_filename}: {e}")
            return False

    # Create consistent cell style for data cells
    cell_style = create_cell_style(styles)

    try:
        for zone_name, zone_info in zone_data.items():
            # Zone Title
            zone_title = f"Zone: {zone_name}"
            story.append(Paragraph(zone_title, zone_name_style))
            story.append(Spacer(1, 0.2*cm)) # Space after zone title

            # Zone Properties Table
            properties = zone_info['properties']
            prop_data = [
                [wrap_text("Property", header_cell_style),
                 wrap_text("Value", header_cell_style),
                 wrap_text("Units", header_cell_style)],
                [wrap_text("Floor Area", cell_style), wrap_text(f"{properties['area']:.2f}", cell_style), wrap_text("m²", cell_style)],
                [wrap_text("Volume", cell_style), wrap_text(f"{properties['volume']:.2f}", cell_style), wrap_text("m³", cell_style)],
                [wrap_text("Zone Multiplier", cell_style), wrap_text(str(properties['multiplier']), cell_style), wrap_text("-", cell_style)]
            ]
            prop_table = Table(
                prop_data,
                colWidths=[content_width*0.4, content_width*0.4, content_width*0.2],
                # rowHeights removed - let platypus calculate height based on content
                hAlign='LEFT' # Align table to the left
            )
            prop_table.setStyle(create_table_style())
            story.append(prop_table)
            story.append(Spacer(1, 0.5*cm)) # Space after properties table

            # People Loads Section
            story.append(Paragraph("Occupancy Loads", section_title_style))
            if zone_info['loads']['people']:
                people_data = [
                    [wrap_text("Description", header_cell_style),
                     wrap_text("Density", header_cell_style),
                     wrap_text("Activity Schedule", header_cell_style),
                     wrap_text("Occupancy Schedule", header_cell_style)]
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

                people_table = Table(
                    people_data,
                    colWidths=[content_width*0.3, content_width*0.2, content_width*0.3, content_width*0.2],
                    hAlign='LEFT'
                )
                people_table.setStyle(create_table_style())
                story.append(people_table)
                story.append(Spacer(1, 0.5*cm)) # Space after people table
            else:
                 story.append(Paragraph("No occupancy loads defined for this zone.", styles['Normal']))
                 story.append(Spacer(1, 0.5*cm))

            # Lighting Loads Section
            story.append(Paragraph("Lighting Loads", section_title_style))
            if zone_info['loads']['lights']:
                lights_data = [
                    [wrap_text("Description", header_cell_style),
                     wrap_text("Load Density", header_cell_style),
                     wrap_text("Schedule", header_cell_style),
                     wrap_text("Category", header_cell_style)]
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

                lights_table = Table(
                    lights_data,
                    colWidths=[content_width*0.3, content_width*0.2, content_width*0.3, content_width*0.2],
                    hAlign='LEFT'
                )
                lights_table.setStyle(create_table_style())
                story.append(lights_table)
                story.append(Spacer(1, 0.5*cm)) # Space after lights table
            else:
                 story.append(Paragraph("No lighting loads defined for this zone.", styles['Normal']))
                 story.append(Spacer(1, 0.5*cm))

            # Equipment Loads Section
            story.append(Paragraph("Equipment Loads", section_title_style))
            if zone_info['loads']['equipment']:
                equip_data = [
                    [wrap_text("Description", header_cell_style),
                     wrap_text("Load Density", header_cell_style),
                     wrap_text("Schedule", header_cell_style),
                     wrap_text("Type", header_cell_style)]
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

                equip_table = Table(
                    equip_data,
                    colWidths=[content_width*0.3, content_width*0.2, content_width*0.3, content_width*0.2],
                    hAlign='LEFT'
                )
                equip_table.setStyle(create_table_style())
                story.append(equip_table)
                story.append(Spacer(1, 0.5*cm)) # Space after equipment table
            else:
                 story.append(Paragraph("No equipment loads defined for this zone.", styles['Normal']))
                 story.append(Spacer(1, 0.5*cm))

            # Temperature Schedules Section (Renamed for clarity)
            story.append(Paragraph("Temperature Schedules", section_title_style))
            schedules = zone_info['schedules']
            active_schedules = {k: v for k, v in schedules.items() if v} # Filter out empty schedules

            if active_schedules:
                sched_data = [
                    [wrap_text("Schedule Type", header_cell_style),
                     wrap_text("Schedule Name", header_cell_style)]
                ]
                for sched_type, sched_name in active_schedules.items():
                     sched_data.append([
                         wrap_text(sched_type.replace('_', ' ').title(), cell_style), # Nicer formatting
                         wrap_text(sched_name, cell_style)
                     ])

                sched_table = Table(
                    sched_data,
                    colWidths=[content_width*0.4, content_width*0.6],
                    hAlign='LEFT'
                )
                sched_table.setStyle(create_table_style())
                story.append(sched_table)
                story.append(Spacer(1, 0.5*cm)) # Space after schedules table
            else:
                 story.append(Paragraph("No temperature schedules defined for this zone.", styles['Normal']))
                 story.append(Spacer(1, 0.5*cm))

            # Add a page break between zones if desired (optional)
            # story.append(PageBreak())

        # Build the PDF document from the story
        doc.build(story)
        print(f"Successfully generated loads report: {output_filename}")
        return True

    except Exception as e:
        print(f"Error generating or saving loads PDF file {output_filename}: {e}")
        # Consider re-raising or logging the exception for better debugging
        # import traceback
        # traceback.print_exc()
        return False