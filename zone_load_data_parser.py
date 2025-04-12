import re
from idf_parser import strip_inline_comment

class ZoneLoadDataExtractor:
    """
    Extracts key load data parameters for each zone from relevant IDF objects.
    """
    def __init__(self):
        # Main data structure: {zone_id: {param_key: value}}
        self.zone_data = {}
        # Temporary storage for setpoint schedules keyed by ThermostatSetpoint object name
        self.setpoint_schedules_by_thermostat_name = {}

    def _initialize_zone_data(self, zone_id):
        """Initializes the data dictionary for a new zone."""
        if zone_id not in self.zone_data:
            self.zone_data[zone_id] = {
                # Zone Info
                'zone_floor_area': None,
                'zone_volume': None,
                # Occupancy
                'occupancy_people_per_area': None,
                'occupancy_activity_schedule': None,
                'occupancy_schedule': None,
                'occupancy_clothing_schedule': None, # Added based on example
                'occupancy_air_velocity_schedule': None, # Added based on example
                # Lighting
                'lighting_watts_per_area': None,
                'lighting_schedule': None,
                # Non-Fixed Equipment (Guessing based on name/schedule)
                'non_fixed_equip_watts_per_area': None,
                'non_fixed_equip_schedule': None,
                # Fixed Equipment (Guessing based on name/schedule)
                'fixed_equip_watts_per_area': None,
                'fixed_equip_schedule': None,
                # Thermostat & Setpoints (Linked later)
                'thermostat_setpoint_object_name': None,
                'heating_setpoint_schedule': None, # Linked via thermostat_setpoint_object_name
                'cooling_setpoint_schedule': None, # Linked via thermostat_setpoint_object_name
                # Availability Schedules (Assumed naming convention for now)
                'heating_availability_schedule': f"{zone_id} Heating Availability Sch", # Assumption
                'cooling_availability_schedule': f"{zone_id} Cooling Availability Sch", # Assumption
                # Infiltration
                'infiltration_ach': None, # Calculated
                'infiltration_schedule': None,
                # Ventilation
                'ventilation_ach': None, # Calculated
                'ventilation_schedule': None,
                # Raw data for calculation
                '_infiltration_flow_rate': None,
                '_infiltration_flow_per_area': None,
                '_infiltration_flow_per_ext_area': None,
                '_infiltration_ach_rate': None,
                '_ventilation_flow_rate': None,
                '_ventilation_flow_per_area': None,
                '_ventilation_flow_per_person': None,
                '_ventilation_ach_rate': None,
            }

    def _calculate_ach(self, zone_id):
        """Calculates ACH for infiltration and ventilation if possible."""
        if zone_id not in self.zone_data:
            return

        zone_info = self.zone_data[zone_id]
        volume = zone_info.get('zone_volume')
        if volume is None or volume <= 0:
            return # Cannot calculate without volume

        # Infiltration ACH
        total_infiltration_m3_per_s = 0
        if zone_info.get('_infiltration_flow_rate') is not None:
            total_infiltration_m3_per_s += zone_info['_infiltration_flow_rate']
        # Add other terms if needed (flow/area, flow/ext area) - requires area data
        if zone_info.get('_infiltration_ach_rate') is not None:
             # If ACH is directly specified, use it (convert from hr^-1 to s^-1 for consistency?)
             # For now, let's assume the direct ACH value is what we report
             zone_info['infiltration_ach'] = zone_info['_infiltration_ach_rate'] # Store directly
        elif total_infiltration_m3_per_s > 0:
             zone_info['infiltration_ach'] = (total_infiltration_m3_per_s * 3600) / volume

        # Ventilation ACH
        total_ventilation_m3_per_s = 0
        if zone_info.get('_ventilation_flow_rate') is not None:
            total_ventilation_m3_per_s += zone_info['_ventilation_flow_rate']
        # Add other terms if needed (flow/area, flow/person) - requires area/people data
        if zone_info.get('_ventilation_ach_rate') is not None:
             zone_info['ventilation_ach'] = zone_info['_ventilation_ach_rate'] # Store directly
        elif total_ventilation_m3_per_s > 0:
             zone_info['ventilation_ach'] = (total_ventilation_m3_per_s * 3600) / volume


    def process_element(self, element_type, identifier, data, current_zone_id):
        """Processes elements, extracting relevant load data from cleaned fields."""

        # --- Helper to safely get field and convert to float ---
        def get_float_field(field_list, index):
            if index < len(field_list):
                val_str = field_list[index]
                if val_str: # Check if not empty string
                    try:
                        return float(val_str)
                    except ValueError:
                        # print(f"Warning: Could not convert field '{val_str}' at index {index} to float for {identifier}")
                        return None
            return None

        # --- Helper to safely get field as string ---
        def get_string_field(field_list, index):
             if index < len(field_list):
                  return field_list[index] # Already cleaned string
             return None

        # --- Main Processing Logic ---
        # Handle ThermostatSetpoint:DualSetpoint even if not in zone context
        if element_type == 'object' and identifier == 'ThermostatSetpoint:DualSetpoint':
             # Data is list of cleaned fields
             if data:
                  thermostat_name = get_string_field(data, 0) # Name is first field
                  if thermostat_name:
                       heating_sched = get_string_field(data, 1)
                       cooling_sched = get_string_field(data, 2)
                       self.setpoint_schedules_by_thermostat_name[thermostat_name] = {
                           'heating': heating_sched,
                           'cooling': cooling_sched
                       }
                       # print(f"  DEBUG ZoneLoad: Stored Setpoint Links for Thermostat '{thermostat_name}': H={heating_sched}, C={cooling_sched}")
             return # Don't process further if it's this object type

        # Process other objects only if they are within a zone context
        if element_type != 'object' or current_zone_id is None or not isinstance(data, list):
            return

        self._initialize_zone_data(current_zone_id)
        zone_info = self.zone_data[current_zone_id]

        try:
            # --- Zone Object ---
            if identifier == 'Zone':
                # Indices: Floor Area(A7=6), Volume(A8=7) (0-based index from cleaned_fields list)
                zone_info['zone_floor_area'] = get_float_field(data, 6)
                zone_info['zone_volume'] = get_float_field(data, 7)
                # print(f"  DEBUG ZoneLoad: Zone {current_zone_id} - Floor Area={zone_info['zone_floor_area']}, Volume={zone_info['zone_volume']}")

            # --- People Object ---
            elif identifier == 'People':
                # Indices: Schedule(A3=2), People/Area(A6=5), Activity Sched(A9=8), Clothing Sched(A15=14), Air Velocity Sched(A16=15)
                zone_info['occupancy_schedule'] = get_string_field(data, 2)
                zone_info['occupancy_people_per_area'] = get_float_field(data, 5)
                zone_info['occupancy_activity_schedule'] = get_string_field(data, 8)
                zone_info['occupancy_clothing_schedule'] = get_string_field(data, 14)
                zone_info['occupancy_air_velocity_schedule'] = get_string_field(data, 15)
                # print(f"  DEBUG ZoneLoad: Zone {current_zone_id} - People Data Extracted")

            # --- Lights Object ---
            elif identifier == 'Lights':
                # Indices: Schedule(A3=2), Watts/Area(A6=5)
                zone_info['lighting_schedule'] = get_string_field(data, 2)
                zone_info['lighting_watts_per_area'] = get_float_field(data, 5)
                # print(f"  DEBUG ZoneLoad: Zone {current_zone_id} - Lights Data Extracted")

            # --- OtherEquipment Object ---
            elif identifier == 'OtherEquipment':
                # Indices: Name(A1=0), Schedule(A4=3), Watts/Area(A7=6)
                equip_name = get_string_field(data, 0).lower() if get_string_field(data, 0) else ""
                schedule_name = get_string_field(data, 3)
                watts_per_area = get_float_field(data, 6)

                if "non fixed" in equip_name or "miscellaneous" in equip_name or (schedule_name and "non fixed" in schedule_name.lower()):
                    if watts_per_area is not None: zone_info['non_fixed_equip_watts_per_area'] = watts_per_area
                    if schedule_name: zone_info['non_fixed_equip_schedule'] = schedule_name
                    # print(f"  DEBUG ZoneLoad: Zone {current_zone_id} - Non-Fixed Equip W/Area = {watts_per_area}, Schedule = {schedule_name}")
                else: # Assume fixed
                    if watts_per_area is not None: zone_info['fixed_equip_watts_per_area'] = watts_per_area
                    if schedule_name: zone_info['fixed_equip_schedule'] = schedule_name
                    # print(f"  DEBUG ZoneLoad: Zone {current_zone_id} - Fixed Equip W/Area = {watts_per_area}, Schedule = {schedule_name}")

            # --- ZoneControl:Thermostat Object ---
            elif identifier == 'ZoneControl:Thermostat':
                 # Index: ThermostatSetpoint Object Name (A4=3)
                 thermostat_name_field = get_string_field(data, 3)
                 if thermostat_name_field:
                      # Extract the actual name part if it's like "Type, Name"
                      if ',' in thermostat_name_field:
                           thermostat_name = thermostat_name_field.split(',',1)[1].strip()
                      else: # Assume the whole field is the name
                           thermostat_name = thermostat_name_field
                      zone_info['thermostat_setpoint_object_name'] = thermostat_name
                      # print(f"  DEBUG ZoneLoad: Zone {current_zone_id} - Thermostat Object Name = {thermostat_name}")

            # --- ZoneInfiltration:DesignFlowRate Object ---
            elif identifier == 'ZoneInfiltration:DesignFlowRate':
                 # Indices: Schedule(A3=2), Flow Rate(A4=3), Flow/Area(A5=4), Flow/ExtArea(A6=5), ACH(A7=6)
                 zone_info['infiltration_schedule'] = get_string_field(data, 2)
                 zone_info['_infiltration_flow_rate'] = get_float_field(data, 3)
                 zone_info['_infiltration_flow_per_area'] = get_float_field(data, 4)
                 zone_info['_infiltration_flow_per_ext_area'] = get_float_field(data, 5)
                 zone_info['_infiltration_ach_rate'] = get_float_field(data, 6)
                 # print(f"  DEBUG ZoneLoad: Zone {current_zone_id} - Infiltration Data Extracted")

            # --- ZoneVentilation:DesignFlowRate Object ---
            elif identifier == 'ZoneVentilation:DesignFlowRate':
                 # Indices: Schedule(A3=2), Flow Rate(A4=3), Flow/Area(A5=4), Flow/Person(A6=5), ACH(A7=6)
                 zone_info['ventilation_schedule'] = get_string_field(data, 2)
                 zone_info['_ventilation_flow_rate'] = get_float_field(data, 3)
                 zone_info['_ventilation_flow_per_area'] = get_float_field(data, 4)
                 zone_info['_ventilation_flow_per_person'] = get_float_field(data, 5)
                 zone_info['_ventilation_ach_rate'] = get_float_field(data, 6)
                 # print(f"  DEBUG ZoneLoad: Zone {current_zone_id} - Ventilation Data Extracted")

        except (IndexError, TypeError) as e: # Removed ValueError as get_float_field handles it
            print(f"Warning: Error processing object '{identifier}' for zone '{current_zone_id}': {e}. Cleaned Fields: {data}")

    def get_zone_load_data(self):
        """Returns the dictionary of extracted zone load data."""
        # Calculate ACH values before returning
        #print("\nDEBUG ZoneLoad: Calculating final ACH values...") # Debug
        for zone_id in self.zone_data:
            self._calculate_ach(zone_id)
        #print("\nDEBUG ZoneLoad: Final zone_data before return:") # Debug
        #import pprint; pprint.pprint(self.zone_data) # Debug
        return self.zone_data

    def get_setpoint_schedule_links(self):
        """Returns the temporarily stored setpoint schedule names."""
        #print("\nDEBUG ZoneLoad: Final setpoint_schedules_by_thermostat_name before return:") # Debug
        #import pprint; pprint.pprint(self.setpoint_schedules_by_thermostat_name) # Debug
        return self.setpoint_schedules_by_thermostat_name

# Example usage placeholder
if __name__ == '__main__':
    print("zone_load_data_parser.py executed directly (intended for import).")