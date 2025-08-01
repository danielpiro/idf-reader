"""
Generates PDF reports showing materials and their thermal properties within constructions.
"""
from typing import Dict, Any, List
from utils.logging_config import get_logger
from reportlab.lib.colors import lightgrey
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Table
from generators.base_report_generator import BaseReportGenerator, handle_report_errors, StandardPageSizes
from generators.shared_design_system import (
    COLORS, FONTS, FONT_SIZES, LAYOUT,
    create_standard_table_style, create_cell_style, 
    create_title_style, wrap_text
)
from generators.utils.formatting_utils import ValueFormatter

logger = get_logger(__name__)


class MaterialsReportGenerator(BaseReportGenerator):
    """Materials Report Generator using the refactored architecture."""
    
    def __init__(self, element_data: List[Dict[str, Any]], output_path: str, project_name="N/A", run_id="N/A", city_name="N/A", area_name="N/A"):
        super().__init__(project_name, run_id, city_name, area_name)
        self.element_data = element_data
        self.output_path = output_path
        self.formatter = ValueFormatter()
    
    @handle_report_errors("Materials")
    def generate_report(self) -> bool:
        """Generate materials PDF report."""
        if not self.element_data:
            logger.warning("No element data provided for materials report. Skipping generation.")
            return False

        # Group the data
        grouped_data = group_element_data(self.element_data)
        if not grouped_data:
            logger.warning("Element data could not be grouped or resulted in no groups for materials report. Skipping generation.")
            return False

        # Get standard page configuration
        page_config = StandardPageSizes.get_config('materials')
        
        # Create document
        doc = self.create_document(
            self.output_path,
            page_size=page_config['page_size'],
            orientation=page_config['orientation']
        )
        
        # Build story
        story = []
        report_title = "Building Elements Materials Properties"
        
        # Add standardized header
        header_elements = self.add_standardized_header(doc, report_title)
        story.extend(header_elements)
        
        # Add title
        title_style = create_title_style(self.styles)
        story.append(Paragraph(f"{report_title} Report", title_style))
        
        # Create and add table
        table = self._create_materials_table(grouped_data, doc)
        story.append(table)
        
        # Build document
        return self.build_document(doc, story)
    
    def _create_materials_table(self, grouped_data: List[Dict[str, Any]], doc) -> Table:
        """Create materials table with standardized styling."""
        # Create styles
        cell_style = create_cell_style(self.styles, is_header=False, font_size=FONT_SIZES['table_body'])
        header_cell_style = create_cell_style(self.styles, is_header=True, font_size=FONT_SIZES['table_header'])
        total_style = create_cell_style(self.styles, is_header=False, font_size=FONT_SIZES['table_body'])
        
        # Calculate content width
        page_size = doc.pagesize
        margins = doc.leftMargin + doc.rightMargin
        content_width = page_size[0] - margins
        
        # Define column widths
        col_widths = [
            content_width * 0.09, content_width * 0.12, content_width * 0.14, content_width * 0.06,
            content_width * 0.07, content_width * 0.07, content_width * 0.07, content_width * 0.08,
            content_width * 0.07, content_width * 0.09, content_width * 0.07, content_width * 0.07
        ]
        
        # Build table data
        table_data, total_rows = _build_table_data(grouped_data, cell_style, header_cell_style, total_style)
        
        # Create table
        table = Table(table_data, colWidths=col_widths)
        
        # Apply styling
        table_style = create_standard_table_style()
        for i in range(1, len(table_data)):
            if i in total_rows:
                table_style.add('BACKGROUND', (0, i), (-1, i), lightgrey)
                table_style.add('FONTNAME', (2, i), (2, i), 'Helvetica-Bold')
                table_style.add('FONTNAME', (3, i), (3, i), 'Helvetica-Bold')
                table_style.add('FONTNAME', (6, i), (6, i), 'Helvetica-Bold')
                table_style.add('FONTNAME', (7, i), (7, i), 'Helvetica-Bold')
                table_style.add('FONTNAME', (10, i), (10, i), 'Helvetica-Bold')
                table_style.add('FONTNAME', (11, i), (11, i), 'Helvetica-Bold')
        
        table.setStyle(table_style)
        return table


def _normalize_glazing_str(s: str) -> str:
    return "External glazing" if s == "External Glazing" else s

def _clean_element_type(element_type) -> str:
    """
    Cleans the element type for display, removing list formatting, quotes, and boolean values.
    Args:
        element_type: Element type which could be a string, tuple, or list,
                     potentially with a boolean value
    Returns:
        str: Cleaned element type string for display
    """
    if isinstance(element_type, str):
        return _normalize_glazing_str(element_type.strip())

    if isinstance(element_type, (list, tuple)):
        if len(element_type) == 2 and isinstance(element_type[1], bool):
            raw_element_types = element_type[0]
            if isinstance(raw_element_types, (list, tuple)):
                return '\n'.join([_normalize_glazing_str(str(et).strip()) for et in raw_element_types])
            else:
                return _normalize_glazing_str(str(raw_element_types).strip())
        else:
            return '\n'.join([_normalize_glazing_str(str(et).strip()) for et in element_type])

    return _normalize_glazing_str(str(element_type).strip())

def _get_element_type_sort_keys(element_type_val):
    """Assigns primary and secondary sort keys based on element type string,
    using cleaning logic consistent with area_report_generator.py."""
    cleaned_element_type_str = _clean_element_type(element_type_val)
    element_type_lower = (cleaned_element_type_str or "").lower()

    primary_key = 99
    secondary_key = 99

    if 'ground floor' in element_type_lower:
        primary_key = 0
        secondary_key = 0
    elif 'intermediate floor' in element_type_lower:
        primary_key = 0
        secondary_key = 1
    elif 'separation floor' in element_type_lower:
        primary_key = 0
        secondary_key = 2
    elif 'floor' in element_type_lower:
        primary_key = 0
        secondary_key = 3
    elif 'ceiling' in element_type_lower or 'roof' in element_type_lower:
        primary_key = 1
    elif 'wall' in element_type_lower:
        primary_key = 2
        if 'internal' in element_type_lower:
            secondary_key = 0
        elif 'intermediate' in element_type_lower:
            secondary_key = 1
        elif 'separation' in element_type_lower:
            secondary_key = 2
        elif 'external' in element_type_lower:
            secondary_key = 3
        else:
            secondary_key = 4
    elif 'glazing' in element_type_lower:
        primary_key = 3

    return primary_key, secondary_key

def custom_material_sort_key(item):
    """Create a custom sort key for materials based on element type and name."""
    element_type = item.get('element_type', '') or ''
    element_name = item.get('element_name', '') or ''

    primary_sort, secondary_sort = _get_element_type_sort_keys(element_type)

    return (primary_sort, secondary_sort, element_name)

def _calc_group_totals(group):
    """Calculate totals and derived values for a group of layers."""
    total_thickness = sum(g.get('thickness') or 0.0 for g in group)
    total_mass = sum(g.get('mass') or 0.0 for g in group)
    total_resistance = sum(g.get('thermal_resistance') or 0.0 for g in group)
    film_resistance = (group[0].get('surface_film_resistance') or 0.0) if group else 0.0
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
    except (TypeError, ValueError, KeyError, AttributeError) as e:
        logger.error(f"Error processing or grouping element data: {type(e).__name__} - {str(e)}. Problematic item might be missing expected keys or have incorrect data types.", exc_info=True)
        return []
    except Exception as e:
        logger.error(f"Unexpected error grouping element data: {type(e).__name__} - {str(e)}", exc_info=True)
        return []

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

# Backward compatibility function
@handle_report_errors("Materials")
def generate_materials_report_pdf(element_data: List[Dict[str, Any]],
                                 output_filename: str = "output/materials.pdf", 
                                 project_name: str = "N/A", 
                                 run_id: str = "N/A",
                                 city_name: str = "N/A", 
                                 area_name: str = "N/A") -> bool:
    """
    Generate a PDF report containing materials thermal properties.
    
    This function provides backward compatibility while using the new refactored architecture.
    
    Args:
        element_data (List[Dict[str, Any]]): List of dictionaries containing element data.
        output_filename (str): The name of the output PDF file.
        project_name (str): Name of the project.
        run_id (str): Identifier for the current run.
        city_name (str): City name.
        area_name (str): Area name.
    
    Returns:
        bool: True if report generated successfully, False otherwise.
    """
    generator = MaterialsReportGenerator(
        element_data=element_data,
        output_path=output_filename,
        project_name=project_name,
        run_id=run_id,
        city_name=city_name,
        area_name=area_name
    )
    
    return generator.generate_report()
