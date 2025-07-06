"""
Generates reports for area-specific information extracted from IDF files.
"""
from typing import Dict, Any, List
import logging
from collections import defaultdict
from pathlib import Path
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
from generators.base_report_generator import BaseReportGenerator, handle_report_errors, StandardPageSizes
from generators.shared_design_system import (
    COLORS, FONTS, FONT_SIZES, LAYOUT,
    create_standard_table_style, create_title_style
)
from generators.utils.formatting_utils import ValueFormatter

logger = logging.getLogger(__name__)


class AreaReportGenerator(BaseReportGenerator):
    """Area Report Generator using the refactored architecture."""
    
    def __init__(self, project_name="N/A", run_id="N/A", city_name="N/A", area_name="N/A"):
        super().__init__(project_name, run_id, city_name, area_name)
        self.formatter = ValueFormatter()
    
    @handle_report_errors("Area")
    def generate_report(self, area_id: str, area_data: List[Dict[str, Any]], 
                       output_filename: str, total_floor_area: float = 0.0,
                       wall_mass_per_area: float = 0.0, location: str = "Unknown",
                       areas_data=None, glazing_data: List[Dict[str, Any]] = None) -> bool:
        """Generate area PDF report."""
        # Get standard page configuration
        page_config = StandardPageSizes.get_config('area')
        
        # Create document
        doc = self.create_document(
            output_filename,
            page_size=page_config['page_size'],
            orientation=page_config['orientation']
        )
        
        # Build story
        story = []
        report_title = f"Area {area_id} - Thermal Properties"
        
        # Add standardized header
        header_elements = self.add_standardized_header(doc, report_title)
        story.extend(header_elements)
        
        # Add title
        title_style = create_title_style(self.styles)
        title_style.spaceAfter = 20
        story.append(Paragraph(f"{report_title} Report", title_style))
        
        # Add area summary
        summary_element = self._create_area_summary(area_id, total_floor_area, location, 
                                                   wall_mass_per_area, areas_data, doc)
        story.append(summary_element)
        story.append(Spacer(1, 15))
        
        # Add main area table (excluding glazing)
        if area_data:
            area_table_elements = _create_area_table(area_data, "", doc.width)
            story.extend(area_table_elements)
            story.append(Spacer(1, 15))
        
        # Add glazing table if glazing data exists
        if glazing_data:
            glazing_table_elements = _create_glazing_table(glazing_data, "", doc.width)
            story.extend(glazing_table_elements)
        
        # Build document
        return self.build_document(doc, story)
    
    def _create_area_summary(self, area_id: str, total_floor_area: float, location: str,
                           wall_mass_per_area: float, areas_data, doc) -> Table:
        """Create area summary table with standardized styling."""
        # Collect window directions from CSV data
        window_directions = set()
        if areas_data:
            if hasattr(areas_data, 'glazing_data_from_csv'):
                glazing_data_from_csv = areas_data.glazing_data_from_csv
                if glazing_data_from_csv:
                    # Extract area ID from the current area_id
                    current_area_id = area_id
                    if ":" in current_area_id:
                        current_area_id = current_area_id.split(":")[1]
                    
                    # Only include directions for surfaces in this area
                    for surface_name, data in glazing_data_from_csv.items():
                        # Extract area ID from surface name (e.g., "00:01XLIVING_WALL_4_0_0_0_0_0_WIN" -> "01")
                        surface_area_id = None
                        if ":" in surface_name:
                            parts = surface_name.split(":")
                            if len(parts) > 1 and parts[1][:2].isdigit():
                                surface_area_id = parts[1][:2]
                        
                        if surface_area_id == current_area_id and 'CardinalDirection' in data:
                            direction = data['CardinalDirection']
                            if direction and direction != "Unknown":
                                window_directions.add(direction)
        
        # Define custom sort order for directions
        direction_order = {'North': 0, 'South': 1, 'East': 2, 'West': 3}
        
        # Sort directions according to custom order
        sorted_directions = sorted(window_directions, key=lambda x: direction_order.get(x, 999))
        
        # Format window directions for display
        window_directions_str = ", ".join(sorted_directions) if sorted_directions else "None"
        
        summary_content_style = ParagraphStyle(
            'SummaryContent',
            parent=self.styles['Normal'],
            fontSize=FONT_SIZES['body'],
            fontName=FONTS['body'],
            textColor=COLORS['dark_gray'],
            leading=14,
            spaceBefore=0,
            spaceAfter=0
        )
        
        summary_text = f"""
        <font name="{FONTS['heading']}" size="{FONT_SIZES['heading']}" color="{COLORS['primary_blue'].hexval()}"><b>Area Summary</b></font><br/>
        <br/>
        <b>Area Name:</b> {area_id}<br/>
        <b>Total Area:</b> {self.formatter.format_number(total_floor_area, precision=2)} m²<br/>
        <b>Location:</b> {location}<br/>
        <b>Windows Directions:</b> {window_directions_str}<br/>
        <b>Wall Mass:</b> {self.formatter.format_number(wall_mass_per_area, precision=2)} kg/m²
        """
        
        summary_paragraph = Paragraph(summary_text, summary_content_style)
        summary_table_data = [[summary_paragraph]]
        summary_table = Table(summary_table_data, colWidths=[doc.width - 2*cm])
        
        summary_table_style = TableStyle([
            ('BOX', (0, 0), (-1, -1), 1.5, COLORS['primary_blue']),
            ('BACKGROUND', (0, 0), (-1, -1), COLORS['light_blue']),
            ('PADDING', (0, 0), (-1, -1), 15),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, COLORS['border_gray']),
        ])
        
        summary_table.setStyle(summary_table_style)
        return summary_table

def _format_construction_name(construction: str) -> str:
    """
    Format construction name for better display in the table.
    Adds line breaks for better readability.

    Args:
        construction: Construction name

    Returns:
        str: Formatted construction name
    """
    if len(construction) <= 18:
        return construction

    parts = construction.split(' ')
    if len(parts) > 1:
        lines = []
        current_line = parts[0]
        for part in parts[1:]:
            if len(current_line) + 1 + len(part) <= 18:
                current_line += " " + part
            else:
                lines.append(current_line)
                current_line = part
        lines.append(current_line)
        return "<br/>".join(lines)
    else:
        return "<br/>".join([construction[i:i + 15] for i in range(0, len(construction), 15)])

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

def _get_element_type_sort_keys_area(element_type_val):
    """Assigns primary and secondary sort keys based on element type string for area report."""
    cleaned_element_type_str = _clean_element_type(element_type_val)
    element_type_lower = (cleaned_element_type_str or "").lower()

    primary_key = 99
    secondary_key = 99

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
            secondary_key = 3
    elif 'glazing' in element_type_lower:
        primary_key = 3

    return primary_key, secondary_key

def custom_area_sort_key(item):
    """Create a custom sort key for area data based on zone, element type, and construction name."""
    zone = item.get('zone', '')
    element_type = item.get('element_type', '')
    construction_name = item.get('construction', '')

    primary_sort, secondary_sort = _get_element_type_sort_keys_area(element_type)

    return (zone, primary_sort, secondary_sort, construction_name)

def _area_table_data(merged_data):
    """
    Prepare and sort area table data for report generation using custom sort key.

    Args:
        merged_data: Merged area data rows

    Returns:
        Sorted list of area data rows
    """
    return sorted(merged_data, key=custom_area_sort_key)

# Backward compatibility function
def generate_area_report_pdf(area_id: str, area_data: List[Dict[str, Any]], 
                           output_filename: str, total_floor_area: float = 0.0, 
                           project_name: str = "N/A", run_id: str = "N/A", 
                           city_name: str = "N/A", area_name: str = "N/A", 
                           wall_mass_per_area: float = 0.0, location: str = "Unknown", 
                           areas_data=None, glazing_data: List[Dict[str, Any]] = None) -> bool:
    """
    Generate a PDF report with area information, including a header and separate glazing table.
    
    This function provides backward compatibility while using the new refactored architecture.

    Args:
        area_id (str): The area ID for the report.
        area_data (List[Dict[str, Any]]): List of area data rows for this area (excluding glazing).
        output_filename (str): Path where to save the PDF report.
        total_floor_area (float): The total floor area for this area.
        project_name (str): Name of the project.
        run_id (str): Identifier for the current run.
        city_name (str): City name.
        area_name (str): Area name.
        wall_mass_per_area (float): Mass per area (kg/m²) of the largest external wall's construction.
        location (str): The location type of the area (e.g., Ground Floor, Intermediate Floor).
        areas_data: AreaParser instance or dictionary of area information by zone.
        glazing_data (List[Dict[str, Any]]): List of glazing data rows for this area.

    Returns:
        bool: True if report generation was successful, False otherwise.
    """
    try:
        generator = AreaReportGenerator(
            project_name=project_name,
            run_id=run_id,
            city_name=city_name,
            area_name=area_name
        )
        
        return generator.generate_report(
            area_id=area_id,
            area_data=area_data,
            output_filename=output_filename,
            total_floor_area=total_floor_area,
            wall_mass_per_area=wall_mass_per_area,
            location=location,
            areas_data=areas_data,
            glazing_data=glazing_data
        )
    except Exception as e:
        logger.error(f"Error in generate_area_report_pdf: {type(e).__name__} - {str(e)}", exc_info=True)
        return False

def _create_area_table(merged_data, table_title, page_width):
    """
    Create the main area table for building elements (excluding glazing).
    
    Args:
        merged_data: List of area data rows
        table_title: Title for the table (unused now)
        page_width: Available page width
        
    Returns:
        List of reportlab elements
    """
    elements = []
    styles = getSampleStyleSheet()

    cell_style = ParagraphStyle(
        'CellStyle',
        parent=styles['Normal'],
        fontSize=9,
        leading=10,
        spaceBefore=0,
        spaceAfter=0
    )

    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Heading4'],
        fontSize=10,
        alignment=1,
        textColor=COLORS['white']
    )

    headers = [
        Paragraph("Zone", header_style),
        Paragraph("Construction", header_style),
        Paragraph("Element type", header_style),
        Paragraph("Area", header_style),
        Paragraph("U-Value", header_style)
    ]

    table_data = [headers]

    sorted_rows = _area_table_data(merged_data)

    last_zone = None

    for row in sorted_rows:
        construction_text = _format_construction_name(row['construction'])

        if row['zone'] != last_zone:
            zone_cell = Paragraph(row['zone'], cell_style)
            last_zone = row['zone']
        else:
            zone_cell = ""

        construction_cell = Paragraph(construction_text, cell_style)

        element_type = row.get('element_type', '')
        element_type_cell = Paragraph(_clean_element_type(element_type), cell_style)

        area_value = f"{row['area']:.2f}"
        u_value_to_format = row.get('weighted_u_value', row.get('u_value', 0.0))
        u_value = f"{u_value_to_format:.3f}"

        table_data.append([
            zone_cell,
            construction_cell,
            element_type_cell,
            area_value,
            u_value
        ])

    col_widths = [
        5.0*cm,
        8.0*cm,
        3.5*cm,
        2.7*cm,
        3.0*cm
    ]

    area_table = Table(table_data, colWidths=col_widths, repeatRows=1)

    table_style = create_standard_table_style()
    # Add right alignment for numeric columns
    table_style.add('ALIGN', (3, 1), (-1, -1), 'RIGHT')

    area_table.setStyle(table_style)
    elements.append(area_table)
    
    return elements

def _create_glazing_table(glazing_data, table_title, page_width):
    """
    Create the glazing table with shading information.
    
    Args:
        glazing_data: List of glazing data rows
        table_title: Title for the table (unused now)
        page_width: Available page width
        
    Returns:
        List of reportlab elements
    """
    elements = []
    styles = getSampleStyleSheet()

    cell_style = ParagraphStyle(
        'CellStyle',
        parent=styles['Normal'],
        fontSize=9,
        leading=10,
        spaceBefore=0,
        spaceAfter=0
    )

    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Heading4'],
        fontSize=10,
        alignment=1,
        textColor=COLORS['white']
    )

    headers = [
        Paragraph("Zone", header_style),
        Paragraph("Construction", header_style),
        Paragraph("Element type", header_style),
        Paragraph("Area", header_style),
        Paragraph("U-Value", header_style),
        Paragraph("Shading", header_style)
    ]

    table_data = [headers]

    # Sort glazing data similar to area data
    sorted_rows = sorted(glazing_data, key=custom_area_sort_key)

    last_zone = None

    for row in sorted_rows:
        construction_text = _format_construction_name(row['construction'])

        if row['zone'] != last_zone:
            zone_cell = Paragraph(row['zone'], cell_style)
            last_zone = row['zone']
        else:
            zone_cell = ""

        construction_cell = Paragraph(construction_text, cell_style)

        element_type = row.get('element_type', '')
        element_type_cell = Paragraph(_clean_element_type(element_type), cell_style)

        area_value = f"{row['area']:.2f}"
        u_value = f"{row['u_value']:.3f}"
        shading_value = row.get('shading', '-')

        table_data.append([
            zone_cell,
            construction_cell,
            element_type_cell,
            area_value,
            u_value,
            shading_value
        ])

    col_widths = [
        4.0*cm,
        6.5*cm,
        3.0*cm,
        2.5*cm,
        2.5*cm,
        4.0*cm
    ]

    glazing_table = Table(table_data, colWidths=col_widths, repeatRows=1)

    table_style = create_standard_table_style()
    # Add right alignment for numeric columns
    table_style.add('ALIGN', (3, 1), (4, -1), 'RIGHT')

    glazing_table.setStyle(table_style)
    elements.append(glazing_table)
    
    return elements

def generate_area_reports(areas_data, output_dir: str = "output/areas",
                          project_name: str = "N/A", run_id: str = "N/A",
                          city_name: str = "N/A", area_name: str = "N/A") -> bool:
    """
    Generate individual reports for each area, including header information.

    Args:
        areas_data: AreaParser instance or dictionary of area information by zone.
        output_dir (str): Directory for output files.
        project_name (str): Name of the project.
        run_id (str): Identifier for the current run.

    Returns:
        bool: True if all report generation was successful, False otherwise.
    """
    all_reports_successful = True
    try:
        output_path = Path(output_dir)
        if not output_path.exists():
            try:
                output_path.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                error_message = f"Error creating base output directory '{output_path}' for area reports: {e.strerror}"
                logger.error(error_message, exc_info=True)
                return False
        elif not output_path.is_dir():
            error_message = f"Error: Base output path '{output_path}' for area reports exists but is not a directory."
            logger.error(error_message)
            return False

        from parsers.materials_parser import MaterialsParser

        materials_parser = None
        data_loader = None
        glazing_data_from_csv = None

        if hasattr(areas_data, 'data_loader'):
            data_loader = areas_data.data_loader
            if hasattr(areas_data, 'glazing_data_from_csv'):
                glazing_data_from_csv = areas_data.glazing_data_from_csv

        if data_loader:
            try:
                materials_parser = MaterialsParser(data_loader)
                materials_parser.process_idf(None)
            except Exception as e:
                logger.warning(f"Could not initialize or process MaterialsParser for area reports: {e}", exc_info=True)
                materials_parser = None

        surfaces = {}
        zones = {}
        if data_loader:
            surfaces = data_loader.get_surfaces()
            zones = data_loader.get_zones()

        area_table_data = {}

        area_floor_totals = {}

        if hasattr(areas_data, 'areas_by_zone'):
            for zone_id, zone_data in areas_data.areas_by_zone.items():
                area_id = zone_data.get("area_id", "unknown")
                if area_id not in area_floor_totals:
                    area_totals = areas_data.get_area_totals(area_id)
                    area_floor_totals[area_id] = area_totals.get("total_floor_area", 0.0)
        else:
            for zone_id, zone_data in zones.items():
                area_id = None
                if hasattr(areas_data, 'get') and isinstance(areas_data.get(zone_id), dict):
                    area_id = areas_data.get(zone_id, {}).get("area_id", "unknown")

                if area_id:
                    if area_id not in area_floor_totals:
                        area_floor_totals[area_id] = 0.0

                    floor_area = zone_data.get("floor_area", 0.0)
                    multiplier = zone_data.get("multiplier", 1)
                    area_floor_totals[area_id] += floor_area * multiplier

        if hasattr(areas_data, 'get_area_table_data'):
            area_table_data = areas_data.get_area_table_data(materials_parser)
        else:
            areas_grouped = defaultdict(dict)
            for zone_id, zone_data in areas_data.items():
                area_id = zone_data.get("area_id", "unknown")
                if area_id not in areas_grouped:
                    areas_grouped[area_id] = {}
                areas_grouped[area_id][zone_id] = zone_data

            for area_id, area_zones in areas_grouped.items():
                rows = []

                for zone_id, zone_data in area_zones.items():
                    for construction_name, construction_data in zone_data.get("constructions", {}).items():
                        total_area = construction_data.get("total_area", 0.0)
                        construction_data.get("total_u_value", 0.0)

                        element_type = None

                        if materials_parser and surfaces:
                            try:
                                element_type = materials_parser._get_element_type(construction_name, surfaces)
                            except Exception as e_mat_type:
                                logger.warning(f"Error getting element type from MaterialsParser for construction '{construction_name}': {e_mat_type}")

                        if not element_type:
                            for element in construction_data.get("elements", []):
                                surface_name = element.get("surface_name")
                                if surface_name and surface_name in surfaces:
                                    surface = surfaces[surface_name]
                                    if surface.get('is_glazing', False):
                                        element_type = "Glazing"
                                        break

                        if not element_type and construction_data.get("elements"):
                            fallback_type = construction_data["elements"][0].get("element_type", "Unknown")
                            element_type = fallback_type
                        elif not element_type:
                            element_type = "Unknown"

                        row = {
                            "zone": zone_id,
                            "construction": construction_name,
                            "element_type": element_type,
                            "area": total_area,
                            "u_value": construction_data.get("elements", [{}])[0].get("u_value", 0.0) if construction_data.get("elements") else 0.0
                        }
                        rows.append(row)

                area_table_data[area_id] = rows

        # Get glazing table data separately
        glazing_table_data = {}
        if hasattr(areas_data, 'get_glazing_table_data'):
            glazing_table_data = areas_data.get_glazing_table_data(materials_parser)
        else:
            logger.warning("AreaParser does not have get_glazing_table_data method. Glazing table will be empty.")

        area_locations = {}
        if hasattr(areas_data, 'get_area_h_values'):
            try:
                area_h_values = areas_data.get_area_h_values()
                for item in area_h_values:
                    area_id = item.get('area_id')
                    location = item.get('location', 'Unknown')
                    if area_id:
                        area_locations[area_id] = location
            except Exception as e_hval:
                logger.warning(f"Could not retrieve area H values for area reports: {e_hval}", exc_info=True)

        for area_id, merged_rows in area_table_data.items():
            total_floor_area = area_floor_totals.get(area_id, 0.0)

            wall_mass_per_area = 0.0
            largest_ext_wall_area = 0.0
            largest_ext_wall_construction = None

            for row in merged_rows:
                raw_element_type = row.get('element_type', '')
                cleaned_type_str = _clean_element_type(raw_element_type).lower()

                if 'external wall' in cleaned_type_str.split('\n'):
                    current_area = row.get('area', 0.0)
                    if current_area > largest_ext_wall_area:
                        largest_ext_wall_area = current_area
                        largest_ext_wall_construction = row.get('construction')

            if largest_ext_wall_construction and materials_parser:
                try:
                    wall_mass_per_area = materials_parser.calculate_construction_mass_per_area(largest_ext_wall_construction)
                except Exception as e_mass:
                    logger.warning(f"Error calculating wall mass for area '{area_id}', construction '{largest_ext_wall_construction}': {e_mass}", exc_info=True)
            elif largest_ext_wall_construction:
                logger.warning(f"Materials parser not available to calculate wall mass for construction '{largest_ext_wall_construction}'")

            location = area_locations.get(area_id, "Unknown")

            output_file = output_path / f"{area_id}.pdf"

            # Create a temporary object to hold the glazing data
            class TempAreasData:
                def __init__(self, glazing_data):
                    self.glazing_data_from_csv = glazing_data

            temp_areas_data = TempAreasData(glazing_data_from_csv)

            # Get glazing data for this area
            area_glazing_data = glazing_table_data.get(area_id, [])

            success = generate_area_report_pdf(
                area_id=area_id,
                area_data=merged_rows,
                output_filename=str(output_file),
                total_floor_area=total_floor_area,
                project_name=project_name,
                run_id=run_id,
                city_name=city_name,
                area_name=area_name,
                wall_mass_per_area=wall_mass_per_area,
                location=location,
                areas_data=temp_areas_data,
                glazing_data=area_glazing_data  # Pass the glazing data for this area
            )
            if not success:
                all_reports_successful = False
                logger.error(f"Failed to generate PDF report for Area ID: {area_id}")

        return all_reports_successful

    except ImportError as ie:
        logger.error(f"Failed to import a required module (e.g., MaterialsParser) for generating area reports: {ie}", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred in generate_area_reports: {type(e).__name__} - {str(e)}", exc_info=True)
        return False

def generate_area_reports_by_base_zone(areas_data, output_dir: str = "output/areas",
                                     project_name: str = "N/A", run_id: str = "N/A",
                                     city_name: str = "N/A", area_name: str = "N/A") -> bool:
    """
    Generate individual reports for each base zone, grouping related zones together.
    Zones like '25:A338XLIV' and '25:A338XMMD' will be in the same report.

    Args:
        areas_data: AreaParser instance or dictionary of area information by zone.
        output_dir (str): Directory for output files.
        project_name (str): Name of the project.
        run_id (str): Identifier for the current run.

    Returns:
        bool: True if all report generation was successful, False otherwise.
    """
    all_reports_successful = True
    try:
        output_path = Path(output_dir)
        if not output_path.exists():
            try:
                output_path.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                error_message = f"Error creating base output directory '{output_path}' for base zone area reports: {e.strerror}"
                logger.error(error_message, exc_info=True)
                return False
        elif not output_path.is_dir():
            error_message = f"Error: Base output path '{output_path}' for base zone area reports exists but is not a directory."
            logger.error(error_message)
            return False

        from parsers.materials_parser import MaterialsParser

        materials_parser = None
        data_loader = None

        if hasattr(areas_data, 'data_loader'):
            data_loader = areas_data.data_loader

        if data_loader:
            try:
                materials_parser = MaterialsParser(data_loader)
                materials_parser.process_idf(None)
            except Exception as e:
                logger.warning(f"Could not initialize or process MaterialsParser for base zone area reports: {e}", exc_info=True)
                materials_parser = None

        zones = {}
        if data_loader:
            zones = data_loader.get_zones()

        # Get base zone groupings
        base_zone_groupings = {}
        base_zone_floor_totals = {}
        
        if hasattr(areas_data, 'get_area_groupings_by_base_zone'):
            base_zone_groupings = areas_data.get_area_groupings_by_base_zone()
            logger.info(f"Found {len(base_zone_groupings)} base zone groups")
        else:
            logger.warning("AreaParser does not have get_area_groupings_by_base_zone method. Falling back to regular area grouping.")
            return generate_area_reports(areas_data, output_dir, project_name, run_id, city_name, area_name)

        # Calculate floor totals for each base zone
        if hasattr(areas_data, 'areas_by_zone'):
            for zone_id, zone_data in areas_data.areas_by_zone.items():
                base_zone_id = zone_data.get("base_zone_id", zone_id)
                if base_zone_id not in base_zone_floor_totals:
                    base_zone_floor_totals[base_zone_id] = 0.0
                
                floor_area = zone_data.get("floor_area", 0.0)
                multiplier = zone_data.get("multiplier", 1)
                base_zone_floor_totals[base_zone_id] += floor_area * multiplier

        # Get table data grouped by base zone
        base_zone_table_data = {}
        if hasattr(areas_data, 'get_area_table_data_by_base_zone'):
            base_zone_table_data = areas_data.get_area_table_data_by_base_zone(materials_parser)
        else:
            logger.warning("AreaParser does not have get_area_table_data_by_base_zone method.")
            return False

        # Get glazing table data separately
        glazing_table_data = {}
        if hasattr(areas_data, 'get_glazing_table_data'):
            glazing_table_data = areas_data.get_glazing_table_data(materials_parser)
        else:
            logger.warning("AreaParser does not have get_glazing_table_data method. Glazing table will be empty.")

        # Get area locations
        area_locations = {}
        if hasattr(areas_data, 'get_area_h_values'):
            try:
                area_h_values = areas_data.get_area_h_values()
                for item in area_h_values:
                    area_id = item.get('area_id')
                    location = item.get('location', 'Unknown')
                    if area_id:
                        area_locations[area_id] = location
            except Exception as e_hval:
                logger.warning(f"Could not retrieve area H values for base zone area reports: {e_hval}", exc_info=True)

        # Generate reports for each base zone
        for base_zone_id, merged_rows in base_zone_table_data.items():
            total_floor_area = base_zone_floor_totals.get(base_zone_id, 0.0)

            # Calculate wall mass per area (using same logic as original function)
            wall_mass_per_area = 0.0
            largest_ext_wall_area = 0.0
            largest_ext_wall_construction = None

            for row in merged_rows:
                raw_element_type = row.get('element_type', '')
                cleaned_type_str = _clean_element_type(raw_element_type).lower()

                if 'external wall' in cleaned_type_str.split('\n'):
                    current_area = row.get('area', 0.0)
                    if current_area > largest_ext_wall_area:
                        largest_ext_wall_area = current_area
                        largest_ext_wall_construction = row.get('construction')

            if largest_ext_wall_construction and materials_parser:
                try:
                    wall_mass_per_area = materials_parser.calculate_construction_mass_per_area(largest_ext_wall_construction)
                except Exception as e_mass:
                    logger.warning(f"Error calculating mass per area for construction '{largest_ext_wall_construction}' in base zone '{base_zone_id}': {e_mass}")
                    wall_mass_per_area = 0.0

            # Determine location (use first area_id from zones in this base zone)
            location = "Unknown"
            if base_zone_id in base_zone_groupings and base_zone_groupings[base_zone_id]:
                first_zone_id = base_zone_groupings[base_zone_id][0]
                if hasattr(areas_data, 'areas_by_zone') and first_zone_id in areas_data.areas_by_zone:
                    first_area_id = areas_data.areas_by_zone[first_zone_id].get("area_id", "unknown")
                    location = area_locations.get(first_area_id, "Unknown")

            # Create a safe filename from base_zone_id
            safe_base_zone_id = base_zone_id.replace(":", "_").replace("/", "_")
            output_file = output_path / f"{safe_base_zone_id}.pdf"

            # Create temporary object with glazing data for compatibility
            temp_areas_data = type('TempAreasData', (), {})()
            if hasattr(areas_data, 'glazing_data_from_csv'):
                temp_areas_data.glazing_data_from_csv = areas_data.glazing_data_from_csv
            else:
                temp_areas_data.glazing_data_from_csv = {}

            # Get glazing data for this base zone (combine glazing from all areas in this base zone)
            base_zone_glazing_data = []
            if base_zone_id in base_zone_groupings:
                for zone_id in base_zone_groupings[base_zone_id]:
                    if hasattr(areas_data, 'areas_by_zone') and zone_id in areas_data.areas_by_zone:
                        zone_area_id = areas_data.areas_by_zone[zone_id].get("area_id", "unknown")
                        area_glazing = glazing_table_data.get(zone_area_id, [])
                        # Filter glazing data for this specific zone
                        zone_glazing = [g for g in area_glazing if g.get('zone') == zone_id]
                        base_zone_glazing_data.extend(zone_glazing)

            logger.info(f"Generating base zone area report for: {base_zone_id} (includes {len(base_zone_groupings.get(base_zone_id, []))} zones)")

            success = generate_area_report_pdf(
                area_id=base_zone_id,
                area_data=merged_rows,
                output_filename=str(output_file),
                total_floor_area=total_floor_area,
                project_name=project_name,
                run_id=run_id,
                city_name=city_name,
                area_name=area_name,
                wall_mass_per_area=wall_mass_per_area,
                location=location,
                areas_data=temp_areas_data,
                glazing_data=base_zone_glazing_data  # Pass the glazing data for this base zone
            )
            if not success:
                all_reports_successful = False
                logger.error(f"Failed to generate PDF report for Base Zone ID: {base_zone_id}")

        return all_reports_successful

    except ImportError as ie:
        logger.error(f"Failed to import a required module for generating base zone area reports: {ie}", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred in generate_area_reports_by_base_zone: {type(e).__name__} - {str(e)}", exc_info=True)
        return False
