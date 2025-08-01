"""
Base Report Generator

Provides common functionality for all PDF report generators to eliminate code duplication
and ensure consistency across all report types.
"""
import datetime
from utils.logging_config import get_logger
from pathlib import Path
from functools import wraps
from reportlab.platypus import SimpleDocTemplate
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from generators.shared_design_system import (
    LAYOUT, create_standardized_header
)

logger = get_logger(__name__)


def handle_report_errors(report_type_name):
    """
    Decorator for consistent error handling across all report generators.
    
    Args:
        report_type_name (str): Name of the report type for error messages
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
                result = func(self, *args, **kwargs)
                if result is None:
                    return True  # Default success if None returned
                return result
            except (IOError, OSError) as e:
                output_filename = kwargs.get('output_filename', 'unknown')
                error_message = f"Error during file operation for {report_type_name} report '{output_filename}': {e.strerror}"
                logger.error(error_message, exc_info=True)
                return False
            except Exception as e:
                output_filename = kwargs.get('output_filename', 'unknown')
                error_message = f"An unexpected error occurred while generating {report_type_name} report '{output_filename}': {type(e).__name__} - {str(e)}"
                logger.error(error_message, exc_info=True)
                return False
        return wrapper
    return decorator


class BaseReportGenerator:
    """
    Base class for all PDF report generators.
    
    Provides common functionality including:
    - Document creation and setup
    - Directory management
    - Header generation
    - Error handling
    - Standard styling
    """
    
    def __init__(self, project_name="N/A", run_id="N/A", city_name="N/A", area_name="N/A"):
        """
        Initialize base report generator.
        
        Args:
            project_name (str): Name of the project
            run_id (str): Run identifier
            city_name (str): City name
            area_name (str): Area name
        """
        self.project_name = project_name
        self.run_id = run_id
        self.city_name = city_name
        self.area_name = area_name
        self.styles = getSampleStyleSheet()
    
    def ensure_output_directory(self, output_filename):
        """
        Ensure output directory exists with proper error handling.
        
        Args:
            output_filename (str): Path to output file
            
        Returns:
            bool: True if directory exists or was created successfully
            
        Raises:
            RuntimeError: If directory cannot be created or path exists but is not a directory
        """
        output_path = Path(output_filename).parent
        
        if not output_path.exists():
            try:
                output_path.mkdir(parents=True, exist_ok=True)
                logger.debug(f"Created output directory: {output_path}")
            except OSError as e:
                error_message = f"Error creating output directory '{output_path}': {e.strerror}"
                logger.error(error_message, exc_info=True)
                raise RuntimeError(error_message)
        elif not output_path.is_dir():
            error_message = f"Error: Output path '{output_path}' exists but is not a directory."
            logger.error(error_message)
            raise RuntimeError(error_message)
        
        return True
    
    def create_document(self, output_filename, page_size=A4, orientation='portrait', 
                       margins=None, **doc_kwargs):
        """
        Create a standardized ReportLab document with consistent setup.
        
        Args:
            output_filename (str): Path where PDF will be saved
            page_size: ReportLab page size (default: A4)
            orientation (str): 'portrait' or 'landscape' (default: 'portrait')
            margins (float): Margin size in cm, uses default if None
            **doc_kwargs: Additional arguments passed to SimpleDocTemplate
            
        Returns:
            SimpleDocTemplate: Configured document object
        """
        # Ensure output directory exists
        self.ensure_output_directory(output_filename)
        
        # Apply orientation
        if orientation == 'landscape':
            page_size = landscape(page_size)
        
        # Set margins
        if margins is None:
            margins = LAYOUT['margins']['default']
        
        # Create document with standard settings
        doc_params = {
            'pagesize': page_size,
            'leftMargin': margins,
            'rightMargin': margins,
            'topMargin': margins,
            'bottomMargin': margins
        }
        doc_params.update(doc_kwargs)
        
        doc = SimpleDocTemplate(str(output_filename), **doc_params)
        logger.debug(f"Created document: {output_filename}, page_size: {page_size}, orientation: {orientation}")
        
        return doc
    
    def add_standardized_header(self, doc, report_title, timestamp=None):
        """
        Add standardized header with logo and metadata.
        
        Args:
            doc: ReportLab document object
            report_title (str): Title of the report
            timestamp (str): Optional timestamp string (current time if None)
            
        Returns:
            list: ReportLab elements for the header
        """
        return create_standardized_header(
            doc=doc,
            project_name=self.project_name,
            run_id=self.run_id,
            city_name=self.city_name,
            area_name=self.area_name,
            report_title=report_title,
            timestamp=timestamp
        )
    
    def get_timestamp(self):
        """
        Get standardized timestamp string.
        
        Returns:
            str: Formatted timestamp
        """
        return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    def build_document(self, doc, story):
        """
        Build document with error handling.
        
        Args:
            doc: ReportLab document object
            story: List of ReportLab elements
            
        Returns:
            bool: True if successful
        """
        try:
            doc.build(story)
            logger.info(f"Successfully built document")
            return True
        except Exception as e:
            logger.error(f"Error building document: {e}", exc_info=True)
            raise
    
    def generate_report(self, *args, **kwargs):
        """
        Abstract method to be implemented by subclasses.
        
        Raises:
            NotImplementedError: This method must be implemented by subclasses
        """
        raise NotImplementedError("Subclasses must implement generate_report method")


class StandardPageSizes:
    """Standard page size configurations for different report types."""
    
    PORTRAIT_A4 = {'page_size': A4, 'orientation': 'portrait'}
    LANDSCAPE_A4 = {'page_size': A4, 'orientation': 'landscape'}
    PORTRAIT_A3 = {'page_size': (297*2.83465, 420*2.83465), 'orientation': 'portrait'}  # A3 in points
    LANDSCAPE_A3 = {'page_size': (297*2.83465, 420*2.83465), 'orientation': 'landscape'}
    
    @classmethod
    def get_config(cls, report_type):
        """
        Get standard page configuration for report type.
        
        Args:
            report_type (str): Type of report
            
        Returns:
            dict: Page configuration
        """
        configs = {
            'area_loss': cls.PORTRAIT_A4,
            'energy_rating': cls.LANDSCAPE_A4,
            'materials': cls.LANDSCAPE_A3,
            'loads': cls.LANDSCAPE_A4,
            'settings': cls.PORTRAIT_A4,
            'glazing': cls.LANDSCAPE_A3,
            'lighting': cls.PORTRAIT_A4,
            'natural_ventilation': cls.PORTRAIT_A4,
            'schedule': cls.PORTRAIT_A4,
            'area': cls.LANDSCAPE_A4,
            'error_detection': cls.PORTRAIT_A4
        }
        return configs.get(report_type, cls.PORTRAIT_A4)