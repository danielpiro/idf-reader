"""
Data loader module for EPJSON data access with Hebrew/Unicode support.
Provides centralized data loading functionality with caching and error handling.
"""
from typing import Dict, Optional, List, Any, Union
from pathlib import Path
from utils.epjson_handler import EPJSONHandler
from utils.path_utils import (
    get_data_file_path, contains_non_ascii,
    create_safe_path_for_energyplus
)
from utils.logger import get_module_logger
import os
import sys
import re
import pandas as pd

logger = get_module_logger(__name__)


class DataLoadError(Exception):
    """Custom exception for data loading errors."""
    pass


class EnergyDataService:
    """Service for loading energy consumption data from CSV models."""
    
    @staticmethod
    def get_energy_consumption(iso_type_input: str, area_location_input: str, 
                             area_definition_input: str) -> float:
        """
        Retrieve energy consumption value based on ISO type and location.
        
        Args:
            iso_type_input: ISO type (e.g., "ISO_TYPE_2017_A", "ISO_TYPE_2023_B")
            area_location_input: Area type description
            area_definition_input: Climate zone (2017: 'A'-'D', 2023: '1'-'8')
            
        Returns:
            Energy consumption value as float
            
        Raises:
            DataLoadError: If data cannot be loaded or found
        """
        try:
            year = None
            file_name = None
            
            if "2017" in iso_type_input:
                year = 2017
                file_name = f"{year}_model.csv"
            elif "2023" in iso_type_input:
                year = 2023
                file_name = f"{year}_model.csv"
            elif "office" in iso_type_input.lower():
                file_name = "office_model.csv"
            else:
                raise DataLoadError(f"Invalid ISO type: {iso_type_input}")
            
            csv_path = get_data_file_path(file_name)
            
            if not os.path.isfile(csv_path):
                raise DataLoadError(f"Model file not found: {csv_path}")
            
            df = pd.read_csv(csv_path)
            
            if area_location_input not in df.columns:
                raise DataLoadError(f"Area location '{area_location_input}' not found in {file_name}")
            
            if area_definition_input not in df.index:
                raise DataLoadError(f"Area definition '{area_definition_input}' not found in {file_name}")
            
            energy_value = df.loc[area_definition_input, area_location_input]
            
            return float(energy_value)
            
        except (ValueError, KeyError, FileNotFoundError) as e:
            logger.error(f"Error loading energy consumption data: {e}")
            raise DataLoadError(f"Failed to load energy consumption: {e}")


class DataLoader:
    """
    Centralized data loader for IDF files with caching and Hebrew support.
    Provides cached access to all IDF object types for improved performance.
    """
    
    def __init__(self):
        """Initialize data loader with empty cache."""
        self.data = {}
        self.is_loaded = False
        self.file_path = None
        self.idd_path = None
        self._object_cache = {}
        self.energyplus_input_file_path = None
        self.energyplus_output_dir = None
        
    def load_idf(self, file_path: str, idd_path: Optional[str] = None) -> bool:
        """
        Load IDF file using EPJSON handler.
        
        Args:
            file_path: Path to IDF or EPJSON file
            idd_path: Path to IDD file (optional for EPJSON)
            
        Returns:
            True if loading successful, False otherwise
        """
        try:
            self.file_path = file_path
            self.idd_path = idd_path
            
            # Handle Hebrew/Unicode paths for EnergyPlus compatibility
            if contains_non_ascii(file_path):
                safe_path = create_safe_path_for_energyplus(file_path)
                self.energyplus_input_file_path = safe_path
                logger.info(f"Created safe path for EnergyPlus: {safe_path}")
            else:
                self.energyplus_input_file_path = file_path
            
            # Use EPJSON handler for data loading
            handler = EPJSONHandler(file_path, idd_path)
            
            if not handler.load():
                logger.error("Failed to load file with EPJSON handler")
                return False
                
            self.data = handler.get_data()
            self.is_loaded = True
            self._clear_cache()
            
            logger.info(f"Successfully loaded IDF file: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error loading IDF file {file_path}: {e}", exc_info=True)
            self.is_loaded = False
            return False
    
    def get_objects(self, object_type: str) -> Dict[str, Any]:
        """
        Get all objects of a specific type with caching.
        
        Args:
            object_type: IDF object type (e.g., 'Zone', 'BuildingSurface:Detailed')
            
        Returns:
            Dictionary of objects {name: object_data}
        """
        if not self.is_loaded:
            logger.warning("Data not loaded. Call load_idf() first.")
            return {}
        
        # Use cache if available
        if object_type in self._object_cache:
            return self._object_cache[object_type]
        
        # Load and cache objects
        objects = self.data.get(object_type, {})
        self._object_cache[object_type] = objects
        
        logger.debug(f"Loaded {len(objects)} objects of type '{object_type}'")
        return objects
    
    def get_object_names(self, object_type: str) -> List[str]:
        """
        Get list of object names for a specific type.
        
        Args:
            object_type: IDF object type
            
        Returns:
            List of object names
        """
        objects = self.get_objects(object_type)
        return list(objects.keys())
    
    def get_object(self, object_type: str, object_name: str) -> Optional[Dict[str, Any]]:
        """
        Get specific object by type and name.
        
        Args:
            object_type: IDF object type
            object_name: Object name
            
        Returns:
            Object data dictionary or None if not found
        """
        objects = self.get_objects(object_type)
        return objects.get(object_name)
    
    def has_object_type(self, object_type: str) -> bool:
        """
        Check if object type exists in loaded data.
        
        Args:
            object_type: IDF object type to check
            
        Returns:
            True if object type exists and has objects
        """
        return bool(self.get_objects(object_type))
    
    def get_all_object_types(self) -> List[str]:
        """
        Get list of all available object types.
        
        Returns:
            List of object type names
        """
        if not self.is_loaded:
            return []
        return list(self.data.keys())
    
    def get_object_count(self, object_type: str) -> int:
        """
        Get count of objects for a specific type.
        
        Args:
            object_type: IDF object type
            
        Returns:
            Number of objects of this type
        """
        return len(self.get_objects(object_type))
    
    def search_objects(self, object_type: str, field: str, value: Any) -> Dict[str, Any]:
        """
        Search for objects with specific field value.
        
        Args:
            object_type: IDF object type
            field: Field name to search
            value: Value to match
            
        Returns:
            Dictionary of matching objects
        """
        objects = self.get_objects(object_type)
        matches = {}
        
        for name, obj_data in objects.items():
            if isinstance(obj_data, dict) and obj_data.get(field) == value:
                matches[name] = obj_data
        
        return matches
    
    def _clear_cache(self):
        """Clear object cache."""
        self._object_cache.clear()
    
    def get_file_info(self) -> Dict[str, Any]:
        """
        Get information about loaded file.
        
        Returns:
            Dictionary with file information
        """
        return {
            'file_path': self.file_path,
            'idd_path': self.idd_path,
            'is_loaded': self.is_loaded,
            'energyplus_input_path': self.energyplus_input_file_path,
            'total_object_types': len(self.get_all_object_types()) if self.is_loaded else 0,
            'total_objects': sum(self.get_object_count(ot) for ot in self.get_all_object_types()) if self.is_loaded else 0
        }


# Legacy function wrapper for backwards compatibility
def get_energy_consumption(iso_type_input: str, area_location_input: str, 
                         area_definition_input: str) -> float:
    """Legacy wrapper for energy consumption data."""
    return EnergyDataService.get_energy_consumption(
        iso_type_input, area_location_input, area_definition_input
    )