"""
Extracts and processes energy consumption and rating information from EnergyPlus output files.
"""
from typing import Dict, Any, List, Optional
import re
import csv
import os
from venv import logger
from parsers.area_parser import AreaParser
from utils.data_loader import safe_float

class EnergyRatingParser:
    """
    Processes energy consumption data from EnergyPlus output files (eplusout.csv).
    Uses area data from AreaParser for energy per area calculations.
    """
    def __init__(self, data_loader, area_parser: AreaParser):
        try:
            if data_loader is None:
                raise ValueError("DataLoader instance cannot be None.")
            if area_parser is None:
                raise ValueError("AreaParser instance cannot be None.")

            self.data_loader = data_loader
            self.area_parser = area_parser
            self.energy_data_by_area: Dict[str, Dict[str, Any]] = {}
            self.processed = False
            # Regex to capture: Floor, Area ID, Zone Name, Optional Equipment Type, Metric, Unit, Period
            self.zone_pattern = re.compile(
                r'(\d{2}):(\d{2})X([A-Za-z0-9_]+)'  # Floor:AreaIDXZoneName
                r'(?:\s+([A-Za-z0-9_ ]+))?:'         # Optional Equipment Type then :
                r'([A-Za-z0-9_ ]+(?:\s+[A-Za-z0-9_ ]+)*)\s+' # Metric (can have spaces)
                r'\[([A-Za-z0-9/]+)\]'              # [Unit]
                r'\(([A-Za-z0-9]+)\)'               # (Period)
            )
            logger.info("EnergyRatingParser initialized successfully.")
        except ValueError as ve:
            logger.error(f"Initialization error in EnergyRatingParser: {ve}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Unexpected error during EnergyRatingParser initialization: {e}", exc_info=True)
            # Ensure a consistent state even if regex compilation fails, though unlikely with a fixed pattern
            self.energy_data_by_area = {}
            self.processed = False
            self.zone_pattern = None # Indicate pattern compilation failure
            raise # Re-raise to signal a critical initialization failure

    def process_output(self, output_file_path: Optional[str] = None) -> None:
        """
        Process EnergyPlus output file (eplusout.csv) to extract energy consumption data.
        """
        if self.processed:
            logger.info("Energy data already processed. Skipping.")
            return
        if not self.zone_pattern: # Check if regex compiled successfully during init
            logger.error("Zone pattern regex not compiled. Cannot process output.")
            self.processed = False # Ensure not marked as processed
            return # Or raise an error

        final_output_file_path = None
        try:
            if not output_file_path:
                idf_path = self.data_loader.get_idf_path()
                if idf_path:
                    idf_dir = os.path.dirname(idf_path)
                    possible_paths_relative_to_idf_dir = [
                        "eplusout.csv",
                        os.path.join("..", "tests", "eplusout.csv")
                    ]
                    script_dir_fallback = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "simulation_output", "eplusout.csv")
                    
                    candidate_paths = [os.path.join(idf_dir, p) for p in possible_paths_relative_to_idf_dir]
                    candidate_paths.append(script_dir_fallback)

                    for path_candidate in candidate_paths:
                        normalized_path = os.path.normpath(path_candidate)
                        if os.path.basename(normalized_path).lower() == "eplusout.csv" and os.path.exists(normalized_path):
                            final_output_file_path = normalized_path
                            logger.info(f"Found eplusout.csv at: {final_output_file_path}")
                            break
                    if not final_output_file_path:
                        logger.warning("Could not automatically find eplusout.csv based on IDF path or fallback locations.")
                else:
                    logger.warning("IDF path not available from DataLoader, cannot automatically find eplusout.csv.")
            else: # output_file_path was provided
                final_output_file_path = output_file_path

            # If eplustbl.csv was given, try to switch to eplusout.csv in the same dir
            if final_output_file_path and os.path.basename(final_output_file_path).lower() == "eplustbl.csv":
                logger.info(f"Received eplustbl.csv path: {final_output_file_path}. Attempting to use eplusout.csv from the same directory.")
                candidate_out = os.path.join(os.path.dirname(final_output_file_path), "eplusout.csv")
                if os.path.exists(candidate_out):
                    final_output_file_path = candidate_out
                    logger.info(f"Switched to eplusout.csv: {final_output_file_path}")
                else:
                    logger.warning(f"eplustbl.csv provided, but eplusout.csv not found in the same directory ({os.path.dirname(final_output_file_path)}).")
            
            if not final_output_file_path or not os.path.exists(final_output_file_path):
                logger.error(f"EnergyPlus output file (eplusout.csv) not found. Tried path: {final_output_file_path if final_output_file_path else 'auto-detection failed'}.")
                # Not raising FileNotFoundError here to allow GUI to handle it, but logging error.
                self.processed = False # Ensure not marked as processed
                return # Exit if file not found

            logger.info(f"Processing EnergyPlus output file: {final_output_file_path}")

            if not self.area_parser.processed:
                logger.info("Area parser data not yet processed. Processing now.")
                try:
                    self.area_parser.process_idf(None) # Assuming IDF object isn't strictly needed if data_loader is primary
                except Exception as ap_e:
                    logger.error(f"Error processing area data via AreaParser: {ap_e}. Energy processing may be incomplete.", exc_info=True)
                    # Decide if this is critical enough to stop, or proceed with potentially missing area data
                    # For now, proceed but log heavily.

            with open(final_output_file_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)
                headers = next(reader, None) # Read headers, default to None if empty
                if headers is None:
                    logger.error(f"CSV file '{final_output_file_path}' is empty or has no headers.")
                    self.processed = False
                    return

                last_row = None
                for row in reader: # Efficiently get the last row
                    last_row = row
                
                if not last_row:
                    logger.error(f"No data rows found in EnergyPlus output file '{final_output_file_path}'.")
                    self.processed = False
                    return

                self._process_headers_and_values(headers, last_row)
            self._calculate_totals()
            self.processed = True
            logger.info("Successfully processed EnergyPlus output file.")

        except FileNotFoundError: # Should be caught by the check above, but as a safeguard
            logger.error(f"EnergyPlus output file not found (should have been caught earlier): {final_output_file_path}", exc_info=True)
            self.processed = False
        except StopIteration: # If `next(reader)` fails on an empty file after header check (unlikely with current logic but safe)
            logger.error(f"CSV file '{final_output_file_path}' seems to be empty after headers.", exc_info=True)
            self.processed = False
        except csv.Error as csv_e:
            logger.error(f"CSV formatting error in '{final_output_file_path}': {csv_e}", exc_info=True)
            self.processed = False
        except ValueError as val_e: # Catch ValueErrors from _process_headers_and_values or other places
            logger.error(f"ValueError during processing of '{final_output_file_path}': {val_e}", exc_info=True)
            self.processed = False
        except RuntimeError as run_e: # Catch RuntimeErrors from _process_headers_and_values
            logger.error(f"RuntimeError during processing of '{final_output_file_path}': {run_e}", exc_info=True)
            self.processed = False
        except Exception as e: # Catch-all for any other unexpected error
            logger.error(f"Unexpected error processing EnergyPlus output file '{final_output_file_path}': {e}", exc_info=True)
            self.processed = False
        # Do not re-raise here to allow the application to continue if possible, errors are logged.

    def _process_headers_and_values(self, headers: List[str], values: List[str]) -> None:
        """
        Process headers to extract zone information and corresponding values.
        """
        self.energy_data_by_area = {} # Reset data
        if not headers or not values:
            logger.warning("Headers or values list is empty in _process_headers_and_values. Skipping.")
            return
        if not self.zone_pattern:
            logger.error("Zone pattern regex not compiled in _process_headers_and_values. Skipping.")
            return

        all_zones_data_from_loader = self.data_loader.get_zones() # Get all zones data once

        for i, header in enumerate(headers):
            try:
                if i == 0: # Skip first column (timestamp)
                    continue
                if "X" not in header: # Quick check for relevant headers
                    logger.debug(f"Skipping header (no 'X'): '{header}'")
                    continue

                match = self.zone_pattern.search(header)
                if not match:
                    logger.debug(f"Header '{header}' did not match zone pattern. Skipping.")
                    continue

                groups = match.groups()
                if len(groups) != 7:
                    logger.warning(f"Regex match for header '{header}' yielded unexpected number of groups ({len(groups)}). Expected 7. Groups: {groups}. Skipping.")
                    continue
                
                floor, area_id_from_header, zone_name_from_header, equipment_type, metric, unit, period = groups
                
                if period != "RunPeriod":
                    continue

                value_str = values[i] if i < len(values) else "0.0"
                value = safe_float(value_str, 0.0)
                processed_value = self._process_value(value, header.lower())

                if zone_name_from_header is None:
                    logger.warning(f"Zone name part is None for header '{header}' after regex match. Skipping this header.")
                    continue
                # Construct the full_zone_id key to match DataLoader keys (e.g., "00:01XLIVING")
                full_zone_id_key = f"{floor}:{area_id_from_header}X{zone_name_from_header}"

                if full_zone_id_key not in self.energy_data_by_area:
                    # Get multiplier and individual zone floor area directly from DataLoader
                    zone_multiplier = 1 # Default
                    individual_zone_floor_area = 0.0 # Default
                    
                    # Check if all_zones_data_from_loader is a valid dictionary before accessing
                    if isinstance(all_zones_data_from_loader, dict) and full_zone_id_key in all_zones_data_from_loader:
                        dl_zone_data = all_zones_data_from_loader[full_zone_id_key]
                        zone_multiplier = int(dl_zone_data.get('multiplier', 1))
                        individual_zone_floor_area = safe_float(dl_zone_data.get('floor_area', 0.0), 0.0)
                        logger.debug(f"EnergyRatingParser: For key '{full_zone_id_key}', DataLoader provided: multiplier={zone_multiplier}, floor_area={individual_zone_floor_area}.")
                    elif isinstance(all_zones_data_from_loader, dict): # It's a dict, but key is not in it
                        logger.warning(f"EnergyRatingParser: Key '{full_zone_id_key}' (from eplusout.csv) NOT FOUND in DataLoader's cached zones (which has {len(all_zones_data_from_loader)} items). Sample keys: {list(all_zones_data_from_loader.keys())[:20]}. Using defaults for multiplier/floor_area.")
                    else: # all_zones_data_from_loader was not a dict (e.g. None or empty after initial check)
                        logger.warning(f"EnergyRatingParser: DataLoader's cached zones is not a valid dictionary or is empty when trying to get key '{full_zone_id_key}'. Using defaults for multiplier/floor_area.")
                        # Defaults for zone_multiplier (1) and individual_zone_floor_area (0.0) are already set

                    # For location and total_area_of_legacy_grouping (these still use AreaParser for broader context)
                    # area_id_from_header is the '01' part, used for legacy grouping.
                    total_area_for_legacy_grouping = self._get_area_total_for_area_id(area_id_from_header)
                    location_for_grouping = self._determine_location(area_id_from_header)
                    
                    self.energy_data_by_area[full_zone_id_key] = {
                        'floor_id_report': floor,
                        'area_id_report': area_id_from_header,
                        'zone_name_report': zone_name_from_header,
                        'multiplier': zone_multiplier,
                        'individual_zone_floor_area': individual_zone_floor_area,
                        'lighting': 0.0, 'heating': 0.0, 'cooling': 0.0, 'total': 0.0, # Absolute energy
                        'location': location_for_grouping,
                        'total_area_of_legacy_grouping': total_area_for_legacy_grouping
                    }

                category = None
                header_lower = header.lower()
                if 'light' in header_lower: category = 'lighting'
                elif 'heating' in header_lower: category = 'heating'
                elif 'cooling' in header_lower: category = 'cooling'

                if category and category in self.energy_data_by_area[full_zone_id_key]:
                    self.energy_data_by_area[full_zone_id_key][category] += processed_value
                elif category:
                    logger.warning(f"Category '{category}' derived from header '{header}' not pre-defined in energy_data_by_area structure for key '{full_zone_id_key}'. Value not added.")

            except IndexError:
                logger.error(f"IndexError while processing header '{header}' at index {i}. Values list length: {len(values)}. Skipping.", exc_info=True)
                continue
            except (TypeError, ValueError) as e_val:
                logger.error(f"ValueError/TypeError processing header '{header}' or its value: {e_val}. Skipping.", exc_info=True)
                continue
            except Exception as e:
                logger.error(f"Unexpected error processing header '{header}': {e}. Skipping this header.", exc_info=True)
                continue


    def _process_value(self, value: float, header_lower: str) -> float:
        """
        Process value based on header type (energy unit conversion).
        J to kWh for lighting (3,600,000 J/kWh).
        J to MWh for heating/cooling (10,800,000 J / 3 = 3,600,000 J/kWh, then kWh to MWh by /1000, so J to MWh is /3.6e9, but original was /10.8e6 which is J to 1/3 kWh.
        Let's assume the original factors were for J to kWh, and then some other scaling.
        If original values are in Joules:
        Lighting: J to kWh -> value / 3,600,000
        Heating/Cooling: J to kWh -> value / 3,600,000. If the report needs MWh, then further /1000.
        The original code had 10.8e6 for heating/cooling. This is 3 * 3.6e6.
        This implies the heating/cooling values might be 3x the energy of lighting for the same "unit" reported by E+, or it's a different unit.
        Let's stick to J to kWh for now for all, assuming the report wants kWh.
        If the output is already in kWh, no conversion is needed.
        The headers usually specify units like J, GJ, kWh, MWh.
        For now, assuming input 'value' is in Joules as per typical E+ detailed CSV outputs.
        """
        try:
            # Standard conversion from Joules to kWh
            joules_to_kwh_factor = 3600000.0

            # It's safer to check the unit from the header if available, but the regex doesn't always capture it cleanly for this decision.
            # The original logic used different factors for light vs. heat/cool.
            # If 'light' in header_lower:
            #     return value / joules_to_kwh_factor
            # elif 'heating' in header_lower or 'cooling' in header_lower:
            #     # The original factor 10.8e6 is 3 * 3.6e6. This is unusual.
            #     # If the intent was to scale heating/cooling differently or they are reported in different base units
            #     # that needs clarification. For now, let's assume all are J and convert to kWh.
            #     return value / joules_to_kwh_factor
            # For now, using the original logic's distinct factors:
            processed_val = 0.0
            divisor_info = "None"
            if 'light' in header_lower:
                processed_val = value / 3600000.0  # J to kWh
                divisor_info = "3.6M (J to kWh)"
            elif 'heating' in header_lower or 'cooling' in header_lower:
                # This factor (10.8e6) is puzzling if input is Joules and output is kWh.
                processed_val = value / 10800000.0
                divisor_info = "10.8M"
            else:
                logger.warning(f"Header '{header_lower}' did not match known energy categories for unit conversion. Original value: {value} returned.")
                processed_val = value # Return original value if category not matched
            
            logger.info(f"EnergyRatingParser._process_value: Header='{header_lower}', Input={value:.2f}, Output={processed_val:.4f}, DivisorFactor='{divisor_info}'")
            return processed_val
        except TypeError: # If value is not a number
            logger.error(f"Cannot process non-numeric value '{value}' for header '{header_lower}'. Returning 0.0.", exc_info=True)
            return 0.0


    def _calculate_totals(self) -> None:
        """
        Calculate total energy consumption and per area values for each processed area.
        """
        if not self.energy_data_by_area:
            logger.info("No energy data processed by area. Skipping total calculations.")
            return
        
        for full_zone_id_key, data_for_zone in self.energy_data_by_area.items():
            try:
                # Ensure all required keys exist and are numbers before summing
                lighting = safe_float(data_for_zone.get('lighting', 0.0), 0.0)
                heating = safe_float(data_for_zone.get('heating', 0.0), 0.0)
                cooling = safe_float(data_for_zone.get('cooling', 0.0), 0.0)
                # total_area_of_grouping is used for per-area calculations
                total_area_group = safe_float(data_for_zone.get('total_area_of_grouping', 0.0), 0.0)

                data_for_zone['lighting'] = lighting # Update with safe_float version
                data_for_zone['heating'] = heating
                data_for_zone['cooling'] = cooling
                data_for_zone['total_area_of_legacy_grouping'] = total_area_group # Update with safe_float

                data_for_zone['total'] = lighting + heating + cooling # This is the sum of absolute energy values

                if total_area_group > 0:
                    data_for_zone['lighting_per_area'] = lighting / total_area_group
                    data_for_zone['heating_per_area'] = heating / total_area_group
                    data_for_zone['cooling_per_area'] = cooling / total_area_group
                    data_for_zone['total_per_area'] = data_for_zone['total'] / total_area_group
                else:
                    logger.warning(f"Total area for grouping related to '{full_zone_id_key}' is {total_area_group}. Per-area values will be set to absolute energy values (or 0 if energy is 0).")
                    data_for_zone['lighting_per_area'] = lighting
                    data_for_zone['heating_per_area'] = heating
                    data_for_zone['cooling_per_area'] = cooling
                    data_for_zone['total_per_area'] = data_for_zone['total']
                
                # 'zones' set is no longer part of data_for_zone structure at this level

            except (TypeError, KeyError, ZeroDivisionError) as e:
                logger.error(f"Error calculating totals for zone '{full_zone_id_key}': {e}. Data for this zone might be incomplete.", exc_info=True)
                # Ensure problematic zone still has default/zeroed fields
                data_for_zone.setdefault('total', 0.0)
                data_for_zone.setdefault('lighting_per_area', 0.0)
                data_for_zone.setdefault('heating_per_area', 0.0)
                data_for_zone.setdefault('cooling_per_area', 0.0)
                data_for_zone.setdefault('total_per_area', 0.0)
            except Exception as e_unexp:
                 logger.critical(f"Unexpected error calculating totals for area '{area_key}': {e_unexp}.", exc_info=True)


    def _get_area_total_for_area_id(self, area_id: str) -> float:
        """
        Get the total floor area for a specific area ID from AreaParser.
        Returns 0.0 if area_id is not found or an error occurs.
        """
        if not area_id:
            logger.warning("_get_area_total_for_area_id called with empty area_id. Returning 0.0.")
            return 0.0
        try:
            if not self.area_parser or not self.area_parser.processed:
                logger.warning(f"AreaParser not available or not processed when getting total for area_id '{area_id}'. Returning 0.0.")
                return 0.0
            
            area_totals = self.area_parser.get_area_totals(area_id) # This method in AreaParser should also be robust
            return safe_float(area_totals.get("total_floor_area", 0.0), 0.0)
        except AttributeError: # If area_parser is None or methods are missing (should be caught by above)
            logger.error(f"AttributeError accessing AreaParser for area_id '{area_id}'. Returning 0.0.", exc_info=True)
            return 0.0
        except Exception as e:
            logger.error(f"Error getting total area for area_id '{area_id}': {e}. Returning 0.0.", exc_info=True)
            return 0.0


    def _determine_location(self, area_id: str) -> str:
        """
        Determine the location type for an area ID using AreaParser's H-value data.
        Falls back to simple floor number logic if H-value data is unavailable.
        Returns 'Unknown' if location cannot be determined.
        """
        unknown_location = "Unknown"
        if not area_id:
            logger.warning("_determine_location called with empty area_id. Returning 'Unknown'.")
            return unknown_location
        try:
            if not self.area_parser or not self.area_parser.processed:
                logger.warning(f"AreaParser not available or not processed for determining location of area_id '{area_id}'. Falling back to basic logic.")
            else:
                area_h_values = self.area_parser.get_area_h_values() # This method in AreaParser should be robust
                if area_h_values: # Check if it returned data
                    for area_data in area_h_values:
                        if area_data.get('area_id') == area_id:
                            return area_data.get('location', unknown_location)
                else:
                    logger.info(f"No H-value data returned from AreaParser for area_id '{area_id}'. Falling back.")

            # Fallback logic based on area_id format (e.g., "00", "01")
            if len(area_id) >= 2 and area_id[:2].isdigit():
                floor_num_str = area_id[:2]
                try:
                    floor_num = int(floor_num_str)
                    if floor_num == 0: return "Ground Floor"
                    # Add more sophisticated logic if needed, e.g., max floor from IDF to determine "Top Floor"
                    return "Intermediate Floor"
                except ValueError:
                    logger.warning(f"Could not parse floor number from area_id prefix '{floor_num_str}' for '{area_id}'.")
            
            logger.info(f"Could not determine location for area_id '{area_id}' through H-values or basic logic.")
            return unknown_location
        except AttributeError: # If area_parser is None or methods are missing
            logger.error(f"AttributeError accessing AreaParser for location of area_id '{area_id}'. Returning '{unknown_location}'.", exc_info=True)
            return unknown_location
        except Exception as e:
            logger.error(f"Error determining location for area_id '{area_id}': {e}. Returning '{unknown_location}'.", exc_info=True)
            return unknown_location

    # New method to provide raw energy data keyed by full_zone_id
    def get_raw_energy_data_by_full_zone_id(self) -> Dict[str, Dict[str, Any]]:
        """
        Get the processed energy data, keyed by full_zone_id, containing absolute energy values.
        Returns an empty dictionary if not processed.
        """
        if not self.processed:
            logger.warning("Energy data not processed yet. Call process_output() first. Returning empty dict for raw energy data.")
            return {}
        return self.energy_data_by_area

    def get_energy_data_by_area(self) -> Dict[str, Dict[str, Any]]: # Original method, might be deprecated or refactored later
        """
        Get the processed energy data, traditionally keyed by a simpler area_key.
        NOTE: With changes to use full_zone_id as primary key in self.energy_data_by_area,
        this method's original behavior might be altered.
        Consider if this method is still needed or how it should adapt.
        For now, it returns the same as get_raw_energy_data_by_full_zone_id.
        Returns an empty dictionary if not processed.
        """
        if not self.processed:
            logger.warning("Energy data not processed yet. Call process_output() first. Returning empty dict for get_energy_data_by_area.")
            return {}
        return self.energy_data_by_area # Returns the dict keyed by full_zone_id

    def get_energy_rating_table_data(self) -> List[Dict[str, Any]]: # This method prepares data for a specific report
        """
        Get data for energy rating reports in table format.
        This method iterates over self.energy_data_by_area (keyed by full_zone_id)
        and extracts/calculates values for the rating table.
        Returns an empty list if not processed or if errors occur.
        """
        table_data: List[Dict[str, Any]] = []
        if not self.processed:
            logger.warning("Energy data not processed. Call process_output() first. Returning empty list for rating table.")
            return table_data
        if not self.energy_data_by_area:
            logger.info("No energy data available by area. Returning empty list for rating table.")
            return table_data

        try:
            # Pre-calculate sum of individual_zone_floor_area for each (floor_id, area_id) combination
            floor_area_id_sums: Dict[tuple[str, str], float] = {}
            for data_for_zone_pre_calc in self.energy_data_by_area.values():
                floor_id = data_for_zone_pre_calc.get('floor_id_report', 'N/A')
                area_id = data_for_zone_pre_calc.get('area_id_report', 'N/A')
                individual_area = safe_float(data_for_zone_pre_calc.get('individual_zone_floor_area', 0.0), 0.0)
                
                key = (floor_id, area_id)
                if key not in floor_area_id_sums:
                    floor_area_id_sums[key] = 0.0
                floor_area_id_sums[key] += individual_area

            for full_zone_id_key, data_for_zone in self.energy_data_by_area.items():
                try:
                    # This is the individual zone's area, used for the 'Zone area' column
                    current_zone_floor_area = safe_float(data_for_zone.get('individual_zone_floor_area', 0.0), 0.0)
                    
                    abs_lighting = safe_float(data_for_zone.get('lighting', 0.0), 0.0)
                    abs_heating = safe_float(data_for_zone.get('heating', 0.0), 0.0)
                    abs_cooling = safe_float(data_for_zone.get('cooling', 0.0), 0.0)
                    abs_total = safe_float(data_for_zone.get('total', 0.0), 0.0) # This is sum of abs_lighting, abs_heating, abs_cooling

                    # Determine the correct total floor area for division
                    report_floor_id = data_for_zone.get('floor_id_report', 'N/A')
                    report_area_id = data_for_zone.get('area_id_report', 'N/A')
                    group_lookup_key = (report_floor_id, report_area_id)
                    correct_total_floor_area_for_group = floor_area_id_sums.get(group_lookup_key, 0.0)

                    if correct_total_floor_area_for_group > 0:
                        val_lighting = abs_lighting / correct_total_floor_area_for_group
                        val_heating = abs_heating / correct_total_floor_area_for_group
                        val_cooling = abs_cooling / correct_total_floor_area_for_group
                        # Recalculate total based on per-area values if needed, or sum of per-area components
                        # For consistency, let's sum the per-area components.
                        # Or, divide the absolute total by the correct_total_floor_area_for_group
                        val_total = (abs_lighting + abs_heating + abs_cooling) / correct_total_floor_area_for_group
                    else:
                        logger.warning(f"Correct total floor area for group ('{report_floor_id}', '{report_area_id}') is {correct_total_floor_area_for_group} for zone '{full_zone_id_key}'. Energy values in report will be absolute (not per m^2).")
                        val_lighting = abs_lighting
                        val_heating = abs_heating
                        val_cooling = abs_cooling
                        val_total = abs_lighting + abs_heating + abs_cooling # Sum of absolute values

                    row = {
                        'floor_id_report': report_floor_id,
                        'area_id_report': report_area_id,
                        'zone_name_report': data_for_zone.get('zone_name_report', 'N/A'),
                        'multiplier': data_for_zone.get('multiplier', 1),
                        'total_area': current_zone_floor_area, # Display individual zone area
                        'lighting': val_lighting, # Divided by correct_total_floor_area_for_group
                        'heating': val_heating,   # Divided by correct_total_floor_area_for_group
                        'cooling': val_cooling,   # Divided by correct_total_floor_area_for_group
                        'total': val_total,       # Divided by correct_total_floor_area_for_group
                        # Placeholders
                        'location': data_for_zone.get('location', 'Unknown'),
                        'energy_consumption_model': '',
                        'better_percent': '',
                        'energy_rating': '',
                    }
                    table_data.append(row)
                except (TypeError, KeyError) as e_row:
                    logger.error(f"Error creating table row for full_zone_id_key '{full_zone_id_key}': {e_row}. Skipping this zone.", exc_info=True)
                    continue # Skip to the next zone
            return table_data
        except Exception as e:
            logger.error(f"Unexpected error generating energy rating table data: {e}", exc_info=True)
            return [] # Return empty list on major failure
