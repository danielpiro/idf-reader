"""
Generates reports for area-specific information extracted from IDF files.
"""
from typing import Dict, Any, List
from pathlib import Path
from collections import defaultdict
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import letter, landscape, A4
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

def generate_area_report_pdf(area_id: str, area_data: List[Dict[str, Any]], output_filename: str) -> bool:
    """
    Generate a PDF report with area information in a consolidated table.
    
    Args:
        area_id: The area ID for the report
        area_data: List of area data rows for this area
        output_filename: Path where to save the PDF report
        
    Returns:
        bool: True if report generation was successful, False otherwise
    """
    try:
        # Ensure output directory exists
        output_path = Path(output_filename).parent
        output_path.mkdir(exist_ok=True)
        
        # Create PDF document
        doc = SimpleDocTemplate(output_filename, pagesize=landscape(A4))
        styles = getSampleStyleSheet()
        story = []
        
        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=20
        )
        story.append(Paragraph(f"Area {area_id} - Thermal Properties Report", title_style))
        story.append(Spacer(1, 10))
        
        # Header row for the table
        headers = ["Zone", "Construction", "Element type", "Area", "Conductivity", 
                   "Area * Conductivity", "Area loss"]
        
        # Prepare table data
        table_data = [headers]
        
        # Sort rows by zone and construction for better readability
        sorted_rows = sorted(area_data, key=lambda x: (x['zone'], x['construction']))
        
        # Format values and add to table
        for row in sorted_rows:
            table_data.append([
                row['zone'],
                row['construction'],
                row['element_type'],
                f"{row['area']:.2f}",
                f"{row['conductivity']:.3f}",
                f"{row['area_conductivity']:.2f}",
                f"{row['area_loss']:.2f}"
            ])
        
        # Create the table
        # Set relative column widths 
        col_widths = [
            4.0*cm,    # Zone
            5.0*cm,    # Construction
            3.0*cm,    # Element type
            2.5*cm,    # Area
            2.5*cm,    # Conductivity
            3.0*cm,    # Area * Conductivity
            2.5*cm     # Area loss
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
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            # Data rows
            ('BACKGROUND', (0, 1), (-1, -1), colors.whitesmoke),
            ('ALIGN', (0, 1), (2, -1), 'LEFT'),      # Text columns left-aligned
            ('ALIGN', (3, 1), (-1, -1), 'RIGHT'),    # Number columns right-aligned
            # Grid style
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            # Cell padding
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            # Alternating row colors for better readability
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgrey])
        ])
        
        area_table.setStyle(table_style)
        story.append(area_table)
        
        # Build the document
        doc.build(story)
        print(f"Successfully generated area report for Area {area_id}: {output_filename}")
        return True
        
    except Exception as e:
        print(f"Error generating area report PDF for Area {area_id}: {e}")
        import traceback
        traceback.print_exc()
        return False

def generate_area_reports(areas_data, output_dir: str = "output/areas") -> bool:
    """
    Generate individual reports for each area with area data in a table format.
    
    Args:
        areas_data: AreaParser instance or dictionary of area information by zone
        output_dir: Directory for output files
        
    Returns:
        bool: True if all report generation was successful, False otherwise
    """
    try:
        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True, parents=True)
        
        # Get table data for each area
        from parsers.materials_parser import MaterialsParser
        
        # Convert the data to table rows by area
        area_table_data = {}
        
        if hasattr(areas_data, 'get_area_table_data'):
            # If we have the AreaParser instance
            area_table_data = areas_data.get_area_table_data()
        else:
            # Process manually from parsed areas dict
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
                        total_conductivity = construction_data.get("total_conductivity", 0.0)
                        
                        # Get element type from first element
                        element_type = "Floor"  # Default
                        if construction_data.get("elements"):
                            element_type = construction_data["elements"][0].get("element_type", "Floor")
                        
                        # Add row for this construction
                        row = {
                            "zone": zone_id,
                            "construction": construction_name,
                            "element_type": element_type,
                            "area": total_area,
                            "conductivity": construction_data.get("elements", [{}])[0].get("conductivity", 0.0) if construction_data.get("elements") else 0.0,
                            "area_conductivity": total_conductivity,
                            "area_loss": 0.0
                        }
                        rows.append(row)
                
                area_table_data[area_id] = rows
        
        # Generate a report for each area
        successes = []
        for area_id, rows in area_table_data.items():
            output_file = output_path / f"area_{area_id}.pdf"
            success = generate_area_report_pdf(area_id, rows, str(output_file))
            successes.append(success)
            
            if not success:
                print(f"Failed to generate report for Area {area_id}")
            
        return all(successes)
        
    except Exception as e:
        print(f"Error processing area data for reports: {e}")
        import traceback
        traceback.print_exc()
        return False