"""
Generates PDF reports showing materials and their thermal properties within constructions.
"""
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.lib.colors import navy, black, grey, lightgrey, white

def wrap_text(text, style):
    """Helper function to create wrapped text in a cell."""
    return Paragraph(str(text), style)

def create_cell_style(styles, is_header=False, total_row=False):
    """Create a cell style for wrapped text."""
    style = ParagraphStyle(
        'Cell',
        parent=styles['Normal'],
        fontSize=9.5,
        leading=13,
        spaceBefore=5,
        spaceAfter=5,
        fontName='Helvetica-Bold' if is_header or total_row else 'Helvetica',
        wordWrap='CJK',
        alignment=0
    )
    return style

def create_table_style(row_count):
    """Create a consistent table style for all tables in the report."""
    style = [
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9.5),
        ('FONTSIZE', (0, 1), (-1, -1), 9.5),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, grey),
        ('BACKGROUND', (0, 0), (-1, 0), lightgrey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LINEAFTER', (1, 0), (1, -1), 1.5, grey),
        ('LINEAFTER', (4, 0), (4, -1), 1.5, grey),
        ('LINEAFTER', (7, 0), (7, -1), 1.5, grey),
    ]
    
    for i in range(2, row_count, 3):
        style.append(('BACKGROUND', (0, i), (-1, i), lightgrey))
        if i + 1 < row_count:
            style.append(('TOPPADDING', (0, i+1), (-1, i+1), 20))
    
    return TableStyle(style)

def safe_sort_key(item):
    """Create a safe sort key that handles None values."""
    element_type = item.get('element_type', '')
    element_name = item.get('element_name', '')
    return (element_type or '', element_name or '')

def group_element_data(element_data):
    """Group element data by element type and name, and calculate totals."""
    try:
        sorted_data = sorted(element_data, key=safe_sort_key)
        grouped_data = []
        current_key = None
        current_group = []
        
        for item in sorted_data:
            key = (item.get('element_type', ''), item.get('element_name', ''))
            
            if key != current_key:
                if current_group:
                    total_thickness = sum(float(g.get('thickness', 0)) for g in current_group)
                    total_mass = sum(float(g.get('mass', 0)) for g in current_group)
                    total_resistance = sum(float(g.get('thermal_resistance', 0)) for g in current_group)
                    
                    grouped_data.append({
                        'element_type': current_key[0],
                        'element_name': current_key[1],
                        'layers': current_group,
                        'total_thickness': total_thickness,
                        'total_mass': total_mass,
                        'total_resistance': total_resistance
                    })
                current_key = key
                current_group = [item]
            else:
                current_group.append(item)
        
        if current_group:
            total_thickness = sum(float(g.get('thickness', 0)) for g in current_group)
            total_mass = sum(float(g.get('mass', 0)) for g in current_group)
            total_resistance = sum(float(g.get('thermal_resistance', 0)) for g in current_group)
            
            grouped_data.append({
                'element_type': current_key[0],
                'element_name': current_key[1],
                'layers': current_group,
                'total_thickness': total_thickness,
                'total_mass': total_mass,
                'total_resistance': total_resistance
            })
        
        return grouped_data
        
    except Exception as e:
        print(f"Error grouping element data: {e}")
        return []

def safe_value(value, default=""):
    """Safely convert a value to string, handling None."""
    return str(value) if value is not None else default

def generate_materials_report_pdf(element_data, output_filename="output/materials.pdf"):
    """
    Generates a PDF report containing materials thermal properties in a table format.

    Args:
        element_data (list): List of dictionaries containing element data and calculated properties.
        output_filename (str): The name of the output PDF file.
    """
    if not element_data:
        print("Warning: No element data provided for report generation")
        return False
        
    if canvas is None:
        print("Cannot generate PDF because reportlab is not installed.")
        return False

    try:
        # Group the data first
        grouped_data = group_element_data(element_data)
        if not grouped_data:
            print("Warning: No groups created from element data")
            return False

        # Use landscape for wider tables
        c = canvas.Canvas(output_filename, pagesize=landscape(A4))
        width, height = landscape(A4)
        margin_x = 2 * cm
        margin_y = 2 * cm
        content_width = width - 2 * margin_x
        current_y = height - margin_y

        # Styles
        styles = getSampleStyleSheet()
        cell_style = create_cell_style(styles)
        total_style = create_cell_style(styles, total_row=True)
        title_style = styles['h1']
        title_style.textColor = navy

        # Title
        title_text = "Building Elements Materials Properties Report"
        p_title = Paragraph(title_text, title_style)
        p_title.wrapOn(c, content_width, margin_y)
        title_height = p_title.height
        p_title.drawOn(c, margin_x, current_y - title_height)
        current_y -= (title_height + 1 * cm)

        # Create table headers
        headers = [
            "Element Type",
            "Element Name",
            "Material Name",
            "Thickness\n(m)",
            "Conductivity\n(W/m-K)",
            "Density\n(kg/m³)",
            "Mass\n(kg/m²)",
            "Thermal Resistance\n(m²K/W)",
            "Solar\nAbsorptance",
            "Specific Heat\n(J/kg-K)"
        ]

        headers_row = [wrap_text(header, create_cell_style(styles, True)) for header in headers]

        # Column widths
        col_widths = [
            content_width * 0.14,  # Element Type
            content_width * 0.14,  # Element Name
            content_width * 0.14,  # Material Name
            content_width * 0.08,  # Thickness
            content_width * 0.09,  # Conductivity
            content_width * 0.09,  # Density
            content_width * 0.08,  # Mass
            content_width * 0.09,  # Thermal Resistance
            content_width * 0.07,  # Solar Absorptance
            content_width * 0.08   # Specific Heat
        ]

        # Create all data rows
        all_rows = []
        for group in grouped_data:
            try:
                # First material row includes element type and name
                first_layer = group["layers"][0]
                first_row = [
                    wrap_text(safe_value(group["element_type"]), cell_style),
                    wrap_text(safe_value(group["element_name"]), cell_style),
                    wrap_text(safe_value(first_layer.get("material_name")), cell_style),
                    wrap_text(f"{first_layer.get('thickness', 0):.3f}", cell_style),
                    wrap_text(f"{first_layer.get('conductivity', 0):.3f}", cell_style),
                    wrap_text(f"{first_layer.get('density', 0):.1f}", cell_style),
                    wrap_text(f"{first_layer.get('mass', 0):.1f}", cell_style),
                    wrap_text(f"{first_layer.get('thermal_resistance', 0):.3f}", cell_style),
                    wrap_text(f"{first_layer.get('solar_absorptance', 0):.3f}", cell_style),
                    wrap_text(f"{first_layer.get('specific_heat', 0):.1f}", cell_style)
                ]
                all_rows.append(first_row)

                # Remaining material rows
                for layer in group["layers"][1:]:
                    all_rows.append([
                        wrap_text("", cell_style),
                        wrap_text("", cell_style),
                        wrap_text(safe_value(layer.get("material_name")), cell_style),
                        wrap_text(f"{layer.get('thickness', 0):.3f}", cell_style),
                        wrap_text(f"{layer.get('conductivity', 0):.3f}", cell_style),
                        wrap_text(f"{layer.get('density', 0):.1f}", cell_style),
                        wrap_text(f"{layer.get('mass', 0):.1f}", cell_style),
                        wrap_text(f"{layer.get('thermal_resistance', 0):.3f}", cell_style),
                        wrap_text(f"{layer.get('solar_absorptance', 0):.3f}", cell_style),
                        wrap_text(f"{layer.get('specific_heat', 0):.1f}", cell_style)
                    ])

                # Totals row
                totals_row = [
                    wrap_text("", cell_style),
                    wrap_text("", cell_style),
                    wrap_text("TOTALS", total_style),
                    wrap_text(f"{group['total_thickness']:.3f}", total_style),
                    wrap_text("", cell_style),
                    wrap_text("", cell_style),
                    wrap_text(f"{group['total_mass']:.1f}", total_style),
                    wrap_text(f"{group['total_resistance']:.3f}", total_style),
                    wrap_text("", cell_style),
                    wrap_text("", cell_style)
                ]
                all_rows.append(totals_row)

            except Exception as e:
                print(f"Error processing group: {e}")
                continue

        # Calculate rows per page
        row_height = 1.2*cm
        max_rows_per_page = int((height - 2 * margin_y - title_height - cm) / row_height) - 1

        # Split into pages
        current_row = 0
        first_page = True

        while current_row < len(all_rows):
            if not first_page:
                c.showPage()
                current_y = height - margin_y

            # Calculate rows for this page
            rows_remaining = len(all_rows) - current_row
            rows_this_page = min(max_rows_per_page, rows_remaining)
            
            # Get data rows for this page
            page_rows = all_rows[current_row:current_row + rows_this_page]
            
            # Always add headers
            table_rows = [headers_row] + page_rows

            # Create and draw table
            table = Table(
                table_rows,
                colWidths=col_widths,
                rowHeights=[row_height] * len(table_rows)
            )
            table.setStyle(create_table_style(len(table_rows)))
            
            table_width, table_height = table.wrapOn(c, content_width, current_y)
            table.drawOn(c, margin_x, current_y - table_height)
            current_y -= table_height
            
            current_row += rows_this_page
            first_page = False

        c.save()
        print(f"Successfully generated materials report: {output_filename}")
        return True

    except Exception as e:
        print(f"Error generating materials report: {e}")
        return False