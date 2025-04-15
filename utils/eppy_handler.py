"""
Handles eppy IDF model loading, initialization and common operations.
"""
from pathlib import Path
from typing import Optional
import os

from eppy.modeleditor import IDF

class EppyHandler:
    """Handles eppy IDF model loading and provides utility functions."""
    
    def __init__(self, idd_path: Optional[str] = None):
        """
        Initialize the EppyHandler.
        
        Args:
            idd_path: Path to the Energy+.idd file. If None, will look in common locations.
        """
        self.idd_path = self._find_idd_file(idd_path)
        if not self.idd_path:
            raise FileNotFoundError(
                "Energy+.idd file not found. Please provide path to IDD file or place it in the project root."
            )
        self._initialize_eppy()

    def _find_idd_file(self, idd_path: Optional[str] = None) -> Optional[str]:
        """
        Find the Energy+.idd file.
        
        Args:
            idd_path: Optional path to IDD file.
            
        Returns:
            Path to IDD file if found, None otherwise.
        """
        if idd_path and os.path.isfile(idd_path):
            return idd_path
            
        # System installation path and common locations
        search_paths = [
            r"C:\EnergyPlusV9-4-0\Energy+.idd",  # System installation path
            "Energy+.idd",  # Current directory
            "tests/Energy+.idd",  # Tests directory
            "../Energy+.idd",  # Parent directory
        ]
        
        for path in search_paths:
            if os.path.isfile(path):
                return path
                
        return None

    def _initialize_eppy(self) -> None:
        """Initialize eppy with the IDD file."""
        IDF.setiddname(self.idd_path)

    def load_idf(self, idf_path: str) -> IDF:
        """
        Load and return an IDF model.
        
        Args:
            idf_path: Path to the IDF file to load.
            
        Returns:
            IDF: The loaded IDF model.
            
        Raises:
            FileNotFoundError: If IDF file not found.
            Exception: For other eppy-related errors.
        """
        if not os.path.isfile(idf_path):
            raise FileNotFoundError(f"IDF file not found at '{idf_path}'")
            
        try:
            return IDF(idf_path)
        except Exception as e:
            raise Exception(f"Failed to load IDF file: {e}")

    def get_objects_by_type(self, idf: IDF, object_type: str) -> list:
        """
        Get all objects of a specific type from the IDF model.
        
        Args:
            idf: The IDF model to query.
            object_type: The type of objects to retrieve (e.g., 'Schedule:Compact').
            
        Returns:
            list: List of objects matching the specified type.
        """
        try:
            return idf.idfobjects[object_type]
        except KeyError:
            return []  # Return empty list if object type not found


    def get_schedule_objects(self, idf: IDF) -> list:
        """
        Get all Schedule:Compact objects from the IDF model.
        
        Args:
            idf: The IDF model to query.
            
        Returns:
            list: List of Schedule:Compact objects.
        """
        return self.get_objects_by_type(idf, "Schedule:Compact")

    def get_settings_objects(self, idf: IDF) -> dict:
        """
        Get common settings objects from the IDF model.
        
        Args:
            idf: The IDF model to query.
            
        Returns:
            dict: Dictionary of settings objects by type.
        """
        settings_types = [
            "Version",
            "RunPeriod",
            "Timestep",
            "ConvergenceLimits",
            "SimulationControl",
            "Site:Location",
            "Site:GroundTemperature:BuildingSurface",
            "Site:GroundTemperature:Deep",
            "Site:GroundTemperature:Shallow",
            "Site:GroundTemperature:FCfactorMethod",
            "Site:GroundReflectance",
            "Site:GroundReflectance:SnowModifier"
        ]
        
        return {
            obj_type: self.get_objects_by_type(idf, obj_type)
            for obj_type in settings_types
        }