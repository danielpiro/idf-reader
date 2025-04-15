"""
Generates PDF reports for storage zone information extracted from IDF files.
"""
from typing import Dict, Any
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

def generate_storage_report_pdf(storage_data: Dict[str, Any], output_path: str) -> bool:
    """
    Generate a PDF report for storage zones.
    
    Args:
        storage_data: Dictionary of storage zone information
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
        story.append(Paragraph("Storage Zones Report", title_style))
        
        # Calculate storage metrics
        total_floor_area = 0
        total_volume = 0
        for zone_data in storage_data.values():
            props = zone_data["properties"]
            multiplier = props.get("multiplier", 1)
            total_floor_area += props.get("floor_area", 0) * multiplier
            total_volume += props.get("volume", 0) * multiplier
        
        # Storage Summary
        story.append(Paragraph("Storage Summary", styles["Heading2"]))
        story.append(Spacer(1, 12))
        
        summary_data = [
            ["Total Storage Zones", str(len(storage_data))],
            ["Total Floor Area", f"{total_floor_area:.2f} m²"],
            ["Total Volume", f"{total_volume:.2f} m³"],
            ["Average Zone Size", f"{total_floor_area/len(storage_data):.2f} m²"]
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
        
        # Zone Details
        story.append(Paragraph("Storage Zone Details", styles["Heading2"]))
        story.append(Spacer(1, 12))
        
        zone_data = [["Zone ID", "Floor Area", "Volume", "Multiplier"]]
        for zone_id, data in sorted(storage_data.items()):
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
        print(f"Error generating storage report PDF: {e}")
        return False