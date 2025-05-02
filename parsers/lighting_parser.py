"""
Parser for Daylighting:Controls and Daylighting:ReferencePoint objects.
"""
from typing import Dict, List, Any
from utils.data_loader import DataLoader, safe_float

class LightingParser:
    """Parses Daylighting IDF objects."""

    def __init__(self, data_loader: DataLoader):
        """
        Initializes the LightingParser.

        Args:
            data_loader: An instance of DataLoader containing cached IDF data.
        """
        self._data_loader = data_loader
        self._controls_data = []
        self._reference_point_data = []

    def parse(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Parses the Daylighting:Controls and Daylighting:ReferencePoint data.

        Returns:
            A dictionary containing two lists: 'controls' and 'reference_points'.
        """
        controls_raw = self._data_loader.get_daylighting_controls()
        ref_points_raw = self._data_loader.get_daylighting_reference_points()

        # --- Parse Daylighting:Controls ---
        self._controls_data = []
        for control_id, control_cache in controls_raw.items():
            control = control_cache['raw_object']
            zone_name = str(getattr(control, "Zone_Name", ""))
            lighting_control_type = str(getattr(control, "Lighting_Control_Type", ""))
            availability_schedule = str(getattr(control, "Availability_Schedule_Name", ""))
            num_stepped_steps = int(safe_float(getattr(control, "Number_of_Stepped_Control_Steps", 0)))
            min_power_frac = None
            min_output_frac = None

            if lighting_control_type in ["Continuous", "ContinuousOff"]:
                min_power_frac = safe_float(getattr(control, "Minimum_Input_Power_Fraction_for_Continuous_or_ContinuousOff_Dimming_Control", 0.0))
                min_output_frac = safe_float(getattr(control, "Minimum_Light_Output_Fraction_for_Continuous_or_ContinuousOff_Dimming_Control", 0.0))

            # Iterate through potential reference points (EnergyPlus allows many)
            # We'll check fields dynamically up to a reasonable limit (e.g., 10)
            for i in range(1, 11): # Check for up to 10 reference points
                ref_point_field_name = f"Daylighting_Reference_Point_{i}_Name"
                fraction_field_name = f"Fraction_of_Zone_Controlled_by_Reference_Point_{i}"
                setpoint_field_name = f"Illuminance_Setpoint_at_Reference_Point_{i}"

                # Check if the reference point name field exists and has a value
                ref_point_name = str(getattr(control, ref_point_field_name, ""))
                if not ref_point_name:
                    # If the first ref point name is empty, stop checking for this control
                    if i == 1:
                        break
                    # Otherwise, if a later ref point name is empty, assume no more points
                    continue

                fraction = safe_float(getattr(control, fraction_field_name, 0.0))
                setpoint = safe_float(getattr(control, setpoint_field_name, 0.0))

                # Only add entry if the reference point is named and fraction > 0 (or maybe just if named?)
                # Let's add if named, fraction can be 0.
                # if ref_point_name and fraction > 0:
                if ref_point_name:
                    control_entry = {
                        "Zone": zone_name,
                        "Availability Schedule Name": availability_schedule,
                        "Lighting Control Type": lighting_control_type,
                        "Number of Stepped Control Steps": num_stepped_steps,
                        "Daylighting Reference": ref_point_name,
                        "Fraction of Zone Controlled": fraction,
                        "Illuminance Setpoint": setpoint,
                        # Add conditional fields if applicable for this control type
                        "Minimum Input Power Fraction": min_power_frac,
                        "Minimum Light Output Fraction": min_output_frac,
                    }
                    self._controls_data.append(control_entry)


        # --- Parse Daylighting:ReferencePoint ---
        # This part needs adjustment to correctly link back to the control and get the *correct* fraction/setpoint
        self._reference_point_data = []
        for ref_point_id, ref_point_cache in ref_points_raw.items():
            ref_point = ref_point_cache['raw_object']
            zone_name = str(getattr(ref_point, "Zone_Name", ""))

            # Find the Daylighting:Controls object(s) that use this reference point
            # A reference point might theoretically be used by multiple controls,
            # or multiple times within one control (though less likely).
            # We'll create an entry for each time it's referenced in a control.
            found_in_control = False
            for control_cache in controls_raw.values():
                control_obj = control_cache['raw_object']
                control_type_for_ref = str(getattr(control_obj, "Lighting_Control_Type", ""))
                min_power_frac_ref = None
                min_output_frac_ref = None
                if control_type_for_ref in ["Continuous", "ContinuousOff"]:
                    min_power_frac_ref = safe_float(getattr(control_obj, "Minimum_Input_Power_Fraction_for_Continuous_or_ContinuousOff_Dimming_Control", 0.0))
                    min_output_frac_ref = safe_float(getattr(control_obj, "Minimum_Light_Output_Fraction_for_Continuous_or_ContinuousOff_Dimming_Control", 0.0))

                # Iterate through potential reference points in the control object
                for i in range(1, 11): # Check up to 10 points
                    ref_point_field_name = f"Daylighting_Reference_Point_{i}_Name"
                    fraction_field_name = f"Fraction_of_Zone_Controlled_by_Reference_Point_{i}"
                    setpoint_field_name = f"Illuminance_Setpoint_at_Reference_Point_{i}"

                    control_ref_point_name = str(getattr(control_obj, ref_point_field_name, ""))

                    # If this control uses the current reference point at this index (i)
                    if control_ref_point_name == ref_point_id:
                        found_in_control = True
                        fraction = safe_float(getattr(control_obj, fraction_field_name, 0.0))
                        setpoint = safe_float(getattr(control_obj, setpoint_field_name, 0.0))

                        ref_point_entry = {
                            "Zone": zone_name, # Zone from the RefPoint object
                            "X-Coordinate": safe_float(getattr(ref_point, "XCoordinate_of_Reference_Point", 0.0)),
                            "Y-Coordinate": safe_float(getattr(ref_point, "YCoordinate_of_Reference_Point", 0.0)),
                            "Z-Coordinate": safe_float(getattr(ref_point, "ZCoordinate_of_Reference_Point", 0.0)),
                            "Daylighting Reference": ref_point_id, # The reference point name
                            # Get fraction and setpoint specific to this index (i) from the control
                            "Fraction of Zone Controlled": fraction,
                            "Illuminance Setpoint": setpoint,
                            # Add conditional fields based on the control type
                            "Minimum Input Power Fraction": min_power_frac_ref,
                            "Minimum Light Output Fraction": min_output_frac_ref,
                        }
                        self._reference_point_data.append(ref_point_entry)
                        # Don't break here, a ref point could potentially be listed multiple times in one control

            # If a reference point exists but isn't linked by any control, maybe still list it?
            # Current logic only adds if found in a control. Let's keep it this way for now.
            # if not found_in_control:
            #     # Optionally add an entry with placeholders if needed
            #     pass


        return {
            "controls": self._controls_data,
            "reference_points": self._reference_point_data
        }