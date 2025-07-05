"""
Unified design system for all PDF reports to ensure consistency and professional appearance.
"""
from reportlab.lib.colors import Color
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.units import cm
from reportlab.platypus import TableStyle, Paragraph
from utils.hebrew_text_utils import get_hebrew_font_name

# Professional Color Palette
COLORS = {
    'primary_blue': Color(0.2, 0.4, 0.7),
    'secondary_blue': Color(0.4, 0.6, 0.85),
    'light_blue': Color(0.9, 0.94, 0.98),
    'dark_gray': Color(0.2, 0.2, 0.2),
    'medium_gray': Color(0.5, 0.5, 0.5),
    'light_gray': Color(0.9, 0.9, 0.9),
    'white': Color(1, 1, 1),
    'border_gray': Color(0.8, 0.8, 0.8),
    'error_red': Color(0.8, 0.2, 0.2),
    'warning_orange': Color(0.9, 0.6, 0.2),
    'success_green': Color(0.2, 0.7, 0.3),
}

# Professional Font System
FONTS = {
    'title': 'Helvetica-Bold',
    'heading': 'Helvetica-Bold',
    'body': 'Helvetica',
    'table_header': 'Helvetica-Bold',
    'table_body': 'Helvetica',
}

FONT_SIZES = {
    'title': 16,
    'heading': 12,
    'body': 10,
    'table_header': 9,
    'table_body': 8,
    'small': 7,
    'large': 14,
}

# Standard Layout Settings
LAYOUT = {
    'margins': {
        'default': 1.0 * cm,
        'narrow': 0.5 * cm,
        'wide': 2.0 * cm,
    },
    'spacing': {
        'standard': 0.5 * cm,
        'small': 0.2 * cm,
        'large': 1.0 * cm,
        'section': 0.8 * cm,
    },
    'logo': {
        'max_width': 4 * cm,
        'max_height': 2 * cm,
        'table_width': 5 * cm,
        'vertical_spacing': 0.3 * cm,  # Space around logo for better alignment
    }
}

def create_standard_table_style(header_rows=1, spans=None):
    """
    Create a professional, consistent table style for all reports.
    
    Args:
        header_rows (int): Number of header rows (default: 1)
        spans (list): List of span tuples for merged cells, e.g., [('SPAN', (0, 0), (2, 0))]
    
    Returns:
        TableStyle: Professionally styled table
    """
    style_commands = []
    
    # Add spans first if provided
    if spans:
        style_commands.extend(spans)
    
    # Header styling
    style_commands.extend([
        ('BACKGROUND', (0, 0), (-1, header_rows-1), COLORS['primary_blue']),
        ('TEXTCOLOR', (0, 0), (-1, header_rows-1), COLORS['white']),
        ('ALIGN', (0, 0), (-1, header_rows-1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, header_rows-1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, header_rows-1), FONTS['table_header']),
        ('FONTSIZE', (0, 0), (-1, header_rows-1), FONT_SIZES['table_header']),
        ('TOPPADDING', (0, 0), (-1, header_rows-1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, header_rows-1), 6),
    ])
    
    # Data rows styling
    style_commands.extend([
        ('FONTNAME', (0, header_rows), (-1, -1), FONTS['table_body']),
        ('FONTSIZE', (0, header_rows), (-1, -1), FONT_SIZES['table_body']),
        ('TEXTCOLOR', (0, header_rows), (-1, -1), COLORS['dark_gray']),
        ('VALIGN', (0, header_rows), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, header_rows), (-1, -1), 'LEFT'),
        
        # Alternating row backgrounds
        ('ROWBACKGROUNDS', (0, header_rows), (-1, -1), [COLORS['white'], COLORS['light_blue']]),
        
        # Borders
        ('GRID', (0, 0), (-1, -1), 0.5, COLORS['border_gray']),
        ('BOX', (0, 0), (-1, -1), 1, COLORS['medium_gray']),
        
        # Padding
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, header_rows), (-1, -1), 4),
        ('BOTTOMPADDING', (0, header_rows), (-1, -1), 4),
    ])
    
    return TableStyle(style_commands)

def create_multi_header_table_style(header_rows=2, spans=None):
    """
    Create a table style with multiple header rows (e.g., for grouped columns).
    
    Args:
        header_rows (int): Number of header rows (default: 2)
        spans (list): List of span tuples for merged cells
    
    Returns:
        TableStyle: Professionally styled table with multi-row headers
    """
    style_commands = []
    
    # Add spans first if provided
    if spans:
        style_commands.extend(spans)
    
    # Main header row styling
    style_commands.extend([
        ('BACKGROUND', (0, 0), (-1, 0), COLORS['primary_blue']),
        ('TEXTCOLOR', (0, 0), (-1, 0), COLORS['white']),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, 0), FONTS['table_header']),
        ('FONTSIZE', (0, 0), (-1, 0), FONT_SIZES['table_body']),
        ('TOPPADDING', (0, 0), (-1, 0), 4),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 4),
    ])
    
    # Sub-header row styling
    style_commands.extend([
        ('BACKGROUND', (0, 1), (-1, header_rows-1), COLORS['secondary_blue']),
        ('TEXTCOLOR', (0, 1), (-1, header_rows-1), COLORS['white']),
        ('ALIGN', (0, 1), (-1, header_rows-1), 'CENTER'),
        ('VALIGN', (0, 1), (-1, header_rows-1), 'MIDDLE'),
        ('FONTNAME', (0, 1), (-1, header_rows-1), FONTS['table_header']),
        ('FONTSIZE', (0, 1), (-1, header_rows-1), FONT_SIZES['small']),
        ('TOPPADDING', (0, 1), (-1, header_rows-1), 2),
        ('BOTTOMPADDING', (0, 1), (-1, header_rows-1), 2),
    ])
    
    # Data rows styling
    style_commands.extend([
        ('FONTNAME', (0, header_rows), (-1, -1), FONTS['table_body']),
        ('FONTSIZE', (0, header_rows), (-1, -1), FONT_SIZES['small']),
        ('TEXTCOLOR', (0, header_rows), (-1, -1), COLORS['dark_gray']),
        ('VALIGN', (0, header_rows), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, header_rows), (-1, -1), 'LEFT'),
        ('ALIGN', (0, header_rows), (0, -1), 'CENTER'),  # Center align first column (usually zone names)
        
        # Alternating row backgrounds
        ('ROWBACKGROUNDS', (0, header_rows), (-1, -1), [COLORS['white'], COLORS['light_blue']]),
        
        # Borders
        ('GRID', (0, 0), (-1, -1), 0.5, COLORS['border_gray']),
        ('BOX', (0, 0), (-1, -1), 1, COLORS['medium_gray']),
        
        # Padding
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, header_rows), (-1, -1), 2),
        ('BOTTOMPADDING', (0, header_rows), (-1, -1), 2),
    ])
    
    return TableStyle(style_commands)

def create_cell_style(styles, is_header=False, center_align=False, font_size=None):
    """
    Create a standardized cell style for wrapped text in tables.
    
    Args:
        styles: ReportLab styles object
        is_header (bool): Whether this is a header cell
        center_align (bool): Whether to center align the text
        font_size (int): Override font size
    
    Returns:
        ParagraphStyle: Styled paragraph for table cells
    """
    if is_header:
        return ParagraphStyle(
            'HeaderCell',
            parent=styles['Normal'],
            fontSize=font_size or FONT_SIZES['small'],
            leading=(font_size or FONT_SIZES['small']) + 1,
            spaceBefore=3,
            spaceAfter=3,
            fontName=FONTS['table_header'],
            textColor=COLORS['white'],
            wordWrap='CJK',
            alignment=TA_CENTER
        )
    else:
        return ParagraphStyle(
            'DataCell',
            parent=styles['Normal'],
            fontSize=font_size or FONT_SIZES['small'],
            leading=(font_size or FONT_SIZES['small']) + 1,
            spaceBefore=1,
            spaceAfter=1,
            fontName=FONTS['table_body'],
            textColor=COLORS['dark_gray'],
            wordWrap='CJK',
            alignment=TA_CENTER if center_align else TA_LEFT
        )

def create_title_style(styles):
    """Create a standardized title style."""
    title_style = styles['h1']
    title_style.textColor = COLORS['primary_blue']
    title_style.fontName = FONTS['title']
    title_style.fontSize = FONT_SIZES['title']
    title_style.alignment = TA_CENTER
    return title_style

def create_header_info_style(styles):
    """Create a standardized header info style."""
    hebrew_font = get_hebrew_font_name()
    return ParagraphStyle(
        'HeaderInfo',
        parent=styles['Normal'],
        fontSize=9,
        fontName=hebrew_font,
        textColor=COLORS['dark_gray'],
        alignment=TA_RIGHT
    )

def create_section_title_style(styles):
    """Create a standardized section title style."""
    return ParagraphStyle(
        'SectionTitle',
        parent=styles['h2'],
        textColor=COLORS['primary_blue'],
        fontName=FONTS['heading'],
        fontSize=FONT_SIZES['heading'],
        spaceBefore=LAYOUT['spacing']['section'],
        spaceAfter=LAYOUT['spacing']['small'],
        alignment=TA_LEFT
    )

def wrap_text(text, style):
    """Helper function to create wrapped text in a cell."""
    return Paragraph(str(text), style)

def create_error_table_style():
    """Create a specialized table style for error detection reports."""
    return TableStyle([
        # Header styling
        ('BACKGROUND', (0, 0), (-1, 0), COLORS['error_red']),
        ('TEXTCOLOR', (0, 0), (-1, 0), COLORS['white']),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, 0), FONTS['table_header']),
        ('FONTSIZE', (0, 0), (-1, 0), FONT_SIZES['table_header']),
        ('TOPPADDING', (0, 0), (-1, 0), 6),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        
        # Data rows
        ('FONTNAME', (0, 1), (-1, -1), FONTS['table_body']),
        ('FONTSIZE', (0, 1), (-1, -1), FONT_SIZES['table_body']),
        ('TEXTCOLOR', (0, 1), (-1, -1), COLORS['dark_gray']),
        ('VALIGN', (0, 1), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
        
        # Alternating backgrounds
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [COLORS['white'], Color(1, 0.95, 0.95)]),
        
        # Borders
        ('GRID', (0, 0), (-1, -1), 0.5, COLORS['border_gray']),
        ('BOX', (0, 0), (-1, -1), 1, COLORS['medium_gray']),
        
        # Padding
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 1), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
    ])

def create_total_row_style(row_index):
    """Create a style for total/summary rows in tables."""
    return [
        ('BACKGROUND', (0, row_index), (-1, row_index), COLORS['light_gray']),
        ('FONTNAME', (0, row_index), (-1, row_index), FONTS['table_header']),
        ('FONTSIZE', (0, row_index), (-1, row_index), FONT_SIZES['table_body']),
        ('TEXTCOLOR', (0, row_index), (-1, row_index), COLORS['dark_gray']),
        ('TOPPADDING', (0, row_index), (-1, row_index), 6),
        ('BOTTOMPADDING', (0, row_index), (-1, row_index), 6),
    ]

def create_standardized_header(doc, project_name="N/A", run_id="N/A", 
                              city_name="N/A", area_name="N/A", 
                              report_title="Report", timestamp=None):
    """
    Create a standardized header with logo on top left and metadata on top right.
    
    Args:
        doc: ReportLab document object (for width calculations)
        project_name (str): Name of the project
        run_id (str): Run identifier
        city_name (str): City name
        area_name (str): Area name
        report_title (str): Title of the report
        timestamp (str): Timestamp string (if None, current time is used)
    
    Returns:
        List of ReportLab elements for the header
    """
    from utils.logo_utils import create_logo_image
    from utils.hebrew_text_utils import safe_format_header_text, get_hebrew_font_name
    from reportlab.platypus import Table, TableStyle, Paragraph, Spacer
    import datetime
    
    elements = []
    
    # Use current time if timestamp not provided
    if timestamp is None:
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Create logo image
    logo_image = create_logo_image(
        max_width=LAYOUT['logo']['max_width'], 
        max_height=LAYOUT['logo']['max_height']
    )
    
    # Create header info style optimized for horizontal alignment
    hebrew_font = get_hebrew_font_name()
    header_info_style = ParagraphStyle(
        'StandardHeaderInfo',
        parent=getSampleStyleSheet()['Normal'],
        fontSize=FONT_SIZES['body'],
        fontName=hebrew_font,
        textColor=COLORS['dark_gray'],
        alignment=TA_RIGHT,  # Right alignment for metadata
        leading=FONT_SIZES['body'] + 2,  # Improved line spacing
        spaceBefore=0,
        spaceAfter=0
    )
    
    # Format header text
    header_text = safe_format_header_text(
        project_name=project_name,
        run_id=run_id,
        timestamp=timestamp,
        city_name=city_name,
        area_name=area_name,
        report_title=report_title
    )
    
    # Create header metadata paragraph
    header_metadata = Paragraph(header_text, header_info_style)
    
    # Create header table: logo on left, metadata on right with optimized spacing
    available_width = doc.width
    if logo_image:
        # Reserve space for logo with some margin
        logo_width = LAYOUT['logo']['table_width']
        metadata_width = available_width - logo_width
        header_data = [[logo_image, header_metadata]]
        header_table = Table(header_data, colWidths=[logo_width, metadata_width])
    else:
        # If no logo, center the metadata or align to right with full width
        header_data = [["", header_metadata]]
        header_table = Table(header_data, colWidths=[0, available_width])
    
    # Style the header table for perfect horizontal alignment
    header_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),    # Logo left aligned
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),   # Metadata right aligned
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), # Middle vertical alignment for both logo and metadata
        ('LEFTPADDING', (0, 0), (-1, -1), 0),   # Remove left padding for cleaner alignment
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),  # Remove right padding for cleaner alignment
        ('TOPPADDING', (0, 0), (-1, -1), 8),    # Consistent top padding
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8), # Consistent bottom padding
        ('NOSPLIT', (0, 0), (-1, -1)),          # Prevent table from splitting across pages
    ]))
    
    elements.append(header_table)
    elements.append(Spacer(1, LAYOUT['spacing']['small']))
    
    return elements

# Export all design elements for easy import
__all__ = [
    'COLORS', 'FONTS', 'FONT_SIZES', 'LAYOUT',
    'create_standard_table_style', 'create_multi_header_table_style', 
    'create_cell_style', 'create_title_style', 'create_header_info_style',
    'create_section_title_style', 'wrap_text', 'create_error_table_style',
    'create_total_row_style', 'create_standardized_header'
]