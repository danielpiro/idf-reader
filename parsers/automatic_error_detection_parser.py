"""
Extracts and processes automatic error detection data.
Contains hardcoded data for error detection analysis.
"""
from typing import Dict, Any, Optional, List
from utils.data_loader import DataLoader

class AutomaticErrorDetectionParser:
    """
    Extracts automatic error detection data with hardcoded values for analysis.
    """
    def __init__(self, data_loader: Optional[DataLoader] = None):
        self.data_loader = data_loader
        self.error_detection_data = []

    def process_idf(self, idf) -> None:
        """
        Process the IDF file and extract automatic error detection data.
        Currently uses hardcoded data as specified.
        """
        # DataLoader is not required for hardcoded data
        self._process_error_detection_data()

    def _process_error_detection_data(self) -> None:
        """Process hardcoded error detection data."""
        # Hardcoded data as specified
        self.error_detection_data = [
            {
                'zone_name': 'Site',
                'category': 'Terrain',
                'current_model_value': 'Suburbs',
                'recommended_standard_value': 'City',
                'remark': 'Need to change'
            },
            {
                'zone_name': 'Site',
                'category': 'Ground Temperature',
                'current_model_value': '10',
                'recommended_standard_value': '18',
                'remark': 'Need to change'
            },
            {
                'zone_name': '00:01XLIV',
                'category': 'Natural Ventilation',
                'current_model_value': '2',
                'recommended_standard_value': '0',
                'remark': 'Direction is not Correct'
            },
            {
                'zone_name': '00:01XMMD',
                'category': 'Natural Ventilation',
                'current_model_value': '2',
                'recommended_standard_value': '0',
                'remark': 'Direction is not Correct'
            },
            {
                'zone_name': '01:03XLIV',
                'category': 'Lighting',
                'current_model_value': '2',
                'recommended_standard_value': '5',
                'remark': 'Need to change'
            },
            {
                'zone_name': '02:05XLIV',
                'category': 'Lighting Control',
                'current_model_value': 'cheek',
                'recommended_standard_value': '-',
                'remark': 'Not allowed'
            },
            {
                'zone_name': '3:07XLIV',
                'category': 'Infiltration',
                'current_model_value': '2',
                'recommended_standard_value': '1',
                'remark': 'Need to change'
            }
        ]

    def get_error_detection_data(self) -> List[Dict[str, Any]]:
        """Returns the processed error detection data."""
        return self.error_detection_data 