"""
Parser for Daylighting:Controls and Daylighting:ReferencePoint objects.
"""
from typing import Dict, List, Any
from utils.data_loader import DataLoader, safe_float

class LightingParser:
    """
    Parses Daylighting:Controls, Daylighting:ReferencePoint, Exterior:Lights, and Lights (for task lighting) data.
    """

    def __init__(self, data_loader: DataLoader):
        """
        Initializes the LightingParser.

        Args:
            data_loader: An instance of DataLoader containing cached IDF data.
        """
        self._data_loader = data_loader
        self._controls_data = []
        self._reference_point_data = []
        self._exterior_lights_data = []
        self._task_lights_data = []

    def parse(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Parses Daylighting:Controls, Daylighting:ReferencePoint, Exterior:Lights, and Lights (for task lighting) data.

        Returns:
            A dictionary containing lists for: 'controls', 'reference_points',
            'exterior_lights', and 'task_lights'.
        """
        controls_raw = self._data_loader.get_daylighting_controls()
        ref_points_raw = self._data_loader.get_daylighting_reference_points()
        exterior_lights_raw = self._data_loader.get_exterior_lights_loads()
        lights_raw = self._data_loader.get_lights_loads()

        self._controls_data = self._parse_controls(controls_raw)
        self._reference_point_data = self._parse_reference_points(ref_points_raw, controls_raw)
        self._exterior_lights_data = self._parse_exterior_lights(exterior_lights_raw)
        self._task_lights_data = self._parse_task_lights(lights_raw)

        return {
            "controls": self._controls_data,
            "reference_points": self._reference_point_data,
            "exterior_lights": self._exterior_lights_data,
            "task_lights": self._task_lights_data
        }

    def _parse_controls(self, controls_raw) -> List[Dict[str, Any]]:
        """
        Parses the raw data for Daylighting:Controls objects.

        Args:
            controls_raw: The raw controls data from the DataLoader.

        Returns:
            A list of dictionaries, each representing a parsed Daylighting:Controls object.
        """
        controls = []
        for control_cache in controls_raw.values():
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

            for i in range(1, 11): # Check for up to 10 reference points
                ref_point_field_name = f"Daylighting_Reference_Point_{i}_Name"
                fraction_field_name = f"Fraction_of_Zone_Controlled_by_Reference_Point_{i}"
                setpoint_field_name = f"Illuminance_Setpoint_at_Reference_Point_{i}"

                ref_point_name = str(getattr(control, ref_point_field_name, ""))
                if not ref_point_name:
                    # If the first ref point name is empty, stop checking for this control
                    if i == 1:
                        break
                    # Otherwise, if a later ref point name is empty, assume no more points
                    continue

                fraction = safe_float(getattr(control, fraction_field_name, 0.0))
                setpoint = safe_float(getattr(control, setpoint_field_name, 0.0))

                controls.append({
                    "Zone": zone_name,
                    "Availability Schedule Name": availability_schedule,
                    "Lighting Control Type": lighting_control_type,
                    "Number of Stepped Control Steps": num_stepped_steps,
                    "Daylighting Reference": ref_point_name,
                    "Fraction of Zone Controlled": fraction,
                    "Illuminance Setpoint": setpoint,
                    "Minimum Input Power Fraction": min_power_frac,
                    "Minimum Light Output Fraction": min_output_frac,
                })

        return controls

    def _parse_reference_points(self, ref_points_raw, controls_raw) -> List[Dict[str, Any]]:
        """
        Parses the raw data for Daylighting:ReferencePoint objects.

        Args:
            ref_points_raw: The raw reference points data from the DataLoader.
            controls_raw: The raw controls data from the DataLoader.

        Returns:
            A list of dictionaries, each representing a parsed Daylighting:ReferencePoint object.
        """
        reference_points = []
        for ref_point_id, ref_point_cache in ref_points_raw.items():
            ref_point = ref_point_cache['raw_object']
            zone_name = str(getattr(ref_point, "Zone_Name", ""))

            for control_cache in controls_raw.values():
                control_obj = control_cache['raw_object']
                control_type_for_ref = str(getattr(control_obj, "Lighting_Control_Type", ""))
                min_power_frac_ref = None
                min_output_frac_ref = None
                if control_type_for_ref in ["Continuous", "ContinuousOff"]:
                    min_power_frac_ref = safe_float(getattr(control_obj, "Minimum_Input_Power_Fraction_for_Continuous_or_ContinuousOff_Dimming_Control", 0.0))
                    min_output_frac_ref = safe_float(getattr(control_obj, "Minimum_Light_Output_Fraction_for_Continuous_or_ContinuousOff_Dimming_Control", 0.0))

                for i in range(1, 11): # Check up to 10 points
                    ref_point_field_name = f"Daylighting_Reference_Point_{i}_Name"
                    fraction_field_name = f"Fraction_of_Zone_Controlled_by_Reference_Point_{i}"
                    setpoint_field_name = f"Illuminance_Setpoint_at_Reference_Point_{i}"

                    control_ref_point_name = str(getattr(control_obj, ref_point_field_name, ""))

                    # If this control uses the current reference point at this index (i)
                    if control_ref_point_name == ref_point_id:
                        fraction = safe_float(getattr(control_obj, fraction_field_name, 0.0))
                        setpoint = safe_float(getattr(control_obj, setpoint_field_name, 0.0))

                        reference_points.append({
                            "Zone": zone_name, # Zone from the RefPoint object
                            "X-Coordinate": safe_float(getattr(ref_point, "XCoordinate_of_Reference_Point", 0.0)),
                            "Y-Coordinate": safe_float(getattr(ref_point, "YCoordinate_of_Reference_Point", 0.0)),
                            "Z-Coordinate": safe_float(getattr(ref_point, "ZCoordinate_of_Reference_Point", 0.0)),
                            "Daylighting Reference": ref_point_id, # The reference point name
                            "Fraction of Zone Controlled": fraction,
                            "Illuminance Setpoint": setpoint,
                            "Minimum Input Power Fraction": min_power_frac_ref,
                            "Minimum Light Output Fraction": min_output_frac_ref,
                        })

        return reference_points

    def _parse_exterior_lights(self, exterior_lights_raw) -> List[Dict[str, Any]]:
        """
        Parses the raw data for Exterior:Lights objects.

        Args:
            exterior_lights_raw: The raw exterior lights data from the DataLoader.

        Returns:
            A list of dictionaries, each representing a parsed Exterior:Lights object.
        """
        return [{
            "Name": ext_light.get("name", "-"),
            "Lighting SCHEDULE Name": ext_light.get("schedule_name", "-"),
            "Design Equipment Level (W)": ext_light.get("design_level", 0.0)
        } for ext_light in exterior_lights_raw]

    def _parse_task_lights(self, lights_raw) -> List[Dict[str, Any]]:
        """
        Parses the raw data for task lighting from Lights objects.

        Args:
            lights_raw: The raw lights data from the DataLoader.

        Returns:
            A list of dictionaries, each representing a parsed task lighting entry.
        """
        task_lights = []
        for zone_name, light_list in lights_raw.items():
            for light_data in light_list:
                if "task" in light_data.get("name", "").lower():
                    task_lights.append({
                        "Zone Name": light_data.get("zone_name", "-"),
                        "Lighting SCHEDULE Name": light_data.get("schedule", "-")
                    })
        return task_lights