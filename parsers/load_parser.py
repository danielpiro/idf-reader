"""
Extracts and processes zone loads and their associated schedules using eppy.
"""

class LoadExtractor:
    """
    Extracts zone loads and their associated schedules using eppy.
    Tracks equipment, occupancy, schedules and loads for each zone.
    """
    def __init__(self):
        # Store loads and schedules by zone
        self.loads_by_zone = {}  # {zone_name: {properties: {}, loads: {}, schedules: {}}}

    def process_idf(self, idf):
        """
        Process an entire IDF model to extract all zone loads and schedules.
        
        Args:
            idf: eppy IDF object
        """
        # First get all zones and their basic properties
        for zone in idf.idfobjects['ZONE']:
            zone_name = str(zone.Name)
            self.loads_by_zone[zone_name] = {
                "properties": {
                    "area": float(getattr(zone, "Floor_Area", 100.0)),  # Default to 100 if not specified
                    "volume": float(getattr(zone, "Volume", 300.0)),  # Default to 300 if not specified
                    "multiplier": int(float(getattr(zone, "Multiplier", 1)))  # Default to 1 if not specified
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
            
        # Process people loads
        for people in idf.idfobjects['PEOPLE']:
            zone_name = people.Zone_or_ZoneList_Name
            if zone_name in self.loads_by_zone:
                # Match the field names from the IDF file
                people_data = {
                    "name": str(people.Name),
                    "calculation_method": str(people.Number_of_People_Calculation_Method),
                    "value": float(getattr(people, "People_per_Zone_Floor_Area", 0.0)),
                    "schedule": str(getattr(people, "Number_of_People_Schedule_Name", "")),
                    "activity_schedule": str(getattr(people, "Activity_Level_Schedule_Name", ""))
                }
                self.loads_by_zone[zone_name]["loads"]["people"].append(people_data)
                
        # Process lighting loads
        for lights in idf.idfobjects['LIGHTS']:
            zone_name = str(lights.Zone_or_ZoneList_Name)
            if zone_name in self.loads_by_zone:
                # Following IDF field names from example
                lights_data = {
                    "name": str(lights.Name),
                    "calculation_method": str(getattr(lights, "Design_Level_Calculation_Method", "")),
                    "watts_per_area": float(getattr(lights, "Watts_per_Area", 5.0)),  # Default to 5 W/m2
                    "schedule": str(getattr(lights, "Schedule_Name", ""))
                }
                self.loads_by_zone[zone_name]["loads"]["lights"].append(lights_data)
                
        # Process other equipment loads
        for equip in idf.idfobjects['OTHEREQUIPMENT']:
            zone_name = str(equip.Zone_or_ZoneList_Name)
            if zone_name in self.loads_by_zone:
                # Set default watts based on equipment type
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
                
        # Process infiltration loads
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

    def get_parsed_zone_loads(self):
        """
        Returns the dictionary of parsed zone loads.
        
        Returns:
            dict: Dictionary of zone loads and their associated schedules
        """
        return self.loads_by_zone

    def _process_zone_data(self, data):
        """Process Zone object data."""
        if not data or len(data) < 10:  # Need at least basic zone fields
            return

        try:
            zone_name = data[0]
            # Initialize zone data structure
            self.loads_by_zone[zone_name] = {
                "properties": {
                    "area": float(data[8]) if data[8] else 0.0,
                    "volume": float(data[7]) if data[7] else 0.0,
                    "ceiling_height": None,  # Let EnergyPlus calculate
                    "multiplier": int(float(data[5])) if data[5] else 1
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
        except (IndexError, ValueError) as e:
            print(f"Warning: Could not process zone data for {data[0] if data else 'unknown'}: {e}")

    def _process_people_load(self, data, zone_id):
        """Process People object data."""
        try:
            people_data = {
                "name": data[0],
                "calculation_method": data[3],
                "value": float(data[4]) if data[4] else float(data[5]) if data[5] else 0.0,
                "schedule": data[2],  # Number of People schedule
                "activity_schedule": data[8]  # Activity level schedule
            }
            self.loads_by_zone[zone_id]["loads"]["people"].append(people_data)
        except (IndexError, ValueError) as e:
            print(f"Warning: Could not process people load for zone {zone_id}: {e}")

    def _process_lights_load(self, data, zone_id):
        """Process Lights object data."""
        try:
            lights_data = {
                "name": data[0],
                "calculation_method": data[3],
                "watts_per_area": float(data[4]) if data[4] else 0.0,
                "schedule": data[2]
            }
            self.loads_by_zone[zone_id]["loads"]["lights"].append(lights_data)
        except (IndexError, ValueError) as e:
            print(f"Warning: Could not process lights load for zone {zone_id}: {e}")

    def _process_equipment_load(self, data, zone_id):
        """Process OtherEquipment object data."""
        try:
            equipment_data = {
                "name": data[0],
                "fuel_type": data[1],
                "calculation_method": data[4],
                "watts_per_area": float(data[5]) if data[5] else 0.0,
                "schedule": data[3]
            }
            self.loads_by_zone[zone_id]["loads"]["equipment"].append(equipment_data)
        except (IndexError, ValueError) as e:
            print(f"Warning: Could not process equipment load for zone {zone_id}: {e}")

    def _process_infiltration_load(self, data, zone_id):
        """Process ZoneInfiltration object data."""
        try:
            infiltration_data = {
                "name": data[0],
                "calculation_method": data[3],
                "flow_rate": float(data[4]) if data[4] else 0.0,
                "schedule": data[2]
            }
            self.loads_by_zone[zone_id]["loads"]["infiltration"].append(infiltration_data)
        except (IndexError, ValueError) as e:
            print(f"Warning: Could not process infiltration load for zone {zone_id}: {e}")

    def _process_schedule(self, data, zone_id):
        """Process Schedule:Compact object data."""
        if not data or len(data) < 2:
            return
            
        schedule_name = data[0].lower()
        zone_name = zone_id.lower()
        
        # Only process schedules that belong to this zone
        if not schedule_name.startswith(zone_name):
            return
            
        # Identify schedule type from name
        if "heating" in schedule_name:
            self.loads_by_zone[zone_id]["schedules"]["heating"] = data[0]
        elif "cooling" in schedule_name:
            self.loads_by_zone[zone_id]["schedules"]["cooling"] = data[0]
        elif "lighting" in schedule_name:
            self.loads_by_zone[zone_id]["schedules"]["lighting"] = data[0]
        elif "equipment" in schedule_name:
            self.loads_by_zone[zone_id]["schedules"]["equipment"] = data[0]
        elif "occupancy" in schedule_name:
            self.loads_by_zone[zone_id]["schedules"]["occupancy"] = data[0]

    def process_eppy_zone(self, zone_obj):
        """
        Process a Zone object from eppy directly.
        
        Args:
            zone_obj: An eppy Zone object
        """
        data = [field for field in zone_obj.fieldvalues]
        self._process_zone_data(data)

    def process_eppy_equipment(self, equip_obj):
        """
        Process an equipment object from eppy directly.
        
        Args:
            equip_obj: An eppy object (People, Lights, OtherEquipment, etc.)
        """
        data = [field for field in equip_obj.fieldvalues]
        zone_name = None
        
        # Get zone name from equipment object
        if hasattr(equip_obj, 'Zone_or_ZoneList_Name'):
            zone_name = equip_obj.Zone_or_ZoneList_Name
        
        if zone_name:
            self.process_element('object', equip_obj.key, data, zone_name)

    def get_parsed_zone_loads(self):
        """
        Returns the dictionary of parsed zone loads.
        
        Returns:
            dict: Dictionary of zone loads and their associated schedules
        """
        return self.loads_by_zone