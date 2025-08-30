"""
Extracts and processes zone loads and their associated schedules using cached data from DataLoader.
"""
from typing import Dict, Any, Optional
from utils.data_loader import DataLoader
from .utils import safe_float
from utils.logging_config import get_logger

logger = get_logger(__name__)

class LoadParser:
    """
    Extracts zone loads and their associated schedules using cached data from DataLoader.
    """
    def __init__(self, data_loader: Optional[DataLoader] = None):
        self.data_loader = data_loader
        self.loads_by_zone = {}

    def process_idf(self, idf) -> None:
        if not self.data_loader:
            raise RuntimeError("LoadExtractor requires a DataLoader instance.")
        self._process_zones()
        self._process_people_loads()
        self._process_lights_loads()
        self._process_equipment_loads()
        self._process_infiltration_loads()
        self._process_ventilation_loads()
        self._process_mechanical_ventilation_loads()
        self._process_temperature_schedules()

    def _process_zones(self) -> None:
        zones = self.data_loader.get_zones()
        for zone_id, zone_data in zones.items():
            self.loads_by_zone[zone_id] = {
                "properties": {
                    "area": zone_data['floor_area'],
                    "volume": zone_data['volume'],
                    "multiplier": zone_data['multiplier']
                },
                "loads": {
                    "people": {"people_per_area": None, "activity_schedule": None, "schedule": None},
                    "lights": {"watts_per_area": None, "schedule": None},
                    "non_fixed_equipment": {"watts_per_area": None, "schedule": None},
                    "fixed_equipment": {"watts_per_area": None, "schedule": None},
                    "infiltration": {"rate_ach": None, "schedule": None},
                    "ventilation": {"rate_ach": None, "schedule": None},
                    "mechanical_ventilation": {"outdoor_air_flow_per_person": None, "schedule": None}
                },
                "schedules": {"heating": None, "cooling": None},
                "setpoints": {"non_work_time_heating": None, "non_work_time_cooling": None}
            }

    def _process_people_loads(self) -> None:
        people_loads = self.data_loader.get_people_loads()
        for zone_name, loads in people_loads.items():
            if zone_name not in self.loads_by_zone:
                continue
            zone_load_data = self.loads_by_zone[zone_name]["loads"]["people"]
            for load in loads:
                # Initialize and accumulate people per area
                if zone_load_data["people_per_area"] is None:
                    zone_load_data["people_per_area"] = 0.0
                zone_load_data["people_per_area"] += load['people_per_area']
                
                # Set schedule if not already set
                if zone_load_data["schedule"] is None:
                    zone_load_data["schedule"] = load['schedule']
                
                # Set activity schedule if not already set
                if zone_load_data["activity_schedule"] is None:
                    rules = self.data_loader.get_schedule_rules(load['activity_schedule'])
                    if rules and len(rules) > 3:
                        zone_load_data["activity_schedule"] = rules[3]

    def _process_lights_loads(self) -> None:
        lights_loads = self.data_loader.get_lights_loads()
        self._process_power_loads(lights_loads, "lights", "watts_per_area")

    def _process_power_loads(self, loads_data: dict, load_type: str, power_key: str) -> None:
        """Helper method to process power-based loads (lights, equipment)."""
        for zone_name, loads in loads_data.items():
            if zone_name not in self.loads_by_zone:
                continue
            zone_load_data = self.loads_by_zone[zone_name]["loads"][load_type]
            for load in loads:
                if zone_load_data[power_key] is None:
                    zone_load_data[power_key] = 0.0
                zone_load_data[power_key] += load[power_key]
                if zone_load_data["schedule"] is None:
                    zone_load_data["schedule"] = load['schedule']

    def _process_equipment_loads(self) -> None:
        equipment_loads = self.data_loader.get_equipment_loads()
        for zone_name, loads in equipment_loads.items():
            if zone_name not in self.loads_by_zone:
                continue
            for load in loads:
                load_type = "fixed_equipment" if load['type'] == 'fixed' else "non_fixed_equipment"
                zone_load_data = self.loads_by_zone[zone_name]["loads"][load_type]
                if zone_load_data["watts_per_area"] is None:
                    zone_load_data["watts_per_area"] = 0.0
                zone_load_data["watts_per_area"] += load['watts_per_area']
                if zone_load_data["schedule"] is None:
                    zone_load_data["schedule"] = load['schedule']

    def _process_infiltration_loads(self) -> None:
        infiltration_loads = self.data_loader.get_infiltration_loads()
        self._process_ach_loads(infiltration_loads, "infiltration", "air_changes_per_hour")

    def _process_ach_loads(self, loads_data: dict, load_type: str, ach_key: str) -> None:
        """Helper method to process air change rate loads (infiltration)."""
        for zone_name, loads in loads_data.items():
            if zone_name not in self.loads_by_zone:
                continue
            zone_load_data = self.loads_by_zone[zone_name]["loads"][load_type]
            for load in loads:
                if zone_load_data["rate_ach"] is None:
                    zone_load_data["rate_ach"] = 0.0
                zone_load_data["rate_ach"] += load[ach_key]
                if zone_load_data["schedule"] is None:
                    zone_load_data["schedule"] = load['schedule']

    def _process_ventilation_loads(self) -> None:
        ventilation_loads = self.data_loader.get_ventilation_loads()
        zones = self.data_loader.get_zones()
        for zone_name, loads in ventilation_loads.items():
            if zone_name not in self.loads_by_zone:
                continue
            zone_load_data = self.loads_by_zone[zone_name]["loads"]["ventilation"]
            zone_volume = zones[zone_name]['volume']
            for load in loads:
                calculation_method = getattr(load['raw_object'], "design_flow_rate_calculation_method", "").strip()
                
                ach = 0.0
                if calculation_method == "AirChanges/Hour":
                    # Read Air Changes per Hour field directly
                    ach = safe_float(getattr(load['raw_object'], "air_changes_per_hour", 0.0))
                else:
                    # Fallback to Design Flow Rate calculation
                    design_flow_rate = safe_float(getattr(load['raw_object'], "design_flow_rate", 0.0))
                    if zone_volume > 0:
                        ach = (design_flow_rate * 3600) / zone_volume
                    else:
                        logger.warning(f"LOAD PARSER DEBUG - Zone '{zone_name}': zone_volume is 0, cannot calculate ACH")
                
                if zone_load_data["rate_ach"] is None:
                    zone_load_data["rate_ach"] = 0.0
                zone_load_data["rate_ach"] += ach
                if zone_load_data["schedule"] is None:
                    zone_load_data["schedule"] = load.get('schedule_name', '')

    def _process_mechanical_ventilation_loads(self) -> None:
        outdoor_air_specs = self.data_loader.get_outdoor_air_specifications()
        for zone_name, spec_data in outdoor_air_specs.items():
            if zone_name in self.loads_by_zone:
                zone_load_data = self.loads_by_zone[zone_name]["loads"]["mechanical_ventilation"]
                zone_load_data["outdoor_air_flow_per_person"] = spec_data.get('outdoor_air_flow_per_person')
                if zone_load_data["schedule"] is None:
                    zone_load_data["schedule"] = spec_data.get('outdoor_air_flow_rate_fraction_schedule_name')

    def _process_temperature_schedules(self) -> None:
        schedule_data = self.data_loader.get_schedules()
        if not schedule_data:
            return
        zone_temp_schedules = {}
        for schedule_id, schedule in schedule_data.items():
            schedule_name = schedule_id
            schedule_type = schedule.get('type', '')
            schedule_name_lower = schedule_name.lower()
            is_heating = 'heating' in schedule_name_lower or 'heat' in schedule_name_lower and not 'availability' in schedule_name_lower
            is_cooling = 'cooling' in schedule_name_lower or 'cool' in schedule_name_lower and not 'availability' in schedule_name_lower
            is_availability = 'availability' in schedule_name_lower or 'avail' in schedule_name_lower
            zone_prefix = schedule_name.split(' ')[0] if ':' in schedule_name else None
            if (is_heating or is_cooling) and zone_prefix:
                if zone_prefix in self.loads_by_zone:
                    zone_name = zone_prefix
                    if zone_name not in zone_temp_schedules:
                        zone_temp_schedules[zone_name] = {
                            'heating_setpoint': None,
                            'heating_availability': None,
                            'cooling_setpoint': None,
                            'cooling_availability': None
                        }
                    schedule_rules = self.data_loader.get_schedule_rules(schedule_id)
                    schedule_info = {
                        "name": schedule_name,
                        "type": schedule_type,
                        "schedule_values": schedule_rules
                    }
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
        for zone_name, temp_schedules in zone_temp_schedules.items():
            if temp_schedules['heating_setpoint']:
                heating_data = temp_schedules['heating_setpoint'].copy()
                if temp_schedules['heating_availability']:
                    heating_data['heating_availability'] = temp_schedules['heating_availability']
                self.loads_by_zone[zone_name]["schedules"]["heating"] = heating_data
            if temp_schedules['cooling_setpoint']:
                cooling_data = temp_schedules['cooling_setpoint'].copy()
                if temp_schedules['cooling_availability']:
                    cooling_data['cooling_availability'] = temp_schedules['cooling_availability']
                self.loads_by_zone[zone_name]["schedules"]["cooling"] = cooling_data
            
            # Extract non-work time setpoints
            self._extract_non_work_time_setpoints(zone_name, temp_schedules)

    def _extract_non_work_time_setpoints(self, zone_name: str, temp_schedules: Dict[str, Any]) -> None:
        """
        Extract setpoint values when availability is 0 (non-work time).
        """
        # Process heating non-work time setpoint
        if temp_schedules['heating_setpoint'] and temp_schedules['heating_availability']:
            heating_setpoint_values = temp_schedules['heating_setpoint']['schedule_values']
            heating_availability_values = temp_schedules['heating_availability']['schedule_values']
            
            non_work_heating = self._get_non_work_setpoint(heating_setpoint_values, heating_availability_values)
            if non_work_heating is not None:
                self.loads_by_zone[zone_name]["setpoints"]["non_work_time_heating"] = non_work_heating
        
        # Process cooling non-work time setpoint  
        if temp_schedules['cooling_setpoint'] and temp_schedules['cooling_availability']:
            cooling_setpoint_values = temp_schedules['cooling_setpoint']['schedule_values']
            cooling_availability_values = temp_schedules['cooling_availability']['schedule_values']
            
            non_work_cooling = self._get_non_work_setpoint(cooling_setpoint_values, cooling_availability_values)
            if non_work_cooling is not None:
                self.loads_by_zone[zone_name]["setpoints"]["non_work_time_cooling"] = non_work_cooling

    def _get_non_work_setpoint(self, setpoint_values: list, availability_values: list) -> Optional[float]:
        """
        Find the setpoint value corresponding to when availability is 0.
        """
        if not setpoint_values or not availability_values:
            return None
            
        # Parse schedule values to find periods where availability is 0
        availability_periods = self._parse_schedule_periods(availability_values)
        setpoint_periods = self._parse_schedule_periods(setpoint_values)
        
        # Find setpoint values when availability is 0
        for avail_period in availability_periods:
            if avail_period['value'] == '0':
                # Find corresponding setpoint for this period
                for setpoint_period in setpoint_periods:
                    if self._periods_overlap(avail_period, setpoint_period):
                        try:
                            return float(setpoint_period['value'])
                        except (ValueError, TypeError):
                            continue
        return None

    def _parse_schedule_periods(self, schedule_values: list) -> list:
        """
        Parse schedule values into periods with start/end dates and values.
        """
        periods = []
        current_period = {}
        
        for i, value in enumerate(schedule_values):
            if value.startswith('Through:'):
                current_period['end_date'] = value.replace('Through: ', '').strip()
            elif value.startswith('For:'):
                current_period['day_type'] = value.replace('For: ', '').strip()
            elif value.startswith('Until:'):
                current_period['end_time'] = value.replace('Until: ', '').strip()
            else:
                # This should be the actual value
                current_period['value'] = value.strip()
                if 'end_date' in current_period:
                    periods.append(current_period.copy())
                    current_period = {}
        
        return periods

    def _periods_overlap(self, period1: dict, period2: dict) -> bool:
        """
        Check if two schedule periods overlap (simplified check based on end_date).
        """
        return period1.get('end_date') == period2.get('end_date')

    def get_parsed_zone_loads(self, include_core: bool = False) -> Dict[str, Any]:
        """
        Returns the dictionary of parsed zone loads, optionally filtering to energy-included zones only.
        """
        logger.info(f"LOAD PARSER DEBUG - get_parsed_zone_loads called with include_core={include_core}")
        logger.info(f"LOAD PARSER DEBUG - Total zones in loads_by_zone: {len(self.loads_by_zone)}")
        
        if include_core:
            logger.info("LOAD PARSER DEBUG - Returning all zones (include_core=True)")
            return self.loads_by_zone
        
        # Filter to only zones with include_in_energy=True from CSV "Part of Total Floor Area (Y/N)" flags
        energy_zones = set(self.data_loader.get_energy_included_zones())
        logger.info(f"LOAD PARSER DEBUG - Energy included zones from CSV: {len(energy_zones)} zones")
        logger.info(f"LOAD PARSER DEBUG - Sample energy zones: {list(energy_zones)[:5]}")
        
        filtered_loads = {
            zone_name: zone_data
            for zone_name, zone_data in self.loads_by_zone.items()
            if zone_name in energy_zones
        }
        
        logger.info(f"LOAD PARSER DEBUG - Filtered result: {len(filtered_loads)} zones")
        logger.info(f"LOAD PARSER DEBUG - Sample filtered zones: {list(filtered_loads.keys())[:5]}")
        
        return filtered_loads

