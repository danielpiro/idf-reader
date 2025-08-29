"""
Generates reports for area-specific information extracted from IDF files.
"""
from typing import Dict, Any, List
from utils.logging_config import get_logger
from collections import defaultdict
from pathlib import Path
from generators.reportlab_commons import ParagraphStyle, getSampleStyleSheet, cm, Paragraph, Spacer, Table, TableStyle
from generators.base_report_generator import BaseReportGenerator, handle_report_errors, StandardPageSizes
from generators.shared_design_system import (
    COLORS, FONTS, FONT_SIZES, LAYOUT,
    create_standard_table_style, create_title_style
)
from generators.utils.formatting_utils import ValueFormatter

logger = get_logger(__name__)


class AreaReportGenerator(BaseReportGenerator):
    """Area Report Generator using the refactored architecture."""
    
    def __init__(self, project_name="-", run_id="-", city_name="-", area_name="-"):
        super().__init__(project_name, run_id, city_name, area_name)
        self.formatter = ValueFormatter()
    
    @handle_report_errors("Area")
    def generate_report(self, floor_id: str, area_data: List[Dict[str, Any]], 
                       output_filename: str, total_floor_area: float = 0.0,
                       wall_mass_per_area: float = 0.0, location: str = "-",
                       areas_data=None, glazing_data: List[Dict[str, Any]] = None) -> bool:
        """Generate area PDF report."""
        logger.info(f"AREA CLASS DEBUG - AreaReportGenerator.generate_report called for floor '{floor_id}'")
        logger.info(f"AREA CLASS DEBUG - Output filename: {output_filename}")
        
        # Check if there's actual data to generate a report with
        has_area_data = area_data and len(area_data) > 0
        has_glazing_data = glazing_data and len(glazing_data) > 0
        has_floor_area = total_floor_area > 0.0
        
        if not has_area_data and not has_glazing_data and not has_floor_area:
            logger.warning(f"AREA CLASS DEBUG - Skipping report generation for floor '{floor_id}' - no data available")
            logger.info(f"AREA CLASS DEBUG - area_data: {len(area_data) if area_data else 0} items")
            logger.info(f"AREA CLASS DEBUG - glazing_data: {len(glazing_data) if glazing_data else 0} items") 
            logger.info(f"AREA CLASS DEBUG - total_floor_area: {total_floor_area}")
            return True  # Return True to indicate successful handling (just skipped)
        
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
        report_title = f"Floor {floor_id}"
        
        # Add standardized header
        header_elements = self.add_standardized_header(doc, report_title)
        story.extend(header_elements)
        
        # Add title
        title_style = create_title_style(self.styles)
        title_style.spaceAfter = 20
        story.append(Paragraph(f"{report_title} Report", title_style))
        
        # Add area summary
        summary_element = self._create_area_summary(floor_id, total_floor_area, location, 
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
        logger.info(f"AREA CLASS DEBUG - Building PDF document for floor '{floor_id}' with {len(story)} story elements")
        result = self.build_document(doc, story)
        logger.info(f"AREA CLASS DEBUG - Document build result for floor '{floor_id}': {result}")
        return result
    
    def _create_area_summary(self, floor_id: str, total_floor_area: float, location: str,
                           wall_mass_per_area: float, areas_data, doc) -> Table:
        """Create area summary table with standardized styling."""
        logger.info(f"AREA SUMMARY DEBUG - Creating summary for floor '{floor_id}' with total_floor_area={total_floor_area}")
        # Collect window directions from CSV data
        window_directions = set()
        if areas_data:
            if hasattr(areas_data, 'glazing_data_from_csv'):
                glazing_data_from_csv = areas_data.glazing_data_from_csv
                if glazing_data_from_csv:
                    # Extract area ID from the current floor_id using consistent logic
                    current_area_id = floor_id
                    if ":" in current_area_id:
                        parts = current_area_id.split(":")
                        if len(parts) > 1:
                            zone_part = parts[1]
                            # Use same logic as new grouping system for consistency  
                            has_x = 'X' in zone_part
                            has_underscore = '_' in zone_part
                            
                            if has_x or has_underscore:
                                # Extract the B part from A:BXC or A:B_C patterns
                                if has_x:
                                    separator_index = zone_part.find('X')
                                else:
                                    separator_index = zone_part.find('_')
                                
                                b_part = zone_part[:separator_index]
                                if b_part:
                                    current_area_id = b_part
                            else:
                                # For A:B pattern, use the whole zone part
                                current_area_id = zone_part
                    
                    # Only include directions for surfaces in this area
                    for surface_name, data in glazing_data_from_csv.items():
                        # Extract area ID from surface name using new generalized logic
                        surface_area_id = None
                        if ":" in surface_name:
                            parts = surface_name.split(":")
                            if len(parts) > 1:
                                zone_part = parts[1]
                                # Use same logic as the new grouping system for consistency
                                has_x = 'X' in zone_part
                                has_underscore = '_' in zone_part
                                
                                if has_x or has_underscore:
                                    # Extract the B part from A:BXC or A:B_C patterns
                                    if has_x:
                                        separator_index = zone_part.find('X')
                                    else:
                                        separator_index = zone_part.find('_')
                                    
                                    b_part = zone_part[:separator_index]
                                    if b_part:
                                        surface_area_id = b_part
                                else:
                                    # For A:B pattern, use the whole zone part
                                    surface_area_id = zone_part
                        
                        if surface_area_id == current_area_id and 'CardinalDirection' in data:
                            direction = data['CardinalDirection']
                            if direction and direction != "-":
                                window_directions.add(direction)
        
        # Define custom sort order for directions (clockwise from North)
        direction_order = {'North': 0, 'East': 1, 'South': 2, 'West': 3}
        
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
        <b>Floor Name:</b> {floor_id}<br/>
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
def generate_area_report_pdf(floor_id: str, area_data: List[Dict[str, Any]], 
                           output_filename: str, total_floor_area: float = 0.0, 
                           project_name: str = "-", run_id: str = "-", 
                           city_name: str = "-", area_name: str = "-", 
                           wall_mass_per_area: float = 0.0, location: str = "-", 
                           areas_data=None, glazing_data: List[Dict[str, Any]] = None) -> bool:
    """
    Generate a PDF report with area information, including a header and separate glazing table.
    
    This function provides backward compatibility while using the new refactored architecture.

    Args:
        floor_id (str): The floor ID for the report.
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
    logger.info(f"PDF GENERATOR DEBUG - Starting PDF generation for floor '{floor_id}'")
    logger.info(f"PDF GENERATOR DEBUG - Output file: {output_filename}")
    logger.info(f"PDF GENERATOR DEBUG - Area data length: {len(area_data) if area_data else 0}")
    logger.info(f"PDF GENERATOR DEBUG - Glazing data length: {len(glazing_data) if glazing_data else 0}")
    
    try:
        generator = AreaReportGenerator(
            project_name=project_name,
            run_id=run_id,
            city_name=city_name,
            area_name=area_name
        )
        
        logger.info(f"PDF GENERATOR DEBUG - Calling generator.generate_report for floor '{floor_id}'")
        
        result = generator.generate_report(
            floor_id=floor_id,
            area_data=area_data,
            output_filename=output_filename,
            total_floor_area=total_floor_area,
            wall_mass_per_area=wall_mass_per_area,
            location=location,
            areas_data=areas_data,
            glazing_data=glazing_data
        )
        
        logger.info(f"PDF GENERATOR DEBUG - Generator result for floor '{floor_id}': {result}")
        return result
        
    except Exception as e:
        logger.error(f"Error in generate_area_report_pdf for floor '{floor_id}': {type(e).__name__} - {str(e)}", exc_info=True)
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
        # Show '-' for missing U-values instead of defaulting to 0
        u_value_to_format = row.get('weighted_u_value') or row.get('u_value')
        if u_value_to_format is not None:
            u_value = f"{u_value_to_format:.3f}"
        else:
            u_value = "-"

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
                          project_name: str = "-", run_id: str = "-",
                          city_name: str = "-", area_name: str = "-", 
                          is_office_iso: bool = True) -> bool:
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
    logger.info(f"AREA GENERATOR DEBUG - Starting generate_area_reports")
    logger.info(f"AREA GENERATOR DEBUG - Output dir: {output_dir}")
    logger.info(f"AREA GENERATOR DEBUG - Areas data type: {type(areas_data)}")
    
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
            logger.info(f"AREA REPORT DEBUG - Processing {len(areas_data.areas_by_zone)} zones from area_parser")
            logger.info(f"AREA REPORT DEBUG - Sample zone IDs: {list(areas_data.areas_by_zone.keys())[:10]}")
            logger.info(f"AREA REPORT DEBUG - Is office ISO: {is_office_iso}")
            for zone_id, zone_data in areas_data.areas_by_zone.items():
                if is_office_iso:
                    # For office ISO: each zone gets its individual floor area
                    floor_area = zone_data.get("floor_area", 0.0)
                    multiplier = zone_data.get("multiplier", 1)
                    total_area = floor_area * multiplier
                    area_floor_totals[zone_id] = total_area
                    logger.info(f"AREA REPORT DEBUG - Zone {zone_id}: floor_area={floor_area}, multiplier={multiplier}, total={total_area}")
                else:
                    # For non-office ISO: group by floor_id as before
                    floor_id = zone_data.get("floor_id", "unknown")
                    if floor_id not in area_floor_totals:
                        area_totals = areas_data.get_area_totals(floor_id)
                        calculated_total = area_totals.get("total_floor_area", 0.0)
                        area_floor_totals[floor_id] = calculated_total
                        logger.info(f"AREA REPORT DEBUG - Floor {floor_id} total from get_area_totals(): {calculated_total}")
                        
                        # Also log individual zone contributions for debugging
                        zone_floor_area = zone_data.get("floor_area", 0.0)
                        zone_multiplier = zone_data.get("multiplier", 1)
                        logger.info(f"AREA REPORT DEBUG - Zone {zone_id} contributes: floor_area={zone_floor_area}, multiplier={zone_multiplier}")
        else:
            for zone_id, zone_data in zones.items():
                if is_office_iso:
                    # For office ISO: individual zones
                    floor_area = zone_data.get("floor_area", 0.0)
                    multiplier = zone_data.get("multiplier", 1)
                    area_floor_totals[zone_id] = floor_area * multiplier
                else:
                    # For non-office ISO: group by floor_id
                    floor_id = None
                    if hasattr(areas_data, 'get') and isinstance(areas_data.get(zone_id), dict):
                        floor_id = areas_data.get(zone_id, {}).get("floor_id", "unknown")

                    if floor_id:
                        if floor_id not in area_floor_totals:
                            area_floor_totals[floor_id] = 0.0

                        floor_area = zone_data.get("floor_area", 0.0)
                        multiplier = zone_data.get("multiplier", 1)
                        area_floor_totals[floor_id] += floor_area * multiplier

        # Use different methods based on ISO type
        if hasattr(areas_data, 'get_area_table_data'):
            if is_office_iso and hasattr(areas_data, 'get_area_table_data_by_individual_zones'):
                logger.info(f"AREA GENERATOR DEBUG - Getting individual zone data for office ISO")
                area_table_data = areas_data.get_area_table_data_by_individual_zones(materials_parser)
                logger.info(f"AREA GENERATOR DEBUG - Individual zone data keys: {list(area_table_data.keys()) if area_table_data else 'None'}")
            else:
                logger.info(f"AREA GENERATOR DEBUG - Getting area table data from areas_data (non-office ISO)")
                area_table_data = areas_data.get_area_table_data(materials_parser)
                logger.info(f"AREA GENERATOR DEBUG - Area table data keys: {list(area_table_data.keys()) if area_table_data else 'None'}")
        else:
            if is_office_iso:
                # For office ISO: each zone gets its own entry
                for zone_id, zone_data in areas_data.items():
                    rows = []
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
                            fallback_type = construction_data["elements"][0].get("element_type", "-")
                            element_type = fallback_type
                        elif not element_type:
                            element_type = "-"

                        row = {
                            "zone": zone_id,
                            "construction": construction_name,
                            "element_type": element_type,
                            "area": total_area,
                            "u_value": construction_data.get("elements", [{}])[0].get("u_value") if construction_data.get("elements") else None
                        }
                        rows.append(row)
                    
                    area_table_data[zone_id] = rows
            else:
                # For non-office ISO: group by floor_id as before
                areas_grouped = defaultdict(dict)
                for zone_id, zone_data in areas_data.items():
                    floor_id = zone_data.get("floor_id", "unknown")
                    if floor_id not in areas_grouped:
                        areas_grouped[floor_id] = {}
                    areas_grouped[floor_id][zone_id] = zone_data

                for floor_id, area_zones in areas_grouped.items():
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
                                fallback_type = construction_data["elements"][0].get("element_type", "-")
                                element_type = fallback_type
                            elif not element_type:
                                element_type = "-"

                            row = {
                                "zone": zone_id,
                                "construction": construction_name,
                                "element_type": element_type,
                                "area": total_area,
                                "u_value": construction_data.get("elements", [{}])[0].get("u_value") if construction_data.get("elements") else None
                            }
                            rows.append(row)

                    area_table_data[floor_id] = rows

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
                    floor_id = item.get('floor_id')
                    location = item.get('location', '-')
                    if floor_id:
                        area_locations[floor_id] = location
            except Exception as e_hval:
                logger.warning(f"Could not retrieve area H values for area reports: {e_hval}", exc_info=True)

        entity_label = "individual zones" if is_office_iso else "areas"
        logger.info(f"AREA GENERATOR DEBUG - Processing {len(area_table_data)} {entity_label} for PDF generation")
        
        # Debug zone filtering comparison
        if hasattr(areas_data, 'areas_by_zone'):
            total_zones_in_area_parser = len(areas_data.areas_by_zone)
            zones_in_table_data = len(area_table_data)
            logger.info(f"ZONE FILTERING DEBUG - Total zones in area_parser: {total_zones_in_area_parser}")
            logger.info(f"ZONE FILTERING DEBUG - Zones in table data: {zones_in_table_data}")
            logger.info(f"ZONE FILTERING DEBUG - Missing zones: {total_zones_in_area_parser - zones_in_table_data}")
            
            # Sample the missing zones
            area_parser_zone_ids = set(areas_data.areas_by_zone.keys())
            table_data_zone_ids = set(area_table_data.keys())
            missing_zones = area_parser_zone_ids - table_data_zone_ids
            logger.info(f"ZONE FILTERING DEBUG - Sample missing zone IDs (first 10): {list(missing_zones)[:10]}")
            
            # Check if any of the problematic zones are missing
            problematic_zones = ["02XED:17XCR", "02XED:11XCR", "02XED:10XCR"]
            for zone_id in problematic_zones:
                if zone_id in missing_zones:
                    logger.error(f"ZONE FILTERING DEBUG - Problematic zone '{zone_id}' is missing from table data!")
                    if zone_id in areas_data.areas_by_zone:
                        zone_data = areas_data.areas_by_zone[zone_id]
                        logger.info(f"ZONE FILTERING DEBUG - Missing zone '{zone_id}' data in area_parser: {zone_data}")
                elif zone_id in table_data_zone_ids:
                    logger.info(f"ZONE FILTERING DEBUG - Problematic zone '{zone_id}' found in table data")
                else:
                    logger.warning(f"ZONE FILTERING DEBUG - Problematic zone '{zone_id}' not found in either area_parser or table data")
        
        for entity_id, merged_rows in area_table_data.items():
            logger.info(f"AREA GENERATOR DEBUG - Processing {entity_label[:-1]} '{entity_id}' with {len(merged_rows)} rows")
            total_floor_area = area_floor_totals.get(entity_id, 0.0)
            logger.info(f"AREA GENERATOR DEBUG - {entity_label[:-1].title()} '{entity_id}' total floor area: {total_floor_area}")

            wall_mass_per_area = 0.0
            largest_ext_wall_area = 0.0
            largest_ext_wall_construction = None

            external_wall_candidates = []
            for row in merged_rows:
                raw_element_type = row.get('element_type', '')
                cleaned_type_str = _clean_element_type(raw_element_type).lower()
                current_area = row.get('area', 0.0)
                construction_name = row.get('construction', '')

                if 'external wall' in cleaned_type_str:
                    external_wall_candidates.append({
                        'construction': construction_name,
                        'area': current_area,
                        'zone': row.get('zone', ''),
                        'element_type': cleaned_type_str
                    })
                    
                    if current_area > largest_ext_wall_area:
                        largest_ext_wall_area = current_area
                        largest_ext_wall_construction = construction_name

            if largest_ext_wall_construction and materials_parser:
                try:
                    wall_mass_per_area = materials_parser.calculate_construction_mass_per_area(largest_ext_wall_construction)
                except Exception as e_mass:
                    logger.warning(f"Error calculating wall mass for entity '{entity_id}', construction '{largest_ext_wall_construction}': {e_mass}", exc_info=True)
            elif largest_ext_wall_construction:
                logger.warning(f"Materials parser not available to calculate wall mass for construction '{largest_ext_wall_construction}'")

            # For location, use floor_id for lookup even in office ISO (area_locations is keyed by floor_id)
            if is_office_iso:
                # For office ISO, try to get floor_id from zone data for location lookup
                location = "-"
                if hasattr(areas_data, 'areas_by_zone') and entity_id in areas_data.areas_by_zone:
                    floor_id_for_location = areas_data.areas_by_zone[entity_id].get("floor_id", "unknown")
                    location = area_locations.get(floor_id_for_location, "-")
            else:
                location = area_locations.get(entity_id, "-")

            # Create a safe filename from entity_id by replacing invalid characters
            safe_entity_id = entity_id.replace(":", "_").replace("/", "_").replace("\\", "_")
            output_file = output_path / f"{safe_entity_id}.pdf"

            # Create a temporary object to hold the glazing data
            class TempAreasData:
                def __init__(self, glazing_data):
                    self.glazing_data_from_csv = glazing_data

            temp_areas_data = TempAreasData(glazing_data_from_csv)

            # Get glazing data for this entity
            if is_office_iso:
                # For office ISO, glazing data might be keyed by floor_id, so we need to find the correct floor_id
                entity_glazing_data = []
                if hasattr(areas_data, 'areas_by_zone') and entity_id in areas_data.areas_by_zone:
                    floor_id_for_glazing = areas_data.areas_by_zone[entity_id].get("floor_id", "unknown")
                    entity_glazing_data = glazing_table_data.get(floor_id_for_glazing, [])
            else:
                entity_glazing_data = glazing_table_data.get(entity_id, [])

            # Check if there's actual data to generate a report with
            has_construction_data = merged_rows and len(merged_rows) > 0
            has_glazing_data = entity_glazing_data and len(entity_glazing_data) > 0
            has_floor_area = total_floor_area > 0.0
            
            if not has_construction_data and not has_glazing_data and not has_floor_area:
                logger.warning(f"AREA GENERATOR DEBUG - Skipping report generation for {entity_label[:-1]} '{entity_id}' - no data available")
                logger.info(f"AREA GENERATOR DEBUG - Construction data: {len(merged_rows) if merged_rows else 0} rows")
                logger.info(f"AREA GENERATOR DEBUG - Glazing data: {len(entity_glazing_data) if entity_glazing_data else 0} rows")
                logger.info(f"AREA GENERATOR DEBUG - Total floor area: {total_floor_area}")
                continue  # Skip this entity and move to the next one
            
            logger.info(f"AREA GENERATOR DEBUG - Generating PDF for {entity_label[:-1]} '{entity_id}' (safe filename: '{safe_entity_id}') at: {output_file}")
            logger.info(f"AREA GENERATOR DEBUG - Entity data rows: {len(merged_rows)}, Glazing data: {len(entity_glazing_data) if entity_glazing_data else 0}")
            
            success = generate_area_report_pdf(
                floor_id=entity_id,
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
                glazing_data=entity_glazing_data  # Pass the glazing data for this entity
            )
            
            logger.info(f"AREA GENERATOR DEBUG - PDF generation for {entity_label[:-1]} '{entity_id}' success: {success}")
            
            if not success:
                all_reports_successful = False
                logger.error(f"Failed to generate PDF report for {entity_label[:-1]} ID: {entity_id}")

        return all_reports_successful

    except ImportError as ie:
        logger.error(f"Failed to import a required module (e.g., MaterialsParser) for generating area reports: {ie}", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred in generate_area_reports: {type(e).__name__} - {str(e)}", exc_info=True)
        return False

def generate_area_reports_by_base_zone(areas_data, output_dir: str = "output/areas",
                                     project_name: str = "-", run_id: str = "-",
                                     city_name: str = "-", area_name: str = "-") -> bool:
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
            # Log first few base zone keys for debugging
            sample_keys = list(base_zone_table_data.keys())[:3]
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
                    floor_id = item.get('floor_id')
                    location = item.get('location', '-')
                    if floor_id:
                        area_locations[floor_id] = location
            except Exception as e_hval:
                logger.warning(f"Could not retrieve area H values for base zone area reports: {e_hval}", exc_info=True)

        # Generate reports for each base zone
        for base_zone_id, merged_rows in base_zone_table_data.items():
            # Skip zones without construction data (non-HVAC zones)
            if not merged_rows:
                logger.info(f"Skipping area report for base zone '{base_zone_id}': No construction data (likely non-HVAC zone)")
                continue
                
            total_floor_area = base_zone_floor_totals.get(base_zone_id, 0.0)

            # Calculate wall mass per area (using same logic as original function)
            wall_mass_per_area = 0.0
            largest_ext_wall_area = 0.0
            largest_ext_wall_construction = None

            external_wall_candidates = []
            for row in merged_rows:
                raw_element_type = row.get('element_type', '')
                cleaned_type_str = _clean_element_type(raw_element_type).lower()
                current_area = row.get('area', 0.0)
                construction_name = row.get('construction', '')

                if 'external wall' in cleaned_type_str:
                    external_wall_candidates.append({
                        'construction': construction_name,
                        'area': current_area,
                        'zone': row.get('zone', ''),
                        'element_type': cleaned_type_str
                    })
                    
                    if current_area > largest_ext_wall_area:
                        largest_ext_wall_area = current_area
                        largest_ext_wall_construction = construction_name

            if largest_ext_wall_construction and materials_parser:
                try:
                    wall_mass_per_area = materials_parser.calculate_construction_mass_per_area(largest_ext_wall_construction)
                except Exception as e_mass:
                    logger.warning(f"Error calculating mass per area for construction '{largest_ext_wall_construction}' in base zone '{base_zone_id}': {e_mass}")
                    wall_mass_per_area = 0.0

            # Determine location (use first floor_id from zones in this base zone)
            location = "Unknown"
            if base_zone_id in base_zone_groupings and base_zone_groupings[base_zone_id]:
                first_zone_id = base_zone_groupings[base_zone_id][0]
                if hasattr(areas_data, 'areas_by_zone') and first_zone_id in areas_data.areas_by_zone:
                    first_floor_id = areas_data.areas_by_zone[first_zone_id].get("floor_id", "unknown")
                    location = area_locations.get(first_floor_id, "-")

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
                        zone_floor_id = areas_data.areas_by_zone[zone_id].get("floor_id", "unknown")
                        area_glazing = glazing_table_data.get(zone_floor_id, [])
                        # Filter glazing data for this specific zone
                        zone_glazing = [g for g in area_glazing if g.get('zone') == zone_id]
                        base_zone_glazing_data.extend(zone_glazing)

            zones_in_group = base_zone_groupings.get(base_zone_id, [])

            success = generate_area_report_pdf(
                floor_id=base_zone_id,
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
