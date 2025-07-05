"""
Extracts and processes automatic error detection data.
Uses validation tables for settings, loads, and HVAC.
"""
from typing import Dict, Any, Optional, List
from utils.data_loader import DataLoader

class AutomaticErrorDetectionParser:
    """
    Extracts automatic error detection data using validation tables.
    """
    def __init__(self, data_loader: Optional[DataLoader] = None, climate_zone: str = 'A'):
        self.data_loader = data_loader
        self.error_detection_data = []
        self.supported_iso_types = ['Office', '2017', '2023']
        self.settings_extractor = None
        self.climate_zone = climate_zone.upper()  # Ensure uppercase for consistency
        self._init_validation_tables()

    def process_idf(self, idf, iso_type: str = 'Office') -> None:
        """
        Process the IDF file and extract automatic error detection data.
        Uses validation tables based on ISO type and climate zone.
        """
        if iso_type not in self.supported_iso_types:
            iso_type = 'Office'  # Default fallback
        
        # Initialize settings extractor to get actual IDF values
        if self.data_loader:
            from parsers.settings_parser import SettingsExtractor
            self.settings_extractor = SettingsExtractor(self.data_loader)
            self.settings_extractor.process_idf()
        
        self._process_error_detection_data(iso_type, idf)

    def _init_validation_tables(self) -> None:
        """Initialize validation tables for settings, loads, and HVAC."""
        # Settings validation table (applies to all ISO types)
        self.settings_table = {
            'EnergyPlus Version': {'recommended': '9.4.0.2', 'details': 'Version should be between 9.4.0.0 and 9.4.0.1'},
            'Surface Convection Algorithm (Inside)': {'recommended': 'TARP', 'details': 'Not supported value'},
            'Surface Convection Algorithm (Outside)': {'recommended': 'DOE-2', 'details': 'Not supported value'},
            'Heat Balance Algorithm': {'recommended': 'ConductionTransferFunction', 'details': 'Not supported value'},
            'Time Step': {'recommended': '6', 'details': 'Not supported value'},
            'Run Period Start Date': {'recommended': '1/1', 'details': 'Not supported value'},
            'Run Period End Date': {'recommended': '12/31', 'details': 'Not supported value'},
            'Shading Calculation Method': {'recommended': 'PolygonClipping', 'details': 'Not supported value'},
            'Shading Calculation Update Frequency Method': {'recommended': 'Periodic', 'details': 'Not supported value'},
            'Shading Calculation Update Frequency': {'recommended': '20', 'details': 'Not supported value'},
            'Maximum Figures in Shadow Overlap Calculations': {'recommended': '15000', 'details': 'Not supported value'},
            'Polygon Clipping Algorithm': {'recommended': 'SutherlandHodgman', 'details': 'Not supported value'},
            'Sky Diffuse Modeling Algorithm': {'recommended': 'SimpleSkyDiffuseModeling', 'details': 'Not supported value'},
            'Terrain': {'recommended': 'City', 'details': 'Not supported value'},
            'Ground Temperature January': {'recommended': '18.0', 'details': 'Not supported value'},
            'Ground Temperature February': {'recommended': '18.0', 'details': 'Not supported value'},
            'Ground Temperature March': {'recommended': '18.0', 'details': 'Not supported value'},
            'Ground Temperature April': {'recommended': '18.0', 'details': 'Not supported value'},
            'Ground Temperature May': {'recommended': '18.0', 'details': 'Not supported value'},
            'Ground Temperature June': {'recommended': '18.0', 'details': 'Not supported value'},
            'Ground Temperature July': {'recommended': '18.0', 'details': 'Not supported value'},
            'Ground Temperature August': {'recommended': '18.0', 'details': 'Not supported value'},
            'Ground Temperature September': {'recommended': '18.0', 'details': 'Not supported value'},
            'Ground Temperature October': {'recommended': '18.0', 'details': 'Not supported value'},
            'Ground Temperature November': {'recommended': '18.0', 'details': 'Not supported value'},
            'Ground Temperature December': {'recommended': '18.0', 'details': 'Not supported value'},
            'Ground Temp Deep January': {'recommended': '18.0', 'details': 'Not supported value'},
            'Ground Temp Deep February': {'recommended': '18.0', 'details': 'Not supported value'},
            'Ground Temp Deep March': {'recommended': '18.0', 'details': 'Not supported value'},
            'Ground Temp Deep April': {'recommended': '18.0', 'details': 'Not supported value'},
            'Ground Temp Deep May': {'recommended': '18.0', 'details': 'Not supported value'},
            'Ground Temp Deep June': {'recommended': '18.0', 'details': 'Not supported value'},
            'Ground Temp Deep July': {'recommended': '18.0', 'details': 'Not supported value'},
            'Ground Temp Deep August': {'recommended': '18.0', 'details': 'Not supported value'},
            'Ground Temp Deep September': {'recommended': '18.0', 'details': 'Not supported value'},
            'Ground Temp Deep October': {'recommended': '18.0', 'details': 'Not supported value'},
            'Ground Temp Deep November': {'recommended': '18.0', 'details': 'Not supported value'},
            'Ground Temp Deep December': {'recommended': '18.0', 'details': 'Not supported value'},
            'Ground Temp Shallow January': {'recommended': '18.0', 'details': 'Not supported value'},
            'Ground Temp Shallow February': {'recommended': '18.0', 'details': 'Not supported value'},
            'Ground Temp Shallow March': {'recommended': '18.0', 'details': 'Not supported value'},
            'Ground Temp Shallow April': {'recommended': '18.0', 'details': 'Not supported value'},
            'Ground Temp Shallow May': {'recommended': '18.0', 'details': 'Not supported value'},
            'Ground Temp Shallow June': {'recommended': '18.0', 'details': 'Not supported value'},
            'Ground Temp Shallow July': {'recommended': '18.0', 'details': 'Not supported value'},
            'Ground Temp Shallow August': {'recommended': '18.0', 'details': 'Not supported value'},
            'Ground Temp Shallow September': {'recommended': '18.0', 'details': 'Not supported value'},
            'Ground Temp Shallow October': {'recommended': '18.0', 'details': 'Not supported value'},
            'Ground Temp Shallow November': {'recommended': '18.0', 'details': 'Not supported value'},
            'Ground Temp Shallow December': {'recommended': '18.0', 'details': 'Not supported value'},
            'Ground Reflectance January': {'recommended': '0.2', 'details': 'Not supported value'},
            'Ground Reflectance February': {'recommended': '0.2', 'details': 'Not supported value'},
            'Ground Reflectance March': {'recommended': '0.2', 'details': 'Not supported value'},
            'Ground Reflectance April': {'recommended': '0.2', 'details': 'Not supported value'},
            'Ground Reflectance May': {'recommended': '0.2', 'details': 'Not supported value'},
            'Ground Reflectance June': {'recommended': '0.2', 'details': 'Not supported value'},
            'Ground Reflectance July': {'recommended': '0.2', 'details': 'Not supported value'},
            'Ground Reflectance August': {'recommended': '0.2', 'details': 'Not supported value'},
            'Ground Reflectance September': {'recommended': '0.2', 'details': 'Not supported value'},
            'Ground Reflectance October': {'recommended': '0.2', 'details': 'Not supported value'},
            'Ground Reflectance November': {'recommended': '0.2', 'details': 'Not supported value'},
            'Ground Reflectance December': {'recommended': '0.2', 'details': 'Not supported value'}
        }
        
        # Loads validation table (per ISO type)
        # Structure: Zone -> Load Type -> Field -> {recommended, details}
        self.loads_table = {
            'Office': {
                # Example structure - will be populated with actual data
                'Zone1': {
                    'Lighting': {
                        'Power Density': {'recommended': '12', 'details': 'Not supported value'},
                        'Schedule': {'recommended': 'Office_Lighting', 'details': 'Not supported value'}
                    },
                    'Equipment': {
                        'Power Density': {'recommended': '8', 'details': 'Not supported value'},
                        'Schedule': {'recommended': 'Office_Equipment', 'details': 'Not supported value'}
                    }
                }
            },
            '2017': {
                # 2017 ISO Load Table
                'Occupancy': {
                    'people_per_area': {'recommended': '0.04', 'details': 'Not supported value'},
                    'activity_schedule_per_person': {'recommended': '125', 'details': 'Not supported value'},
                    'schedule_rule': {'recommended': '0.64 0.64 0.64 0.64 0.64 0.64 0.64 0 0 0 0 0 0 0 0 1 1 1 1 1 1 1 1 0.64', 'details': 'Not supported value'}
                },
                'Lighting': {
                    'power_density_w_m2': {'recommended': '5', 'details': 'Not supported value'},
                    'schedule_rule': {'recommended': '0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 1 1 1 1 1 1 1 0', 'details': 'Not supported value'}
                },
                'Non Fixed Equipment (area <= 150)': {
                    'power_density_w_m2': {'recommended': '8', 'details': 'Not supported value'},
                    'schedule_rule': {'recommended': '0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 1 1 1 1 1 1 1 1 0', 'details': 'Not supported value'}
                },
                'Fixed Equipment (area <= 150)': {
                    'power_density_w_m2': {'recommended': '1', 'details': 'Not supported value'},
                    'schedule_rule': {'recommended': '1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1', 'details': 'Not supported value'}
                },
                'Non Fixed Equipment (area > 150)': {
                    'power_density_w_m2': {'recommended': '6', 'details': 'Not supported value'},
                    'schedule_rule': {'recommended': '0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 1 1 1 1 1 1 1 1 0', 'details': 'Not supported value'}
                },
                'Fixed Equipment (area > 150)': {
                    'power_density_w_m2': {'recommended': '0.74', 'details': 'Not supported value'},
                    'schedule_rule': {'recommended': '1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1', 'details': 'Not supported value'}
                },
                'Combined Equipment (area <= 150, edge case)': {
                    'power_density_w_m2': {'recommended': '9', 'details': 'Not supported value'},
                    'schedule_rule': {'recommended': '0.11 0.11 0.11 0.11 0.11 0.11 0.11 0.11 0.11 0.11 0.11 0.11 0.11 0.11 0.11 0.11 1 1 1 1 1 1 1 0.11', 'details': 'Not supported value'}
                },
                'Combined Equipment (area > 150, edge case)': {
                    'power_density_w_m2': {'recommended': '7', 'details': 'Not supported value'},
                    'schedule_rule': {'recommended': '0.14 0.14 0.14 0.14 0.14 0.14 0.14 0.14 0.14 0.14 0.14 0.14 0.14 0.14 0.14 0.14 1 1 1 1 1 1 1 0.14', 'details': 'Not supported value'}
                }
            },
            '2023': {
                # Will be populated when you provide the data for 2023 ISO
            }
        }
        
        # HVAC validation table (per ISO type)
        # Structure: Climate Zone -> System Type -> Field -> {recommended, details}
        self.hvac_table = {
            'Office': {
                # Example structure - will be populated with actual data
                'Zone1': {
                    'Heating_Schedule': {
                        'Setpoint': {'recommended': '20', 'details': 'Not supported value'},
                        'Schedule_Type': {'recommended': 'Compact', 'details': 'Not supported value'}
                    },
                    'Cooling_Schedule': {
                        'Setpoint': {'recommended': '24', 'details': 'Not supported value'},
                        'Schedule_Type': {'recommended': 'Compact', 'details': 'Not supported value'}
                    }
                }
            },
            '2017': {
                # 2017 ISO HVAC Table - Climate zones A, B, C, D
                'A': {
                    'Heating Schedule': {
                        'setpoint_non_work_time': {'recommended': '-', 'details': 'Not supported value'},
                        'setpoint_c': {'recommended': '20', 'details': 'Not supported value'},
                        'schedule_rule': {'recommended': '01/01 -> 31/03: 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1; 31/03 -> 30/11: 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0; 30/11 -> 31/12: 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1', 'details': 'Not supported value'}
                    },
                    'Cooling Schedule': {
                        'setpoint_non_work_time': {'recommended': '-', 'details': 'Not supported value'},
                        'setpoint_c': {'recommended': '24', 'details': 'Not supported value'},
                        'schedule_rule': {'recommended': '01/01 -> 31/03: 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0; 31/03 -> 30/11: 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1; 30/11 -> 31/12: 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0', 'details': 'Not supported value'}
                    },
                    'Infiltration': {
                        'rate_ach': {'recommended': '1', 'details': 'Not supported value'},
                        'schedule_rule': {'recommended': '1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1', 'details': 'Not supported value'}
                    },
                    'Natural Ventilation': {
                        'rate_ach': {'recommended': '2', 'details': 'Not supported value'},
                        'schedule_rule': {'recommended': '01/01 -> 31/03: 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0; 31/03 -> 30/11: 1 1 1 1 1 1 0 0 0 0 0 0 0 0 0 0 0 0 0 1 1 1 1 1; 30/11 -> 31/12: 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0', 'details': 'Not supported value'},
                        'windows_directions_required': {'recommended': '2', 'details': 'Missing at least 2 windows directions'}
                    }
                },
                'B': {
                    'Heating Schedule': {
                        'setpoint_non_work_time': {'recommended': '-', 'details': 'Not supported value'},
                        'setpoint_c': {'recommended': '20', 'details': 'Not supported value'},
                        'schedule_rule': {'recommended': '01/01 -> 31/03: 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1; 31/03 -> 30/11: 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0; 30/11 -> 31/12: 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1', 'details': 'Not supported value'}
                    },
                    'Cooling Schedule': {
                        'setpoint_non_work_time': {'recommended': '-', 'details': 'Not supported value'},
                        'setpoint_c': {'recommended': '24', 'details': 'Not supported value'},
                        'schedule_rule': {'recommended': '01/01 -> 31/03: 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0; 31/03 -> 30/11: 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1; 30/11 -> 31/12: 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0', 'details': 'Not supported value'}
                    },
                    'Infiltration': {
                        'rate_ach': {'recommended': '1', 'details': 'Not supported value'},
                        'schedule_rule': {'recommended': '1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1', 'details': 'Not supported value'}
                    },
                    'Natural Ventilation': {
                        'rate_ach': {'recommended': '2', 'details': 'Not supported value'},
                        'schedule_rule': {'recommended': '01/01 -> 31/03: 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0; 31/03 -> 30/11: 1 1 1 1 1 1 0 0 0 0 0 0 0 0 0 0 0 0 0 1 1 1 1 1; 30/11 -> 31/12: 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0', 'details': 'Not supported value'},
                        'windows_directions_required': {'recommended': '2', 'details': 'Missing at least 2 windows directions'}
                    }
                },
                'C': {
                    'Heating Schedule': {
                        'setpoint_non_work_time': {'recommended': '-', 'details': 'Not supported value'},
                        'setpoint_c': {'recommended': '20', 'details': 'Not supported value'},
                        'schedule_rule': {'recommended': '01/01 -> 30/04: 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1; 30/04 -> 31/10: 1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0; 31/10 -> 31/12: 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1', 'details': 'Not supported value'}
                    },
                    'Cooling Schedule': {
                        'setpoint_non_work_time': {'recommended': '-', 'details': 'Not supported value'},
                        'setpoint_c': {'recommended': '24', 'details': 'Not supported value'},
                        'schedule_rule': {'recommended': '01/01 -> 30/04: 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0; 30/04 -> 31/10: 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1; 31/10 -> 31/12: 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0', 'details': 'Not supported value'}
                    },
                    'Infiltration': {
                        'rate_ach': {'recommended': '1', 'details': 'Not supported value'},
                        'schedule_rule': {'recommended': '1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1', 'details': 'Not supported value'}
                    },
                    'Natural Ventilation': {
                        'rate_ach': {'recommended': '2', 'details': 'Not supported value'},
                        'schedule_rule': {'recommended': '01/01 -> 30/04: 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0; 30/04 -> 31/10: 1 1 1 1 1 1 0 0 0 0 0 0 0 0 0 0 0 0 0 1 1 1 1 1; 31/10 -> 31/12: 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0', 'details': 'Not supported value'},
                        'windows_directions_required': {'recommended': '2', 'details': 'Missing at least 2 windows directions'}
                    }
                },
                'D': {
                    'Heating Schedule': {
                        'setpoint_non_work_time': {'recommended': '-', 'details': 'Not supported value'},
                        'setpoint_c': {'recommended': '20', 'details': 'Not supported value'},
                        'schedule_rule': {'recommended': '01/01 -> 28/02: 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1; 28/02 -> 30/11: 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0; 30/11 -> 31/12: 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1', 'details': 'Not supported value'}
                    },
                    'Cooling Schedule': {
                        'setpoint_non_work_time': {'recommended': '-', 'details': 'Not supported value'},
                        'setpoint_c': {'recommended': '24', 'details': 'Not supported value'},
                        'schedule_rule': {'recommended': '01/01 -> 28/02: 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0; 28/02 -> 30/11: 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1; 30/11 -> 31/12: 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0', 'details': 'Not supported value'}
                    },
                    'Infiltration': {
                        'rate_ach': {'recommended': '1', 'details': 'Not supported value'},
                        'schedule_rule': {'recommended': '1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1', 'details': 'Not supported value'}
                    },
                    'Natural Ventilation': {
                        'rate_ach': {'recommended': '2', 'details': 'Not supported value'},
                        'schedule_rule': {'recommended': '01/01 -> 28/02: 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0; 28/02 -> 30/11: 1 1 1 1 1 1 0 0 0 0 0 0 0 0 0 0 0 0 0 1 1 1 1 1; 30/11 -> 31/12: 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0', 'details': 'Not supported value'},
                        'windows_directions_required': {'recommended': '2', 'details': 'Missing at least 2 windows directions'}
                    }
                }
            },
            '2023': {
                # Will be populated when you provide the data for 2023 ISO
            }
        }

    def _process_error_detection_data(self, iso_type: str = 'Office', idf=None) -> None:
        """Process error detection data using validation tables."""
        self.error_detection_data = []
        
        # Process settings validation (applies to all ISO types)
        self._validate_settings()
        
        # Process loads validation (per ISO type)
        self._validate_loads(iso_type, idf)
        
        # Process HVAC validation (per ISO type)
        self._validate_hvac(iso_type, self.climate_zone, idf)
        
        # Keep some hardcoded data for loads and HVAC until we implement full validation
        # These will be replaced when we implement loads and HVAC validation
        self.error_detection_data.extend([
            {
                'zone_name': '00:01XLIV',
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
            }
        ])
        
    def _validate_settings(self) -> None:
        """Validate settings using the settings table."""
        if not self.settings_extractor:
            return
        
        # Get current settings from IDF
        current_settings = self.settings_extractor.get_settings()
        
        print(f"\n=== SETTINGS VALIDATION DEBUG ===")
        print(f"Climate Zone: {self.climate_zone}")
        
        # Validate EnergyPlus version
        version_info = current_settings.get('version', {})
        if version_info.get('energyplus'):
            current_version = version_info['energyplus']
            recommended_version = self.settings_table['EnergyPlus Version']['recommended']
            print(f"EnergyPlus Version - Current: {current_version}, Recommended: {recommended_version}")
            if current_version != recommended_version:
                print(f"✗ VERSION MISMATCH DETECTED!")
                self.error_detection_data.append({
                    'zone_name': 'Site',
                    'category': 'EnergyPlus Version',
                    'current_model_value': current_version,
                    'recommended_standard_value': recommended_version,
                    'remark': self.settings_table['EnergyPlus Version']['details']
                })
            else:
                print(f"✓ Version matches standard")
        else:
            print("⚠ No EnergyPlus version found in settings")
        
        # Validate terrain
        site_info = current_settings.get('site', {})
        if site_info.get('terrain'):
            current_terrain = site_info['terrain']
            recommended_terrain = self.settings_table['Terrain']['recommended']
            print(f"Terrain - Current: {current_terrain}, Recommended: {recommended_terrain}")
            if current_terrain != recommended_terrain:
                print(f"✗ TERRAIN MISMATCH DETECTED!")
                self.error_detection_data.append({
                    'zone_name': 'Site',
                    'category': 'Terrain',
                    'current_model_value': current_terrain,
                    'recommended_standard_value': recommended_terrain,
                    'remark': 'Need to change'
                })
            else:
                print(f"✓ Terrain matches standard")
        else:
            print("⚠ No terrain found in settings")
        
        # Validate Surface Convection Algorithms
        algorithms = current_settings.get('algorithms', {})
        if algorithms.get('surface_convection_inside'):
            current_inside = algorithms['surface_convection_inside']
            recommended_inside = self.settings_table['Surface Convection Algorithm (Inside)']['recommended']
            if current_inside != recommended_inside:
                self.error_detection_data.append({
                    'zone_name': 'Site',
                    'category': 'Surface Convection Algorithm (Inside)',
                    'current_model_value': current_inside,
                    'recommended_standard_value': recommended_inside,
                    'remark': self.settings_table['Surface Convection Algorithm (Inside)']['details']
                })
        
        if algorithms.get('surface_convection_outside'):
            current_outside = algorithms['surface_convection_outside']
            recommended_outside = self.settings_table['Surface Convection Algorithm (Outside)']['recommended']
            if current_outside != recommended_outside:
                self.error_detection_data.append({
                    'zone_name': 'Site',
                    'category': 'Surface Convection Algorithm (Outside)',
                    'current_model_value': current_outside,
                    'recommended_standard_value': recommended_outside,
                    'remark': self.settings_table['Surface Convection Algorithm (Outside)']['details']
                })
        
        # Validate Heat Balance Algorithm
        if algorithms.get('heat_balance'):
            current_heat_balance = algorithms['heat_balance']
            recommended_heat_balance = self.settings_table['Heat Balance Algorithm']['recommended']
            if current_heat_balance != recommended_heat_balance:
                self.error_detection_data.append({
                    'zone_name': 'Site',
                    'category': 'Heat Balance Algorithm',
                    'current_model_value': current_heat_balance,
                    'recommended_standard_value': recommended_heat_balance,
                    'remark': self.settings_table['Heat Balance Algorithm']['details']
                })
        
        # Validate Time Step
        if current_settings.get('simulation', {}).get('time_step'):
            current_timestep = str(current_settings['simulation']['time_step'])
            recommended_timestep = self.settings_table['Time Step']['recommended']
            if current_timestep != recommended_timestep:
                self.error_detection_data.append({
                    'zone_name': 'Site',
                    'category': 'Time Step',
                    'current_model_value': current_timestep,
                    'recommended_standard_value': recommended_timestep,
                    'remark': self.settings_table['Time Step']['details']
                })
        
        # Validate Ground Temperature (all months)
        ground_temp = current_settings.get('site', {}).get('ground_temperature', {})
        if ground_temp:
            for month in ['January', 'February', 'March', 'April', 'May', 'June', 
                         'July', 'August', 'September', 'October', 'November', 'December']:
                if month in ground_temp:
                    current_temp = str(ground_temp[month])
                    recommended_temp = self.settings_table[f'Ground Temperature {month}']['recommended']
                    if current_temp != recommended_temp:
                        self.error_detection_data.append({
                            'zone_name': 'Site',
                            'category': f'Ground Temperature {month}',
                            'current_model_value': current_temp,
                            'recommended_standard_value': recommended_temp,
                            'remark': 'Need to change'
                        })
        
        # Validate Ground Reflectance (all months)
        ground_reflectance = current_settings.get('site', {}).get('ground_reflectance', {})
        if ground_reflectance:
            for month in ['January', 'February', 'March', 'April', 'May', 'June', 
                         'July', 'August', 'September', 'October', 'November', 'December']:
                if month in ground_reflectance:
                    current_reflectance = str(ground_reflectance[month])
                    recommended_reflectance = self.settings_table[f'Ground Reflectance {month}']['recommended']
                    if current_reflectance != recommended_reflectance:
                        self.error_detection_data.append({
                            'zone_name': 'Site',
                            'category': f'Ground Reflectance {month}',
                            'current_model_value': current_reflectance,
                            'recommended_standard_value': recommended_reflectance,
                            'remark': 'Need to change'
                        })
        
        # Summary
        settings_issues = [item for item in self.error_detection_data if 'Site' in item.get('zone_name', '') or 'Global' in item.get('zone_name', '')]
        print(f"Settings validation completed. Found {len(settings_issues)} issues.\n")
        
    def _validate_loads(self, iso_type: str, idf) -> None:
        """Validate loads using the loads table for specific ISO type."""
        if iso_type not in self.loads_table or not self.data_loader:
            return
        
        # Get zones and areas for area calculation
        zones = self.data_loader.get_zones()
        
        # Import and initialize required parsers
        try:
            from parsers.lighting_parser import LightingParser
            from parsers.schedule_parser import ScheduleExtractor
            from parsers.area_parser import AreaParser  # Fixed import name
            from parsers.load_parser import LoadExtractor  # Fixed class name
            from parsers.materials_parser import MaterialsParser  # Needed for AreaParser
            
            lighting_parser = LightingParser(self.data_loader) 
            schedule_parser = ScheduleExtractor(self.data_loader)
            materials_parser = MaterialsParser(self.data_loader)  # Create MaterialsParser first
            areas_parser = AreaParser(self.data_loader, materials_parser)  # Pass materials_parser
            load_parser = LoadExtractor(self.data_loader)
            
            # Process all parsers
            # lighting_parser.parse() is called directly, no process_idf() needed
            schedule_parser.process_idf(idf)
            materials_parser.process_idf(idf)  # Process materials first
            areas_parser.process_idf(idf)
            load_parser.process_idf(idf)
            
            # Get extracted data
            lighting_data = lighting_parser.parse()  # Updated method name
            schedule_data = schedule_parser.get_all_schedules()  # Updated method name
            load_data = load_parser.get_parsed_zone_loads()  # Get people and equipment data by zone
            
            print(f"\n=== LOADS VALIDATION DEBUG (ISO: {iso_type}, Climate: {self.climate_zone}) ===")
            print(f"Lighting data keys: {list(lighting_data.keys()) if lighting_data else 'None'}")
            print(f"Schedule data keys: {list(schedule_data.keys()) if schedule_data else 'None'}")
            print(f"Load data keys: {list(load_data.keys()) if load_data else 'None'}")
            
            # Extract people and equipment data from zone-based load_data
            # load_data structure: {zone_name: {loads: {people: {...}, lights: {...}, equipment: {...}}}}
            people_data = {}
            lights_data_from_loads = {}
            equipment_data = {}
            
            if load_data:
                for zone_name, zone_info in load_data.items():
                    zone_loads = zone_info.get('loads', {})
                    if zone_loads.get('people'):
                        people_data[zone_name] = zone_loads['people']
                    if zone_loads.get('lights'):
                        lights_data_from_loads[zone_name] = zone_loads['lights']
                    # Combine fixed and non-fixed equipment
                    equipment_info = {}
                    if zone_loads.get('non_fixed_equipment'):
                        equipment_info.update(zone_loads['non_fixed_equipment'])
                    if zone_loads.get('fixed_equipment'):
                        equipment_info['fixed'] = zone_loads['fixed_equipment']
                    if equipment_info:
                        equipment_data[zone_name] = equipment_info
            
            print(f"People data sample: {dict(list(people_data.items())[:2]) if people_data else 'None'}")
            print(f"Lighting data sample: {dict(list(lighting_data.items())[:2]) if lighting_data else 'None'}")
            print(f"Lights from loads sample: {dict(list(lights_data_from_loads.items())[:2]) if lights_data_from_loads else 'None'}")
            print(f"Equipment data sample: {dict(list(equipment_data.items())[:2]) if equipment_data else 'None'}")
            
            # For 2017 ISO validation
            if iso_type == '2017':
                self._validate_2017_loads(people_data, lights_data_from_loads, equipment_data, schedule_data, zones, areas_parser)
                
        except ImportError as e:
            print(f"LOADS ERROR: Could not import parser: {e}")
        except Exception as e:
            print(f"LOADS ERROR: Error in loads validation: {e}")
    
    def _validate_2017_loads(self, people_data, lights_data_from_loads, equipment_data, schedule_data, zones, areas_parser):
        """Validate loads according to 2017 ISO standards with area-based criteria."""
        print(f"\n=== 2017 LOADS VALIDATION COMPARISON (Climate: {self.climate_zone}) ===")
        
        validation_count = 0
        
        # Filter for HVAC zones only
        hvac_zones = self.data_loader.get_hvac_zones()
        print(f"HVAC zones: {hvac_zones}")
        
        # Group zones by floor (extract floor prefix like "00:", "01:", "02:")
        floors_data = {}
        for zone_id, zone_info in zones.items():
            if zone_id not in hvac_zones:
                continue  # Skip non-HVAC zones
                
            # Extract floor number (e.g., "00:01XLIVING" -> "01")
            if ':' in zone_id:
                parts = zone_id.split(':')
                if len(parts) > 1 and len(parts[1]) >= 2:
                    floor_prefix = parts[1][:2]  # Get first 2 digits after colon
                else:
                    floor_prefix = zone_id[:2]  # Fallback
            else:
                floor_prefix = zone_id[:2]  # Fallback
            
            if floor_prefix not in floors_data:
                floors_data[floor_prefix] = {
                    'zones': [],
                    'total_area': 0,
                    'people_data': {},
                    'lights_data': {},
                    'equipment_data': {}
                }
            
            floor_area = zone_info.get('floor_area', 0)
            floors_data[floor_prefix]['zones'].append(zone_id)
            floors_data[floor_prefix]['total_area'] += floor_area
            
            # Aggregate data for this floor
            if zone_id in people_data:
                floors_data[floor_prefix]['people_data'][zone_id] = people_data[zone_id]
            if zone_id in lights_data_from_loads:
                floors_data[floor_prefix]['lights_data'][zone_id] = lights_data_from_loads[zone_id]
            if zone_id in equipment_data:
                floors_data[floor_prefix]['equipment_data'][zone_id] = equipment_data[zone_id]
        
        # Validate each floor
        for floor_prefix, floor_info in floors_data.items():
            total_floor_area = floor_info['total_area']
            zones_in_floor = floor_info['zones']
            
            print(f"\nValidating floor: {floor_prefix} (Total Area: {total_floor_area:.2f} m²)")
            print(f"  Zones in floor: {zones_in_floor}")
            
            # Determine area category for 2017 validation based on total floor area
            area_category = '≤150 m²' if total_floor_area <= 150 else '>150 m²'
            area_requirements = self.loads_table['2017'].get(area_category, {})
            print(f"Using {area_category} requirements")
            
            # Validate People/Occupancy (check any zone in the floor has people data)
            if floor_info['people_data']:
                # Use first zone's people density (should be consistent across floor)
                sample_zone = next(iter(floor_info['people_data']))
                zone_people_info = floor_info['people_data'][sample_zone]
                current_people_per_area = zone_people_info.get('people_per_area', 0)
                
                if 'People' in area_requirements:
                    recommended_people = float(area_requirements['People']['value'].split()[0])  # Extract number from "0.08 people/m²"
                    print(f"  People: Current={current_people_per_area}, Recommended={recommended_people}")
                    
                    if abs(current_people_per_area - recommended_people) > 0.001:
                        print(f"  ✗ PEOPLE MISMATCH DETECTED!")
                        self.error_detection_data.append({
                            'zone_name': f'Floor {floor_prefix}',
                            'category': 'People Density',
                            'current_model_value': f"{current_people_per_area} people/m²",
                            'recommended_standard_value': area_requirements['People']['value'],
                            'remark': area_requirements['People']['details']
                        })
                        validation_count += 1
                    else:
                        print(f"  ✓ People density matches standard")
            
            # Validate Lighting (from loads data, not lighting parser)
            if floor_info['lights_data']:
                # Use first zone's lighting density (should be consistent across floor)
                sample_zone = next(iter(floor_info['lights_data']))
                zone_lights_info = floor_info['lights_data'][sample_zone]
                current_lighting_watts = zone_lights_info.get('watts_per_area', 0)
                
                if 'Lighting' in area_requirements:
                    recommended_lighting = float(area_requirements['Lighting']['value'].split()[0])  # Extract number from "4 W/m²"
                    print(f"  Lighting: Current={current_lighting_watts}, Recommended={recommended_lighting}")
                    
                    if abs(current_lighting_watts - recommended_lighting) > 0.001:
                        print(f"  ✗ LIGHTING MISMATCH DETECTED!")
                        self.error_detection_data.append({
                            'zone_name': f'Floor {floor_prefix}',
                            'category': 'Lighting Power Density',
                            'current_model_value': f"{current_lighting_watts} W/m²",
                            'recommended_standard_value': area_requirements['Lighting']['value'],
                            'remark': area_requirements['Lighting']['details']
                        })
                        validation_count += 1
                    else:
                        print(f"  ✓ Lighting power density matches standard")
            
            # Validate Equipment
            if floor_info['equipment_data']:
                # Use first zone's equipment density (should be consistent across floor)
                sample_zone = next(iter(floor_info['equipment_data']))
                zone_equipment_info = floor_info['equipment_data'][sample_zone]
                current_equipment_watts = zone_equipment_info.get('watts_per_area', 0)
                current_fixed_watts = zone_equipment_info.get('fixed', {}).get('watts_per_area', 0)
                total_equipment_watts = current_equipment_watts + current_fixed_watts
                
                if 'Equipment' in area_requirements:
                    recommended_equipment = float(area_requirements['Equipment']['value'].split()[0])  # Extract number from "14 W/m²"
                    print(f"  Equipment: Current={total_equipment_watts} (non-fixed: {current_equipment_watts} + fixed: {current_fixed_watts}), Recommended={recommended_equipment}")
                    
                    if abs(total_equipment_watts - recommended_equipment) > 0.001:
                        print(f"  ✗ EQUIPMENT MISMATCH DETECTED!")
                        self.error_detection_data.append({
                            'zone_name': f'Floor {floor_prefix}',
                            'category': 'Equipment Power Density',
                            'current_model_value': f"{total_equipment_watts} W/m²",
                            'recommended_standard_value': area_requirements['Equipment']['value'],
                            'remark': area_requirements['Equipment']['details']
                        })
                        validation_count += 1
                    else:
                        print(f"  ✓ Equipment power density matches standard")
        
        print(f"\n2017 Loads validation completed. Found {validation_count} mismatches.\n")
        print(f"Total floors validated: {len(floors_data)}")
        print(f"Floors: {list(floors_data.keys())}")
        
        # Show floor mapping for verification
        for floor_prefix, floor_info in floors_data.items():
            print(f"  Floor {floor_prefix}: {floor_info['zones']} (Total: {floor_info['total_area']:.1f} m²)")
    
    def _validate_hvac(self, iso_type: str, climate_zone: str = 'A', idf=None) -> None:
        """Validate HVAC using the HVAC table for specific ISO type and climate zone."""
        if iso_type not in self.hvac_table or not self.data_loader:
            return
        
        # TODO: Get climate_zone from GUI input (A, B, C, D)
        # For now using default 'A', should be passed from GUI
        
        try:
            from parsers.natural_ventilation_parser import NaturalVentilationExtractor
            from parsers.schedule_parser import ScheduleExtractor
            from parsers.area_parser import AreaParser  # Fixed import name
            from parsers.load_parser import LoadExtractor  # Fixed class name
            from parsers.materials_parser import MaterialsParser  # Needed for AreaParser
            
            natural_vent_parser = NaturalVentilationExtractor(self.data_loader)
            schedule_parser = ScheduleExtractor(self.data_loader)
            materials_parser = MaterialsParser(self.data_loader)  # Create MaterialsParser first
            areas_parser = AreaParser(self.data_loader, materials_parser)  # Pass materials_parser
            load_parser = LoadExtractor(self.data_loader)
            
            # Process all parsers
            natural_vent_parser.process_idf(idf)
            schedule_parser.process_idf(idf)
            materials_parser.process_idf(idf)  # Process materials first
            areas_parser.process_idf(idf)
            load_parser.process_idf(idf)
            
            # Get extracted data
            natural_vent_data = natural_vent_parser.get_ventilation_data()  # Updated method name
            schedule_data = schedule_parser.get_all_schedules()  # Updated method name
            load_data = load_parser.get_parsed_zone_loads()  # Get load data by zone
            
            # Extract HVAC and infiltration data from zone-based load_data
            hvac_data = {}
            infiltration_data = {}
            ventilation_data_from_loads = {}
            
            if load_data:
                for zone_name, zone_info in load_data.items():
                    zone_loads = zone_info.get('loads', {})
                    zone_schedules = zone_info.get('schedules', {})
                    
                    # Extract HVAC schedules (heating/cooling)
                    if zone_schedules.get('heating') or zone_schedules.get('cooling'):
                        hvac_data[zone_name] = zone_schedules
                    
                    # Extract infiltration data
                    if zone_loads.get('infiltration'):
                        infiltration_data[zone_name] = zone_loads['infiltration']
                    
                    # Extract ventilation data
                    if zone_loads.get('ventilation') or zone_loads.get('mechanical_ventilation'):
                        ventilation_data_from_loads[zone_name] = {
                            'natural': zone_loads.get('ventilation', {}),
                            'mechanical': zone_loads.get('mechanical_ventilation', {})
                        }
            infiltration_data = load_data.get('infiltration', {}) if load_data else {}
            
            print(f"DEBUG HVAC: Load data keys: {list(load_data.keys()) if load_data else 'None'}")
            print(f"DEBUG HVAC: Schedule data keys: {list(schedule_data.keys()) if schedule_data else 'None'}")
            print(f"DEBUG HVAC: Natural vent data keys: {list(natural_vent_data.keys()) if natural_vent_data else 'None'}")
            
            print(f"DEBUG HVAC: Climate zone: {climate_zone}")
            print(f"DEBUG HVAC: HVAC data: {hvac_data}")
            print(f"DEBUG HVAC: Infiltration data: {infiltration_data}")
            print(f"DEBUG HVAC: Natural ventilation data: {natural_vent_data}")
            
            # For 2017 ISO validation
            if iso_type == '2017' and climate_zone in self.hvac_table['2017']:
                self._validate_2017_hvac(hvac_data, infiltration_data, natural_vent_data, 
                                       schedule_data, areas_parser, climate_zone)
                
            print(f"\n=== HVAC VALIDATION DEBUG (ISO: {iso_type}, Climate: {climate_zone}) ===")
            print(f"Natural ventilation data keys: {list(natural_vent_data.keys()) if natural_vent_data else 'None'}")
            print(f"HVAC data sample: {dict(list(hvac_data.items())[:2]) if hvac_data else 'None'}")
            print(f"Infiltration data sample: {dict(list(infiltration_data.items())[:2]) if infiltration_data else 'None'}")
            print(f"Ventilation from loads sample: {dict(list(ventilation_data_from_loads.items())[:2]) if ventilation_data_from_loads else 'None'}")
            if iso_type in self.hvac_table:
                print(f"HVAC validation table for {iso_type}: {list(self.hvac_table[iso_type].keys())}")
            else:
                print(f"No HVAC validation table found for ISO type: {iso_type}")
            
            # For 2017 ISO validation
            if iso_type == '2017':
                self._validate_2017_hvac(hvac_data, infiltration_data, natural_vent_data, schedule_data, areas_parser, climate_zone)
            
        except ImportError as e:
            print(f"HVAC ERROR: Could not import parser: {e}")
        except Exception as e:
            print(f"HVAC ERROR: Error in HVAC validation: {e}")
    
    def _validate_2017_hvac(self, hvac_data, infiltration_data, natural_vent_data, 
                           schedule_data, areas_parser, climate_zone):
        """Validate HVAC according to 2017 ISO standards for specific climate zone."""
        
        print(f"\n=== 2017 HVAC VALIDATION (Climate: {climate_zone}) ===")
        
        # Check if climate zone exists in HVAC table
        if climate_zone not in self.hvac_table['2017']:
            print(f"No HVAC validation rules for climate zone {climate_zone}")
            return
            
        climate_hvac_table = self.hvac_table['2017'][climate_zone]
        print(f"Using HVAC validation rules for climate zone {climate_zone}")
        
        # Get zones and their window directions from area report
        zones = self.data_loader.get_zones()
        zone_window_directions = {}
        
        # Extract window directions from area data
        try:
            if hasattr(areas_parser, 'glazing_data_from_csv'):
                glazing_data = areas_parser.glazing_data_from_csv
                print(f"Processing glazing data: {type(glazing_data)} with {len(glazing_data)} items")
                for surface_name, data in glazing_data.items():
                    # Ensure data is a dict before calling .get()
                    if not isinstance(data, dict):
                        print(f"Skipping non-dict glazing data for {surface_name}: {type(data)}")
                        continue
                        
                    # Extract zone from surface name
                    if ':' in surface_name:
                        parts = surface_name.split(':')
                        if len(parts) > 1:
                            zone_id = f"{parts[0]}:{parts[1][:7]}"  # Get zone part
                            direction = data.get('CardinalDirection', 'Unknown')
                            if direction and direction != 'Unknown':
                                if zone_id not in zone_window_directions:
                                    zone_window_directions[zone_id] = set()
                                zone_window_directions[zone_id].add(direction)
            else:
                print("No glazing_data_from_csv found in areas_parser")
        except Exception as e:
            print(f"Error processing glazing data: {e}")
            zone_window_directions = {}
        
        for zone_id in zones.keys():
            # Validate Heating Schedule
            if zone_id in hvac_data and 'heating' in hvac_data[zone_id]:
                heating_info = hvac_data[zone_id]['heating']
                print(f"  Validating heating for zone {zone_id}: {heating_info.get('name', 'Unknown')}")
                
                # For now, skip detailed heating validation and just log
                print(f"  Heating validation skipped for simplicity")
            
            # Validate Cooling Schedule  
            if zone_id in hvac_data and 'cooling' in hvac_data[zone_id]:
                cooling_info = hvac_data[zone_id]['cooling']
                print(f"  Validating cooling for zone {zone_id}: {cooling_info.get('name', 'Unknown')}")
                
                # For now, skip detailed cooling validation and just log
                print(f"  Cooling validation skipped for simplicity")
            
            # Validate Infiltration
            if zone_id in infiltration_data:
                zone_infiltration = infiltration_data[zone_id]
                for infiltration_item in zone_infiltration:
                    # Check ACH rate
                    ach_rate = infiltration_item.get('air_changes_per_hour', 0)
                    recommended_ach = float(climate_hvac_table['Infiltration']['rate_ach']['recommended'])
                    
                    if abs(ach_rate - recommended_ach) > 0.1:
                        self.error_detection_data.append({
                            'zone_name': zone_id,
                            'category': f'Infiltration Rate (Climate {climate_zone})',
                            'current_model_value': str(ach_rate),
                            'recommended_standard_value': str(recommended_ach),
                            'remark': 'Need to change'
                        })
                    
                    # Validate schedule rule
                    schedule_name = infiltration_item.get('schedule_name', '')
                    if schedule_name and schedule_name in schedule_data:
                        print(f"DEBUG HVAC: Validating infiltration schedule: {schedule_name}")
                        self._validate_schedule_rule(schedule_name, schedule_data[schedule_name], 
                                                    climate_hvac_table['Infiltration']['schedule_rule']['recommended'],
                                                    zone_id, f'Infiltration Schedule Rule (Climate {climate_zone})')
            
            # Validate Natural Ventilation
            if zone_id in natural_vent_data:
                zone_nat_vent = natural_vent_data[zone_id]
                for nat_vent_item in zone_nat_vent:
                    # Check ACH rate
                    ach_rate = nat_vent_item.get('air_changes_per_hour', 0)
                    recommended_ach = float(climate_hvac_table['Natural Ventilation']['rate_ach']['recommended'])
                    
                    if abs(ach_rate - recommended_ach) > 0.1:
                        self.error_detection_data.append({
                            'zone_name': zone_id,
                            'category': f'Natural Ventilation Rate (Climate {climate_zone})',
                            'current_model_value': str(ach_rate),
                            'recommended_standard_value': str(recommended_ach),
                            'remark': 'Need to change'
                        })
                    
                    # Check window directions requirement using helper method
                    window_count = self._count_window_directions(zone_id, areas_parser)
                    required_directions = int(climate_hvac_table['Natural Ventilation']['windows_directions_required']['recommended'])
                    
                    if window_count < required_directions:
                        self.error_detection_data.append({
                            'zone_name': zone_id,
                            'category': f'Natural Ventilation Windows (Climate {climate_zone})',
                            'current_model_value': str(window_count),
                            'recommended_standard_value': str(required_directions),
                            'remark': 'Missing at least 2 windows directions'
                        })
                        print(f"DEBUG HVAC: Window direction validation failed for {zone_id}: {window_count} < {required_directions}")
                    else:
                        print(f"DEBUG HVAC: Window direction validation passed for {zone_id}: {window_count} >= {required_directions}")
                    
                    # Validate schedule rule
                    schedule_name = nat_vent_item.get('schedule_name', '')
                    if schedule_name and schedule_name in schedule_data:
                        print(f"DEBUG HVAC: Validating natural ventilation schedule: {schedule_name}")
                        self._validate_schedule_rule(schedule_name, schedule_data[schedule_name], 
                                                    climate_hvac_table['Natural Ventilation']['schedule_rule']['recommended'],
                                                    zone_id, f'Natural Ventilation Schedule Rule (Climate {climate_zone})')

    def get_error_detection_data(self) -> List[Dict[str, Any]]:
        """Returns the processed error detection data."""
        return self.error_detection_data
    
    def _validate_schedule_rule(self, schedule_name, schedule_data, recommended_rule, zone_id, category):
        """Helper method to validate schedule rules against recommended values."""
        try:
            print(f"DEBUG SCHEDULE: Validating {schedule_name} for zone {zone_id}")
            print(f"DEBUG SCHEDULE: Schedule data structure: {type(schedule_data)}")
            
            # Extract hourly values from schedule data
            current_rule = self._extract_schedule_rule(schedule_data)
            
            print(f"DEBUG SCHEDULE: Current rule: {current_rule[:50]}..." if current_rule else "No rule extracted")
            print(f"DEBUG SCHEDULE: Recommended rule: {recommended_rule[:50]}...")
            
            if current_rule and current_rule != recommended_rule:
                self.error_detection_data.append({
                    'zone_name': zone_id,
                    'category': category,
                    'current_model_value': current_rule[:100] + '...' if len(current_rule) > 100 else current_rule,
                    'recommended_standard_value': recommended_rule[:100] + '...' if len(recommended_rule) > 100 else recommended_rule,
                    'remark': 'Schedule rule does not match standard'
                })
                print(f"DEBUG SCHEDULE: Rule mismatch found for {schedule_name}")
            else:
                print(f"DEBUG SCHEDULE: Rule matches or could not extract for {schedule_name}")
                
        except Exception as e:
            print(f"DEBUG SCHEDULE: Error validating schedule {schedule_name}: {e}")
    
    def _extract_schedule_rule(self, schedule_data):
        """Extract schedule rule from schedule data structure."""
        try:
            if isinstance(schedule_data, dict):
                # Check for rule_blocks (typical structure)
                if 'rule_blocks' in schedule_data:
                    rule_blocks = schedule_data['rule_blocks']
                    if isinstance(rule_blocks, list) and rule_blocks:
                        # Extract hourly values from first rule block
                        first_block = rule_blocks[0]
                        if isinstance(first_block, dict) and 'hourly_values' in first_block:
                            hourly_values = first_block['hourly_values']
                            if isinstance(hourly_values, list):
                                return ' '.join([str(v) for v in hourly_values])
                
                # Check for direct hourly_values
                if 'hourly_values' in schedule_data:
                    hourly_values = schedule_data['hourly_values']
                    if isinstance(hourly_values, list):
                        return ' '.join([str(v) for v in hourly_values])
                
                # Check for compact schedule format
                if 'schedule_values' in schedule_data:
                    return str(schedule_data['schedule_values'])
                    
            print(f"DEBUG SCHEDULE: Could not extract rule from structure: {schedule_data}")
            return None
            
        except Exception as e:
            print(f"DEBUG SCHEDULE: Error extracting schedule rule: {e}")
            return None
    
    def _count_window_directions(self, zone_id, areas_parser):
        """Count unique window directions for a zone."""
        window_directions = set()
        
        try:
            if hasattr(areas_parser, 'glazing_data_from_csv'):
                glazing_data = areas_parser.glazing_data_from_csv
                print(f"DEBUG WINDOWS: Checking glazing data for zone {zone_id}")
                
                for surface_name, data in glazing_data.items():
                    # Check if this surface belongs to the zone
                    if zone_id in surface_name:
                        direction = data.get('CardinalDirection', 'Unknown')
                        if direction and direction != 'Unknown':
                            window_directions.add(direction)
                            print(f"DEBUG WINDOWS: Found {direction} window in {surface_name}")
                
                print(f"DEBUG WINDOWS: Zone {zone_id} has {len(window_directions)} directions: {window_directions}")
                
        except Exception as e:
            print(f"DEBUG WINDOWS: Error counting window directions for {zone_id}: {e}")
            
        return len(window_directions) 