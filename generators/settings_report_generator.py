from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.colors import Color
from reportlab.lib.enums import TA_LEFT, TA_CENTER
import datetime
from utils.logging_config import get_logger
from pathlib import Path
from utils.hebrew_text_utils import get_hebrew_font_name
from utils.logo_utils import create_logo_image
from generators.shared_design_system import (
    COLORS, FONTS, FONT_SIZES, LAYOUT,
    create_standard_table_style, create_title_style, create_section_title_style,
    create_standardized_header
)

logger = get_logger(__name__)

def format_dict_value(value_dict):
    """Format dictionary values for display in the report"""
    if not value_dict:
        return "Not specified"

    if isinstance(value_dict, dict) and any(key in ['January', 'February', 'March'] for key in value_dict.keys()):
        month_order = [
            'January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December'
        ]
        return "<br/>".join(f"{month}: {value_dict[month]}" for month in month_order if month in value_dict)

    if isinstance(value_dict, dict) and any(key in ['start_month', 'end_month', 'location'] for key in value_dict.keys()):
        lines = []
        if 'start_month' in value_dict and 'start_day' in value_dict:
            lines.append(f"Start Date: {value_dict['start_month']}/{value_dict['start_day']}")
        if 'end_month' in value_dict and 'end_day' in value_dict:
            lines.append(f"End Date: {value_dict['end_month']}/{value_dict['end_day']}")
        if 'location' in value_dict:
            lines.append(f"Location: {value_dict['location']}")

        for k, v in value_dict.items():
            if k not in ['start_month', 'start_day', 'end_month', 'end_day', 'location'] and v is not None:
                lines.append(f"{k.replace('_', ' ').title()}: {v}")

        return "<br/>".join(lines)

    if isinstance(value_dict, dict) and any(key in ['start', 'end'] for key in value_dict.keys()):
        lines = []
        if 'start' in value_dict:
            lines.append(f"Start: {value_dict['start']}")
        if 'end' in value_dict:
            lines.append(f"End: {value_dict['end']}")
        return "<br/>".join(lines)

    if isinstance(value_dict, dict) and any(key in ['ground', 'daylighting'] for key in value_dict.keys()):
        lines = []
        if 'ground' in value_dict:
            lines.append(f"Ground Reflected: {value_dict['ground']}")
        if 'daylighting' in value_dict:
            lines.append(f"Daylighting: {value_dict['daylighting']}")
        return "<br/>".join(lines)

    return "<br/>".join([f"{k}: {v}" for k, v in value_dict.items()])

def _make_table(data, col_widths, style):
    """Helper function to create and style a table"""
    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(style)
    return table

def _process_category(category_name, settings, story, category_style, header_style, 
                     key_cell_style, value_cell_style, doc):
    """Process a single category and add it to the story"""
    
    # Special handling for DesignBuilder category
    if category_name == 'designbuilder':
        if settings and any(settings.values()):
            story.append(Paragraph("DesignBuilder Metadata", category_style))
            
            db_param_map = {
                'version': "DesignBuilder Version",
                'date': "File Generation Date", 
                'time': "File Generation Time",
                'geometry_convention': "Geometry Convention",
                'zone_geometry_surface_areas': "Zone Geometry Surface Areas",
                'zone_volume_calculation': "Zone Volume Calculation",
                'zone_floor_area_calculation': "Zone Floor Area Calculation",
                'window_wall_ratio': "Window to Wall Ratio Method"
            }
            
            table_data = [
                [Paragraph('Parameter', header_style), Paragraph('Value', header_style)]
            ]
            
            for key, display_name in db_param_map.items():
                value = settings.get(key)
                if value not in (None, ''):
                    table_data.append([
                        Paragraph(display_name, key_cell_style),
                        Paragraph(str(value), value_cell_style)
                    ])
            
            if len(table_data) > 1:
                col_widths = [doc.width * 0.30, doc.width * 0.70]
                table_style = _get_standard_table_style()
                story.append(_make_table(table_data, col_widths, table_style))
                story.append(Spacer(1, LAYOUT['spacing']['section']))
        # If no DesignBuilder metadata found, skip the section entirely
        return
    
    # Standard category processing with improved display names
    category_display_names = {
        'version': 'Version Information',
        'location': 'Site Location',
        'algorithms': 'Calculation Algorithms',
        'simulation': 'Simulation Parameters',
        'site': 'Site Properties'
    }
    
    display_category = category_display_names.get(category_name, category_name.replace('_', ' ').title())
    story.append(Paragraph(display_category, category_style))
    
    table_data = [
        [Paragraph('Setting', header_style), Paragraph('Value', header_style)]
    ]
    
    # Improved key display names for algorithms
    algorithm_key_names = {
        'surface_convection_inside': 'Surface Convection Algorithm (Inside)',
        'surface_convection_outside': 'Surface Convection Algorithm (Outside)', 
        'heat_balance': 'Heat Balance Algorithm'
    }
    
    for key, value in settings.items():
        if category_name == 'algorithms' and key in algorithm_key_names:
            display_key = algorithm_key_names[key]
        else:
            display_key = key.replace('_', ' ').title()
        
        if isinstance(value, dict):
            formatted_value = format_dict_value(value)
            value_para = Paragraph(formatted_value, value_cell_style)
        elif value is None:
            value_para = Paragraph("Not specified", value_cell_style)
        else:
            value_para = Paragraph(str(value), value_cell_style)
        
        key_para = Paragraph(display_key, key_cell_style)
        table_data.append([key_para, value_para])
    
    col_widths = [doc.width * 0.30, doc.width * 0.70]
    table_style = _get_standard_table_style()
    story.append(_make_table(table_data, col_widths, table_style))
    story.append(Spacer(1, 0.8*cm))

def _get_standard_table_style():
    """Get the standard table style for settings tables"""
    style = create_standard_table_style()
    # Add custom styling for settings tables
    style.add('VALIGN', (0, 1), (-1, -1), 'TOP')
    style.add('ALIGN', (0, 1), (0, -1), 'LEFT')
    style.add('ALIGN', (1, 1), (1, -1), 'LEFT')
    style.add('BOTTOMPADDING', (0, 0), (-1, 0), 6)
    style.add('TOPPADDING', (0, 0), (-1, 0), 6)
    return style

def generate_settings_report_pdf(settings_data, output_filename="output/settings.pdf",
                                 project_name: str = "N/A", run_id: str = "N/A",
                                 city_name: str = "N/A", area_name: str = "N/A"):
    """
    Generates a PDF report showing all extracted settings, including a header.

    Args:
        settings_data (dict): Dictionary of settings organized by category.
        output_filename (str): The name of the output PDF file.
        project_name (str): Name of the project.
        run_id (str): Identifier for the current run.

    Returns:
        bool: True if report generation was successful, False otherwise.
    """
    doc = None
    try:
        output_file_path = Path(output_filename)
        output_dir = output_file_path.parent
        if not output_dir.exists():
            try:
                output_dir.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                error_message = f"Error creating output directory '{output_dir}' for settings report: {e.strerror}"
                logger.error(error_message, exc_info=True)
                return False
        elif not output_dir.is_dir():
            error_message = f"Error: Output path '{output_dir}' for settings report exists but is not a directory."
            logger.error(error_message)
            return False

        doc = SimpleDocTemplate(str(output_file_path),
                               pagesize=landscape(A4),
                               leftMargin=1.5*cm,
                               rightMargin=1.5*cm,
                               topMargin=1.5*cm,
                               bottomMargin=1.5*cm)

        styles = getSampleStyleSheet()
        story = []

        # Add standardized header
        report_title = "Settings"
        header_elements = create_standardized_header(
            doc=doc,
            project_name=project_name,
            run_id=run_id,
            city_name=city_name,
            area_name=area_name,
            report_title=report_title
        )
        story.extend(header_elements)

        title_style = create_title_style(styles)
        title_style.spaceBefore = LAYOUT['spacing']['standard']
        title_style.spaceAfter = LAYOUT['spacing']['large']
        story.append(Paragraph(f"{report_title} Report", title_style))

        header_style = ParagraphStyle(
            name='TableHeader',
            parent=styles['Normal'],
            fontSize=10,
            leading=12,
            fontName='Helvetica-Bold',
            alignment=TA_CENTER,
            textColor=COLORS['white']
        )

        key_cell_style = ParagraphStyle(
            name='KeyCell',
            parent=styles['Normal'],
            fontSize=9,
            leading=11,
            spaceBefore=4,
            spaceAfter=4,
            wordWrap='CJK',
            alignment=TA_LEFT
        )

        value_cell_style = ParagraphStyle(
            name='ValueCell',
            parent=styles['Normal'],
            fontSize=9,
            leading=11,
            spaceBefore=4,
            spaceAfter=4,
            wordWrap='CJK',
            alignment=TA_LEFT
        )

        category_style = create_section_title_style(styles)
        category_style.fontSize = 14
        category_style.textColor = colors.darkblue
        category_style.spaceBefore = LAYOUT['spacing']['standard']
        category_style.spaceAfter = LAYOUT['spacing']['small']

        # Define the order in which categories should appear
        category_order = [
            'designbuilder',
            'version', 
            'location',
            'algorithms',
            'simulation',
            'site'
        ]
        
        # Process categories in the defined order
        processed_categories = set()
        
        for category_name in category_order:
            if category_name in settings_data:
                _process_category(category_name, settings_data[category_name], story, 
                                category_style, header_style, key_cell_style, value_cell_style, doc)
                processed_categories.add(category_name)
        
        # Process any remaining categories not in the order list
        for category_name, settings in settings_data.items():
            if category_name not in processed_categories:
                _process_category(category_name, settings, story, 
                                category_style, header_style, key_cell_style, value_cell_style, doc)

        if not story:
            logger.warning("No content was added to the story for settings report. PDF will be empty or may fail.")
            story.append(Paragraph("No settings data found to generate the report.", styles['Normal']))

        doc.build(story)
        return True
    except (IOError, OSError) as e:
        error_message = f"Error during file operation for Settings report '{output_filename}': {e.strerror}"
        logger.error(error_message, exc_info=True)
        return False
    except Exception as e:
        error_message = f"An unexpected error occurred while generating Settings report '{output_filename}': {type(e).__name__} - {str(e)}"
        logger.error(error_message, exc_info=True)
        if doc and hasattr(doc, 'canv') and doc.canv:
            try:
                if not doc.canv._saved: doc.canv.save()
            except Exception as save_err:
                logger.error(f"Could not save PDF {output_filename} via doc.canv.save() after an error: {save_err}", exc_info=True)
        return False
    finally:
        pass
