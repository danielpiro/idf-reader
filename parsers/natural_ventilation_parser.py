"""
Extracts and processes natural ventilation data from ZoneVentilation:DesignFlowRate objects.
"""
from typing import Dict, Any, Optional
from utils.data_loader import DataLoader, safe_float

class NaturalVentilationExtractor:
    """
    Extracts natural ventilation data from ZoneVentilation:DesignFlowRate objects.
    """
    def __init__(self, data_loader: Optional[DataLoader] = None):
        self.data_loader = data_loader
        self.ventilation_data = {}

    def process_idf(self, idf) -> None:
        """Process the IDF file and extract natural ventilation data."""
        if not self.data_loader:
            raise RuntimeError("NaturalVentilationExtractor requires a DataLoader instance.")
        
        self._process_ventilation_data()

    def _process_ventilation_data(self) -> None:
        """Process ventilation data from ZoneVentilation:DesignFlowRate objects."""
        if not self.data_loader:
            return

        ventilation_loads = self.data_loader.get_ventilation_loads()
        
        for zone_name, loads in ventilation_loads.items():
            for load in loads:
                self.ventilation_data[zone_name] = {
                    'zone_name': zone_name,
                    'schedule_name': load.get('schedule_name', ''),
                    'design_flow_rate': load.get('design_flow_rate', 0.0),
                    'ventilation_type': load.get('ventilation_type', ''),
                    'min_indoor_temp': load.get('min_indoor_temp', 0.0),
                    'max_indoor_temp': load.get('max_indoor_temp', 0.0),
                    'max_temp_difference': load.get('max_temp_difference', 0.0),
                    'min_outdoor_temp': load.get('min_outdoor_temp', 0.0),
                    'max_outdoor_temp': load.get('max_outdoor_temp', 0.0),
                    'max_wind_speed': load.get('max_wind_speed', 0.0)
                }

    def get_ventilation_data(self) -> Dict[str, Dict[str, Any]]:
        """Returns the processed ventilation data."""
        return self.ventilation_data 