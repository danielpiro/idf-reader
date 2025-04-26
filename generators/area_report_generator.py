"""
Generates reports for area-specific information extracted from IDF files.
"""
from typing import Dict, Any, List
from pathlib import Path
from collections import defaultdict
import re
import datetime
from colorama import Fore, Style, init
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import letter, landscape, A4
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

# Initialize colorama
init(autoreset=True)

def generate_area_report_pdf(area_id: str, area_data: List[Dict[str, Any]],
                             output_filename: str, total_floor_area: float = 0.0,
                             project_name: str = "N/A", run_id: str = "N/A",
                             wall_mass_per_area: float = 0.0) -> bool: # Changed parameter name
    """
    Generate a PDF report with area information, including a header.

    Args:
        area_id (str): The area ID for the report.
        area_data (List[Dict[str, Any]]): List of area data rows for this area.
        output_filename (str): Path where to save the PDF report.
        total_floor_area (float): The total floor area for this area.
        project_name (str): Name of the project.
        run_id (str): Identifier for the current run.
        wall_mass_per_area (float): Mass per area (kg/m²) of the largest external wall's construction.

    Returns:
        bool: True if report generation was successful, False otherwise.
    """
    try:
        # Ensure output directory exists
        output_path = Path(output_filename).parent
        output_path.mkdir(exist_ok=True)
        
        # Create PDF document
        doc = SimpleDocTemplate(output_filename, pagesize=landscape(A4))
        styles = getSampleStyleSheet()
        story = []
        
        # Header Information
        now = datetime.datetime.now()
        header_style = ParagraphStyle(
            'HeaderInfo',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.black, # Changed from darkgrey to black
            alignment=2 # Right aligned
        )
        header_text = f"""
        Project: {project_name}<br/>
        Run ID: {run_id}<br/>
        Date: {now.strftime('%Y-%m-%d %H:%M:%S')}<br/>
        Report: Area {area_id} - Thermal Properties
        """
        story.append(Paragraph(header_text, header_style))
        story.append(Spacer(1, 5)) # Add some space after header

        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=20
        )
        story.append(Paragraph(f"Area {area_id} - Thermal Properties Report", title_style))
        
        # Data is now pre-merged before calling this function
        merged_data = area_data # Use the pre-merged data passed in
        
        # Wall mass is now calculated and passed in
        # wall_mass = 0.0 # Removed placeholder calculation
        
        # Generate summary section as a card (Table)
        summary_content_style = ParagraphStyle(
            'SummaryContent',
            parent=styles['Normal'],
            fontSize=10,
            leading=12
        )
        
        summary_text = f"""
        <b>Area Summary:</b><br/>
        ------------------------------------<br/>
        <b>Area Name:</b> {area_id}<br/>
        <b>Total Area:</b> {total_floor_area:.2f} m²<br/>
        <b>Location:</b> Unknown<br/>
        <b>Directions:</b> N, S, E, W<br/>
        <b>Largest Ext. Wall Mass:</b> {wall_mass_per_area:.2f} kg/m²
        """
        
        summary_paragraph = Paragraph(summary_text, summary_content_style)
        
        # Create a table to act as a card with a border
        summary_table_data = [[summary_paragraph]]
        summary_table = Table(summary_table_data, colWidths=[doc.width - 2*cm]) # Adjust width as needed
        
        summary_table_style = TableStyle([
            ('BOX', (0, 0), (-1, -1), 1, colors.black), # Border around the cell
            ('PADDING', (0, 0), (-1, -1), 10),         # Padding inside the cell
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke) # Optional background color
        ])
        
        summary_table.setStyle(summary_table_style)
        
        story.append(summary_table)
        story.append(Spacer(1, 15))

        # Create cell styles for better formatting
        cell_style = ParagraphStyle(
            'CellStyle',
            parent=styles['Normal'],
            fontSize=9,  # Smaller font for better fit
            leading=10,  # Reduced line spacing
            spaceBefore=0,
            spaceAfter=0
        )
        
        header_style = ParagraphStyle(
            'HeaderStyle',
            parent=styles['Heading4'],
            fontSize=10,
            alignment=1,  # Center alignment
            textColor=colors.whitesmoke
        )
        
        # Header row for the table as Paragraphs for consistent styling
        headers = [
            Paragraph("Zone", header_style),
            Paragraph("Construction", header_style),
            Paragraph("Element type", header_style),
            Paragraph("Area", header_style),
            Paragraph("U-Value", header_style),
            Paragraph("Area * U-Value", header_style)
        ]
        
        # Prepare table data
        table_data = [headers]
        
        # Sort rows by zone and construction for better readability
        sorted_rows = sorted(merged_data, key=lambda x: (x['zone'], x['construction']))
        
        # Track the last zone seen to avoid duplication
        last_zone = None
        
        # Format values and add to table
        for row in sorted_rows:
            # Format construction name with line breaks
            construction_text = format_construction_name(row['construction'])

            # --- DEBUG PRINT ADDED ---
            # Check for the specific construction name after cleaning/merging
            if row.get('construction') == "6+6+6":
                # print(f"\nDEBUG REPORT GEN: Data for '6+6+6' row before formatting:\n{row}\n")
                pass
            # --- END DEBUG PRINT ---

            # Create zone cell - only show zone if different from previous row
            if row['zone'] != last_zone:
                zone_cell = Paragraph(row['zone'], cell_style)
                last_zone = row['zone']
            else:
                zone_cell = ""  # Empty cell if same zone as previous row
                
            construction_cell = Paragraph(construction_text, cell_style)
            element_type_cell = Paragraph(row['element_type'], cell_style)
            
            # Format numeric values with proper alignment
            area_value = f"{row['area']:.2f}"
            # Use weighted_u_value if available (for aggregated glazing), otherwise fallback to u_value
            u_value_to_format = row.get('weighted_u_value', row.get('u_value', 0.0))
            u_value = f"{u_value_to_format:.3f}"
            area_u_value = f"{row['area_u_value']:.2f}"
            # area_loss_value = f"{row['area_loss']:.2f}" # Removed as area_loss is no longer used
            
            # Add all cells to row
            table_data.append([
                zone_cell,
                construction_cell,
                element_type_cell,
                area_value,
                u_value,
                area_u_value
            ])
        
        # Create the table with carefully adjusted column widths
        col_widths = [
            4.5*cm,     # Zone - increased for long zone names
            7.0*cm,     # Construction - increased for long names with breaks
            3.0*cm,     # Element type
            2.3*cm,     # Area
            2.3*cm,     # U-Value
            3.0*cm      # Area * U-Value
        ]
        
        # Create table with data and column widths
        area_table = Table(table_data, colWidths=col_widths, repeatRows=1)
        
        # Style the table
        table_style = TableStyle([
            # Header style
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            # Data rows - numbers right aligned
            ('ALIGN', (3, 1), (-1, -1), 'RIGHT'),
            # Grid style
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            # Enhanced cell padding for better spacing
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            # Alternating row colors
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgrey]),
            # Extra - adjust vertical alignment
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ])
        
        area_table.setStyle(table_style)
        story.append(area_table)
        
        # Build the document
        doc.build(story)
        return True
        
    except Exception as e:
        print(f"{Fore.RED}Error generating area report PDF for Area {area_id}: {e}{Style.RESET_ALL}")
        import traceback
        traceback.print_exc()
        return False

from typing import Optional # Add Optional for type hinting

def merge_reversed_constructions(area_data: List[Dict[str, Any]],
                                 materials_parser: Optional[Any] = None, # Use 'Any' to avoid circular import
                                 surfaces: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Merge constructions with _Rev suffix with their base construction.
    Skips merging for glazing elements if materials_parser and surfaces are provided.

    Args:
        area_data: List of area data rows.
        materials_parser: Instance of MaterialsParser to determine element type (optional).
        surfaces: Dictionary of surface data (optional, required if materials_parser is provided).

    Returns:
        List[Dict[str, Any]]: Merged area data.
    """
    if not materials_parser or not surfaces:
        print(f"{Fore.YELLOW}Warning: MaterialsParser or surfaces not provided to merge_reversed_constructions. Glazing check skipped.{Style.RESET_ALL}")

    merged_dict = {}

    for row in area_data:
        zone = row['zone']
        construction = row['construction']
        element_type = row.get('element_type', 'Unknown') # Get existing type if available

        # Determine base construction name
        base_construction = construction
        is_reversed = False
        rev_patterns = [r'_Rev$', r'_Reversed$', r'_rev$', r'_reversed$']
        for pattern in rev_patterns:
            if re.search(pattern, construction):
                base_construction = re.sub(pattern, '', construction)
                is_reversed = True
                break

        # --- Skip merging for Glazing if parser available ---
        should_merge = True
        if materials_parser and surfaces:
            try:
                # Determine element type accurately using the parser
                # Ensure materials_parser is not None before calling its method
                current_element_type = materials_parser._get_element_type(construction, surfaces)
                if current_element_type == "Glazing":
                    should_merge = False
                    # Use original construction name if not merging glazing
                    base_construction = construction
                    is_reversed = False # Treat as non-reversed if not merging
            except Exception as e:
                print(f"{Fore.YELLOW}Warning: Error checking element type for '{construction}' in merge: {e}{Style.RESET_ALL}")
        # --- End Glazing Check ---

        # Create key based on whether we are merging or not
        # If not merging (glazing), use the original construction name in the key
        key_construction = base_construction if (should_merge and is_reversed) else construction
        key = f"{zone}_{key_construction}"

        if key not in merged_dict:
            # First time seeing this combination (or it's glazing we're not merging)
            merged_dict[key] = row.copy()
            # Ensure the construction name in the stored dict is the one used for the key
            merged_dict[key]['construction'] = key_construction
            # Remove area_loss if it exists
            merged_dict[key].pop('area_loss', None)
        elif should_merge and is_reversed:
            # Merge with existing entry (only if it's a reversed non-glazing construction)
            existing = merged_dict[key]
            existing['area'] += row['area']
            existing['area_u_value'] += row['area_u_value']
            # Area loss is being removed, so no need to merge it.
            # existing['area_loss'] += row['area_loss'] # Removed

            # Recalculate weighted U-value based on merged area and area*U-value
            # Note: This assumes 'u_value' or 'weighted_u_value' exists in the row.
            # A simple weighted average calculation:
            current_u = row.get('weighted_u_value', row.get('u_value', 0.0))
            existing_u = existing.get('weighted_u_value', existing.get('u_value', 0.0))
            new_total_area = existing['area'] # Area already updated above
            # Update area_u_value first
            # existing['area_u_value'] += row['area_u_value'] # Already done above

            # Weighted U-value calculation needs care. Let's recalculate from total area_u_value / total_area later.
            # For now, just ensure the field exists if either input had it.
            if 'weighted_u_value' in row or 'weighted_u_value' in existing:
                 existing['weighted_u_value'] = existing.get('weighted_u_value', 0.0) # Placeholder, recalculated below
            # Remove area_loss if it exists
            existing.pop('area_loss', None)


    # --- Final processing and U-value recalculation ---
    final_list = []
    for key, merged_row in merged_dict.items():
        total_area = merged_row.get('area', 0.0)
        total_area_u_value = merged_row.get('area_u_value', 0.0)

        # Recalculate weighted U-value accurately
        if total_area > 0:
            merged_row['weighted_u_value'] = total_area_u_value / total_area
        elif 'u_value' in merged_row: # Fallback if area is somehow zero
             merged_row['weighted_u_value'] = merged_row['u_value']
        else:
             merged_row['weighted_u_value'] = 0.0 # Ensure field exists

        # Remove area_loss just in case it slipped through
        merged_row.pop('area_loss', None)

        final_list.append(merged_row)

    return final_list

def format_construction_name(construction: str) -> str:
    """
    Format construction name for better display in the table.
    Adds line breaks for better readability.
    
    Args:
        construction: Construction name
        
    Returns:
        str: Formatted construction name
    """
    # If the name is long, insert line breaks at meaningful places
    if len(construction) > 18:  # Reduced threshold for breaking
        # Try to break at spaces
        parts = construction.split(' ')
        if len(parts) > 1:
            # Try to find optimal break points
            result = ""
            current_line = ""
            
            for i, part in enumerate(parts):
                if len(current_line) + len(part) + 1 > 18:  # +1 for space
                    if current_line:
                        result += current_line + "<br/>"
                        current_line = part
                    else:
                        # Single part too long
                        result += part + "<br/>"
                        current_line = ""
                else:
                    if current_line:
                        current_line += " " + part
                    else:
                        current_line = part
            
            # Add the last line
            if current_line:
                result += current_line
                
            return result
        else:
            # No spaces, insert break every ~15 characters
            result = ""
            for i in range(0, len(construction), 15):
                result += construction[i:min(i+15, len(construction))]
                if i + 15 < len(construction):
                    result += "<br/>"
            return result
    
    return construction

def generate_area_reports(areas_data, output_dir: str = "output/areas",
                          project_name: str = "N/A", run_id: str = "N/A") -> bool:
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
    try:
        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True, parents=True)
        
        # Get table data for each area
        from parsers.materials_parser import MaterialsParser
        from utils.data_loader import DataLoader
        
        # Initialize materials parser if needed
        materials_parser = None
        data_loader = None
        
        # Get the data loader from the areas_data if possible
        if hasattr(areas_data, 'data_loader'):
            data_loader = areas_data.data_loader
        
        # Create a materials parser to identify element types
        try:
            if data_loader:
                materials_parser = MaterialsParser(data_loader)
                materials_parser.process_idf(None)
        except Exception as e:
            print(f"{Fore.YELLOW}Warning: Could not initialize MaterialsParser: {e}{Style.RESET_ALL}")
            materials_parser = None
        
        # Get surfaces if we have a data_loader
        surfaces = {}
        zones = {}
        if data_loader:
            surfaces = data_loader.get_surfaces()
            zones = data_loader.get_zones()
        
        # Convert the data to table rows by area
        area_table_data = {}
        
        # Calculate total floor area for each area
        area_floor_totals = {}
        
        # First, calculate total floor area by area ID
        if hasattr(areas_data, 'areas_by_zone'):
            # If AreaParser is available, use its data structure
            for zone_id, zone_data in areas_data.areas_by_zone.items():
                area_id = zone_data.get("area_id", "unknown")
                if area_id not in area_floor_totals:
                    area_totals = areas_data.get_area_totals(area_id)
                    area_floor_totals[area_id] = area_totals.get("total_floor_area", 0.0)
        else:
            # Otherwise calculate from zones dictionary
            for zone_id, zone_data in zones.items():
                area_id = None
                if hasattr(areas_data, 'get') and isinstance(areas_data.get(zone_id), dict):
                    area_id = areas_data.get(zone_id, {}).get("area_id", "unknown")
                
                if area_id:
                    if area_id not in area_floor_totals:
                        area_floor_totals[area_id] = 0.0
                    
                    # Add zone's floor area to area total
                    floor_area = zone_data.get("floor_area", 0.0)
                    multiplier = zone_data.get("multiplier", 1)
                    area_floor_totals[area_id] += floor_area * multiplier
        
        if hasattr(areas_data, 'get_area_table_data'):
            # Pass the materials_parser to get_area_table_data
            area_table_data = areas_data.get_area_table_data(materials_parser)
        else:
            # Group zones by area and process reports
            areas_grouped = defaultdict(dict)
            for zone_id, zone_data in areas_data.items():
                area_id = zone_data.get("area_id", "unknown")
                if area_id not in areas_grouped:
                    areas_grouped[area_id] = {}
                areas_grouped[area_id][zone_id] = zone_data
            
            # For each area, process all zone constructions
            for area_id, area_zones in areas_grouped.items():
                rows = []
                
                for zone_id, zone_data in area_zones.items():
                    # Process constructions for this zone
                    for construction_name, construction_data in zone_data.get("constructions", {}).items():
                        # Sum all elements for this construction
                        total_area = construction_data.get("total_area", 0.0)
                        total_u_value = construction_data.get("total_u_value", 0.0)
                        
                        # Determine element type using proper detection
                        element_type = None  # Initialize to None to track if detection succeeded
                        
                        # Try using MaterialsParser first for element type detection
                        if materials_parser and surfaces:
                            try:
                                element_type = materials_parser._get_element_type(construction_name, surfaces)
                            except Exception:
                                pass
                        
                        # Check if this is a glazing construction if element_type is still None
                        if not element_type:
                            for element in construction_data.get("elements", []):
                                surface_name = element.get("surface_name")
                                if surface_name and surface_name in surfaces:
                                    surface = surfaces[surface_name]
                                    if surface.get('is_glazing', False):
                                        element_type = "Glazing"
                                        break
                        
                        # Fallback: only use if all other methods fail
                        if not element_type and construction_data.get("elements"):
                            fallback_type = construction_data["elements"][0].get("element_type", "Unknown")
                            element_type = fallback_type
                        elif not element_type:
                            element_type = "Unknown"
                        
                        # Add row for this construction
                        row = {
                            "zone": zone_id,
                            "construction": construction_name,
                            "element_type": element_type,
                            "area": total_area,
                            "u_value": construction_data.get("elements", [{}])[0].get("u_value", 0.0) if construction_data.get("elements") else 0.0,
                            "area_u_value": total_u_value,
                            "area_loss": 0.0
                        }
                        rows.append(row)
                
                area_table_data[area_id] = rows
        
        # --- Merge reversed constructions (excluding glazing) ---
        merged_area_table_data = {}
        for area_id, rows in area_table_data.items():
            if materials_parser and surfaces:
                 merged_area_table_data[area_id] = merge_reversed_constructions(rows, materials_parser, surfaces)
            else:
                 # Fallback if parser/surfaces not available
                 merged_area_table_data[area_id] = merge_reversed_constructions(rows)


        # --- Generate a report for each area ---
        successes = []
        for area_id, merged_rows in merged_area_table_data.items():
            # Get total floor area for this area
            total_floor_area = area_floor_totals.get(area_id, 0.0)

            # --- Calculate Wall Mass Per Area ---
            wall_mass_per_area = 0.0 # Initialize mass per area
            largest_ext_wall_area = 0.0
            largest_ext_wall_construction = None

            # Find the largest external wall in this area's data
            for row in merged_rows:
                # Ensure element_type exists and is checked case-insensitively
                element_type = row.get('element_type', '').lower()
                if element_type == 'external wall':
                    current_area = row.get('area', 0.0)
                    if current_area > largest_ext_wall_area:
                        largest_ext_wall_area = current_area # Keep track of largest area for identification
                        largest_ext_wall_construction = row.get('construction')

            # Calculate mass per area if the largest wall was found and parser is available
            if largest_ext_wall_construction and materials_parser:
                try:
                    # Replicate the mass calculation logic here, including the conductivity check
                    construction_data = materials_parser.constructions.get(largest_ext_wall_construction)
                    if construction_data:
                        calculated_mass_per_area = 0.0
                        found_low_conductivity = False # Flag for the conductivity rule
                        for layer_id in construction_data.material_layers:
                            material_data = materials_parser.materials.get(layer_id)
                            if material_data:
                                layer_mass = material_data.density * material_data.thickness
                                # Apply the conductivity rule specifically for external walls
                                if not found_low_conductivity: # Only apply to the first low-conductivity layer found
                                    if material_data.conductivity < 0.2 and material_data.conductivity != 0: # Check conductivity is < 0.2 but not zero
                                        layer_mass /= 2
                                        found_low_conductivity = True # Set flag so rule is only applied once per construction
                                calculated_mass_per_area += layer_mass
                        wall_mass_per_area = calculated_mass_per_area
                    else:
                         print(f"{Fore.YELLOW}Warning: Construction data not found for '{largest_ext_wall_construction}' during mass calculation.{Style.RESET_ALL}")

                except Exception as e:
                    print(f"{Fore.YELLOW}Warning: Could not calculate wall mass per area for area {area_id}, construction '{largest_ext_wall_construction}': {e}{Style.RESET_ALL}")
                    import traceback
                    traceback.print_exc() # Add traceback for debugging calculation errors
            elif largest_ext_wall_construction:
                 print(f"{Fore.YELLOW}Warning: MaterialsParser not available to calculate wall mass per area for area {area_id}.{Style.RESET_ALL}")
            # --- End Wall Mass Per Area Calculation ---

            # Define output filename
            output_file = output_path / f"area_{area_id}.pdf"

            # Generate the PDF report for this area, passing the calculated wall_mass_per_area
            success = generate_area_report_pdf(
                area_id=area_id,
                area_data=merged_rows, # Use merged rows
                output_filename=str(output_file),
                total_floor_area=total_floor_area,
                project_name=project_name,
                run_id=run_id,
                wall_mass_per_area=wall_mass_per_area # Pass calculated mass per area
            )
            successes.append(success)

            if success:
                print(f"{Fore.GREEN}Successfully generated area report for Area {area_id}: {output_file}{Style.RESET_ALL}")
            else:
                print(f"{Fore.RED}Failed to generate report for Area {area_id}{Style.RESET_ALL}")
            
        return all(successes)
        
    except Exception as e:
        print(f"{Fore.RED}Error processing area data for reports: {e}{Style.RESET_ALL}")
        import traceback
        traceback.print_exc()
        return False
