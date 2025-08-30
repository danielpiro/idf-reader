"""
Base parser class to standardize common patterns across all parsers.
Reduces code duplication and provides consistent error handling.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
from utils.logging_config import get_logger
from .utils import log_processing_stats, validate_required_fields

class BaseParser(ABC):
    """
    Abstract base class for all parsers with common functionality.
    """
    
    def __init__(self, data_loader=None, parser_name: str = None):
        """
        Initialize base parser with common setup.
        
        Args:
            data_loader: DataLoader instance for accessing IDF data
            parser_name: Name of the parser for logging
        """
        self.data_loader = data_loader
        self.parser_name = parser_name or self.__class__.__name__
        self.logger = get_logger(self.parser_name)
        self.processed = False
        self._processing_errors = []
        self._processing_stats = {
            "total_items": 0,
            "processed_items": 0,
            "error_items": 0
        }
    
    @abstractmethod
    def process_idf(self, idf=None) -> None:
        """
        Main processing method that each parser must implement.
        
        Args:
            idf: Optional IDF object for processing
        """
        pass
    
    def is_processed(self) -> bool:
        """Check if parser has been processed."""
        return self.processed
    
    def get_processing_stats(self) -> Dict[str, int]:
        """Get processing statistics."""
        return self._processing_stats.copy()
    
    def get_processing_errors(self) -> List[str]:
        """Get list of processing errors."""
        return self._processing_errors.copy()
    
    def _log_start_processing(self, total_items: int = 0):
        """Log start of processing with item count."""
        self.logger.info(f"{self.parser_name}: Starting processing" + 
                        (f" of {total_items} items" if total_items > 0 else ""))
        self._processing_stats["total_items"] = total_items
    
    def _log_item_processed(self, item_name: str = None):
        """Log successful processing of an item."""
        self._processing_stats["processed_items"] += 1
        if item_name:
            self.logger.debug(f"{self.parser_name}: Processed {item_name}")
    
    def _log_item_error(self, error_msg: str, item_name: str = None):
        """Log error processing an item."""
        self._processing_stats["error_items"] += 1
        self._processing_errors.append(error_msg)
        full_msg = f"{self.parser_name}: Error processing"
        if item_name:
            full_msg += f" {item_name}"
        full_msg += f" - {error_msg}"
        self.logger.error(full_msg)
    
    def _log_processing_complete(self):
        """Log completion of processing with statistics."""
        stats = self._processing_stats
        log_processing_stats(
            self.parser_name,
            stats["processed_items"], 
            stats["total_items"],
            stats["error_items"]
        )
        self.processed = True
    
    def _validate_initialization(self) -> bool:
        """Validate that parser is properly initialized."""
        if not self.data_loader:
            self.logger.error(f"{self.parser_name}: DataLoader not provided")
            return False
        return True
    
    def _safe_get_data(self, data_type: str) -> Dict[str, Any]:
        """
        Safely get data from DataLoader with error handling.
        
        Args:
            data_type: Type of data to retrieve (e.g., 'zones', 'surfaces')
            
        Returns:
            Dictionary of data or empty dict if error
        """
        try:
            getter_method = getattr(self.data_loader, f"get_{data_type}", None)
            if not getter_method:
                self.logger.error(f"{self.parser_name}: DataLoader missing get_{data_type} method")
                return {}
            
            data = getter_method()
            if not isinstance(data, dict):
                self.logger.warning(f"{self.parser_name}: Expected dict from get_{data_type}, got {type(data)}")
                return {}
            
            self.logger.debug(f"{self.parser_name}: Retrieved {len(data)} {data_type}")
            return data
            
        except Exception as e:
            self.logger.error(f"{self.parser_name}: Error getting {data_type} - {e}")
            return {}
    
    def _process_items_safely(self, items: Dict[str, Any], process_func, item_type: str = "items"):
        """
        Process a collection of items with error handling and logging.
        
        Args:
            items: Dictionary of items to process
            process_func: Function to process each item
            item_type: Type of items for logging
        """
        if not items:
            self.logger.warning(f"{self.parser_name}: No {item_type} to process")
            return
        
        self._log_start_processing(len(items))
        
        for item_id, item_data in items.items():
            self._process_single_item(item_id, item_data, process_func)
        
        self._log_processing_complete()
    
    def _process_single_item(self, item_id: str, item_data: Any, process_func) -> bool:
        """
        Process a single item with error handling.
        
        Args:
            item_id: Identifier of the item
            item_data: Data of the item
            process_func: Function to process the item
            
        Returns:
            bool: True if processed successfully, False otherwise
        """
        try:
            process_func(item_id, item_data)
            self._log_item_processed(item_id)
            return True
        except Exception as e:
            self._log_item_error(str(e), item_id)
            return False
    
    def _safe_process_with_fallback(self, process_func, fallback_value=None, *args, **kwargs):
        """
        Execute a processing function with safe error handling and fallback.
        
        Args:
            process_func: Function to execute
            fallback_value: Value to return if processing fails
            *args, **kwargs: Arguments to pass to process_func
            
        Returns:
            Result of process_func or fallback_value if error occurs
        """
        try:
            return process_func(*args, **kwargs)
        except Exception as e:
            self.logger.warning(f"{self.parser_name}: Processing failed, using fallback - {e}")
            return fallback_value
    
    def _batch_process_items(self, items: Dict[str, Any], process_func, 
                            batch_size: int = 100, item_type: str = "items"):
        """
        Process items in batches for better memory management with large datasets.
        
        Args:
            items: Dictionary of items to process
            process_func: Function to process each item
            batch_size: Size of each processing batch
            item_type: Type of items for logging
        """
        if not items:
            self.logger.warning(f"{self.parser_name}: No {item_type} to process")
            return
        
        items_list = list(items.items())
        total_batches = (len(items_list) + batch_size - 1) // batch_size
        
        self._log_start_processing(len(items))
        
        for batch_idx in range(total_batches):
            start_idx = batch_idx * batch_size
            end_idx = min(start_idx + batch_size, len(items_list))
            batch = items_list[start_idx:end_idx]
            
            self.logger.debug(f"{self.parser_name}: Processing batch {batch_idx + 1}/{total_batches}")
            
            for item_id, item_data in batch:
                self._process_single_item(item_id, item_data, process_func)
        
        self._log_processing_complete()
    
    def _extract_numeric_field(self, obj, field_name: str, default: float = 0.0) -> float:
        """
        Extract numeric field from object with safe conversion.
        
        Args:
            obj: Object to extract field from
            field_name: Name of field to extract
            default: Default value if extraction fails
            
        Returns:
            Extracted numeric value or default
        """
        from .utils import parse_numeric_field
        return parse_numeric_field(obj, field_name, default)
    
    def _filter_hvac_zones(self, zones: Dict[str, Any]) -> Dict[str, Any]:
        """Get HVAC zones using CSV 'Conditioned (Y/N)' flags."""
        hvac_zone_names = set(self.data_loader.get_hvac_zones())
        return {zone_id: zone_data for zone_id, zone_data in zones.items() if zone_id in hvac_zone_names}
    
    def _validate_required_data(self, data: Dict[str, Any], required_fields: List[str], 
                              item_name: str = "item") -> bool:
        """
        Validate that required fields are present in data.
        
        Args:
            data: Data dictionary to validate
            required_fields: List of required field names
            item_name: Name of item for error logging
            
        Returns:
            True if valid, False otherwise
        """
        missing_fields = validate_required_fields(data, required_fields)
        if missing_fields:
            self._log_item_error(f"Missing required fields: {missing_fields}", item_name)
            return False
        return True
    
    def _safe_get_nested_data(self, data_dict: Dict[str, Any], keys: List[str], default=None):
        """
        Safely navigate nested dictionary structure.
        
        Args:
            data_dict: Dictionary to navigate
            keys: List of keys to follow (e.g., ['level1', 'level2', 'field'])
            default: Default value if navigation fails
            
        Returns:
            Value at the nested location or default
        """
        current = data_dict
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        return current
    
    def _ensure_not_processed(self) -> bool:
        """
        Check if parser has already been processed.
        
        Returns:
            True if already processed (should skip), False if should continue
        """
        if self.processed:
            self.logger.info(f"{self.parser_name} already processed, skipping")
            return True
        return False
    
    def _safe_get_zones(self) -> Dict[str, Any]:
        """Safely get zones with error handling."""
        return self._safe_get_data("zones")
    
    def _safe_get_surfaces(self) -> Dict[str, Any]:
        """Safely get surfaces with error handling."""
        return self._safe_get_data("surfaces")
    
    def _safe_get_constructions(self) -> Dict[str, Any]:
        """Safely get constructions with error handling."""
        return self._safe_get_data("constructions")
    
    def _safe_get_materials(self) -> Dict[str, Any]:
        """Safely get materials with error handling."""
        return self._safe_get_data("materials")

class ZoneDataParser(BaseParser):
    """
    Base class for parsers that primarily process zone data.
    Provides common zone processing patterns.
    """
    
    def __init__(self, data_loader=None, parser_name: str = None):
        super().__init__(data_loader, parser_name)
        self.zone_data = {}
    
    def _process_zones_safely(self, process_func) -> bool:
        """
        Process zones with error handling and logging.
        
        Args:
            process_func: Function to call for each zone (zone_id, zone_data)
            
        Returns:
            True if processing completed successfully
        """
        zones = self._safe_get_zones()
        if not zones:
            self.logger.warning(f"{self.parser_name}: No zones found")
            return False
        
        return self._process_items_safely(zones, process_func, "zones")

class SurfaceDataParser(BaseParser):
    """
    Base class for parsers that primarily process surface data.
    Provides common surface processing patterns.
    """
    
    def __init__(self, data_loader=None, parser_name: str = None):
        super().__init__(data_loader, parser_name)
        self.surface_data = {}
    
    def _process_surfaces_safely(self, process_func) -> bool:
        """
        Process surfaces with error handling and logging.
        
        Args:
            process_func: Function to call for each surface (surface_id, surface_data)
            
        Returns:
            True if processing completed successfully
        """
        surfaces = self._safe_get_surfaces()
        if not surfaces:
            self.logger.warning(f"{self.parser_name}: No surfaces found")
            return False
        
        return self._process_items_safely(surfaces, process_func, "surfaces")

class CSVOutputParser(BaseParser):
    """
    Base class for parsers that process EnergyPlus CSV output files.
    Provides common CSV processing patterns.
    """
    
    def __init__(self, data_loader=None, csv_path: str = None, parser_name: str = None):
        super().__init__(data_loader, parser_name)
        self.csv_path = csv_path
        self.csv_data = {}
    
    def _safe_read_csv(self, csv_path: str = None) -> Optional[Any]:
        """
        Safely read CSV file with error handling.
        
        Args:
            csv_path: Path to CSV file (optional, uses instance csv_path if not provided)
            
        Returns:
            CSV reader object or None if error
        """
        path_to_use = csv_path or self.csv_path
        if not path_to_use:
            self.logger.error(f"{self.parser_name}: No CSV path provided")
            return None
        
        try:
            import csv
            import os
            
            if not os.path.exists(path_to_use):
                self.logger.error(f"{self.parser_name}: CSV file not found: {path_to_use}")
                return None
            
            csvfile = open(path_to_use, 'r', encoding='utf-8')
            reader = csv.reader(csvfile)
            self.logger.debug(f"{self.parser_name}: Successfully opened CSV file: {path_to_use}")
            return reader
            
        except Exception as e:
            self.logger.error(f"{self.parser_name}: Error reading CSV file {path_to_use}: {e}")
            return None

class SimpleParser(BaseParser):
    """
    Simple parser implementation for basic data extraction.
    Can be used directly for simple parsers or as a reference.
    """
    
    def __init__(self, data_loader, data_type: str, parser_name: str = None):
        """
        Initialize simple parser.
        
        Args:
            data_loader: DataLoader instance
            data_type: Type of data to extract (e.g., 'zones', 'surfaces')
            parser_name: Optional parser name
        """
        super().__init__(data_loader, parser_name)
        self.data_type = data_type
        self.extracted_data = {}
    
    def process_idf(self, idf=None) -> None:
        """Process IDF by extracting specified data type."""
        if not self._validate_initialization():
            return
        
        if self.processed:
            return
        
        self.extracted_data = self._safe_get_data(self.data_type)
        self._processing_stats["total_items"] = len(self.extracted_data)
        self._processing_stats["processed_items"] = len(self.extracted_data)
        self._log_processing_complete()
    
    def get_data(self) -> Dict[str, Any]:
        """Get extracted data."""
        if not self.processed:
            self.logger.warning(f"{self.parser_name}: Data not processed yet. Call process_idf() first.")
            return {}
        return self.extracted_data.copy()