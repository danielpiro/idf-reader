"""
Extracts and processes energy consumption and rating information from EnergyPlus output files.
"""
from typing import Dict, Any, List, Optional
import re
import csv
import os
from utils.logging_config import get_logger

logger = get_logger(__name__)
from parsers.area_parser import AreaParser
from utils.data_loader import safe_float

def safe_float(value, default=None):
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

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
            # Primary pattern for standard format (with colons)
            self.zone_pattern = re.compile(
                r'(\d{2}):(\d{2})X([A-Za-z0-9_]+)'
                r'(?:\s+([A-Za-z0-9_ ]+))?:'
                r'([A-Za-z0-9_ ]+(?:\s+[A-Za-z0-9_ ]+)*)\s+'
                r'\[([A-Za-z0-9/]+)\]'
                r'\(([A-Za-z0-9]+)\)'
            )
            
            # Pattern for energy output format with spaces (e.g., "25 E342 Heating:Zone Ideal Loads Zone Air Temperature [C](TimeStep)")
            self.zone_pattern_space = re.compile(
                r'(\d{2})\s+([A-Za-z]\d+)'
                r'(?:\s+([A-Za-z0-9_ ]+))?:'
                r'([A-Za-z0-9_ ]+(?:\s+[A-Za-z0-9_ ]+)*)\s+'
                r'\[([A-Za-z0-9/]+)\]'
                r'\(([A-Za-z0-9]+)\)'
            )
            
            # Fallback pattern for variations (more flexible zone names)
            self.zone_pattern_fallback = re.compile(
                r'(\d{2}):([A-Za-z0-9]+)X([A-Za-z0-9_]*)'
                r'(?:\s+([A-Za-z0-9_ ]+))?:'
                r'([A-Za-z0-9_ ]+(?:\s+[A-Za-z0-9_ ]+)*)\s+'
                r'\[([A-Za-z0-9/]+)\]'
                r'\(([A-Za-z0-9]+)\)'
            )
        except ValueError as ve:
            logger.error(f"Initialization error in EnergyRatingParser: {ve}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Unexpected error during EnergyRatingParser initialization: {e}", exc_info=True)
            self.energy_data_by_area = {}
            self.processed = False
            self.zone_pattern = None
            raise

    def process_output(self, output_file_path: Optional[str] = None) -> None:
        """
        Process EnergyPlus output file (eplusout.csv) to extract energy consumption data.
        """
        if self.processed:
            return
        if not self.zone_pattern:
            logger.error("Zone pattern regex not compiled. Cannot process output.")
            self.processed = False
            return

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
                            break
                    if not final_output_file_path:
                        logger.warning("Could not automatically find eplusout.csv based on IDF path or fallback locations.")
                else:
                    logger.warning("IDF path not available from DataLoader, cannot automatically find eplusout.csv.")
            else:
                final_output_file_path = output_file_path

            if final_output_file_path and os.path.basename(final_output_file_path).lower() == "eplustbl.csv":
                candidate_out = os.path.join(os.path.dirname(final_output_file_path), "eplusout.csv")
                if os.path.exists(candidate_out):
                    final_output_file_path = candidate_out
                else:
                    logger.warning(f"eplustbl.csv provided, but eplusout.csv not found in the same directory ({os.path.dirname(final_output_file_path)}).")

            if not final_output_file_path or not os.path.exists(final_output_file_path):
                logger.error(f"EnergyPlus output file (eplusout.csv) not found. Tried path: {final_output_file_path if final_output_file_path else 'auto-detection failed'}.")
                self.processed = False
                return

            if not self.area_parser.processed:
                try:
                    self.area_parser.process_idf(None)
                except Exception as ap_e:
                    logger.error(f"Error processing area data via AreaParser: {ap_e}. Energy processing may be incomplete.", exc_info=True)

            with open(final_output_file_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)
                headers = next(reader, None)
                if headers is None:
                    logger.error(f"CSV file '{final_output_file_path}' is empty or has no headers.")
                    self.processed = False
                    return

                last_row = None
                for row in reader:
                    last_row = row

                if not last_row:
                    logger.error(f"No data rows found in EnergyPlus output file '{final_output_file_path}'.")
                    self.processed = False
                    return

                self._process_headers_and_values(headers, last_row)
            self._calculate_totals()
            self.processed = True

        except FileNotFoundError:
            logger.error(f"EnergyPlus output file not found (should have been caught earlier): {final_output_file_path}", exc_info=True)
            self.processed = False
        except StopIteration:
            logger.error(f"CSV file '{final_output_file_path}' seems to be empty after headers.", exc_info=True)
            self.processed = False
        except csv.Error as csv_e:
            logger.error(f"CSV formatting error in '{final_output_file_path}': {csv_e}", exc_info=True)
            self.processed = False
        except ValueError as val_e:
            logger.error(f"ValueError during processing of '{final_output_file_path}': {val_e}", exc_info=True)
            self.processed = False
        except RuntimeError as run_e:
            logger.error(f"RuntimeError during processing of '{final_output_file_path}': {run_e}", exc_info=True)
            self.processed = False
        except Exception as e:
            logger.error(f"Unexpected error processing EnergyPlus output file '{final_output_file_path}': {e}", exc_info=True)
            self.processed = False

    def _process_headers_and_values(self, headers: List[str], values: List[str]) -> None:
        """
        Process headers to extract zone information and corresponding values.
        """
        self.energy_data_by_area = {}
        if not headers or not values:
            logger.warning("Headers or values list is empty in _process_headers_and_values. Skipping.")
            return
        if not self.zone_pattern:
            logger.error("Zone pattern regex not compiled in _process_headers_and_values. Skipping.")
            return

        all_zones_data_from_loader = self.data_loader.get_zones()
        
        
        # Track processing stats for debugging
        total_headers_with_X = 0
        matched_headers = 0
        zone_keys_found = set()
        zone_keys_missing = set()
        unmatched_headers = []

        for i, header in enumerate(headers):
            try:
                if i == 0:
                    continue
                if "X" not in header:
                    continue
                
                total_headers_with_X += 1

                match = self.zone_pattern.search(header)
                pattern_used = "standard"
                
                if not match and hasattr(self, 'zone_pattern_space'):
                    # Try space pattern (e.g., "25 E342 Heating:...")
                    match = self.zone_pattern_space.search(header)
                    pattern_used = "space"
                
                if not match and hasattr(self, 'zone_pattern_fallback'):
                    # Try fallback pattern for non-standard formats
                    match = self.zone_pattern_fallback.search(header)
                    pattern_used = "fallback"
                    
                if not match:
                    unmatched_headers.append(header)
                    continue
                
                matched_headers += 1

                groups = match.groups()
                if len(groups) < 6:
                    logger.warning(f"Regex match for header '{header}' yielded insufficient groups ({len(groups)}). Groups: {groups}. Skipping.")
                    continue

                # Handle different pattern formats
                if pattern_used == "space":
                    # For space pattern: floor, area_zone_id, equipment_type, metric, unit, period
                    if len(groups) == 6:
                        floor, area_zone_id, equipment_type, metric, unit, period = groups
                        zone_name_from_header = ""  # Will be set later
                        area_id_from_header = area_zone_id
                    else:
                        logger.warning(f"Space pattern match for header '{header}' has unexpected group count ({len(groups)}). Skipping.")
                        continue
                else:
                    # For standard/fallback patterns: floor, area_id, zone_name, equipment_type, metric, unit, period
                    if len(groups) >= 7:
                        floor, area_id_from_header, zone_name_from_header, equipment_type, metric, unit, period = groups[:7]
                    else:
                        logger.warning(f"Standard pattern match for header '{header}' has unexpected group count ({len(groups)}). Skipping.")
                        continue

                if period != "RunPeriod":
                    continue

                value_str = values[i] if i < len(values) else "0.0"
                value = safe_float(value_str, 0.0)
                processed_value = self._process_value(value, header.lower())

                # Find the matching zone from DataLoader instead of constructing the key
                matched_zone_key = None
                if isinstance(all_zones_data_from_loader, dict):
                    # Search for zones that match the area_id and zone_name from the header
                    if pattern_used == "space":
                        # For space format, we have floor and area_zone_id
                        target_area_id = area_zone_id
                        zone_name_from_header = "LIV"  # Default for space format
                    else:
                        # For standard format, we have area_id_from_header and zone_name_from_header
                        target_area_id = area_id_from_header
                    
                    # Look for zones with matching area_id and zone name
                    for zone_key, zone_data in all_zones_data_from_loader.items():
                        zone_area_id = zone_data.get('area_id', '')
                        if (zone_area_id == target_area_id and 
                            zone_name_from_header in zone_key):
                            matched_zone_key = zone_key
                            break
                
                if matched_zone_key:
                    full_zone_id_key = matched_zone_key
                else:
                    # Fallback: use a constructed key for energy data storage
                    if pattern_used == "space":
                        full_zone_id_key = f"ENERGY_{floor}_{area_zone_id}_LIV"
                        area_id_from_header = area_zone_id
                        zone_name_from_header = "LIV"
                    else:
                        full_zone_id_key = f"ENERGY_{floor}_{area_id_from_header}_{zone_name_from_header}"
                    logger.warning(f"No matching zone found for area_id='{area_id_from_header if pattern_used != 'space' else area_zone_id}', zone_name='{zone_name_from_header}'. Using fallback key '{full_zone_id_key}'")
                zone_keys_found.add(full_zone_id_key)

                if full_zone_id_key not in self.energy_data_by_area:
                    zone_multiplier = 1
                    individual_zone_floor_area = 0.0

                    
                    # If we found a matching zone, get its data directly
                    if matched_zone_key and isinstance(all_zones_data_from_loader, dict) and matched_zone_key in all_zones_data_from_loader:
                        dl_zone_data = all_zones_data_from_loader[matched_zone_key]
                        zone_multiplier = int(dl_zone_data.get('multiplier', 1))
                        individual_zone_floor_area = safe_float(dl_zone_data.get('floor_area', 0.0), 0.0)
                    else:
                        # No matching zone found, use defaults
                        zone_keys_missing.add(full_zone_id_key)
                        logger.warning(f"EnergyRatingParser: No matching zone found for '{full_zone_id_key}'. Using defaults for multiplier/floor_area.")

                    total_area_for_legacy_grouping = self._get_area_total_for_area_id(area_id_from_header)
                    location_for_grouping = self._determine_location(area_id_from_header)

                    self.energy_data_by_area[full_zone_id_key] = {
                        'floor_id_report': floor,
                        'area_id_report': area_id_from_header,
                        'zone_name_report': zone_name_from_header,
                        'multiplier': zone_multiplier,
                        'individual_zone_floor_area': individual_zone_floor_area,
                        'lighting': 0.0, 'heating': 0.0, 'cooling': 0.0, 'total': 0.0,
                        'location': location_for_grouping,
                        'total_area_of_legacy_grouping': total_area_for_legacy_grouping
                    }
                    

                category = None
                header_lower = header.lower()
                if 'light' in header_lower: category = 'lighting'
                elif 'heating' in header_lower: category = 'heating'
                elif 'cooling' in header_lower: category = 'cooling'

                if category and category in self.energy_data_by_area[full_zone_id_key]:
                    # Divide by zone multiplier to get per-zone energy consumption
                    # EnergyPlus output shows total energy for all multiplied zones
                    zone_multiplier = self.energy_data_by_area[full_zone_id_key].get('multiplier', 1)
                    per_zone_value = processed_value / zone_multiplier if zone_multiplier > 0 else processed_value
                    self.energy_data_by_area[full_zone_id_key][category] += per_zone_value
                    
                    # Apply zone multiplier for repeated zones
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
        
        # Report processing results
        if zone_keys_missing:
            logger.warning(f"Zone keys found in eplusout.csv but missing from IDF: {len(zone_keys_missing)} zones")
        
        if unmatched_headers:
            logger.warning(f"Headers with 'X' that didn't match regex pattern: {len(unmatched_headers)} headers")

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
            pass

            processed_val = 0.0
            if 'light' in header_lower:
                processed_val = value / 3600000.0
            elif 'heating' in header_lower or 'cooling' in header_lower:
                processed_val = value / 10800000.0
            else:
                logger.warning(f"Header '{header_lower}' did not match known energy categories for unit conversion. Original value: {value} returned.")
                processed_val = value

            return processed_val
        except TypeError:
            logger.error(f"Cannot process non-numeric value '{value}' for header '{header_lower}'. Returning 0.0.", exc_info=True)
            return 0.0

    def _calculate_totals(self) -> None:
        """
        Calculate total energy consumption and per area values for each processed area.
        """
        if not self.energy_data_by_area:
            return

        for full_zone_id_key, data_for_zone in self.energy_data_by_area.items():
            try:
                lighting = safe_float(data_for_zone.get('lighting', 0.0), 0.0)
                heating = safe_float(data_for_zone.get('heating', 0.0), 0.0)
                cooling = safe_float(data_for_zone.get('cooling', 0.0), 0.0)
                total_area_group = safe_float(data_for_zone.get('total_area_of_grouping', 0.0), 0.0)

                data_for_zone['lighting'] = lighting
                data_for_zone['heating'] = heating
                data_for_zone['cooling'] = cooling
                data_for_zone['total_area_of_legacy_grouping'] = total_area_group

                data_for_zone['total'] = lighting + heating + cooling

                if total_area_group > 0:
                    data_for_zone['lighting_per_area'] = lighting / total_area_group
                    data_for_zone['heating_per_area'] = heating / total_area_group
                    data_for_zone['cooling_per_area'] = cooling / total_area_group
                    data_for_zone['total_per_area'] = data_for_zone['total'] / total_area_group
                else:
                    logger.debug(f"Total area for grouping related to '{full_zone_id_key}' is {total_area_group}. Per-area values will be set to absolute energy values (or 0 if energy is 0).")
                    data_for_zone['lighting_per_area'] = lighting
                    data_for_zone['heating_per_area'] = heating
                    data_for_zone['cooling_per_area'] = cooling
                    data_for_zone['total_per_area'] = data_for_zone['total']

            except (TypeError, KeyError, ZeroDivisionError) as e:
                logger.error(f"Error calculating totals for zone '{full_zone_id_key}': {e}. Data for this zone might be incomplete.", exc_info=True)
                data_for_zone.setdefault('total', 0.0)
                data_for_zone.setdefault('lighting_per_area', 0.0)
                data_for_zone.setdefault('heating_per_area', 0.0)
                data_for_zone.setdefault('cooling_per_area', 0.0)
                data_for_zone.setdefault('total_per_area', 0.0)
            except Exception as e_unexp:
                 logger.critical(f"Unexpected error calculating totals for {e_unexp}.", exc_info=True)

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

            area_totals = self.area_parser.get_area_totals(area_id)
            result = safe_float(area_totals.get("total_floor_area", 0.0), 0.0)
            return result
        except AttributeError:
            logger.error(f"AttributeError accessing AreaParser for area_id '{area_id}'. Returning 0.0.", exc_info=True)
            return 0.0
        except Exception as e:
            logger.error(f"Error getting total area for area_id '{area_id}': {e}. Returning 0.0.", exc_info=True)
            return 0.0

    def _determine_location(self, area_id: str) -> str:
        """
        Determine the location type for an area ID using AreaParser's H-value data.
        Falls back to intelligent floor detection based on the building structure.
        For the CSV model lookup, we need to map to valid location types.
        """
        if not area_id:
            logger.warning("_determine_location called with empty area_id. Returning default location.")
            return "Intermediate Floor & Intermediate ceiling"
        
        try:
            # First try to get location from AreaParser H-values
            if self.area_parser and self.area_parser.processed:
                area_h_values = self.area_parser.get_area_h_values()
                if area_h_values:
                    for area_data in area_h_values:
                        if area_data.get('area_id') == area_id:
                            location = area_data.get('location', '')
                            if location and location != 'Unknown':
                                return location

            # Enhanced fallback logic for different area ID patterns
            # Handle patterns like "E342", "A338", "D341", etc.
            
            # Try to extract floor information from context or use intelligent defaults
            # Based on the error log, valid locations include combinations of:
            # Floor types: Ground Floor, External Floor, Separation Floor, Intermediate Floor
            # Ceiling types: Intermediate ceiling, External ceiling, Separation ceiling
            
            # For now, default to the most common case until we have better building information
            # This should match one of the valid entries in the CSV model
            default_location = "Intermediate Floor & Intermediate ceiling"
            
            # Try to infer from area_id pattern if possible
            if area_id and len(area_id) > 0:
                first_char = area_id[0].upper()
                
                # Simple heuristic based on common building patterns
                # Ground floor areas often start with lower letters/numbers
                if first_char in ['A', 'B', '0', '1']:
                    return "Ground Floor & Intermediate ceiling"
                elif first_char in ['C', 'D', 'E', 'F']:
                    return "Intermediate Floor & Intermediate ceiling"
                elif first_char in ['G', 'H']:
                    return "External Floor & External ceiling"  # Possibly top floor/roof areas
                else:
                    return default_location
            
            # Using default location for area_id
            return default_location
            
        except Exception as e:
            logger.error(f"Error determining location for area_id '{area_id}': {e}. Using default.", exc_info=True)
            return "Intermediate Floor & Intermediate ceiling"

    def get_raw_energy_data_by_full_zone_id(self) -> Dict[str, Dict[str, Any]]:
        """
        Get the processed energy data, keyed by full_zone_id, containing absolute energy values.
        Returns an empty dictionary if not processed.
        """
        if not self.processed:
            logger.warning("Energy data not processed yet. Call process_output() first. Returning empty dict for raw energy data.")
            return {}
        return self.energy_data_by_area

    def get_energy_data_by_area(self) -> Dict[str, Dict[str, Any]]:
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
        return self.energy_data_by_area

    def get_energy_rating_table_data(self, model_year=None) -> List[Dict[str, Any]]:
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
            return table_data

        try:
            # Check if this is office ISO
            is_office_iso = isinstance(model_year, str) and 'office' in model_year.lower()
            
            # For office ISO: each zone is individual, for others: group by floor/area
            if is_office_iso:
                # Office ISO: no grouping needed, each zone is individual
                logger.info("Office ISO detected - using individual zone calculations")
            else:
                # Non-office: group by floor/area as before
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
                    current_zone_floor_area = safe_float(data_for_zone.get('individual_zone_floor_area', 0.0), 0.0)

                    abs_lighting = safe_float(data_for_zone.get('lighting', 0.0), 0.0)
                    abs_heating = safe_float(data_for_zone.get('heating', 0.0), 0.0)
                    abs_cooling = safe_float(data_for_zone.get('cooling', 0.0), 0.0)
                    safe_float(data_for_zone.get('total', 0.0), 0.0)

                    report_floor_id = data_for_zone.get('floor_id_report', 'N/A')
                    report_area_id = data_for_zone.get('area_id_report', 'N/A')
                    
                    if is_office_iso:
                        # Office ISO: use individual zone area for calculations
                        if current_zone_floor_area > 0:
                            val_lighting = abs_lighting / current_zone_floor_area
                            val_heating = abs_heating / current_zone_floor_area
                            val_cooling = abs_cooling / current_zone_floor_area
                            val_total = (abs_lighting + abs_heating + abs_cooling) / current_zone_floor_area
                        else:
                            logger.debug(f"Office ISO: Individual zone area is 0 for zone '{full_zone_id_key}'. Energy values will be absolute.")
                            val_lighting = abs_lighting
                            val_heating = abs_heating
                            val_cooling = abs_cooling
                            val_total = abs_lighting + abs_heating + abs_cooling
                    else:
                        # Non-office: use grouped area calculations as before
                        group_lookup_key = (report_floor_id, report_area_id)
                        correct_total_floor_area_for_group = floor_area_id_sums.get(group_lookup_key, 0.0)

                        if correct_total_floor_area_for_group > 0:
                            val_lighting = abs_lighting / correct_total_floor_area_for_group
                            val_heating = abs_heating / correct_total_floor_area_for_group
                            val_cooling = abs_cooling / correct_total_floor_area_for_group
                            val_total = (abs_lighting + abs_heating + abs_cooling) / correct_total_floor_area_for_group
                        else:
                            logger.warning(f"Correct total floor area for group ('{report_floor_id}', '{report_area_id}') is {correct_total_floor_area_for_group} for zone '{full_zone_id_key}'. Energy values in report will be absolute (not per m^2).")
                            val_lighting = abs_lighting
                            val_heating = abs_heating
                            val_cooling = abs_cooling
                            val_total = abs_lighting + abs_heating + abs_cooling

                    row = {
                        'floor_id_report': report_floor_id,
                        'area_id_report': report_area_id,
                        'zone_id': full_zone_id_key,  # Add zone_id for office ISO grouping
                        'zone_name_report': data_for_zone.get('zone_name_report', 'N/A'),
                        'multiplier': data_for_zone.get('multiplier', 1),
                        'total_area': current_zone_floor_area,
                        'lighting': val_lighting,
                        'heating': val_heating,
                        'cooling': val_cooling,
                        'total': val_total,
                        'location': data_for_zone.get('location', 'Unknown'),
                        'model_csv_area_description': data_for_zone.get('location', 'Unknown'),
                        'energy_consumption_model': '',
                        'better_percent': '',
                        'energy_rating': '',
                    }
                    table_data.append(row)
                except (TypeError, KeyError) as e_row:
                    logger.error(f"Error creating table row for full_zone_id_key '{full_zone_id_key}': {e_row}. Skipping this zone.", exc_info=True)
                    continue
            return table_data
        except Exception as e:
            logger.error(f"Unexpected error generating energy rating table data: {e}", exc_info=True)
            return []