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
                self.loads_by_zone[zone_id] = {
                    "properties": {
                        "area": zone_data.floor_area,
                        "volume": zone_data.volume,
                        "multiplier": zone_data.multiplier
                    },
                    "loads": {
                        "people": [],
                        "lights": [],
                        "equipment": [],
                        "infiltration": []
                    },
                    "schedules": {
                        "heating": None,
                        "cooling": None,
                        "lighting": None,
                        "equipment": None,
                        "occupancy": None
                    }
                }
                
        # Continue with original IDF processing for loads
        # since they're not yet cached in DataLoader
        if idf:
            self._process_people_loads(idf)
            self._process_lights_loads(idf)
            self._process_equipment_loads(idf)
            self._process_infiltration_loads(idf)
            
    def _process_people_loads(self, idf) -> None:
        """Process people loads from IDF."""
        for people in idf.idfobjects['PEOPLE']:
            zone_name = people.Zone_or_ZoneList_Name
            if zone_name in self.loads_by_zone:
                people_data = {
                    "name": str(people.Name),
                    "calculation_method": str(people.Number_of_People_Calculation_Method),
                    "value": float(getattr(people, "People_per_Zone_Floor_Area", 0.0)),
                    "schedule": str(getattr(people, "Number_of_People_Schedule_Name", "")),
                    "activity_schedule": str(getattr(people, "Activity_Level_Schedule_Name", ""))
                }
                self.loads_by_zone[zone_name]["loads"]["people"].append(people_data)
                
    def _process_lights_loads(self, idf) -> None:
        """Process lighting loads from IDF."""
        for lights in idf.idfobjects['LIGHTS']:
            zone_name = str(lights.Zone_or_ZoneList_Name)
            if zone_name in self.loads_by_zone:
                lights_data = {
                    "name": str(lights.Name),
                    "calculation_method": str(getattr(lights, "Design_Level_Calculation_Method", "")),
                    "watts_per_area": float(getattr(lights, "Watts_per_Area", 5.0)),
                    "schedule": str(getattr(lights, "Schedule_Name", ""))
                }
                self.loads_by_zone[zone_name]["loads"]["lights"].append(lights_data)
                
    def _process_equipment_loads(self, idf) -> None:
        """Process equipment loads from IDF."""
        for equip in idf.idfobjects['OTHEREQUIPMENT']:
            zone_name = str(equip.Zone_or_ZoneList_Name)
            if zone_name in self.loads_by_zone:
                default_watts = 8.0 if "Miscellaneous" in str(equip.Name) else 1.0
                equip_data = {
                    "name": str(equip.Name),
                    "fuel_type": str(getattr(equip, "Fuel_Type", "Electricity")),
                    "calculation_method": str(getattr(equip, "Design_Level_Calculation_Method", "Watts/Area")),
                    "watts_per_area": float(getattr(equip, "Watts_per_Area", default_watts)),
                    "schedule": str(getattr(equip, "Schedule_Name", "")),
                    "type": "misc" if "Miscellaneous" in str(equip.Name) else "equipment"
                }
                self.loads_by_zone[zone_name]["loads"]["equipment"].append(equip_data)
                
    def _process_infiltration_loads(self, idf) -> None:
        """Process infiltration loads from IDF."""
        for infil in idf.idfobjects['ZONEINFILTRATION:DESIGNFLOWRATE']:
            zone_name = str(infil.Zone_or_ZoneList_Name)
            if zone_name in self.loads_by_zone:
                infil_data = {
                    "name": str(infil.Name),
                    "calculation_method": str(getattr(infil, "Design_Flow_Rate_Calculation_Method", "")),
                    "flow_rate": float(getattr(infil, "Design_Flow_Rate", 0.0)),
                    "schedule": str(getattr(infil, "Schedule_Name", ""))
                }
                self.loads_by_zone[zone_name]["loads"]["infiltration"].append(infil_data)

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
                    self.loads_by_zone[zone_name] = {
                        "properties": {
                            "area": zone_data.floor_area,
                            "volume": zone_data.volume,
                            "multiplier": zone_data.multiplier
                        },
                        "loads": {
                            "people": [],
                            "lights": [],
                            "equipment": [],
                            "infiltration": []
                        },
                        "schedules": {
                            "heating": None,
                            "cooling": None,
                            "lighting": None,
                            "equipment": None,
                            "occupancy": None
                        }
                    }
                    return
                    
            # Fallback to direct data processing if not in cache
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