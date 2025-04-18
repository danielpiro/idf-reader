"""
Extracts and processes zone loads and their associated schedules.
Uses DataLoader for cached access to zone data.
"""
from typing import Dict, Any, Optional, List
from utils.data_loader import DataLoader, safe_float
from utils.data_models import ZoneData

class LoadExtractor:
    """
    Extracts zone loads and their associated schedules.
    Implementation details moved from DataLoader.
    """
    def __init__(self, data_loader: Optional[DataLoader] = None):
        """
        Initialize LoadExtractor.
        
        Args:
            data_loader: DataLoader instance for accessing cached data
        """
        self.data_loader = data_loader
        # Store loads and schedules by zone
        self.loads_by_zone = {}  # {zone_name: {properties: {}, loads: {}, schedules: {}}}

    def process_idf(self, idf) -> None:
        """
        Process loads and schedules using cached data.
        Implementation details moved from DataLoader.
        
        Args:
            idf: eppy IDF object (kept for compatibility)
        """
        if not self.data_loader:
            print("Warning: LoadExtractor requires a DataLoader instance for efficient processing")
            return
        
        # Get all zones first
        self._process_zones()
        
        # Then process load data for each zone
        self._process_people_loads()
        self._process_lights_loads()
        self._process_equipment_loads()
        self._process_infiltration_loads()
        self._process_ventilation_loads()
        self._process_temperature_schedules()

    def _process_zones(self) -> None:
        """
        Initialize zone data structure for all zones.
        Implementation details moved from DataLoader.
        """
        # Get cached zone data
        zones = self.data_loader.get_zones()
        
        # Initialize zone data structure
        for zone_id, zone_data in zones.items():
            self.loads_by_zone[zone_id] = {
                "properties": {
                    "area": zone_data['floor_area'],
                    "volume": zone_data['volume'],
                    "multiplier": zone_data['multiplier']
                },
                "loads": {
                    "people": {"people_per_area": 0.0, "activity_schedule": None, "schedule": None},
                    "lights": {"watts_per_area": 0.0, "schedule": None},
                    "non_fixed_equipment": {"watts_per_area": 0.0, "schedule": None},
                    "fixed_equipment": {"watts_per_area": 0.0, "schedule": None},
                    "infiltration": {"rate_ach": 0.0, "schedule": None},
                    "ventilation": {"rate_ach": 0.0, "schedule": None}
                },
                "schedules": {
                    "heating": None,
                    "cooling": None
                }
            }

    def _process_people_loads(self) -> None:
        """
        Process and aggregate people loads.
        Implementation details moved from DataLoader.
        """
        # Get cached people loads
        people_loads = self.data_loader.get_people_loads()
        
        # Process each zone's people loads
        for zone_name, loads in people_loads.items():
            if zone_name not in self.loads_by_zone:
                continue
                
            zone_load_data = self.loads_by_zone[zone_name]["loads"]["people"]
            
            # Sum density
            for load in loads:
                zone_load_data["people_per_area"] += load['people_per_area']
                
                # Store first schedule names encountered
                if zone_load_data["schedule"] is None:
                    zone_load_data["schedule"] = load['schedule']
                if zone_load_data["activity_schedule"] is None:
                    zone_load_data["activity_schedule"] = self.data_loader.get_schedule_rules(load['activity_schedule'])[4]

    def _process_lights_loads(self) -> None:
        """
        Process and aggregate lighting loads.
        Implementation details moved from DataLoader.
        """
        # Get cached lights loads
        lights_loads = self.data_loader.get_lights_loads()
        
        # Process each zone's lights loads
        for zone_name, loads in lights_loads.items():
            if zone_name not in self.loads_by_zone:
                continue
                
            zone_load_data = self.loads_by_zone[zone_name]["loads"]["lights"]
            
            # Sum density
            for load in loads:
                zone_load_data["watts_per_area"] += load['watts_per_area']
                
                # Store first schedule name encountered
                if zone_load_data["schedule"] is None:
                    zone_load_data["schedule"] = load['schedule']

    def _process_equipment_loads(self) -> None:
        """
        Process and aggregate equipment loads, splitting into fixed and non-fixed.
        Implementation details moved from DataLoader.
        """
        # Get cached equipment loads
        equipment_loads = self.data_loader.get_equipment_loads()
        
        # Process each zone's equipment loads
        for zone_name, loads in equipment_loads.items():
            if zone_name not in self.loads_by_zone:
                continue
                
            # Split by equipment type
            for load in loads:
                if load['type'] == 'fixed':
                    # Fixed equipment
                    zone_load_data = self.loads_by_zone[zone_name]["loads"]["fixed_equipment"]
                else:
                    # Non-fixed equipment
                    zone_load_data = self.loads_by_zone[zone_name]["loads"]["non_fixed_equipment"]
                
                # Add watts per area
                zone_load_data["watts_per_area"] += load['watts_per_area']
                
                # Store first schedule name encountered
                if zone_load_data["schedule"] is None:
                    zone_load_data["schedule"] = load['schedule']

    def _process_infiltration_loads(self) -> None:
        """
        Process and aggregate infiltration loads.
        Implementation details moved from DataLoader.
        """
        # Get cached infiltration loads
        infiltration_loads = self.data_loader.get_infiltration_loads()
        
        # Process each zone's infiltration loads
        for zone_name, loads in infiltration_loads.items():
            if zone_name not in self.loads_by_zone:
                continue
                
            zone_load_data = self.loads_by_zone[zone_name]["loads"]["infiltration"]
            
            # Sum rate
            for load in loads:
                zone_load_data["rate_ach"] += load['air_changes_per_hour']
                
                # Store first schedule name encountered
                if zone_load_data["schedule"] is None:
                    zone_load_data["schedule"] = load['schedule']

    def _process_ventilation_loads(self) -> None:
        """
        Process and aggregate ventilation loads.
        Implementation details moved from DataLoader.
        """
        # Get cached ventilation loads
        ventilation_loads = self.data_loader.get_ventilation_loads()
        
        # Process each zone's ventilation loads
        for zone_name, loads in ventilation_loads.items():
            if zone_name not in self.loads_by_zone:
                continue
                
            zone_load_data = self.loads_by_zone[zone_name]["loads"]["ventilation"]
            
            # Sum rate
            for load in loads:
                zone_load_data["rate_ach"] += load['air_changes_per_hour']
                
                # Store first schedule name encountered
                if zone_load_data["schedule"] is None:
                    zone_load_data["schedule"] = load['schedule']

    def _process_temperature_schedules(self) -> None:
        """
        Process zone temperature schedules.
        Implementation details moved from DataLoader.
        """
        # Get cached schedule data, which may be from ScheduleExtractor if available
        schedule_data = {}
        if self.data_loader:
            # Try to get processed schedules from ScheduleExtractor
            for obj_name in dir(self.data_loader):
                if obj_name == '_schedules_cache':
                    schedule_data = self.data_loader.get_schedules()
                    break
        
        if not schedule_data:
            # Fallback if ScheduleExtractor data not available
            print("Warning: No schedule data available for processing temperature schedules")
            return
            
        # First pass: Collect all temperature-related schedules by zone
        zone_temp_schedules = {}
        
        # Process each schedule
        for schedule_id, schedule in schedule_data.items():
            # Get schedule name and type
            schedule_name = schedule_id
            schedule_type = schedule.get('type', '')
            schedule_name_lower = schedule_name.lower()
            
            is_heating = 'heating' in schedule_name_lower or 'heat' in schedule_name_lower and not 'availability' in schedule_name_lower
            is_cooling = 'cooling' in schedule_name_lower or 'cool' in schedule_name_lower and not 'availability' in schedule_name_lower
            is_setpoint = 'setpoint' in schedule_name_lower or 'sp' in schedule_name_lower
            is_availability = 'availability' in schedule_name_lower or 'avail' in schedule_name_lower

            # Extract zone name directly from the schedule name for better matching
            zone_prefix = None
            if ':' in schedule_name:  # Format like "00:01XLIVING"
                zone_prefix = schedule_name.split(' ')[0]  # Take the part before the space
                
            # Check if it's a temperature-related schedule
            if (is_heating or is_cooling) and zone_prefix:
                # Direct exact zone name matching
                if zone_prefix in self.loads_by_zone:
                    zone_name = zone_prefix
                    
                    # Initialize zone in temp schedules dict if not present
                    if zone_name not in zone_temp_schedules:
                        zone_temp_schedules[zone_name] = {
                            'heating_setpoint': None,
                            'heating_availability': None,
                            'cooling_setpoint': None,
                            'cooling_availability': None
                        }
                        
                    # Create schedule data with rules
                    schedule_rules = self.data_loader.get_schedule_rules(schedule_id)
                    schedule_info = {
                        "name": schedule_name,
                        "type": schedule_type,
                        "schedule_values": schedule_rules
                    }
                    
                    # Store in appropriate slot
                    if is_heating:
                        if is_availability:
                            zone_temp_schedules[zone_name]['heating_availability'] = schedule_info
                        else:
                            zone_temp_schedules[zone_name]['heating_setpoint'] = schedule_info
                    elif is_cooling:
                        if is_availability:
                            zone_temp_schedules[zone_name]['cooling_availability'] = schedule_info
                        else:
                            zone_temp_schedules[zone_name]['cooling_setpoint'] = schedule_info
        
        # Second pass: Update zone data with all collected temperature schedules
        for zone_name, temp_schedules in zone_temp_schedules.items():
            # Update heating
            if temp_schedules['heating_setpoint']:
                # Create a copy of the setpoint schedule data
                heating_data = temp_schedules['heating_setpoint'].copy()
                # Add availability data if available
                if temp_schedules['heating_availability']:
                    heating_data['heating_availability'] = temp_schedules['heating_availability']
                self.loads_by_zone[zone_name]["schedules"]["heating"] = heating_data
                
            # Update cooling
            if temp_schedules['cooling_setpoint']:
                # Create a copy of the setpoint schedule data
                cooling_data = temp_schedules['cooling_setpoint'].copy()
                # Add availability data if available
                if temp_schedules['cooling_availability']:
                    cooling_data['cooling_availability'] = temp_schedules['cooling_availability']
                self.loads_by_zone[zone_name]["schedules"]["cooling"] = cooling_data

    def process_eppy_zone(self, zone_obj) -> None:
        """
        Process a Zone object from eppy directly.
        
        Args:
            zone_obj: An eppy Zone object
        """
        zone_name = str(zone_obj.Name)
        if zone_name not in self.loads_by_zone:
            # Initialize with zone data from the object
            self.loads_by_zone[zone_name] = {
                "properties": {
                    "area": safe_float(getattr(zone_obj, "Floor_Area", 0.0)),
                    "volume": safe_float(getattr(zone_obj, "Volume", 0.0)),
                    "multiplier": int(safe_float(getattr(zone_obj, "Multiplier", 1)))
                },
                "loads": {
                    "people": {"people_per_area": 0.0, "activity_schedule": None, "schedule": None},
                    "lights": {"watts_per_area": 0.0, "schedule": None},
                    "non_fixed_equipment": {"watts_per_area": 0.0, "schedule": None},
                    "fixed_equipment": {"watts_per_area": 0.0, "schedule": None},
                    "infiltration": {"rate_ach": 0.0, "schedule": None},
                    "ventilation": {"rate_ach": 0.0, "schedule": None}
                },
                "schedules": {
                    "heating": None,
                    "cooling": None
                }
            }

    def get_parsed_zone_loads(self, include_core: bool = False) -> Dict[str, Any]:
        """
        Returns the dictionary of parsed zone loads, optionally filtering out core zones.
        
        Args:
            include_core: If False, core zones will be filtered out from results
            
        Returns:
            dict: Dictionary of zone loads and their associated schedules
        """
        if include_core:
            return self.loads_by_zone
            
        # Filter out core zones
        return {
            zone_name: zone_data
            for zone_name, zone_data in self.loads_by_zone.items()
            if not any(keyword in zone_name.lower() for keyword in ['core', 'corridor', 'stair'])
        }
        
    def get_zone_loads(self, zone_name: str) -> Optional[Dict[str, Any]]:
        """
        Get loads for a specific zone.
        
        Args:
            zone_name: Name of the zone
            
        Returns:
            Optional[Dict[str, Any]]: Zone loads if found, None otherwise
        """
        return self.loads_by_zone.get(zone_name)
    
    def get_zone_load_summary(self) -> Dict[str, Dict[str, float]]:
        """
        Get a summary of load densities for all zones.
        
        Returns:
            Dict[str, Dict[str, float]]: Dictionary of load summaries by zone
        """
        summary = {}
        
        for zone_name, zone_data in self.loads_by_zone.items():
            loads = zone_data["loads"]
            summary[zone_name] = {
                "people": loads["people"]["people_per_area"],
                "lights": loads["lights"]["watts_per_area"],
                "fixed_equipment": loads["fixed_equipment"]["watts_per_area"],
                "non_fixed_equipment": loads["non_fixed_equipment"]["watts_per_area"],
                "infiltration": loads["infiltration"]["rate_ach"],
                "ventilation": loads["ventilation"]["rate_ach"]
            }
            
        return summary