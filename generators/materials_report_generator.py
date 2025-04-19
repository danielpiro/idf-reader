"""
Generates PDF reports showing materials and their thermal properties within constructions.
"""
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape, A3
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph, Table, TableStyle, SimpleDocTemplate, Spacer
from reportlab.lib.colors import navy, black, grey, lightgrey, white
from reportlab.lib.enums import TA_CENTER, TA_LEFT

def wrap_text(text, style):
    """Helper function to create wrapped text in a cell."""
    return Paragraph(str(text), style)

def create_cell_style(styles, is_header=False, total_row=False):
    """Create a cell style for wrapped text."""
    style = ParagraphStyle(
        'Cell',
        parent=styles['Normal'],
        fontSize=8,  # Reduced font size for better fit
        leading=10,  # Reduced leading for better fit
        spaceBefore=2, # Reduced space before
        spaceAfter=2,  # Reduced space after
        fontName='Helvetica-Bold' if is_header or total_row else 'Helvetica',
        wordWrap='CJK',
        alignment=TA_LEFT
    )
    return style

def create_table_style():
    """Create a consistent table style for materials table."""
    return TableStyle([
        # Header styling
        ('BACKGROUND', (0, 0), (-1, 0), lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), black),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        
        # All cell styling
        ('GRID', (0, 0), (-1, -1), 0.5, grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        
        # Reduced padding for all cells
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        
        # Total rows styling - will be applied dynamically
    ])

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
                    
                    # Get surface film resistance from the first item in group (all items in group have same value)
                    film_resistance = float(current_group[0].get('surface_film_resistance', 0))
                    
                    # R-Value is the total thermal resistance of materials
                    r_value = total_resistance
                    
                    # Add surface film resistance to calculate R-Value with film
                    r_value_with_film = r_value + film_resistance
                    
                    # Calculate U-Value as 1 / R-Value with film
                    u_value = 1.0 / r_value_with_film if r_value_with_film > 0 else 0.0
                    
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
            total_thickness = sum(float(g.get('thickness', 0)) for g in current_group)
            total_mass = sum(float(g.get('mass', 0)) for g in current_group)
            total_resistance = sum(float(g.get('thermal_resistance', 0)) for g in current_group)
            
            # Get surface film resistance from the first item in group (all items in group have same value)
            film_resistance = float(current_group[0].get('surface_film_resistance', 0))
            
            # R-Value is the total thermal resistance of materials
            r_value = total_resistance
            
            # Add surface film resistance to calculate R-Value with film
            r_value_with_film = r_value + film_resistance
            
            # Calculate U-Value as 1 / R-Value with film
            u_value = 1.0 / r_value_with_film if r_value_with_film > 0 else 0.0
            
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
        
    try:
        # Group the data first
        grouped_data = group_element_data(element_data)
        if not grouped_data:
            print("Warning: No groups created from element data")
            return False

        # Use SimpleDocTemplate for better pagination and layout
        page_size = landscape(A3)  # Use A3 for more space - better for wide tables
        left_margin = 1.0*cm
        right_margin = 1.0*cm
        top_margin = 1.0*cm
        bottom_margin = 1.0*cm
        
        doc = SimpleDocTemplate(output_filename, 
                               pagesize=page_size,
                               leftMargin=left_margin, 
                               rightMargin=right_margin,
                               topMargin=top_margin, 
                               bottomMargin=bottom_margin)
        
        width, height = page_size
        content_width = width - left_margin - right_margin
        
        # Build story for the document
        story = []
        
        # Styles
        styles = getSampleStyleSheet()
        title_style = styles['Heading1']
        title_style.alignment = TA_CENTER
        title_style.textColor = navy
        title_style.spaceAfter = 0.5*cm
        
        cell_style = create_cell_style(styles)
        header_cell_style = create_cell_style(styles, is_header=True)
        total_style = create_cell_style(styles, total_row=True)

        # Add title
        title_text = "Building Elements Materials Properties Report"
        story.append(Paragraph(title_text, title_style))
        story.append(Spacer(1, 0.5*cm))

        # Create table headers
        headers = [
            "Element Type",
            "Element Name",
            "Material Name",
            "Thickness\n(m)",
            "Conductivity\n(W/m-K)",
            "Density\n(kg/m³)",
            "Mass\n(kg/m²)",
            "Thermal\nResistance\n(m²K/W)",
            "Solar\nAbsorptance",
            "Specific\nHeat (J/kg-K)",
            "R-Value\n(m²K/W)",
            "U-Value\n(W/m²K)"
        ]

        headers_row = [wrap_text(h, header_cell_style) for h in headers]
        
        # Optimized column widths - adjusted based on content needs
        col_widths = [
            content_width * 0.09,   # Element Type - reduced width
            content_width * 0.12,  # Element Name - slightly larger for longer names
            content_width * 0.14,  # Material Name - increased for longer material names
            content_width * 0.06,  # Thickness
            content_width * 0.07,  # Conductivity
            content_width * 0.07,  # Density
            content_width * 0.07,  # Mass
            content_width * 0.08,  # Thermal Resistance
            content_width * 0.07,  # Solar Absorptance
            content_width * 0.09,  # Specific Heat
            content_width * 0.07,  # R-Value
            content_width * 0.07   # U-Value
        ]

        # Build the data rows for the table
        table_data = [headers_row]
        
        # Track rows for styling
        total_rows = []
        row_index = 1  # Start after header
        
        current_element_type = None
        current_element_name = None
        
        for group in grouped_data:
            element_type = group["element_type"]
            element_name = group["element_name"]
            
            # Process each material layer
            for i, layer in enumerate(group["layers"]):
                # Only include element type and name in the first row of the group
                if i == 0:
                    elem_type_cell = element_type
                    elem_name_cell = element_name
                    # Update tracking variables
                    current_element_type = element_type
                    current_element_name = element_name
                else:
                    # Empty cells to avoid repetition
                    elem_type_cell = ""
                    elem_name_cell = ""
                
                # Format numeric values with appropriate precision
                row = [
                    wrap_text(elem_type_cell, cell_style),
                    wrap_text(elem_name_cell, cell_style),
                    wrap_text(safe_value(layer.get("material_name")), cell_style),
                    wrap_text(f"{float(layer.get('thickness', 0)):.3f}", cell_style),
                    wrap_text(f"{float(layer.get('conductivity', 0)):.3f}", cell_style),
                    wrap_text(f"{float(layer.get('density', 0)):.1f}", cell_style),
                    wrap_text(f"{float(layer.get('mass', 0)):.1f}", cell_style),
                    wrap_text(f"{float(layer.get('thermal_resistance', 0)):.3f}", cell_style),
                    wrap_text(f"{float(layer.get('solar_absorptance', 0)):.3f}", cell_style),
                    wrap_text(f"{float(layer.get('specific_heat', 0)):.1f}", cell_style),
                    wrap_text("", cell_style),  # Empty cell for R-Value (element level only)
                    wrap_text("", cell_style)   # Empty cell for U-Value (element level only)
                ]
                table_data.append(row)
                row_index += 1
            
            # Add totals row
            totals_row = [
                wrap_text("", cell_style),
                wrap_text("", cell_style),
                wrap_text("TOTALS", total_style),
                wrap_text(f"{group['total_thickness']:.3f}", total_style),
                wrap_text("", cell_style),
                wrap_text("", cell_style),
                wrap_text(f"{group['total_mass']:.1f}", total_style),
                wrap_text(f"{group['total_resistance']:.3f}", total_style),  # Keep original thermal resistance
                wrap_text("", cell_style),
                wrap_text("", cell_style),
                wrap_text(f"{group['r_value_with_film']:.3f}", total_style),  # R-Value with film resistance
                wrap_text(f"{group['u_value']:.3f}", total_style)  # U-Value based on R-Value with film
            ]
            table_data.append(totals_row)
            total_rows.append(row_index)
            row_index += 1

        # Create the table with all data
        materials_table = Table(table_data, colWidths=col_widths)
        
        # Apply basic table style
        table_style = create_table_style()
        
        # Apply additional styling for alternating elements and total rows
        for i in range(1, len(table_data)):
            if i in total_rows:
                # Highlight total rows
                table_style.add('BACKGROUND', (0, i), (-1, i), lightgrey)
                table_style.add('FONTNAME', (2, i), (2, i), 'Helvetica-Bold')  # TOTALS text
                table_style.add('FONTNAME', (3, i), (3, i), 'Helvetica-Bold')  # Total thickness
                table_style.add('FONTNAME', (6, i), (6, i), 'Helvetica-Bold')  # Total mass
                table_style.add('FONTNAME', (7, i), (7, i), 'Helvetica-Bold')  # Total resistance
                table_style.add('FONTNAME', (10, i), (10, i), 'Helvetica-Bold')  # R-Value
                table_style.add('FONTNAME', (11, i), (11, i), 'Helvetica-Bold')  # U-Value
        
        # Apply style to table
        materials_table.setStyle(table_style)
        
        # Add table to story
        story.append(materials_table)
        
        # Build the document
        doc.build(story)
        print(f"Successfully generated materials report: {output_filename}")
        return True

    except Exception as e:
        print(f"Error generating materials report: {e}")
        import traceback
        traceback.print_exc()  # Enable traceback for better debugging
        return False