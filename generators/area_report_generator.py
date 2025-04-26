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
                             project_name: str = "N/A", run_id: str = "N/A") -> bool:
    """
    Generate a PDF report with area information, including a header.
    
    Args:
        area_id (str): The area ID for the report.
        area_data (List[Dict[str, Any]]): List of area data rows for this area.
        output_filename (str): Path where to save the PDF report.
        total_floor_area (float): The total floor area for this area.
        project_name (str): Name of the project.
        run_id (str): Identifier for the current run.

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
        
        # Preprocess data to merge constructions with _Rev suffix
        merged_data = merge_reversed_constructions(area_data)
        
        # Calculate wall mass (placeholder for now)
        wall_mass = 0.0  # This will need actual wall mass calculation implementation later
        
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
        <b>Wall Mass:</b> {wall_mass:.2f} kg
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
            Paragraph("Area * U-Value", header_style),
            Paragraph("Area loss", header_style)
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
            area_loss_value = f"{row['area_loss']:.2f}"
            
            # Add all cells to row
            table_data.append([
                zone_cell,
                construction_cell,
                element_type_cell,
                area_value,
                u_value,
                area_u_value,
                area_loss_value
            ])
        
        # Create the table with carefully adjusted column widths
        col_widths = [
            4.5*cm,     # Zone - increased for long zone names
            7.0*cm,     # Construction - increased for long names with breaks
            3.0*cm,     # Element type
            2.3*cm,     # Area
            2.3*cm,     # U-Value
            3.0*cm,     # Area * U-Value
            2.3*cm      # Area loss
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

def merge_reversed_constructions(area_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Merge constructions with _Rev suffix with their base construction.
    
    Args:
        area_data: List of area data rows
        
    Returns:
        List[Dict[str, Any]]: Merged area data
    """
    # Group data by zone and construction base name (without _Rev)
    merged_dict = {}
    
    for row in area_data:
        zone = row['zone']
        construction = row['construction']
        
        # Check if construction has _Rev or _Reversed suffix
        base_construction = construction
        
        rev_patterns = [r'_Rev$', r'_Reversed$', r'_rev$', r'_reversed$']
        for pattern in rev_patterns:
            if re.search(pattern, construction):
                base_construction = re.sub(pattern, '', construction)
                break
        
        # Create key to identify unique combinations
        key = f"{zone}_{base_construction}"
        
        if key not in merged_dict:
            # First time seeing this combination
            merged_dict[key] = row.copy()
            merged_dict[key]['construction'] = base_construction  # Use base name
        else:
            # Merge with existing entry
            existing = merged_dict[key]
            existing['area'] += row['area']
            existing['area_u_value'] += row['area_u_value']
            existing['area_loss'] += row['area_loss']
            # Also merge weighted_u_value if present, recalculate later
            if 'weighted_u_value' in row:
                 # Temporarily store the sum, will divide by total area later
                 existing['weighted_u_value'] = existing.get('weighted_u_value', 0.0) * (existing['area'] - row['area']) + row['weighted_u_value'] * row['area']


    # --- Recalculate weighted U-value after merging ---
    final_list = []
    for key, merged_row in merged_dict.items():
        total_area = merged_row.get('area', 0.0)
        # Check if weighted_u_value was summed during merge
        if 'weighted_u_value' in merged_row and total_area > 0:
             # If it looks like a sum (product of area*uvalue), divide by total area
             # This assumes the temporary value stored was the sum of area*weighted_u_value
             # A better approach might be to recalculate from area_u_value / area
             merged_row['weighted_u_value'] = merged_row['area_u_value'] / total_area
        elif 'weighted_u_value' not in merged_row and total_area > 0:
             # If weighted_u_value wasn't present initially, calculate it now
             merged_row['weighted_u_value'] = merged_row['area_u_value'] / total_area
        elif 'weighted_u_value' not in merged_row:
             merged_row['weighted_u_value'] = 0.0 # Ensure field exists

        final_list.append(merged_row)


    # Convert back to list
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
        
        # Generate a report for each area
        successes = []
        for area_id, rows in area_table_data.items():
            output_file = output_path / f"area_{area_id}.pdf"
            
            # Get the correct total floor area for the summary
            total_floor_area = area_floor_totals.get(area_id, 0.0)
            
            success = generate_area_report_pdf(
                area_id=area_id, 
                area_data=rows,
                output_filename=str(output_file),
                total_floor_area=total_floor_area,
                project_name=project_name,
                run_id=run_id
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
