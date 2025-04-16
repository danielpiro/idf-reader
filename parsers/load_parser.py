"""
Extracts and processes zone loads and their associated schedules.
Uses DataLoader for cached access to zone data.
"""
from typing import Dict, Any, Optional
from utils.data_loader import DataLoader

class LoadExtractor:
    """
    Extracts zone loads and their associated schedules.
    Uses cached data from DataLoader for efficient access.
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
        Process loads and schedules using cached zone data.
        
        Args:
            idf: eppy IDF object (kept for compatibility)
        """
        if not idf and not self.data_loader:
            return
            
        # Use either cached data or IDF object
        if self.data_loader:
            # Get zones from cache
            zones = self.data_loader.get_all_zones()
            for zone_id, zone_data in zones.items():
                # Initialize with aggregated structure
                self.loads_by_zone[zone_id] = {
                    "properties": {
                        "area": zone_data.floor_area,
                        "volume": zone_data.volume,
                        "multiplier": zone_data.multiplier
                    },
                    "loads": {
                        "people": {"people_per_area": 0.0, "activity_schedule": None, "schedule": None},
                        "lights": {"watts_per_area": 0.0, "schedule": None},
                        "non_fixed_equipment": {"watts_per_area": 0.0, "schedule": None},
                        "fixed_equipment": {"watts_per_area": 0.0, "schedule": None},
                        "infiltration": {"rate_ach": 0.0, "schedule": None}, # Assuming ACH for now
                        "ventilation": {"rate_ach": 0.0, "schedule": None} # Assuming ACH for now
                    },
                    "schedules": { # Keep detailed schedule info for heating/cooling here
                        "heating": None,
                        "cooling": None
                        # Other schedule types might be redundant if captured in loads,
                        # but keep for now if needed elsewhere.
                        # "lighting": None,
                        # "equipment": None,
                        # "occupancy": None,
                        # "temperature": None
                    }
                }
                
        # Continue with original IDF processing for loads
        # since they're not yet cached in DataLoader
        if idf:
            self._process_people_loads(idf)
            self._process_lights_loads(idf)
            self._process_equipment_loads(idf)
            self._process_infiltration_loads(idf)
            self._process_ventilation_loads(idf) # Add call for ventilation
            self._process_temperature_schedules(idf)

    def _process_people_loads(self, idf) -> None:
        """Process and aggregate people loads from IDF."""
        for people in idf.idfobjects['PEOPLE']:
            zone_name = people.Zone_or_ZoneList_Name
            if zone_name in self.loads_by_zone:
                zone_load_data = self.loads_by_zone[zone_name]["loads"]["people"]
                
                # Sum density
                zone_load_data["people_per_area"] += float(getattr(people, "People_per_Zone_Floor_Area", 0.0))
                
                # Store first schedule names encountered
                if zone_load_data["schedule"] is None:
                    zone_load_data["schedule"] = str(getattr(people, "Number_of_People_Schedule_Name", ""))
                if zone_load_data["activity_schedule"] is None:
                    zone_load_data["activity_schedule"] = str(getattr(people, "Activity_Level_Schedule_Name", ""))

    def _process_lights_loads(self, idf) -> None:
        """Process and aggregate lighting loads from IDF."""
        for lights in idf.idfobjects['LIGHTS']:
            zone_name = str(lights.Zone_or_ZoneList_Name)
            if zone_name in self.loads_by_zone:
                zone_load_data = self.loads_by_zone[zone_name]["loads"]["lights"]
                
                # Sum density (Revised logic)
                watts_val = getattr(lights, "Watts_per_Area", None) # Default to None if missing
                if watts_val is not None:
                    try:
                        # Attempt conversion only if value exists
                        watts_float = float(watts_val)
                        zone_load_data["watts_per_area"] += watts_float
                    except (ValueError, TypeError):
                        # If conversion fails for existing value, add 0 and warn
                        print(f"Warning: Could not convert lights Watts_per_Area '{watts_val}' to float for zone {zone_name}. Adding 0.0.")
                        zone_load_data["watts_per_area"] += 0.0
                else:
                    # If attribute Watts_per_Area is missing entirely, add default 5.0 (based on IDF example)
                    zone_load_data["watts_per_area"] += 5.0

                # Store first non-empty schedule name encountered (Revised logic)
                schedule_name_val = getattr(lights, "Schedule_Name", None) # Default to None
                if zone_load_data["schedule"] is None and schedule_name_val: # Check if current schedule is None and new one is not None/empty
                    zone_load_data["schedule"] = str(schedule_name_val)

    def _process_equipment_loads(self, idf) -> None:
        """Process and aggregate equipment loads from IDF, splitting into fixed and non-fixed."""
        for equip in idf.idfobjects['OTHEREQUIPMENT']:
            zone_name = str(equip.Zone_or_ZoneList_Name)
            if zone_name in self.loads_by_zone:
                # Determine type: non-fixed (misc) or fixed
                is_non_fixed = "Miscellaneous" in str(equip.Name)
                load_key = "non_fixed_equipment" if is_non_fixed else "fixed_equipment"
                zone_load_data = self.loads_by_zone[zone_name]["loads"][load_key]

                # Sum density (Revised logic)
                default_watts = 6.0 if is_non_fixed else 1.0
                watts_val = getattr(equip, "Watts_per_Area", None) # Default to None if missing
                if watts_val is not None:
                    try:
                        # Attempt conversion only if value exists
                        watts_float = float(watts_val)
                        zone_load_data["watts_per_area"] += watts_float
                    except (ValueError, TypeError):
                        # If conversion fails for existing value, add default and warn
                        print(f"Warning: Could not convert equipment Watts_per_Area '{watts_val}' to float for zone {zone_name}. Adding default {default_watts}.")
                        zone_load_data["watts_per_area"] += default_watts
                else:
                    # If attribute Watts_per_Area is missing entirely, add default
                    zone_load_data["watts_per_area"] += default_watts

                # Store first non-empty schedule name encountered (Revised logic)
                schedule_name_val = getattr(equip, "Schedule_Name", None) # Default to None
                if zone_load_data["schedule"] is None and schedule_name_val: # Check if current schedule is None and new one is not None/empty
                    zone_load_data["schedule"] = str(schedule_name_val)

    def _process_infiltration_loads(self, idf) -> None:
        """Process and aggregate infiltration loads from IDF."""
        for infil in idf.idfobjects['ZONEINFILTRATION:DESIGNFLOWRATE']:
            zone_name = str(infil.Zone_or_ZoneList_Name)
            if zone_name in self.loads_by_zone:
                zone_load_data = self.loads_by_zone[zone_name]["loads"]["infiltration"]
                
                # Sum rate (Assuming ACH from 'Air_Changes_Per_Hour' field, default 0 if missing/blank)
                # Note: User confirmed infiltration is ACH, but IDF example shows Flow/zone.
                # Using Air_Changes_Per_Hour field as primary source based on target table header.
                ach_rate = getattr(infil, "Air_Changes_Per_Hour", None) # Check if field exists
                if ach_rate is not None and isinstance(ach_rate, (int, float)):
                     zone_load_data["rate_ach"] += float(ach_rate)
                else:
                     # Placeholder: If ACH field is missing or not numeric, add 0.
                     # Could potentially calculate from flow_rate and volume later if needed.
                     zone_load_data["rate_ach"] += 0.0

                # Store first schedule name encountered
                if zone_load_data["schedule"] is None:
                    zone_load_data["schedule"] = str(getattr(infil, "Schedule_Name", ""))

    def _process_ventilation_loads(self, idf) -> None:
        """Process and aggregate ventilation loads from IDF."""
        for vent in idf.idfobjects.get('ZONEVENTILATION:DESIGNFLOWRATE', []): # Use .get for safety
            zone_name = str(vent.Zone_or_ZoneList_Name)
            if zone_name in self.loads_by_zone:
                zone_load_data = self.loads_by_zone[zone_name]["loads"]["ventilation"]

                # Sum rate (Assuming ACH from 'Air_Changes_Per_Hour' field, default 0 if missing/blank)
                ach_rate = getattr(vent, "Air_Changes_Per_Hour", None) # Check if field exists
                if ach_rate is not None and isinstance(ach_rate, (int, float)):
                     zone_load_data["rate_ach"] += float(ach_rate)
                else:
                     # Placeholder: If ACH field is missing or not numeric, add 0.
                     zone_load_data["rate_ach"] += 0.0

                # Store first schedule name encountered
                if zone_load_data["schedule"] is None:
                    zone_load_data["schedule"] = str(getattr(vent, "Schedule_Name", "")) # IDF uses Schedule_Name

    def _process_temperature_schedules(self, idf) -> None:
        """Process zone temperature schedules from IDF. Stores the full schedule dict."""
        for schedule in idf.idfobjects['Schedule:Compact']:
            # Get schedule name and type
            schedule_name = str(schedule.Name)
            schedule_type = str(schedule.Schedule_Type_Limits_Name)
            
            # Check if it's a temperature setpoint schedule
            schedule_name_lower = schedule_name.lower()
            # Check for heating or cooling temperature schedules
            if 'heating' in schedule_name_lower or 'cooling' in schedule_name_lower:
                # Find corresponding zone by matching schedule name with zone name
                for zone_name in self.loads_by_zone:
                    zone_name_lower = zone_name.lower()
                    if zone_name_lower in schedule_name_lower:
                        # Determine if it's heating or cooling schedule
                        schedule_data = {
                            "name": schedule_name,
                            "type": schedule_type,
                            "schedule_values": [field for field in schedule.fieldvalues[2:]]  # Skip name and type
                        }
                        
                        if 'heating' in schedule_name_lower:
                            self.loads_by_zone[zone_name]["schedules"]["heating"] = schedule_data
                        elif 'cooling' in schedule_name_lower:
                            self.loads_by_zone[zone_name]["schedules"]["cooling"] = schedule_data

    def process_eppy_zone(self, zone_obj) -> None:
        """
        Process a Zone object from eppy directly.
        
        Args:
            zone_obj: An eppy Zone object
        """
        zone_name = str(zone_obj.Name)
        if zone_name not in self.loads_by_zone:
            # Try to get zone from cache first
            if self.data_loader:
                zone_data = self.data_loader.get_zone(zone_name)
                if zone_data:
                     # Initialize with aggregated structure if loading from cache
                    self.loads_by_zone[zone_name] = {
                        "properties": {
                            "area": zone_data.floor_area,
                            "volume": zone_data.volume,
                            "multiplier": zone_data.multiplier
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
                    # Note: Need to re-run IDF processing even if zone props are cached,
                    # as loads/schedules aren't fully cached yet.
                    # So, don't return here. Let it fall through.

            # Fallback to direct data processing if not in cache (or if cache only had props)
            data = [field for field in zone_obj.fieldvalues]
            self._process_zone_data(data)

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