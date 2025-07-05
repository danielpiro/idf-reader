"""
Table Creation Utilities

Provides standardized table creation functionality to eliminate duplicate
table building code across report generators and ensure consistent table layouts.
"""
from typing import List, Dict, Any, Optional, Tuple
from reportlab.platypus import Table, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from generators.shared_design_system import (
    create_standard_table_style, create_multi_header_table_style,
    create_cell_style
)
from generators.utils.formatting_utils import ValueFormatter


class TableBuilder:
    """Utility class for creating standardized tables with consistent styling."""
    
    def __init__(self, page_width: float, styles=None):
        """
        Initialize table builder.
        
        Args:
            page_width: Available page width for table calculations
            styles: ReportLab styles sheet (will create default if None)
        """
        self.page_width = page_width
        self.styles = styles or getSampleStyleSheet()
        self.value_formatter = ValueFormatter()
    
    def calculate_column_widths(self, num_columns: int, 
                              width_percentages: Optional[List[float]] = None,
                              min_width: float = None) -> List[float]:
        """
        Calculate column widths based on page width and percentages.
        
        Args:
            num_columns: Number of columns
            width_percentages: List of percentages (0.0-1.0) for each column
            min_width: Minimum width for any column
            
        Returns:
            List[float]: Column widths in points
        """
        if width_percentages:
            if len(width_percentages) != num_columns:
                raise ValueError(f"Width percentages ({len(width_percentages)}) must match number of columns ({num_columns})")
            
            if abs(sum(width_percentages) - 1.0) > 0.01:
                # Normalize percentages if they don't sum to 1.0
                total = sum(width_percentages)
                width_percentages = [w / total for w in width_percentages]
            
            widths = [self.page_width * percentage for percentage in width_percentages]
        else:
            # Equal width columns
            widths = [self.page_width / num_columns] * num_columns
        
        # Apply minimum width if specified
        if min_width:
            widths = [max(w, min_width) for w in widths]
        
        return widths
    
    def create_data_table(self, headers: List[str], data: List[List[Any]], 
                         column_widths: Optional[List[float]] = None,
                         table_style_type: str = 'standard',
                         format_functions: Optional[Dict[int, callable]] = None,
                         repeat_rows: int = 1) -> Table:
        """
        Create a standardized data table with headers and data.
        
        Args:
            headers: List of column headers
            data: List of data rows (each row is a list of values)
            column_widths: Optional column widths (will calculate if None)
            table_style_type: Type of table style ('standard', 'multi_header', 'error')
            format_functions: Dict mapping column indices to formatting functions
            repeat_rows: Number of header rows to repeat on page breaks
            
        Returns:
            Table: Configured ReportLab table
        """
        # Calculate column widths if not provided
        if column_widths is None:
            column_widths = self.calculate_column_widths(len(headers))
        
        # Create header row with proper styling
        header_row = self._create_header_row(headers)
        
        # Format data rows
        formatted_data = []
        for row in data:
            formatted_row = self._format_data_row(row, format_functions)
            formatted_data.append(formatted_row)
        
        # Combine header and data
        table_data = [header_row] + formatted_data
        
        # Create table
        table = Table(table_data, colWidths=column_widths, repeatRows=repeat_rows)
        
        # Apply appropriate style
        if table_style_type == 'standard':
            table_style = create_standard_table_style(header_rows=1)
        elif table_style_type == 'multi_header':
            table_style = create_multi_header_table_style(header_rows=1)
        else:
            table_style = create_standard_table_style(header_rows=1)
        
        table.setStyle(table_style)
        return table
    
    def create_multi_header_table(self, header_groups: List[Tuple[str, int]], 
                                 sub_headers: List[str], data: List[List[Any]],
                                 column_widths: Optional[List[float]] = None,
                                 format_functions: Optional[Dict[int, callable]] = None) -> Table:
        """
        Create a table with grouped column headers (spanning multiple columns).
        
        Args:
            header_groups: List of (group_name, span_count) tuples
            sub_headers: List of sub-header names for each column
            data: List of data rows
            column_widths: Optional column widths
            format_functions: Dict mapping column indices to formatting functions
            
        Returns:
            Table: Configured ReportLab table with multi-level headers
        """
        # Calculate column widths if not provided
        num_columns = len(sub_headers)
        if column_widths is None:
            column_widths = self.calculate_column_widths(num_columns)
        
        # Create grouped header row
        main_header_row = []
        col_index = 0
        spans = []
        
        for group_name, span_count in header_groups:
            main_header_row.append(Paragraph(group_name, create_cell_style(self.styles, is_header=True)))
            
            # Add empty cells for the span
            for _ in range(span_count - 1):
                main_header_row.append("")
            
            # Add span command
            if span_count > 1:
                spans.append(('SPAN', (col_index, 0), (col_index + span_count - 1, 0)))
            
            col_index += span_count
        
        # Create sub-header row
        sub_header_row = [Paragraph(header, create_cell_style(self.styles, is_header=True)) 
                         for header in sub_headers]
        
        # Format data rows
        formatted_data = []
        for row in data:
            formatted_row = self._format_data_row(row, format_functions)
            formatted_data.append(formatted_row)
        
        # Combine all rows
        table_data = [main_header_row, sub_header_row] + formatted_data
        
        # Create table
        table = Table(table_data, colWidths=column_widths, repeatRows=2)
        
        # Create style with spans
        table_style = create_multi_header_table_style(header_rows=2, spans=spans)
        table.setStyle(table_style)
        
        return table
    
    def create_summary_table(self, summary_data: Dict[str, Any], 
                           title: str = "Summary",
                           format_functions: Optional[Dict[str, callable]] = None) -> Table:
        """
        Create a two-column summary table for key-value pairs.
        
        Args:
            summary_data: Dictionary of key-value pairs
            title: Title for the summary table
            format_functions: Dict mapping keys to formatting functions
            
        Returns:
            Table: Configured summary table
        """
        # Create table data
        table_data = []
        
        # Add title row if provided
        if title:
            title_style = create_cell_style(self.styles, is_header=True, center_align=True)
            table_data.append([Paragraph(title, title_style), ""])
        
        # Add data rows
        cell_style = create_cell_style(self.styles)
        for key, value in summary_data.items():
            # Format value using custom function if provided
            if format_functions and key in format_functions:
                formatted_value = format_functions[key](value)
            else:
                formatted_value = self.value_formatter.safe_string(value)
            
            table_data.append([
                Paragraph(str(key), cell_style),
                Paragraph(str(formatted_value), cell_style)
            ])
        
        # Calculate column widths (30% for labels, 70% for values)
        column_widths = self.calculate_column_widths(2, [0.3, 0.7])
        
        # Create table
        table = Table(table_data, colWidths=column_widths)
        
        # Create style
        table_style = create_standard_table_style(header_rows=1 if title else 0)
        
        # Add span for title if present
        if title:
            table_style.add('SPAN', (0, 0), (1, 0))
        
        table.setStyle(table_style)
        return table
    
    def _create_header_row(self, headers: List[str]) -> List[Paragraph]:
        """Create formatted header row."""
        header_style = create_cell_style(self.styles, is_header=True, center_align=True)
        return [Paragraph(str(header), header_style) for header in headers]
    
    def _format_data_row(self, row: List[Any], 
                        format_functions: Optional[Dict[int, callable]] = None) -> List[Any]:
        """Format a data row using provided formatting functions."""
        formatted_row = []
        cell_style = create_cell_style(self.styles)
        
        for i, value in enumerate(row):
            # Apply custom formatting function if provided
            if format_functions and i in format_functions:
                formatted_value = format_functions[i](value)
            else:
                # Default formatting based on value type
                if isinstance(value, (int, float)):
                    formatted_value = self.value_formatter.format_number(value)
                else:
                    formatted_value = self.value_formatter.safe_string(value)
            
            # Create paragraph for proper cell formatting
            if isinstance(formatted_value, str):
                formatted_row.append(Paragraph(formatted_value, cell_style))
            else:
                formatted_row.append(formatted_value)
        
        return formatted_row


class TableStylePresets:
    """Predefined table style configurations for common table types."""
    
    @staticmethod
    def energy_consumption_table():
        """Style configuration for energy consumption tables."""
        return {
            'table_style_type': 'multi_header',
            'format_functions': {
                # Energy columns (indices 2-4) formatted as energy values
                2: lambda x: ValueFormatter.format_energy(x, 'kWh/m²'),
                3: lambda x: ValueFormatter.format_energy(x, 'kWh/m²'),
                4: lambda x: ValueFormatter.format_energy(x, 'kWh/m²'),
                # Area column formatted as area
                1: lambda x: ValueFormatter.format_area(x),
            }
        }
    
    @staticmethod
    def thermal_properties_table():
        """Style configuration for thermal properties tables."""
        return {
            'table_style_type': 'standard',
            'format_functions': {
                # U-values and thermal properties
                1: lambda x: ValueFormatter.format_number(x, 3),
                2: lambda x: ValueFormatter.format_number(x, 3),
                3: lambda x: ValueFormatter.format_number(x, 2),
            }
        }
    
    @staticmethod
    def materials_table():
        """Style configuration for materials tables."""
        return {
            'table_style_type': 'standard',
            'format_functions': {
                # Thickness column
                2: lambda x: ValueFormatter.format_number(x, 3) + ' m',
                # Thermal properties
                3: lambda x: ValueFormatter.format_number(x, 3),
                4: lambda x: ValueFormatter.format_number(x, 3),
                5: lambda x: ValueFormatter.format_number(x, 1),
            }
        }


# Convenience functions for backward compatibility
def create_table_with_data(headers, data, page_width, column_widths=None, style_type='standard'):
    """Backward compatibility function for table creation."""
    builder = TableBuilder(page_width)
    return builder.create_data_table(headers, data, column_widths, style_type)