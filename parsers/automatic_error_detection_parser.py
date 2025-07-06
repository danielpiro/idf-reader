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
                        'schedule_rule': {'recommended': '01/01 -> 31/03: 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0; 31/03 -> 30/11: 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1; 30/11 -> 31/12: 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0', 'details': 'Not supported value'},
                        'ceiling_fan_error_check': {'recommended': '24.0', 'details': 'Ceiling fan error'}
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
                        'schedule_rule': {'recommended': '01/01 -> 31/03: 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0; 31/03 -> 30/11: 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1; 30/11 -> 31/12: 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0', 'details': 'Not supported value'},
                        'ceiling_fan_error_check': {'recommended': '24.0', 'details': 'Ceiling fan error'}
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
                        'schedule_rule': {'recommended': '01/01 -> 30/04: 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1; 30/04 -> 31/10: 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0; 31/10 -> 31/12: 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1', 'details': 'Not supported value'}
                    },
                    'Cooling Schedule': {
                        'setpoint_non_work_time': {'recommended': '-', 'details': 'Not supported value'},
                        'setpoint_c': {'recommended': '24', 'details': 'Not supported value'},
                        'schedule_rule': {'recommended': '01/01 -> 30/04: 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0; 30/04 -> 31/10: 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1; 31/10 -> 31/12: 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0', 'details': 'Not supported value'},
                        'ceiling_fan_error_check': {'recommended': '24.0', 'details': 'Ceiling fan error'}
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
                        'schedule_rule': {'recommended': '01/01 -> 28/02: 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0; 28/02 -> 30/11: 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1; 30/11 -> 31/12: 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0', 'details': 'Not supported value'},
                        'ceiling_fan_error_check': {'recommended': '24.0', 'details': 'Ceiling fan error'}
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
        
        
    def _validate_settings(self) -> None:
        """Validate settings using the settings table."""
        if not self.settings_extractor:
            return
        
        # Get current settings from IDF
        current_settings = self.settings_extractor.get_settings()
        
        
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
            load_data = load_parser.get_parsed_zone_loads(include_core=False)  # Get people and equipment data by zone, excluding CORE zones
            
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
            
            # For 2017 ISO validation
            if iso_type == '2017':
                self._validate_2017_loads(people_data, lights_data_from_loads, equipment_data, schedule_data, zones, areas_parser)
                
        except ImportError:
            pass
        except Exception:
            pass
    
    def _validate_2017_loads(self, people_data, lights_data_from_loads, equipment_data, schedule_data, zones, areas_parser):
        """Validate loads according to 2017 ISO standards with area-based criteria."""
        # Filter for HVAC zones only, excluding CORE zones
        hvac_zones = self.data_loader.get_hvac_zones()
        # Filter out CORE zones from HVAC zones
        hvac_zones = [zone for zone in hvac_zones if not any(keyword in zone.lower() for keyword in ['core', 'corridor', 'stair'])]
        
        # Group zones by floor (extract floor prefix like "00:", "01:", "02:")
        floors_data = {}
        for zone_id, zone_info in zones.items():
            if zone_id not in hvac_zones:
                continue  # Skip non-HVAC zones or CORE zones
                
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
                    'fixed_equipment_data': {},
                    'non_fixed_equipment_data': {}
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
                # Separate fixed and non-fixed equipment
                floors_data[floor_prefix]['fixed_equipment_data'][zone_id] = equipment_data[zone_id].get('fixed_equipment', {})
                floors_data[floor_prefix]['non_fixed_equipment_data'][zone_id] = equipment_data[zone_id].get('non_fixed_equipment', {})
        
        # Validate each floor according to 2017 requirements
        for floor_prefix, floor_info in floors_data.items():
            total_floor_area = floor_info['total_area']
            zones_in_floor = floor_info['zones']
            
            print(f"\nValidating floor: {floor_prefix} (Total Area: {total_floor_area:.2f} m²)")
            print(f"  Zones in floor: {zones_in_floor}")
            
            # Determine area category (≤150 or >150 m²)
            is_small_area = total_floor_area <= 150
            
            # Validate each zone individually but use floor-based area requirements
            for zone_id in zones_in_floor:
                # Validate Occupancy
                if zone_id in people_data:
                    zone_people_info = people_data[zone_id]
                    current_people_per_area = zone_people_info.get('people_per_area')
                    current_activity_schedule = zone_people_info.get('activity_schedule', None)
                    current_schedule = zone_people_info.get('schedule', None)
                    
                    # Check people per area
                    recommended_people = float(self.loads_table['2017']['Occupancy']['people_per_area']['recommended'])
                    if current_people_per_area is not None:
                        if abs(current_people_per_area - recommended_people) > 0.001:
                            self.error_detection_data.append({
                                'zone_name': zone_id,
                                'category': 'Occupancy - People per Area',
                                'current_model_value': f"{current_people_per_area}",
                                'recommended_standard_value': f"{recommended_people}",
                                'remark': self.loads_table['2017']['Occupancy']['people_per_area']['details']
                            })
                    else:
                        # No people per area data found
                        self.error_detection_data.append({
                            'zone_name': zone_id,
                            'category': 'Occupancy - People per Area',
                            'current_model_value': "-",
                            'recommended_standard_value': f"{recommended_people}",
                            'remark': self.loads_table['2017']['Occupancy']['people_per_area']['details']
                        })
                    
                    # Check activity schedule
                    recommended_activity = float(self.loads_table['2017']['Occupancy']['activity_schedule_per_person']['recommended'])
                    if current_activity_schedule is not None:
                        try:
                            current_activity_value = float(current_activity_schedule)
                            if abs(current_activity_value - recommended_activity) > 0.1:
                                self.error_detection_data.append({
                                    'zone_name': zone_id,
                                    'category': 'Occupancy - Activity Schedule',
                                    'current_model_value': f"{current_activity_value}",
                                    'recommended_standard_value': f"{recommended_activity}",
                                    'remark': self.loads_table['2017']['Occupancy']['activity_schedule_per_person']['details']
                                })
                        except (ValueError, TypeError):
                            pass
                    
                    # Check schedule rule
                    if current_schedule and current_schedule in schedule_data:
                        schedule_info = schedule_data[current_schedule]
                        current_schedule_rule = self._extract_schedule_rule_as_hourly(schedule_info)
                        recommended_schedule_rule = self.loads_table['2017']['Occupancy']['schedule_rule']['recommended']
                        
                        if not self._compare_schedule_rules(current_schedule_rule, recommended_schedule_rule):
                            self.error_detection_data.append({
                                'zone_name': zone_id,
                                'category': 'Occupancy - Schedule Rule',
                                'current_model_value': current_schedule_rule or "-",
                                'recommended_standard_value': recommended_schedule_rule,
                                'remark': self.loads_table['2017']['Occupancy']['schedule_rule']['details']
                            })
                
                # Validate Lighting
                if zone_id in lights_data_from_loads:
                    zone_lights_info = lights_data_from_loads[zone_id]
                    current_lighting_watts = zone_lights_info.get('watts_per_area')
                    current_schedule = zone_lights_info.get('schedule', None)
                    
                    # Check power density
                    recommended_lighting = float(self.loads_table['2017']['Lighting']['power_density_w_m2']['recommended'])
                    if current_lighting_watts is not None:
                        if abs(current_lighting_watts - recommended_lighting) > 0.001:
                            self.error_detection_data.append({
                                'zone_name': zone_id,
                                'category': 'Lighting - Power Density',
                                'current_model_value': f"{current_lighting_watts}",
                                'recommended_standard_value': f"{recommended_lighting}",
                                'remark': self.loads_table['2017']['Lighting']['power_density_w_m2']['details']
                            })
                    else:
                        # No lighting power density data found
                        self.error_detection_data.append({
                            'zone_name': zone_id,
                            'category': 'Lighting - Power Density',
                            'current_model_value': "-",
                            'recommended_standard_value': f"{recommended_lighting}",
                            'remark': self.loads_table['2017']['Lighting']['power_density_w_m2']['details']
                        })
                    
                    # Check schedule rule
                    if current_schedule and current_schedule in schedule_data:
                        current_schedule_rule = self._extract_schedule_rule_as_hourly(schedule_data[current_schedule])
                        recommended_schedule_rule = self.loads_table['2017']['Lighting']['schedule_rule']['recommended']
                        if not self._compare_schedule_rules(current_schedule_rule, recommended_schedule_rule):
                            self.error_detection_data.append({
                                'zone_name': zone_id,
                                'category': 'Lighting - Schedule Rule',
                                'current_model_value': current_schedule_rule or "-",
                                'recommended_standard_value': recommended_schedule_rule,
                                'remark': self.loads_table['2017']['Lighting']['schedule_rule']['details']
                            })
            
                # Validate Equipment for each zone (with edge case handling)
                if zone_id in equipment_data:
                    non_fixed_watts = None
                    fixed_watts = None
                    non_fixed_schedule = None
                    fixed_schedule = None
                    
                    # Get equipment data for this zone
                    zone_equipment = equipment_data[zone_id]
                    if 'non_fixed_equipment' in zone_equipment:
                        non_fixed_watts = zone_equipment['non_fixed_equipment'].get('watts_per_area')
                        non_fixed_schedule = zone_equipment['non_fixed_equipment'].get('schedule', None)
                    if 'fixed_equipment' in zone_equipment:
                        fixed_watts = zone_equipment['fixed_equipment'].get('watts_per_area')
                        fixed_schedule = zone_equipment['fixed_equipment'].get('schedule', None)
                    
                    # Convert None to 0 for calculations, but track if data was missing
                    non_fixed_watts_calc = non_fixed_watts if non_fixed_watts is not None else 0
                    fixed_watts_calc = fixed_watts if fixed_watts is not None else 0
                    
                    # Check for edge case (if either fixed or non-fixed schedule rule is all zeros)
                    non_fixed_is_zero = self._is_schedule_all_zeros(non_fixed_schedule, schedule_data)
                    fixed_is_zero = self._is_schedule_all_zeros(fixed_schedule, schedule_data)
                    
                    if non_fixed_is_zero or fixed_is_zero:
                        # Apply edge case logic
                        combined_watts = non_fixed_watts_calc + fixed_watts_calc
                        area_key = 'Combined Equipment (area <= 150, edge case)' if is_small_area else 'Combined Equipment (area > 150, edge case)'
                        recommended_watts = float(self.loads_table['2017'][area_key]['power_density_w_m2']['recommended'])
                        recommended_schedule_rule = self.loads_table['2017'][area_key]['schedule_rule']['recommended']
                        
                        # Show combined value, or "-" if both are missing
                        if non_fixed_watts is None and fixed_watts is None:
                            combined_display = "-"
                        else:
                            combined_display = f"{combined_watts}"
                        
                        if abs(combined_watts - recommended_watts) > 0.001:
                            self.error_detection_data.append({
                                'zone_name': zone_id,
                                'category': 'Equipment - Combined Power Density (Edge Case)',
                                'current_model_value': combined_display,
                                'recommended_standard_value': f"{recommended_watts}",
                                'remark': self.loads_table['2017'][area_key]['power_density_w_m2']['details']
                            })
                        
                        # Use the non-zero schedule for comparison
                        active_schedule = non_fixed_schedule if not non_fixed_is_zero else fixed_schedule
                        if active_schedule and active_schedule in schedule_data:
                            current_schedule_rule = self._extract_schedule_rule_as_hourly(schedule_data[active_schedule])
                            if not self._compare_schedule_rules(current_schedule_rule, recommended_schedule_rule):
                                self.error_detection_data.append({
                                    'zone_name': zone_id,
                                    'category': 'Equipment - Combined Schedule Rule (Edge Case)',
                                    'current_model_value': current_schedule_rule or "-",
                                    'recommended_standard_value': recommended_schedule_rule,
                                    'remark': self.loads_table['2017'][area_key]['schedule_rule']['details']
                                })
                    else:
                        # Normal case - validate non-fixed and fixed separately
                        area_suffix = "(area <= 150)" if is_small_area else "(area > 150)"
                        
                        # Non-fixed equipment
                        non_fixed_key = f'Non Fixed Equipment {area_suffix}'
                        if non_fixed_key in self.loads_table['2017']:
                            recommended_non_fixed = float(self.loads_table['2017'][non_fixed_key]['power_density_w_m2']['recommended'])
                            non_fixed_display = f"{non_fixed_watts}" if non_fixed_watts is not None else "-"
                            non_fixed_calc = non_fixed_watts if non_fixed_watts is not None else 0
                            
                            if abs(non_fixed_calc - recommended_non_fixed) > 0.001:
                                self.error_detection_data.append({
                                    'zone_name': zone_id,
                                    'category': 'Non-Fixed Equipment - Power Density',
                                    'current_model_value': non_fixed_display,
                                    'recommended_standard_value': f"{recommended_non_fixed}",
                                    'remark': self.loads_table['2017'][non_fixed_key]['power_density_w_m2']['details']
                                })
                            
                            # Check schedule rule
                            if non_fixed_schedule and non_fixed_schedule in schedule_data:
                                current_schedule_rule = self._extract_schedule_rule_as_hourly(schedule_data[non_fixed_schedule])
                                recommended_schedule_rule = self.loads_table['2017'][non_fixed_key]['schedule_rule']['recommended']
                                if not self._compare_schedule_rules(current_schedule_rule, recommended_schedule_rule):
                                    self.error_detection_data.append({
                                        'zone_name': zone_id,
                                        'category': 'Non-Fixed Equipment - Schedule Rule',
                                        'current_model_value': current_schedule_rule or "-",
                                        'recommended_standard_value': recommended_schedule_rule,
                                        'remark': self.loads_table['2017'][non_fixed_key]['schedule_rule']['details']
                                    })
                        
                        # Fixed equipment
                        fixed_key = f'Fixed Equipment {area_suffix}'
                        if fixed_key in self.loads_table['2017']:
                            recommended_fixed = float(self.loads_table['2017'][fixed_key]['power_density_w_m2']['recommended'])
                            fixed_display = f"{fixed_watts}" if fixed_watts is not None else "-"
                            fixed_calc = fixed_watts if fixed_watts is not None else 0
                            
                            if abs(fixed_calc - recommended_fixed) > 0.001:
                                self.error_detection_data.append({
                                    'zone_name': zone_id,
                                    'category': 'Fixed Equipment - Power Density',
                                    'current_model_value': fixed_display,
                                    'recommended_standard_value': f"{recommended_fixed}",
                                    'remark': self.loads_table['2017'][fixed_key]['power_density_w_m2']['details']
                                })
                            
                            # Check schedule rule
                            if fixed_schedule and fixed_schedule in schedule_data:
                                current_schedule_rule = self._extract_schedule_rule_as_hourly(schedule_data[fixed_schedule])
                                recommended_schedule_rule = self.loads_table['2017'][fixed_key]['schedule_rule']['recommended']
                                if not self._compare_schedule_rules(current_schedule_rule, recommended_schedule_rule):
                                    self.error_detection_data.append({
                                        'zone_name': zone_id,
                                        'category': 'Fixed Equipment - Schedule Rule',
                                        'current_model_value': current_schedule_rule or "-",
                                        'recommended_standard_value': recommended_schedule_rule,
                                        'remark': self.loads_table['2017'][fixed_key]['schedule_rule']['details']
                                    })
        
    
    def _extract_schedule_rule_as_hourly(self, schedule_data):
        """Extract schedule rule as hourly values string."""
        if not schedule_data:
            return None
        
        # Handle ScheduleData object (from utils.data_models)
        if hasattr(schedule_data, 'raw_rules'):
            raw_rules = schedule_data.raw_rules
            if raw_rules and isinstance(raw_rules, list):
                # Parse the schedule rules to extract hourly pattern
                return self._parse_schedule_rules_to_hourly(raw_rules)
        
        # Handle dictionary-like objects
        if hasattr(schedule_data, 'get'):
            # Check for rule_blocks structure (from ScheduleExtractor)
            rule_blocks = schedule_data.get('rule_blocks', [])
            if rule_blocks and len(rule_blocks) > 0:
                # Get the first rule block's hourly values
                first_block = rule_blocks[0]
                if 'hourly_values' in first_block:
                    hourly_values = first_block['hourly_values']
                    if hourly_values and len(hourly_values) >= 24:
                        return " ".join(str(val) for val in hourly_values[:24])
            
            # Check for raw_rules (alternative structure)
            raw_rules = schedule_data.get('raw_rules', [])
            if raw_rules:
                # Process schedule rules to extract hourly pattern
                return self._parse_schedule_rules_to_hourly(raw_rules)
            
            # Check for schedule_values (from load parser)
            schedule_values = schedule_data.get('schedule_values', [])
            if schedule_values and isinstance(schedule_values, list):
                # Parse schedule values to extract hourly pattern
                return self._parse_schedule_rules_to_hourly(schedule_values)
        
        return None
    
    def _parse_schedule_rules_to_hourly(self, rules):
        """Parse schedule rules and convert to 24-hour pattern."""
        if not rules or not isinstance(rules, list):
            return None
        
        # Use existing schedule parsing logic from schedule_parser.py
        from parsers.schedule_parser import _parse_compact_rule_blocks
        
        try:
            # Parse the rules using the existing schedule parser logic
            rule_blocks = _parse_compact_rule_blocks(rules)
            
            if rule_blocks and len(rule_blocks) > 0:
                # Get the first rule block's hourly values
                first_block = rule_blocks[0]
                if 'hourly_values' in first_block:
                    hourly_values = first_block['hourly_values']
                    if hourly_values and len(hourly_values) >= 24:
                        pattern_str = " ".join(str(val) for val in hourly_values[:24])
                        return pattern_str
            
            # Fallback to manual parsing if rule blocks approach fails
            # Manual parsing as fallback
            time_value_pairs = []
            i = 0
            while i < len(rules):
                rule = str(rules[i]).strip()
                
                # Skip type indicators and through/for clauses
                if rule.lower() in ['fraction', 'temperature', 'any number'] or \
                   rule.lower().startswith(('through:', 'for:')):
                    i += 1
                    continue
                
                # Look for time-based rules: "Until: HH:MM"
                if rule.lower().startswith('until:'):
                    # Extract time
                    time_part = rule.split(':', 1)[1].strip() if ':' in rule else ''
                    if time_part and i + 1 < len(rules):
                        try:
                            value = float(rules[i + 1])
                            time_value_pairs.append({'end_time': time_part, 'value': str(value)})
                            i += 2  # Skip value
                            continue
                        except (ValueError, IndexError):
                            pass
                
                i += 1
            
            # Convert time-value pairs to hourly pattern
            if time_value_pairs:
                from parsers.schedule_parser import _expand_rules_to_hourly
                hourly_values = _expand_rules_to_hourly(time_value_pairs)
                if hourly_values and len(hourly_values) >= 24:
                    pattern_str = " ".join(str(val) for val in hourly_values[:24])
                    return pattern_str
            
        except Exception:
            pass
        
        # Final fallback: just join the numeric values found
        numeric_values = []
        for rule in rules:
            try:
                val = float(rule)
                numeric_values.append(str(val))
            except ValueError:
                continue
        
        if numeric_values:
            # Repeat pattern to get 24 values
            while len(numeric_values) < 24:
                numeric_values.extend(numeric_values)
            pattern_str = " ".join(numeric_values[:24])
            return pattern_str
        
        return None
    
    def _compare_schedule_rules(self, current_rule, recommended_rule):
        """Compare current schedule rule with recommended rule."""
        if not current_rule or not recommended_rule:
            return False
        return current_rule.strip() == recommended_rule.strip()
    
    def _is_schedule_all_zeros(self, schedule_name, schedule_data):
        """Check if a schedule rule is all zeros."""
        if not schedule_name or schedule_name not in schedule_data:
            return True
        
        schedule_rule = self._extract_schedule_rule_as_hourly(schedule_data[schedule_name])
        if not schedule_rule:
            return True
            
        # Check if all hourly values are zero
        hourly_values = schedule_rule.split()
        return all(float(val) == 0.0 for val in hourly_values if val.replace('.', '').isdigit())
    
    def _validate_hvac(self, iso_type: str, climate_zone: str = 'A', idf=None) -> None:
        """Validate HVAC using the HVAC table for specific ISO type and climate zone."""
        if iso_type not in self.hvac_table or not self.data_loader:
            return
        
        # Climate zone is now passed from constructor and used for validation
        
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
            load_data = load_parser.get_parsed_zone_loads(include_core=False)  # Get load data by zone, excluding CORE zones
            
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
            
            # For 2017 ISO validation (single call to avoid duplication)
            if iso_type == '2017' and climate_zone in self.hvac_table['2017']:
                self._validate_2017_hvac(hvac_data, infiltration_data, natural_vent_data, 
                                       schedule_data, areas_parser, climate_zone)
            
        except ImportError:
            pass
        except Exception:
            pass
    
    def _validate_2017_hvac(self, hvac_data, infiltration_data, natural_vent_data, 
                           schedule_data, areas_parser, climate_zone):
        """Validate HVAC according to 2017 ISO standards for specific climate zone."""
        
        # Check if climate zone exists in HVAC table
        if climate_zone not in self.hvac_table['2017']:
            return
            
        climate_hvac_table = self.hvac_table['2017'][climate_zone]
        
        # Get zones and their window directions from area report
        zones = self.data_loader.get_zones()
        # Filter out CORE zones
        zones = {zone_id: zone_info for zone_id, zone_info in zones.items() 
                if not any(keyword in zone_id.lower() for keyword in ['core', 'corridor', 'stair'])}
        
        zone_window_directions = {}
        
        # Extract window directions from area data
        try:
            if hasattr(areas_parser, 'glazing_data_from_csv'):
                glazing_data = areas_parser.glazing_data_from_csv
                for surface_name, data in glazing_data.items():
                    # Ensure data is a dict before calling .get()
                    if not isinstance(data, dict):
                        continue
                        
                    # Extract zone from surface name
                    if ':' in surface_name:
                        parts = surface_name.split(':')
                        if len(parts) > 1:
                            zone_id = f"{parts[0]}:{parts[1][:7]}"  # Get zone part
                            # Skip CORE zones
                            if any(keyword in zone_id.lower() for keyword in ['core', 'corridor', 'stair']):
                                continue
                            direction = data.get('CardinalDirection', 'Unknown')
                            if direction and direction != 'Unknown':
                                if zone_id not in zone_window_directions:
                                    zone_window_directions[zone_id] = set()
                                zone_window_directions[zone_id].add(direction)
        except Exception:
            zone_window_directions = {}
        
        for zone_id in zones.keys():
            # Validate Heating Schedule
            if zone_id in hvac_data and 'heating' in hvac_data[zone_id]:
                heating_info = hvac_data[zone_id]['heating']
                heating_schedule_name = heating_info.get('name', 'Unknown')
                
                # Validate heating setpoint temperature
                if 'schedule_values' in heating_info and heating_info['schedule_values']:
                    try:
                        schedule_rules = heating_info['schedule_values']
                        if isinstance(schedule_rules, list) and schedule_rules:
                            current_setpoint = self._extract_setpoint_from_schedule(schedule_rules)
                            recommended_setpoint = float(climate_hvac_table['Heating Schedule']['setpoint_c']['recommended'])
                            
                            if current_setpoint is not None and abs(current_setpoint - recommended_setpoint) > 0.5:
                                self.error_detection_data.append({
                                    'zone_name': zone_id,
                                    'category': f'Heating Setpoint (Climate {climate_zone})',
                                    'current_model_value': f"{current_setpoint}°C",
                                    'recommended_standard_value': f"{recommended_setpoint}°C",
                                    'remark': climate_hvac_table['Heating Schedule']['setpoint_c']['details']
                                })
                                
                    except Exception:
                        pass
                
                # Validate heating schedule rule
                if heating_schedule_name in schedule_data:
                    self._validate_schedule_rule(heating_schedule_name, schedule_data[heating_schedule_name], 
                                                climate_hvac_table['Heating Schedule']['schedule_rule']['recommended'],
                                                zone_id, f'Heating Schedule Rule (Climate {climate_zone})')
            
            # Validate Cooling Schedule  
            if zone_id in hvac_data and 'cooling' in hvac_data[zone_id]:
                cooling_info = hvac_data[zone_id]['cooling']
                cooling_schedule_name = cooling_info.get('name', 'Unknown')
                
                # Validate cooling setpoint temperature
                if 'schedule_values' in cooling_info and cooling_info['schedule_values']:
                    try:
                        schedule_rules = cooling_info['schedule_values']
                        if isinstance(schedule_rules, list) and schedule_rules:
                            current_setpoint = self._extract_setpoint_from_schedule(schedule_rules)
                            recommended_setpoint = float(climate_hvac_table['Cooling Schedule']['setpoint_c']['recommended'])
                            
                            if current_setpoint is not None and abs(current_setpoint - recommended_setpoint) > 0.5:
                                self.error_detection_data.append({
                                    'zone_name': zone_id,
                                    'category': f'Cooling Setpoint (Climate {climate_zone})',
                                    'current_model_value': f"{current_setpoint}°C",
                                    'recommended_standard_value': f"{recommended_setpoint}°C",
                                    'remark': climate_hvac_table['Cooling Schedule']['setpoint_c']['details']
                                })
                            
                            # Check for ceiling fan error (24.5°C or 25°C)
                            if current_setpoint is not None and (abs(current_setpoint - 24.5) < 0.1 or abs(current_setpoint - 25.0) < 0.1):
                                self.error_detection_data.append({
                                    'zone_name': zone_id,
                                    'category': f'Cooling Setpoint - Ceiling Fan Error (Climate {climate_zone})',
                                    'current_model_value': f"{current_setpoint}°C",
                                    'recommended_standard_value': f"{recommended_setpoint}°C",
                                    'remark': climate_hvac_table['Cooling Schedule']['ceiling_fan_error_check']['details']
                                })
                                
                    except Exception:
                        pass
                
                # Validate cooling schedule rule
                if cooling_schedule_name in schedule_data:
                    self._validate_schedule_rule(cooling_schedule_name, schedule_data[cooling_schedule_name], 
                                                climate_hvac_table['Cooling Schedule']['schedule_rule']['recommended'],
                                                zone_id, f'Cooling Schedule Rule (Climate {climate_zone})')
            
            # Validate Infiltration
            if zone_id in infiltration_data:
                zone_infiltration = infiltration_data[zone_id]
                
                # Handle both dict and list structures
                if isinstance(zone_infiltration, dict):
                    ach_rate = zone_infiltration.get('rate_ach', 0)
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
                    schedule_name = zone_infiltration.get('schedule', '')
                    if schedule_name and schedule_name in schedule_data:
                        self._validate_schedule_rule(schedule_name, schedule_data[schedule_name], 
                                                    climate_hvac_table['Infiltration']['schedule_rule']['recommended'],
                                                    zone_id, f'Infiltration Schedule Rule (Climate {climate_zone})')
                        
                elif isinstance(zone_infiltration, list):
                    # List of infiltration items
                    for infiltration_item in zone_infiltration:
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
                            self._validate_schedule_rule(schedule_name, schedule_data[schedule_name], 
                                                        climate_hvac_table['Infiltration']['schedule_rule']['recommended'],
                                                        zone_id, f'Infiltration Schedule Rule (Climate {climate_zone})')
            
            # Validate Natural Ventilation
            if zone_id in natural_vent_data:
                zone_nat_vent = natural_vent_data[zone_id]
                
                # Handle both dict and list structures
                if isinstance(zone_nat_vent, dict):
                    # Extract ACH rate from natural ventilation data
                    # Check different possible field names for ACH rate
                    ach_rate = 0
                    if 'rate_ach' in zone_nat_vent:
                        ach_rate = zone_nat_vent.get('rate_ach', 0)
                    elif 'design_flow_rate' in zone_nat_vent:
                        # Convert design flow rate to ACH if zone volume is available
                        design_flow_rate = zone_nat_vent.get('design_flow_rate', 0)
                        zone_volume = zones.get(zone_id, {}).get('volume', 0)
                        if zone_volume > 0:
                            ach_rate = (design_flow_rate * 3600) / zone_volume  # Convert m³/s to ACH
                    
                    recommended_ach = float(climate_hvac_table['Natural Ventilation']['rate_ach']['recommended'])
                    if abs(ach_rate - recommended_ach) > 0.1:
                        self.error_detection_data.append({
                            'zone_name': zone_id,
                            'category': f'Natural Ventilation Rate (Climate {climate_zone})',
                            'current_model_value': f"{ach_rate:.2f} ACH",
                            'recommended_standard_value': f"{recommended_ach} ACH",
                            'remark': 'Natural ventilation rate does not match standard'
                        })
                    
                    # Validate schedule rule
                    schedule_name = zone_nat_vent.get('schedule', '')
                    if schedule_name and schedule_name in schedule_data:
                        self._validate_schedule_rule(schedule_name, schedule_data[schedule_name], 
                                                    climate_hvac_table['Natural Ventilation']['schedule_rule']['recommended'],
                                                    zone_id, f'Natural Ventilation Schedule Rule (Climate {climate_zone})')
                        
                elif isinstance(zone_nat_vent, list):
                    # List of natural ventilation items
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
                        
                        # Window directions are validated per floor separately
                        
                        # Validate schedule rule
                        schedule_name = nat_vent_item.get('schedule_name', '')
                        if schedule_name and schedule_name in schedule_data:
                            self._validate_schedule_rule(schedule_name, schedule_data[schedule_name], 
                                                        climate_hvac_table['Natural Ventilation']['schedule_rule']['recommended'],
                                                        zone_id, f'Natural Ventilation Schedule Rule (Climate {climate_zone})')
        
        # Validate window directions per floor (not per zone)
        self._validate_window_directions_per_floor(zones, areas_parser, climate_hvac_table, climate_zone)

    def get_error_detection_data(self) -> List[Dict[str, Any]]:
        """Returns the processed error detection data."""
        return self.error_detection_data
    
    def _validate_schedule_rule(self, schedule_name, schedule_data, recommended_rule, zone_id, category):
        """Helper method to validate schedule rules against recommended values."""
        try:
            # Extract hourly values from schedule data
            current_rule = self._extract_schedule_rule(schedule_data)
            
            if current_rule and current_rule != recommended_rule:
                self.error_detection_data.append({
                    'zone_name': zone_id,
                    'category': category,
                    'current_model_value': current_rule[:100] + '...' if len(current_rule) > 100 else current_rule,
                    'recommended_standard_value': recommended_rule[:100] + '...' if len(recommended_rule) > 100 else recommended_rule,
                    'remark': 'Schedule rule does not match standard'
                })
                
        except Exception:
            pass
    
    def _extract_schedule_rule(self, schedule_data):
        """Extract schedule rule from schedule data structure."""
        try:
            # Handle ScheduleData objects (from utils.data_models)
            if hasattr(schedule_data, 'raw_rules'):
                raw_rules = schedule_data.raw_rules
                if isinstance(raw_rules, list):
                    # Parse the raw rules into a schedule pattern
                    return self._parse_raw_schedule_rules_to_pattern(raw_rules)
            
            # Handle dictionary structures  
            elif isinstance(schedule_data, dict):
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
                    
            return None
            
        except Exception:
            return None
    
    def _parse_raw_schedule_rules_to_pattern(self, raw_rules):
        """Parse raw schedule rules into a simplified pattern for comparison."""
        try:
            
            # For heating/cooling schedules, we mainly care about the on/off pattern
            # Look for temperature values and convert to 1 (on) or 0 (off)
            pattern_parts = []
            
            i = 0
            while i < len(raw_rules):
                rule = raw_rules[i]
                
                # Look for "Through:" date patterns
                if isinstance(rule, str) and rule.lower().startswith('through:'):
                    date_part = rule.replace('Through:', '').strip()
                    
                    # Normalize date format to match expected format
                    normalized_date = self._normalize_date_format(date_part)
                    
                    # Look ahead for temperature value after "Until:"
                    temp_value = None
                    j = i + 1
                    while j < len(raw_rules) and j < i + 4:  # Look ahead up to 4 items
                        if isinstance(raw_rules[j], str):
                            if raw_rules[j].lower().startswith('until:'):
                                # Next item should be the temperature
                                if j + 1 < len(raw_rules):
                                    try:
                                        temp_value = float(raw_rules[j + 1])
                                        break
                                    except (ValueError, TypeError):
                                        pass
                        j += 1
                    
                    # Convert temperature to pattern (1 for normal temps, 0 for extreme values like -50 or 100)
                    if temp_value is not None:
                        if temp_value == -50 or temp_value >= 100:
                            pattern = "0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0"  # Off
                        else:
                            pattern = "1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1"  # On
                        
                        pattern_parts.append(f"{normalized_date}: {pattern}")
                
                i += 1
            
            if pattern_parts:
                result = "; ".join(pattern_parts)
                return result
            else:
                return None
                
        except Exception:
            return None
    
    def _normalize_date_format(self, date_str):
        """Normalize date format to match expected format."""
        # Convert formats like "31 March" to proper date range format
        date_str = date_str.strip()
        
        month_map = {
            'january': '01', 'february': '02', 'march': '03', 'april': '04',
            'may': '05', 'june': '06', 'july': '07', 'august': '08',
            'september': '09', 'october': '10', 'november': '11', 'december': '12'
        }
        
        # Handle formats like "31 March", "30 November", "31 December"
        parts = date_str.split()
        if len(parts) == 2:
            day = parts[0].strip()
            month_name = parts[1].strip().lower()
            if month_name in month_map:
                month_num = month_map[month_name]
                
                # Create proper date ranges based on the actual schedule logic
                if month_name == 'march':
                    return "01/01 -> 31/03"
                elif month_name == 'november':
                    return "31/03 -> 30/11"
                elif month_name == 'december':
                    return "30/11 -> 31/12"
                else:
                    return f"01/01 -> {day}/{month_num}"
        
        # Return as-is if can't normalize
        return date_str
    
    def _count_window_directions(self, zone_id, areas_parser):
        """Count unique window directions for a zone."""
        window_directions = set()
        
        try:
            if hasattr(areas_parser, 'glazing_data_from_csv'):
                glazing_data = areas_parser.glazing_data_from_csv
                for surface_name, data in glazing_data.items():
                    # Check if this surface belongs to the zone
                    if zone_id in surface_name:
                        direction = data.get('CardinalDirection', 'Unknown')
                        if direction and direction != 'Unknown':
                            window_directions.add(direction)
                
        except Exception:
            pass
            
        return len(window_directions) 
    
    def _validate_window_directions_per_floor(self, zones, areas_parser, climate_hvac_table, climate_zone):
        """Validate window directions per floor (not per zone)."""
        try:
            # Group zones by floor, excluding CORE zones
            floors_data = {}
            for zone_id in zones.keys():
                # Skip CORE zones
                if any(keyword in zone_id.lower() for keyword in ['core', 'corridor', 'stair']):
                    continue
                    
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
                        'window_directions': set()
                    }
                
                floors_data[floor_prefix]['zones'].append(zone_id)
            
            # Collect window directions per floor from glazing data
            if hasattr(areas_parser, 'glazing_data_from_csv'):
                glazing_data = areas_parser.glazing_data_from_csv
                
                for surface_name, data in glazing_data.items():
                    # Ensure data is a dict before calling .get()
                    if not isinstance(data, dict):
                        continue
                        
                    # Extract floor from surface name
                    if ':' in surface_name:
                        parts = surface_name.split(':')
                        if len(parts) > 1 and len(parts[1]) >= 2:
                            floor_prefix = parts[1][:2]  # Get floor from surface name
                            direction = data.get('CardinalDirection', 'Unknown')
                            
                            if direction and direction != 'Unknown' and floor_prefix in floors_data:
                                floors_data[floor_prefix]['window_directions'].add(direction)
            
            # Validate each floor's window directions
            required_directions = int(climate_hvac_table['Natural Ventilation']['windows_directions_required']['recommended'])
            
            for floor_prefix, floor_info in floors_data.items():
                window_directions = floor_info['window_directions']
                window_count = len(window_directions)
                
                if window_count < required_directions:
                    # Add validation error for the floor
                    self.error_detection_data.append({
                        'zone_name': f'Floor {floor_prefix}',
                        'category': f'Natural Ventilation Windows (Climate {climate_zone})',
                        'current_model_value': f"{window_count} directions: {list(window_directions)}",
                        'recommended_standard_value': f"{required_directions} different directions required",
                        'remark': f'Floor missing {required_directions - window_count} window directions'
                    })
                    
        except Exception:
            pass
    
    def _extract_setpoint_from_schedule(self, schedule_rules):
        """Extract temperature setpoint from schedule rules.
        
        Args:
            schedule_rules: List of schedule rule strings or values
            
        Returns:
            float: Temperature setpoint if found, None otherwise
        """
        try:
            if isinstance(schedule_rules, list):
                for i, rule in enumerate(schedule_rules):
                    if isinstance(rule, str):
                        # Skip time patterns like "Until: 24:00", look for standalone numbers
                        if rule.lower().startswith('until:') or ':' in rule:
                            continue
                        
                        # Look for standalone numeric values that could be temperatures
                        import re
                        # Match standalone numbers (not part of time or other patterns)
                        if re.match(r'^-?\d+(?:\.\d+)?$', rule.strip()):
                            temp_val = float(rule.strip())
                            # Reasonable temperature range for HVAC setpoints (10-35°C, including -50 for off)
                            if -100 <= temp_val <= 35.0 and temp_val != -50:  # -50 is often used as "off"
                                return temp_val
                    elif isinstance(rule, (int, float)):
                        # Direct numeric value
                        temp_val = float(rule)
                        if -100 <= temp_val <= 35.0 and temp_val != -50:
                            return temp_val
            
            return None
            
        except Exception:
            return None