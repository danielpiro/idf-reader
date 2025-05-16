"""
Generates PDF reports showing materials and their thermal properties within constructions.
"""
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape, A3
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph, Table, TableStyle, SimpleDocTemplate, Spacer
from reportlab.lib.colors import navy, black, grey, lightgrey
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import datetime

def wrap_text(text, style):
    """Create wrapped text in a cell."""
    return Paragraph(str(text), style)

def create_cell_style(styles, is_header=False, total_row=False):
    """Create a cell style for wrapped text."""
    return ParagraphStyle(
        'Cell',
        parent=styles['Normal'],
        fontSize=8,
        leading=10,
        spaceBefore=2,
        spaceAfter=2,
        fontName='Helvetica-Bold' if is_header or total_row else 'Helvetica',
        wordWrap='CJK',
        alignment=TA_LEFT
    )

def create_table_style():
    """Create a consistent table style for materials table."""
    return TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), black),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ])

def _get_element_type_sort_keys(element_type_str):
    """Assigns primary and secondary sort keys based on element type string."""
    element_type_lower = (element_type_str or "").lower()
    primary_key = 99  # Default for unspecified types
    secondary_key = 99 # Default for unspecified sub-types

    if 'floor' in element_type_lower:
        primary_key = 0
    elif 'ceiling' in element_type_lower or 'roof' in element_type_lower:
        primary_key = 1
    elif 'wall' in element_type_lower:
        primary_key = 2
        if 'internal' in element_type_lower:
            secondary_key = 0
        elif 'separation' in element_type_lower:
            secondary_key = 1
        elif 'external' in element_type_lower:
            secondary_key = 2
        else:
            secondary_key = 3 # Other wall types
    elif 'glazing' in element_type_lower:
        primary_key = 3
    
    # Handle cases where element_type might be a list/tuple (though less common in materials)
    # For simplicity, this example assumes element_type_str is a simple string.
    # If it can be a list, the logic would need to iterate or pick the most relevant.

    return primary_key, secondary_key

def custom_material_sort_key(item):
    """Create a custom sort key for materials based on element type and name."""
    element_type = item.get('element_type', '') or ''
    element_name = item.get('element_name', '') or ''
    
    primary_sort, secondary_sort = _get_element_type_sort_keys(element_type)
    
    return (primary_sort, secondary_sort, element_name)

def _calc_group_totals(group):
    """Calculate totals and derived values for a group of layers."""
    total_thickness = sum(float(g.get('thickness', 0)) for g in group)
    total_mass = sum(float(g.get('mass', 0)) for g in group)
    total_resistance = sum(float(g.get('thermal_resistance', 0)) for g in group)
    film_resistance = float(group[0].get('surface_film_resistance', 0)) if group else 0
    r_value = total_resistance
    r_value_with_film = r_value + film_resistance
    u_value = 1.0 / r_value_with_film if r_value_with_film > 0 else 0.0
    return total_thickness, total_mass, total_resistance, film_resistance, r_value, r_value_with_film, u_value

def group_element_data(element_data):
    """Group element data by element type and name, and calculate totals."""
    try:
        sorted_data = sorted(element_data, key=custom_material_sort_key)
        grouped_data = []
        current_key = None
        current_group = []
        for item in sorted_data:
            key = (item.get('element_type', ''), item.get('element_name', ''))
            if key != current_key:
                if current_group:
                    total_thickness, total_mass, total_resistance, film_resistance, r_value, r_value_with_film, u_value = _calc_group_totals(current_group)
                    grouped_data.append({
                        'element_type': current_key[0],
                        'element_name': current_key[1],
                        'layers': current_group,
                        'total_thickness': total_thickness,
                        'total_mass': total_mass,
                        'total_resistance': total_resistance,
                        'film_resistance': film_resistance,
                        'r_value': r_value,
                        'r_value_with_film': r_value_with_film,
                        'u_value': u_value
                    })
                current_key = key
                current_group = [item]
            else:
                current_group.append(item)
        if current_group:
            total_thickness, total_mass, total_resistance, film_resistance, r_value, r_value_with_film, u_value = _calc_group_totals(current_group)
            grouped_data.append({
                'element_type': current_key[0],
                'element_name': current_key[1],
                'layers': current_group,
                'total_thickness': total_thickness,
                'total_mass': total_mass,
                'total_resistance': total_resistance,
                'film_resistance': film_resistance,
                'r_value': r_value,
                'r_value_with_film': r_value_with_film,
                'u_value': u_value
            })
        return grouped_data
    except Exception as e:
        raise RuntimeError(f"Error grouping element data: {e}")

def safe_value(value, default=""):
    """Safely convert a value to string, handling None."""
    return str(value) if value is not None else default

def _build_table_data(grouped_data, cell_style, header_cell_style, total_style):
    """Build table data and track total rows for styling."""
    headers = [
        "Element Type", "Element Name", "Material Name", "Thickness\n(m)", "Conductivity\n(W/m-K)",
        "Density\n(kg/m³)", "Mass\n(kg/m²)", "Thermal\nResistance\n(m²K/W)", "Solar\nAbsorptance",
        "Specific\nHeat (J/kg-K)", "R-Value\n(m²K/W)", "U-Value\n(W/m²K)"
    ]
    table_data = [[wrap_text(h, header_cell_style) for h in headers]]
    total_rows = []
    row_index = 1
    for group in grouped_data:
        element_type = group["element_type"]
        element_name = group["element_name"]
        for i, layer in enumerate(group["layers"]):
            row = [
                wrap_text(element_type if i == 0 else "", cell_style),
                wrap_text(element_name if i == 0 else "", cell_style),
                wrap_text(safe_value(layer.get("material_name")), cell_style),
                wrap_text(f"{float(layer.get('thickness', 0)):.3f}", cell_style),
                wrap_text(f"{float(layer.get('conductivity', 0)):.3f}", cell_style),
                wrap_text(f"{float(layer.get('density', 0)):.1f}", cell_style),
                wrap_text(f"{float(layer.get('mass', 0)):.1f}", cell_style),
                wrap_text(f"{float(layer.get('thermal_resistance', 0)):.3f}", cell_style),
                wrap_text(f"{float(layer.get('solar_absorptance', 0)):.3f}", cell_style),
                wrap_text(f"{float(layer.get('specific_heat', 0)):.1f}", cell_style),
                wrap_text("", cell_style),
                wrap_text("", cell_style)
            ]
            table_data.append(row)
            row_index += 1
        totals_row = [
            wrap_text("", cell_style),
            wrap_text("", cell_style),
            wrap_text("TOTALS", total_style),
            wrap_text(f"{group['total_thickness']:.3f} m", total_style),
            wrap_text("", cell_style),
            wrap_text("", cell_style),
            wrap_text(f"{group['total_mass']:.1f} kg/m²", total_style),
            wrap_text(f"{group['total_resistance']:.3f} m²K/W", total_style),
            wrap_text("", cell_style),
            wrap_text("", cell_style),
            wrap_text(f"{group['r_value_with_film']:.3f} m²K/W", total_style),
            wrap_text(f"{group['u_value']:.3f} W/m²K", total_style)
        ]
        table_data.append(totals_row)
        total_rows.append(row_index)
        row_index += 1
    return table_data, total_rows

def generate_materials_report_pdf(element_data, output_filename="output/materials.pdf", project_name="N/A", run_id="N/A"):
    """
    Generates a PDF report containing materials thermal properties, including a header.
    Args:
        element_data (list): List of dictionaries containing element data.
        output_filename (str): The name of the output PDF file.
        project_name (str): Name of the project.
        run_id (str): Identifier for the current run.
    Returns:
        bool: True if report generated successfully, False otherwise.
    """
    if not element_data:
        return False
    try:
        grouped_data = group_element_data(element_data)
        if not grouped_data:
            return False
        page_size = landscape(A3)
        left_margin = right_margin = top_margin = bottom_margin = 1.0 * cm
        doc = SimpleDocTemplate(output_filename, pagesize=page_size, leftMargin=left_margin, rightMargin=right_margin, topMargin=top_margin, bottomMargin=bottom_margin)
        width, _ = page_size
        content_width = width - left_margin - right_margin
        styles = getSampleStyleSheet()
        title_style = styles['Heading1']
        title_style.alignment = TA_CENTER
        title_style.textColor = navy
        title_style.spaceAfter = 0.5 * cm
        cell_style = create_cell_style(styles)
        header_cell_style = create_cell_style(styles, is_header=True)
        total_style = create_cell_style(styles, total_row=True)
        header_info_style = ParagraphStyle(
            'HeaderInfo',
            parent=styles['Normal'],
            fontSize=9,
            textColor=black,
            alignment=2
        )
        now = datetime.datetime.now()
        header_text = f"""
        Project: {project_name}<br/>
        Run ID: {run_id}<br/>
        Date: {now.strftime('%Y-%m-%d %H:%M:%S')}<br/>
        Report: Building Elements Materials Properties
        """
        story = [
            Paragraph(header_text, header_info_style),
            Spacer(1, 5),
            Paragraph("Building Elements Materials Properties Report", title_style),
            Spacer(1, 0.5 * cm)
        ]
        col_widths = [
            content_width * 0.09, content_width * 0.12, content_width * 0.14, content_width * 0.06,
            content_width * 0.07, content_width * 0.07, content_width * 0.07, content_width * 0.08,
            content_width * 0.07, content_width * 0.09, content_width * 0.07, content_width * 0.07
        ]
        table_data, total_rows = _build_table_data(grouped_data, cell_style, header_cell_style, total_style)
        materials_table = Table(table_data, colWidths=col_widths)
        table_style = create_table_style()
        for i in range(1, len(table_data)):
            if i in total_rows:
                table_style.add('BACKGROUND', (0, i), (-1, i), lightgrey)
                table_style.add('FONTNAME', (2, i), (2, i), 'Helvetica-Bold')
                table_style.add('FONTNAME', (3, i), (3, i), 'Helvetica-Bold')
                table_style.add('FONTNAME', (6, i), (6, i), 'Helvetica-Bold')
                table_style.add('FONTNAME', (7, i), (7, i), 'Helvetica-Bold')
                table_style.add('FONTNAME', (10, i), (10, i), 'Helvetica-Bold')
                table_style.add('FONTNAME', (11, i), (11, i), 'Helvetica-Bold')
        materials_table.setStyle(table_style)
        story.append(materials_table)
        doc.build(story)
        return True
    except Exception as e:
        raise RuntimeError(f"Error generating materials report: {e}")