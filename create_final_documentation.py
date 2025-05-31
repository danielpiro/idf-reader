#!/usr/bin/env python3
"""
Final version of PDF documentation with proper text wrapping and improved spacing.
"""

from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle, Image, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib.colors import HexColor, black, white, blue, darkblue, lightgrey
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Circle
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics import renderPDF
from reportlab.platypus.flowables import HRFlowable
from datetime import datetime
import os

class FinalDocumentGenerator:
    def __init__(self):
        # Color scheme
        self.primary_blue = HexColor('#2563eb')
        self.secondary_blue = HexColor('#3b82f6')
        self.accent_blue = HexColor('#60a5fa')
        self.dark_gray = HexColor('#1f2937')
        self.medium_gray = HexColor('#6b7280')
        self.light_gray = HexColor('#f3f4f6')
        self.success_green = HexColor('#10b981')
        self.warning_orange = HexColor('#f59e0b')
        
        # Set up styles
        self.styles = getSampleStyleSheet()
        self._create_custom_styles()
    
    def _create_custom_styles(self):
        """Create custom paragraph styles with proper text wrapping"""
        
        # Title page styles
        self.title_style = ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            spaceAfter=20,
            spaceBefore=10,
            alignment=TA_CENTER,
            textColor=self.primary_blue,
            fontName='Helvetica-Bold'
        )
        
        self.subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=self.styles['Heading2'],
            fontSize=14,
            spaceAfter=20,
            alignment=TA_CENTER,
            textColor=self.medium_gray,
            fontName='Helvetica'
        )
        
        # Section headers
        self.section_header_style = ParagraphStyle(
            'SectionHeader',
            parent=self.styles['Heading1'],
            fontSize=16,
            spaceBefore=20,
            spaceAfter=12,
            textColor=self.primary_blue,
            fontName='Helvetica-Bold',
            borderWidth=0,
            borderPadding=8,
            backColor=self.light_gray,
            leftIndent=8,
            rightIndent=8
        )
        
        self.subsection_header_style = ParagraphStyle(
            'SubsectionHeader',
            parent=self.styles['Heading2'],
            fontSize=13,
            spaceBefore=12,
            spaceAfter=8,
            textColor=self.secondary_blue,
            fontName='Helvetica-Bold'
        )
        
        self.subsubsection_header_style = ParagraphStyle(
            'SubSubsectionHeader',
            parent=self.styles['Heading3'],
            fontSize=11,
            spaceBefore=10,
            spaceAfter=6,
            textColor=self.dark_gray,
            fontName='Helvetica-Bold'
        )
        
        # Body text styles
        self.body_style = ParagraphStyle(
            'ProfessionalBody',
            parent=self.styles['Normal'],
            fontSize=10,
            spaceBefore=4,
            spaceAfter=4,
            alignment=TA_JUSTIFY,
            leftIndent=0,
            rightIndent=0,
            fontName='Helvetica',
            leading=12
        )
        
        # Special style for report descriptions with better spacing
        self.description_style = ParagraphStyle(
            'DescriptionStyle',
            parent=self.styles['Normal'],
            fontSize=10,
            spaceBefore=4,
            spaceAfter=4,
            alignment=TA_JUSTIFY,
            leftIndent=15,
            rightIndent=0,
            fontName='Helvetica',
            leading=13
        )
        
        # Special style for table cells to ensure wrapping
        self.table_cell_style = ParagraphStyle(
            'TableCell',
            parent=self.styles['Normal'],
            fontSize=9,
            spaceBefore=2,
            spaceAfter=2,
            alignment=TA_LEFT,
            fontName='Helvetica',
            leading=11,
            wordWrap='LTR'
        )
        
        self.bullet_style = ParagraphStyle(
            'ProfessionalBullet',
            parent=self.styles['Normal'],
            fontSize=10,
            spaceBefore=2,
            spaceAfter=2,
            leftIndent=20,
            bulletIndent=12,
            fontName='Helvetica',
            leading=12
        )
        
        self.code_style = ParagraphStyle(
            'CodeStyle',
            parent=self.styles['Normal'],
            fontSize=9,
            spaceBefore=4,
            spaceAfter=4,
            fontName='Courier',
            backColor=self.light_gray,
            borderColor=self.medium_gray,
            borderWidth=1,
            borderPadding=6,
            leftIndent=8,
            rightIndent=8,
            leading=11
        )
        
        self.highlight_box_style = ParagraphStyle(
            'HighlightBox',
            parent=self.styles['Normal'],
            fontSize=10,
            spaceBefore=8,
            spaceAfter=8,
            fontName='Helvetica',
            backColor=HexColor('#eff6ff'),
            borderColor=self.secondary_blue,
            borderWidth=1,
            borderPadding=10,
            leftIndent=8,
            rightIndent=8,
            leading=12
        )

    def create_simple_workflow_diagram(self):
        """Create a simplified workflow diagram that fits better"""
        drawing = Drawing(450, 280)
        
        # Colors
        primary_color = self.primary_blue
        text_color = white
        
        # Simplified workflow steps
        steps = [
            {"text": "Input\nSetup", "x": 60, "y": 220},
            {"text": "Weather\nData", "x": 150, "y": 220},
            {"text": "Energy\nSim", "x": 240, "y": 220},
            {"text": "Data\nProcess", "x": 330, "y": 220},
            {"text": "Analysis", "x": 330, "y": 140},
            {"text": "Reports", "x": 240, "y": 140},
            {"text": "Output", "x": 150, "y": 140}
        ]
        
        # Draw workflow boxes
        for i, step in enumerate(steps):
            rect = Rect(step["x"] - 30, step["y"] - 20, 60, 40, 
                       fillColor=primary_color, strokeColor=primary_color)
            drawing.add(rect)
            
            # Add text
            lines = step["text"].split('\n')
            for j, line in enumerate(lines):
                drawing.add(String(step["x"], step["y"] + 5 - (j * 10), line,
                                 fontSize=9, fillColor=text_color, textAnchor='middle', fontName='Helvetica-Bold'))
        
        # Draw simplified arrows
        arrow_pairs = [
            (90, 220, 120, 220),   # 1 -> 2
            (180, 220, 210, 220),  # 2 -> 3
            (270, 220, 300, 220),  # 3 -> 4
            (330, 200, 330, 160),  # 4 -> 5 (down)
            (300, 140, 270, 140),  # 5 -> 6 (left)
            (210, 140, 180, 140),  # 6 -> 7 (left)
        ]
        
        for x1, y1, x2, y2 in arrow_pairs:
            line = Line(x1, y1, x2, y2, strokeColor=self.dark_gray, strokeWidth=2)
            drawing.add(line)
            
            # Simple arrowheads
            if x1 < x2:  # Right arrow
                drawing.add(Line(x2-6, y2-3, x2, y2, strokeColor=self.dark_gray, strokeWidth=2))
                drawing.add(Line(x2-6, y2+3, x2, y2, strokeColor=self.dark_gray, strokeWidth=2))
            elif x1 > x2:  # Left arrow
                drawing.add(Line(x2+6, y2-3, x2, y2, strokeColor=self.dark_gray, strokeWidth=2))
                drawing.add(Line(x2+6, y2+3, x2, y2, strokeColor=self.dark_gray, strokeWidth=2))
            elif y1 > y2:  # Down arrow
                drawing.add(Line(x2-3, y2+6, x2, y2, strokeColor=self.dark_gray, strokeWidth=2))
                drawing.add(Line(x2+3, y2+6, x2, y2, strokeColor=self.dark_gray, strokeWidth=2))
        
        return drawing

    def create_final_documentation(self, output_filename="Final_IDF_Report_Generator_Documentation.pdf"):
        """Create the final documentation PDF with proper text wrapping"""
        
        # Create document with proper margins
        doc = SimpleDocTemplate(
            output_filename,
            pagesize=A4,
            rightMargin=1.5*cm,
            leftMargin=1.5*cm,
            topMargin=2*cm,
            bottomMargin=2*cm,
            title="IDF Report Generator Documentation",
            author="IDF Report Generator Team",
            subject="Program Documentation for External Testers"
        )
        
        story = []
        
        # Title Page
        story.append(Spacer(1, 1*inch))
        story.append(Paragraph("Professional Building Analysis Suite", self.subsection_header_style))
        story.append(Spacer(1, 0.2*inch))
        story.append(Paragraph("IDF Report Generator", self.title_style))
        story.append(HRFlowable(width="60%", thickness=2, color=self.primary_blue, 
                               spaceBefore=8, spaceAfter=15, hAlign='CENTER'))
        story.append(Paragraph("Program Documentation for External Testers", self.subtitle_style))
        
        version_info = f"""
        <b>Version:</b> 2.0 | <b>Date:</b> {datetime.now().strftime('%B %d, %Y')}<br/>
        <b>Audience:</b> External Testing Teams
        """
        story.append(Paragraph(version_info, self.highlight_box_style))
        story.append(Spacer(1, 0.8*inch))
        
        summary_text = """
        <b>Purpose:</b> This guide provides external testing teams with comprehensive 
        information about the IDF Report Generator program, including workflow, 
        report interpretation, and testing procedures.
        """
        story.append(Paragraph(summary_text, self.highlight_box_style))
        story.append(PageBreak())
        
        # Table of Contents
        story.append(Paragraph("Table of Contents", self.section_header_style))
        story.append(Spacer(1, 10))
        
        toc_data = [
            ["Section", "Page"],
            ["I. Program Overview", "3"],
            ["II. System Architecture & Workflow", "3"],
            ["III. Generated Reports Guide", "4"],
            ["IV. Testing Guidelines", "6"],
            ["V. Troubleshooting", "7"],
            ["VI. Technical Glossary", "7"]
        ]
        
        toc_table = Table(toc_data, colWidths=[4*inch, 1*inch])
        toc_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), self.primary_blue),
            ('TEXTCOLOR', (0,0), (-1,0), white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 11),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('ALIGN', (1,0), (1,-1), 'CENTER'),
            ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,1), (-1,-1), 10),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [white, self.light_gray]),
            ('GRID', (0,0), (-1,-1), 0.5, self.medium_gray),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('TOPPADDING', (0,0), (-1,-1), 6)
        ]))
        
        story.append(toc_table)
        story.append(PageBreak())
        
        # I. Program Overview
        story.append(Paragraph("I. Program Overview", self.section_header_style))
        
        overview_text = """
        The IDF Report Generator processes EnergyPlus IDF files to produce comprehensive 
        building performance reports. It automates simulation execution, data extraction, 
        and professional PDF report generation for building energy analysis.
        """
        story.append(Paragraph(overview_text, self.body_style))
        
        # Core features - using list format instead of table to avoid overflow
        story.append(Paragraph("Key Features:", self.subsection_header_style))
        
        features = [
            "Automated EnergyPlus simulation with weather data integration",
            "Intelligent data extraction from IDF and simulation results", 
            "Professional PDF report generation with analysis",
            "Hebrew and English text support for international projects",
            "ISO 2017/2023 energy rating calculations for compliance"
        ]
        
        for feature in features:
            story.append(Paragraph(f"• {feature}", self.bullet_style))
        
        # II. System Architecture & Workflow
        story.append(Paragraph("II. System Architecture & Workflow", self.section_header_style))
        
        workflow_text = """
        The program follows a seven-step process:
        """
        story.append(Paragraph(workflow_text, self.body_style))
        
        # Add workflow diagram
        workflow_diagram = self.create_simple_workflow_diagram()
        story.append(workflow_diagram)
        story.append(Spacer(1, 10))
        
        # Workflow steps
        workflow_steps = [
            "Input Setup: User specifies IDF file, EnergyPlus path, city, ISO type",
            "Weather Data: System selects appropriate EPW file based on location",
            "Energy Simulation: Automated EnergyPlus execution with optimized settings",
            "Data Processing: Extract simulation results and IDF content",
            "Analysis: Process data into meaningful performance metrics",
            "Reports: Generate professional PDFs across eight categories",
            "Output: Save reports with validation and quality checks"
        ]
        
        for i, step in enumerate(workflow_steps, 1):
            story.append(Paragraph(f"{i}. {step}", self.bullet_style))
        
        story.append(PageBreak())
        
        # III. Generated Reports Guide
        story.append(Paragraph("III. Generated Reports Guide", self.section_header_style))
        
        story.append(Paragraph("Report Location & Structure", self.subsection_header_style))
        
        location_text = """
        Reports are saved in a 'reports' subfolder within your selected output directory. 
        Each report includes the project name and timestamp.
        """
        story.append(Paragraph(location_text, self.body_style))
        
        story.append(Paragraph("Individual Report Descriptions", self.subsection_header_style))
        
        # Instead of a table, use a structured list format to avoid overflow with improved spacing
        reports_list = [
            {
                "file": "settings.pdf",
                "title": "Project Settings & Configuration",
                "description": "Documents project metadata, simulation parameters, user selections, and compliance settings for traceability."
            },
            {
                "file": "schedules.pdf", 
                "title": "Operational Schedules Analysis",
                "description": "Analyzes building operation patterns including occupancy, lighting, equipment timing and HVAC schedules."
            },
            {
                "file": "loads.pdf",
                "title": "Internal Heat Gains & Load Analysis", 
                "description": "Provides zone-by-zone breakdown of internal loads from people, equipment, and lighting with peak demands."
            },
            {
                "file": "materials.pdf",
                "title": "Building Materials & Thermal Properties",
                "description": "Complete catalog of construction materials with thermal properties, R-values, and construction assemblies."
            },
            {
                "file": "glazing.pdf",
                "title": "Fenestration & Glazing Systems",
                "description": "Details window performance including U-values, SHGC, frame properties, and shading systems analysis."
            },
            {
                "file": "lighting.pdf",
                "title": "Lighting Systems & Energy Analysis",
                "description": "Covers power densities, control systems, daylighting integration, and annual energy consumption."
            },
            {
                "file": "area_loss.pdf",
                "title": "Thermal Loss Analysis",
                "description": "Quantifies heat transfer through building envelope components to identify thermal weak points."
            },
            {
                "file": "energy-rating.pdf",
                "title": "Energy Performance Rating",
                "description": "Provides ISO compliance rating with energy benchmarking, performance grade, and improvement recommendations."
            },
            {
                "file": "zones/[name].pdf",
                "title": "Individual Zone Reports",
                "description": "Zone-specific analysis including area, volume, surfaces, loads, and detailed performance breakdowns."
            }
        ]
        
        for i, report in enumerate(reports_list, 1):
            story.append(KeepTogether([
                Paragraph(f"{i}. {report['title']}", self.subsubsection_header_style),
                Paragraph(f"<b>File:</b> <font color='blue'>{report['file']}</font>", self.code_style),
                Spacer(1, 4),
                Paragraph("<b>Description:</b>", self.body_style),
                Paragraph(report['description'], self.description_style),
                Spacer(1, 10)
            ]))
        
        story.append(Paragraph("Key Testing Focus Areas", self.subsection_header_style))
        
        testing_focus = [
            "Energy Rating Reports: Critical for compliance - verify calculation accuracy",
            "Data Consistency: Check that related reports show consistent information",
            "Report Completeness: Ensure all expected sections and data are present",
            "Format Quality: Verify professional appearance and readability"
        ]
        
        for focus in testing_focus:
            story.append(Paragraph(f"• {focus}", self.bullet_style))
        
        story.append(PageBreak())
        
        # IV. Testing Guidelines
        story.append(Paragraph("IV. Quality Assurance & Testing Guidelines", self.section_header_style))
        
        testing_categories = [
            ("Input Validation Testing", [
                "Test various IDF file formats and sizes",
                "Verify error handling for invalid files", 
                "Check city/ISO selection validation",
                "Test file path and permission handling"
            ]),
            ("Simulation Accuracy Testing", [
                "Compare results with manual EnergyPlus runs",
                "Verify weather data selection logic",
                "Test completion under various conditions",
                "Validate energy consumption calculations"
            ]),
            ("Report Quality Testing", [
                "Check formatting and completeness",
                "Verify data consistency across reports",
                "Test edge case handling",
                "Validate multilingual text support"
            ]),
            ("Performance & Reliability Testing", [
                "Test with large building models",
                "Monitor memory and processing time",
                "Test error recovery and cancellation",
                "Verify concurrent processing capabilities"
            ])
        ]
        
        for category, items in testing_categories:
            story.append(Paragraph(category, self.subsubsection_header_style))
            for item in items:
                story.append(Paragraph(f"✓ {item}", self.bullet_style))
            story.append(Spacer(1, 6))
        
        story.append(PageBreak())
        
        # V. Troubleshooting
        story.append(Paragraph("V. Troubleshooting & Error Resolution", self.section_header_style))
        
        # Use list format instead of table
        story.append(Paragraph("Common Issues and Solutions:", self.subsection_header_style))
        
        issues_list = [
            ("Installation Problems", "Program won't start, missing dependencies", "Check Python installation, install required packages, verify system requirements"),
            ("File Access Errors", "Cannot read IDF file, permission denied", "Verify file format and permissions, ensure file is not locked by another program"),
            ("Simulation Failures", "EnergyPlus errors, simulation timeout", "Validate IDF file integrity, check EnergyPlus installation, review simulation parameters"),
            ("Report Generation Issues", "Missing reports, formatting errors", "Check output directory permissions, verify template files, review log messages"),
            ("Performance Problems", "Slow processing, memory errors", "Monitor system resources, optimize IDF complexity, check available disk space")
        ]
        
        for problem, symptoms, solutions in issues_list:
            story.append(KeepTogether([
                Paragraph(f"<b>{problem}</b>", self.subsubsection_header_style),
                Paragraph(f"<b>Symptoms:</b> {symptoms}", self.body_style),
                Paragraph(f"<b>Solutions:</b> {solutions}", self.body_style),
                Spacer(1, 8)
            ]))
        
        # VI. Technical Glossary
        story.append(Paragraph("VI. Technical Glossary", self.section_header_style))
        
        glossary_terms = [
            ("IDF (Input Data File)", "EnergyPlus building model file containing geometry, materials, systems, and operational parameters"),
            ("EnergyPlus", "U.S. Department of Energy's building energy simulation engine for heating, cooling, lighting, and ventilation calculations"),
            ("EPW (EnergyPlus Weather File)", "Standardized hourly weather data file for specific geographic locations used in energy simulations"),
            ("U-value (Thermal Transmittance)", "Heat transfer rate through building elements (W/m²·K) - lower values indicate better insulation performance"),
            ("SHGC (Solar Heat Gain Coefficient)", "Fraction of solar radiation transmitted through windows (0-1 scale) - affects cooling loads"),
            ("Thermal Zone", "Building space or group of spaces with similar thermal conditions controlled by a single thermostat"),
            ("Schedule Objects", "Time-dependent patterns defining operation of building systems, occupancy, or environmental conditions"),
            ("eplustbl.csv", "EnergyPlus tabular output file containing comprehensive simulation results and energy consumption data"),
            ("ISO Energy Standards", "International calculation methods for building energy performance (2017/2023 versions affect methodology)")
        ]
        
        for term, definition in glossary_terms:
            story.append(Paragraph(f"<b>{term}:</b> {definition}", self.body_style))
            story.append(Spacer(1, 4))
        
        # System Requirements
        story.append(Paragraph("System Requirements", self.subsection_header_style))
        
        requirements_text = """
        <b>Minimum Requirements:</b><br/>
        • Operating System: Windows 10 or later<br/>
        • Python: Version 3.8 or later<br/>
        • Memory: 4 GB RAM minimum, 8 GB recommended<br/>
        • Storage: 2 GB available disk space<br/>
        • EnergyPlus: Version 9.0 or later<br/><br/>
        
        <b>Required Python Packages:</b><br/>
        reportlab, eppy, pandas, tkinter, customtkinter
        """
        story.append(Paragraph(requirements_text, self.highlight_box_style))
        
        # Footer
        story.append(Spacer(1, 0.5*inch))
        story.append(HRFlowable(width="100%", thickness=1, color=self.medium_gray))
        
        footer_text = f"""
        <b>Documentation v2.0</b> | Generated: {datetime.now().strftime('%B %d, %Y')}<br/>
        For technical support, contact the development team.
        """
        story.append(Paragraph(footer_text, self.body_style))
        
        # Build the PDF
        doc.build(story)
        print(f"\n✅ Final documentation created successfully!")
        print(f"📄 Output file: {output_filename}")
        print(f"🔧 Fixed all text overflow issues with proper formatting")
        print(f"📋 Improved spacing between labels and descriptions")

def main():
    """Generate the final documentation"""
    generator = FinalDocumentGenerator()
    generator.create_final_documentation()

if __name__ == "__main__":
    main()