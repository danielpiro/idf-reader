"""
Generates reports for area-specific information extracted from IDF files.
"""
from typing import Dict, Any
from pathlib import Path
from collections import defaultdict
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

def generate_area_detail_report_pdf(area_id: str, zones_data: Dict[str, Any], output_path: str) -> bool:
    """
    Generate a detailed PDF report for a specific area.
    
    Args:
        area_id: The ID of the area to generate report for
        zones_data: Dictionary of zone information for this area
        output_path: Path where to save the PDF report
        
    Returns:
        bool: True if report generation was successful, False otherwise
    """
    try:
        doc = SimpleDocTemplate(output_path, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []
        
        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30
        )
        story.append(Paragraph(f"Area {area_id} Report", title_style))
        
        # Calculate area metrics
        total_floor_area = 0
        total_volume = 0
        # Calculate metrics only from zone data portion
        zone_info = {k: v for k, v in zones_data.items() if isinstance(v, dict) and "properties" in v}
        for zone_data in zone_info.values():
            props = zone_data["properties"]
            multiplier = props.get("multiplier", 1)
            total_floor_area += props.get("floor_area", 0) * multiplier
            total_volume += props.get("volume", 0) * multiplier
        
        # Area Summary
        story.append(Paragraph("Area Summary", styles["Heading2"]))
        story.append(Spacer(1, 12))
        
        summary_data = [
            ["Total Zones", str(len(zones_data))],
            ["Total Floor Area", f"{total_floor_area:.2f} m²"],
            ["Total Volume", f"{total_volume:.2f} m³"],
            ["Average Zone Size", f"{total_floor_area/len(zones_data):.2f} m²"]
        ]
        
        summary_table = Table(summary_data, colWidths=[200, 200])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 20))
        
        # Element Details
        story.append(Paragraph("Zone Elements", styles["Heading2"]))
        story.append(Spacer(1, 12))
        
        # Get element data from each zone
        area_elements = []
        for zone_data in zone_info.values():
            if isinstance(zone_data.get("element_data"), list):
                area_elements.extend(zone_data["element_data"])
        
        if area_elements:
            element_data = [["Zone", "Element Name", "Type", "Area (m²)", "Conductivity (W/m·K)", "Area * Conductivity (W/K)"]]
            for elem in area_elements:
                element_data.append([
                    elem["zone"],
                    elem["element_name"],
                    elem["element_type"],
                    f"{elem['area']:.2f}",
                    f"{elem['conductivity']:.3f}",
                    f"{elem['area_conductivity']:.2f}"
                ])
            
            element_table = Table(element_data, colWidths=[80, 120, 80, 80, 80, 80])
            element_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BACKGROUND', (0, 1), (-1, -1), colors.whitesmoke),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(element_table)
            story.append(Spacer(1, 20))
        
        # Zone Details
        story.append(Paragraph("Zone Summary", styles["Heading2"]))
        story.append(Spacer(1, 12))
        
        zone_data = [["Zone ID", "Floor Area", "Volume", "Multiplier"]]
        for zone_id, data in sorted(zone_info.items()):
            if isinstance(data, dict) and "properties" in data:
                props = data["properties"]
                zone_data.append([
                    zone_id,
                    f"{props['floor_area']:.2f} m²",
                    f"{props['volume']:.2f} m³",
                    str(props['multiplier'])
                ])
        
        zone_table = Table(zone_data, colWidths=[200, 100, 100, 100])
        zone_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(zone_table)
        
        # Generate PDF
        doc.build(story)
        return True
        
    except Exception as e:
        print(f"Error generating area detail report PDF: {e}")
        return False

def generate_area_reports(areas_data: Dict[str, Any], output_dir: str = "output/zones") -> bool:
    """
    Generate individual PDF reports for each area.
    
    Args:
        areas_data: Dictionary of area information by zone
        output_dir: Directory where to save the PDF reports
        
    Returns:
        bool: True if all report generation was successful, False otherwise
    """
    try:
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        # Group zones by area and process reports
        areas_grouped = defaultdict(dict)
        for zone_id, zone_data in areas_data.items():
            area_id = zone_data["area_id"]
            if area_id not in areas_grouped:
                areas_grouped[area_id] = {}
            areas_grouped[area_id][zone_id] = zone_data
        
        # Generate individual area reports
        successes = []
        for area_id, area_zones in areas_grouped.items():
            
            success = generate_area_detail_report_pdf(
                area_id,
                area_zones,  # Pass complete zone data including element_data
                str(output_path / f"area_{area_id}.pdf")
            )
            successes.append(success)
        
        return all(successes)
        
    except Exception as e:
        print(f"Error generating area reports: {e}")
        return False