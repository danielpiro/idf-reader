"""
Extracts and processes zone loads and their associated schedules using cached data from DataLoader.
"""
from typing import Dict, Any, Optional
from utils.data_loader import DataLoader, safe_float

class LoadExtractor:
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
                "schedules": {"heating": None, "cooling": None}
            }

    def _process_people_loads(self) -> None:
        people_loads = self.data_loader.get_people_loads()
        for zone_name, loads in people_loads.items():
            if zone_name not in self.loads_by_zone:
                continue
            zone_load_data = self.loads_by_zone[zone_name]["loads"]["people"]
            for load in loads:
                if zone_load_data["people_per_area"] is None:
                    zone_load_data["people_per_area"] = 0.0
                zone_load_data["people_per_area"] += load['people_per_area']
                if zone_load_data["schedule"] is None:
                    zone_load_data["schedule"] = load['schedule']
                if zone_load_data["activity_schedule"] is None:
                    rules = self.data_loader.get_schedule_rules(load['activity_schedule'])
                    if rules and len(rules) > 4:
                        zone_load_data["activity_schedule"] = rules[4]

    def _process_lights_loads(self) -> None:
        lights_loads = self.data_loader.get_lights_loads()
        for zone_name, loads in lights_loads.items():
            if zone_name not in self.loads_by_zone:
                continue
            zone_load_data = self.loads_by_zone[zone_name]["loads"]["lights"]
            for load in loads:
                if zone_load_data["watts_per_area"] is None:
                    zone_load_data["watts_per_area"] = 0.0
                zone_load_data["watts_per_area"] += load['watts_per_area']
                if zone_load_data["schedule"] is None:
                    zone_load_data["schedule"] = load['schedule']

    def _process_equipment_loads(self) -> None:
        equipment_loads = self.data_loader.get_equipment_loads()
        for zone_name, loads in equipment_loads.items():
            if zone_name not in self.loads_by_zone:
                continue
            for load in loads:
                key = "fixed_equipment" if load['type'] == 'fixed' else "non_fixed_equipment"
                zone_load_data = self.loads_by_zone[zone_name]["loads"][key]
                if zone_load_data["watts_per_area"] is None:
                    zone_load_data["watts_per_area"] = 0.0
                zone_load_data["watts_per_area"] += load['watts_per_area']
                if zone_load_data["schedule"] is None:
                    zone_load_data["schedule"] = load['schedule']

    def _process_infiltration_loads(self) -> None:
        infiltration_loads = self.data_loader.get_infiltration_loads()
        for zone_name, loads in infiltration_loads.items():
            if zone_name not in self.loads_by_zone:
                continue
            zone_load_data = self.loads_by_zone[zone_name]["loads"]["infiltration"]
            for load in loads:
                if zone_load_data["rate_ach"] is None:
                    zone_load_data["rate_ach"] = 0.0
                zone_load_data["rate_ach"] += load['air_changes_per_hour']
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
                design_flow_rate = safe_float(getattr(load['raw_object'], "Design_Flow_Rate", 0.0))
                if zone_volume > 0:
                    ach = (design_flow_rate * 3600) / zone_volume
                    if zone_load_data["rate_ach"] is None:
                        zone_load_data["rate_ach"] = 0.0
                    zone_load_data["rate_ach"] += ach
                if zone_load_data["schedule"] is None:
                    zone_load_data["schedule"] = load.get('schedule_name', '')

    def _process_mechanical_ventilation_loads(self) -> None:
        if not self.data_loader:
            return
        outdoor_air_specs = self.data_loader.get_outdoor_air_specifications()
        for zone_name, spec_data in outdoor_air_specs.items():
            if zone_name in self.loads_by_zone:
                zone_load_data = self.loads_by_zone[zone_name]["loads"]["mechanical_ventilation"]
                zone_load_data["outdoor_air_flow_per_person"] = spec_data.get('outdoor_air_flow_per_person')
                if zone_load_data["schedule"] is None:
                    zone_load_data["schedule"] = spec_data.get('outdoor_air_flow_rate_fraction_schedule_name')

    def _process_temperature_schedules(self) -> None:
        schedule_data = {}
        if self.data_loader:
            for obj_name in dir(self.data_loader):
                if obj_name == '_schedules_cache':
                    schedule_data = self.data_loader.get_schedules()
                    break
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

    def get_parsed_zone_loads(self, include_core: bool = False) -> Dict[str, Any]:
        """
        Returns the dictionary of parsed zone loads, optionally filtering out core zones.
        """
        if include_core:
            return self.loads_by_zone
        return {
            zone_name: zone_data
            for zone_name, zone_data in self.loads_by_zone.items()
            if not any(keyword in zone_name.lower() for keyword in ['core', 'corridor', 'stair'])
        }

    def get_zone_loads(self, zone_name: str) -> Optional[Dict[str, Any]]:
        return self.loads_by_zone.get(zone_name)

    def get_zone_load_summary(self) -> Dict[str, Dict[str, float]]:
        summary = {}
        for zone_name, zone_data in self.loads_by_zone.items():
            loads = zone_data["loads"]
            summary[zone_name] = {
                "people": loads["people"]["people_per_area"],
                "lights": loads["lights"]["watts_per_area"],
                "fixed_equipment": loads["fixed_equipment"]["watts_per_area"],
                "non_fixed_equipment": loads["non_fixed_equipment"]["watts_per_area"],
                "infiltration": loads["infiltration"]["rate_ach"],
                "ventilation": loads["ventilation"]["rate_ach"],
                "mechanical_ventilation_per_person": loads["mechanical_ventilation"]["outdoor_air_flow_per_person"]
            }
        return summary
