"""
Formatting Utilities

Centralized value formatting functions for all report generators to ensure
consistency across all reports and eliminate duplicate formatting code.
"""
import pandas as pd
from typing import Any


class ValueFormatter:
    """Centralized value formatting for all reports."""
    
    @staticmethod
    def format_number(value: Any, precision: int = 3, default: str = '-') -> str:
        """
        Standardized number formatting with intelligent precision.
        
        Args:
            value: Value to format (int, float, string, or None)
            precision: Number of decimal places for small numbers
            default: Default value for None/NaN/empty values
            
        Returns:
            str: Formatted number string
        """
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return default
        
        try:
            num_value = float(value)
            
            # Handle zero
            if num_value == 0:
                return "0"
            
            # Apply intelligent formatting based on magnitude
            abs_value = abs(num_value)
            
            if abs_value < 0.001:
                return f"{num_value:.{precision+1}f}".rstrip('0').rstrip('.')
            elif abs_value < 0.01:
                return f"{num_value:.{precision}f}"
            elif abs_value < 1:
                return f"{num_value:.{min(precision, 3)}f}"
            elif abs_value < 10:
                return f"{num_value:.{min(precision-1, 2)}f}"
            elif abs_value < 1000:
                return f"{num_value:.1f}" if num_value % 1 != 0 else f"{int(num_value)}"
            else:
                return f"{int(round(num_value))}"
                
        except (ValueError, TypeError, OverflowError):
            return str(value) if value is not None else default
    
    @staticmethod
    def format_percentage(value: Any, precision: int = 1, default: str = '-') -> str:
        """
        Format values as percentages.
        
        Args:
            value: Value to format (should be decimal, e.g. 0.25 for 25%)
            precision: Number of decimal places
            default: Default value for None/NaN/empty values
            
        Returns:
            str: Formatted percentage string with % symbol
        """
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return default
        
        try:
            num_value = float(value)
            percentage = num_value * 100
            return f"{percentage:.{precision}f}%"
        except (ValueError, TypeError, OverflowError):
            return default
    
    @staticmethod
    def format_scientific(value: Any, precision: int = 2, default: str = '-') -> str:
        """
        Format very small or large numbers in scientific notation.
        
        Args:
            value: Value to format
            precision: Number of decimal places in mantissa
            default: Default value for None/NaN/empty values
            
        Returns:
            str: Formatted scientific notation string
        """
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return default
        
        try:
            num_value = float(value)
            if abs(num_value) < 1e-4 or abs(num_value) >= 1e6:
                return f"{num_value:.{precision}e}"
            else:
                return ValueFormatter.format_number(num_value, precision)
        except (ValueError, TypeError, OverflowError):
            return default
    
    @staticmethod
    def safe_string(value: Any, default: str = '-') -> str:
        """
        Safe string conversion with None handling.
        
        Args:
            value: Value to convert to string
            default: Default value for None/NaN values
            
        Returns:
            str: String representation of value
        """
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return default
        
        if isinstance(value, str):
            return value.strip()
        
        return str(value)
    
    @staticmethod
    def format_temperature(value: Any, unit: str = '°C', precision: int = 1, default: str = '-') -> str:
        """
        Format temperature values with units.
        
        Args:
            value: Temperature value
            unit: Temperature unit (default: '°C')
            precision: Number of decimal places
            default: Default value for None/NaN/empty values
            
        Returns:
            str: Formatted temperature string with unit
        """
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return default
        
        try:
            num_value = float(value)
            formatted = ValueFormatter.format_number(num_value, precision)
            return f"{formatted} {unit}"
        except (ValueError, TypeError, OverflowError):
            return default
    
    @staticmethod
    def format_energy(value: Any, unit: str = 'kWh', precision: int = 2, default: str = '-') -> str:
        """
        Format energy values with units.
        
        Args:
            value: Energy value
            unit: Energy unit (default: 'kWh')
            precision: Number of decimal places
            default: Default value for None/NaN/empty values
            
        Returns:
            str: Formatted energy string with unit
        """
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return default
        
        try:
            num_value = float(value)
            formatted = ValueFormatter.format_number(num_value, precision)
            return f"{formatted} {unit}"
        except (ValueError, TypeError, OverflowError):
            return default
    
    @staticmethod
    def format_area(value: Any, unit: str = 'm²', precision: int = 2, default: str = '-') -> str:
        """
        Format area values with units.
        
        Args:
            value: Area value
            unit: Area unit (default: 'm²')
            precision: Number of decimal places
            default: Default value for None/NaN/empty values
            
        Returns:
            str: Formatted area string with unit
        """
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return default
        
        try:
            num_value = float(value)
            formatted = ValueFormatter.format_number(num_value, precision)
            return f"{formatted} {unit}"
        except (ValueError, TypeError, OverflowError):
            return default


class DataValidator:
    """Data validation utilities for report generation."""
    
    @staticmethod
    def is_valid_number(value: Any) -> bool:
        """
        Check if value is a valid number.
        
        Args:
            value: Value to check
            
        Returns:
            bool: True if value is a valid number
        """
        if value is None:
            return False
        
        try:
            float(value)
            return not pd.isna(float(value))
        except (ValueError, TypeError, OverflowError):
            return False
    
    @staticmethod
    def is_empty_or_none(value: Any) -> bool:
        """
        Check if value is None, NaN, or empty string.
        
        Args:
            value: Value to check
            
        Returns:
            bool: True if value is considered empty
        """
        if value is None:
            return True
        
        if isinstance(value, str) and value.strip() == '':
            return True
        
        if isinstance(value, float) and pd.isna(value):
            return True
        
        return False
    
    @staticmethod
    def safe_float(value: Any, default: float = 0.0) -> float:
        """
        Safe float conversion with default value.
        
        Args:
            value: Value to convert
            default: Default value if conversion fails
            
        Returns:
            float: Converted value or default
        """
        try:
            return float(value)
        except (ValueError, TypeError):
            return default


# Convenience functions for backward compatibility
def format_number(value, precision=3, default='-'):
    """Backward compatibility wrapper."""
    return ValueFormatter.format_number(value, precision, default)

def format_value(value, precision=3, na_rep='-'):
    """Backward compatibility wrapper for existing code."""
    return ValueFormatter.format_number(value, precision, na_rep)

def safe_float(value, default=0.0):
    """Backward compatibility wrapper."""
    return DataValidator.safe_float(value, default)