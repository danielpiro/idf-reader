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
from .utils import safe_float


class EnergyRatingParser:
    """
    Processes energy consumption data from EnergyPlus output files (eplusout.csv).
    Uses area data from AreaParser for energy per area calculations.
    """
    def __init__(self, data_loader, area_parser: AreaParser, load_parser=None):
        try:
            if data_loader is None:
                raise ValueError("DataLoader instance cannot be None.")
            if area_parser is None:
                raise ValueError("AreaParser instance cannot be None.")

            self.data_loader = data_loader
            self.area_parser = area_parser
            self.load_parser = load_parser
            self.energy_data_by_area: Dict[str, Dict[str, Any]] = {}
            self.processed = False
            # Pattern 1: New EnergyPlus CSV format like "GRXEX:W GENERAL LIGHTING:Lights Electricity Energy [J](RunPeriod)"
            self.zone_pattern = re.compile(
                r'([A-Z0-9]+[X][A-Z0-9]*):([A-Z0-9])\s+'
                r'(?:GENERAL\s+)?'
                r'(LIGHTING|IDEAL\s+LOADS\s+AIR):'
                r'([A-Za-z0-9_ ]+(?:\s+[A-Za-z0-9_ ]+)*)\s+'
                r'\[([A-Za-z0-9/]+)\]'
                r'\(([A-Za-z0-9]+)\)'
            )
            
            # Pattern 2: Alternative new format without 'X' like "GREX:W GENERAL LIGHTING:..."
            self.zone_pattern_space = re.compile(
                r'([A-Z0-9]+):([A-Z0-9])\s+'
                r'(?:GENERAL\s+)?'
                r'(LIGHTING|IDEAL\s+LOADS\s+AIR):'
                r'([A-Za-z0-9_ ]+(?:\s+[A-Za-z0-9_ ]+)*)\s+'
                r'\[([A-Za-z0-9/]+)\]'
                r'\(([A-Za-z0-9]+)\)'
            )
            
            # Pattern 3: Legacy numeric format like "02:03X_LIV Equipment:Lights Energy [J](RunPeriod)"
            self.zone_pattern_fallback = re.compile(
                r'(\d{2}):(\d{2})X([A-Za-z0-9_]+)'
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
        logger.info(f"EnergyRatingParser.process_output called with output_file_path: {output_file_path}")
        if self.processed:
            logger.info("EnergyRatingParser already processed, returning early")
            return
        
        # Debug: Check initialization state
        logger.debug(f"EnergyRatingParser state: zone_pattern={self.zone_pattern is not None}, data_loader={self.data_loader is not None}, area_parser={self.area_parser is not None}")
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
                logger.info(f"EnergyRatingParser.process_output: Setting processed=False due to missing file")
                self.processed = False
                return
            else:
                logger.info(f"EnergyRatingParser found eplusout.csv at: {final_output_file_path}")

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

                logger.debug(f"CSV headers found: {len(headers)} columns")
                logger.debug(f"Sample headers (first 10): {headers[:10] if headers else []}")
                
                last_row = None
                row_count = 0
                for row in reader:
                    last_row = row
                    row_count += 1

                logger.debug(f"CSV processing: found {row_count} data rows")
                if not last_row:
                    logger.error(f"No data rows found in EnergyPlus output file '{final_output_file_path}'.")
                    self.processed = False
                    return

                # Get zone data for grouping analysis
                all_zones_data_from_loader = self.data_loader.get_zones()
                
                self._process_headers_and_values(headers, last_row, all_zones_data_from_loader)
                self._calculate_totals()
            
                # STAGE 2: Apply grouping logic after all individual zone data is collected
                logger.debug(f"Before grouping: {len(self.energy_data_by_area)} zones in energy_data_by_area")
                self._apply_zone_grouping(all_zones_data_from_loader)
                logger.debug(f"After grouping: {len(self.energy_data_by_area)} zones in energy_data_by_area")
                
                logger.info(f"EnergyRatingParser.process_output: Successfully processed {len(self.energy_data_by_area)} zones")
                self.processed = True

        except FileNotFoundError:
            logger.error(f"EnergyPlus output file not found (should have been caught earlier): {final_output_file_path}", exc_info=True)
            logger.info(f"EnergyRatingParser.process_output: Setting processed=False due to FileNotFoundError")
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

    def _process_headers_and_values(self, headers: List[str], values: List[str], all_zones_data_from_loader: Dict) -> None:
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
                if pattern_used == "standard" or pattern_used == "space":
                    # New format: zone_area_part, zone_direction, equipment_type, metric, unit, period
                    # Example: GRXEX:W GENERAL LIGHTING:Lights Electricity Energy [J](RunPeriod)
                    # Groups: (GRXEX, W, LIGHTING, Lights Electricity Energy, J, RunPeriod)
                    if len(groups) == 6:
                        zone_area_part, zone_direction, equipment_type, metric, unit, period = groups
                        
                        # Extract floor and area info from zone name like "GRXEX"
                        # GR = Ground, EX = External, etc.
                        if len(zone_area_part) >= 2:
                            # Try to map the zone prefix to floor and area info
                            floor_prefix = zone_area_part[:2] if len(zone_area_part) >= 2 else "00"
                            area_suffix = zone_area_part[2:] if len(zone_area_part) > 2 else "XX"
                            
                            # Map common prefixes to floor numbers
                            floor_map = {"GR": "00", "EX": "01", "IN": "02", "SE": "03", "SP": "04", "BL": "05"}
                            floor = floor_map.get(floor_prefix, "00")
                            
                            area_id_from_header = area_suffix
                            zone_name_from_header = zone_direction  # W, E, N, S
                        else:
                            floor = "00"
                            area_id_from_header = zone_area_part
                            zone_name_from_header = zone_direction
                    else:
                        logger.warning(f"New pattern match for header '{header}' has unexpected group count ({len(groups)}). Groups: {groups}. Skipping.")
                        continue
                elif pattern_used == "fallback":
                    # Legacy format: floor, area_id, zone_name, [optional_equipment], metric, unit, period
                    # Example: "02:03X_LIV Equipment:Lights Energy [J](RunPeriod)"
                    if len(groups) >= 6:
                        if len(groups) == 7:
                            floor, area_id_from_header, zone_name_from_header, optional_equipment, metric, unit, period = groups
                            equipment_type = optional_equipment or "UNKNOWN"
                        else:
                            floor, area_id_from_header, zone_name_from_header, metric, unit, period = groups
                            equipment_type = "UNKNOWN"
                    else:
                        logger.warning(f"Legacy pattern match for header '{header}' has unexpected group count ({len(groups)}). Skipping.")
                        continue
                else:
                    logger.warning(f"Unknown pattern type '{pattern_used}' for header '{header}'. Skipping.")
                    continue

                if period != "RunPeriod":
                    continue

                value_str = values[i] if i < len(values) else "0.0"
                value = safe_float(value_str, 0.0)
                processed_value = self._process_value(value, header.lower())

                # Find the matching zone using improved matching logic
                matched_zone_key = None
                
                # For new format patterns, try direct matching first
                if pattern_used in ["standard", "space"]:
                    # Try to reconstruct the expected zone name from CSV header components
                    expected_zone_name = f"{zone_area_part}:{zone_name_from_header}"
                    
                    if isinstance(all_zones_data_from_loader, dict) and expected_zone_name in all_zones_data_from_loader:
                        matched_zone_key = expected_zone_name
                        logger.debug(f"Direct match found: {expected_zone_name}")
                    else:
                        # Try fuzzy matching for zones that contain the components
                        for zone_key in all_zones_data_from_loader.keys():
                            if (zone_area_part in zone_key and 
                                zone_name_from_header in zone_key):
                                matched_zone_key = zone_key
                                logger.debug(f"Fuzzy match found: {zone_key} for expected {expected_zone_name}")
                                break
                
                if not matched_zone_key and isinstance(all_zones_data_from_loader, dict):
                    # Fallback to legacy area_id based matching
                    target_area_id = area_id_from_header
                    
                    # Look for zones with matching area_id and zone name
                    for zone_key, zone_data in all_zones_data_from_loader.items():
                        zone_area_id = zone_data.get('area_id', '')
                        if (zone_area_id == target_area_id and 
                            zone_name_from_header in zone_key):
                            matched_zone_key = zone_key
                            logger.debug(f"Legacy match found: {zone_key}")
                            break
                
                if matched_zone_key:
                    full_zone_id_key = matched_zone_key
                else:
                    # Fallback: use a constructed key for energy data storage
                    full_zone_id_key = f"ENERGY_{floor}_{area_id_from_header}_{zone_name_from_header}"
                    logger.warning(f"No matching zone found for area_id='{area_id_from_header}', zone_name='{zone_name_from_header}'. Using fallback key '{full_zone_id_key}'")
                zone_keys_found.add(full_zone_id_key)

                if full_zone_id_key not in self.energy_data_by_area:
                    zone_multiplier = 1
                    individual_zone_floor_area = 0.0

                    
                    # If we found a matching zone, get its data directly
                    if matched_zone_key and isinstance(all_zones_data_from_loader, dict) and matched_zone_key in all_zones_data_from_loader:
                        dl_zone_data = all_zones_data_from_loader[matched_zone_key]
                        zone_multiplier = int(dl_zone_data.get('multiplier', 1))
                        individual_zone_floor_area = safe_float(dl_zone_data.get('floor_area', 0.0), 0.0)
                        
                        # Use the zone's grouping key for area calculations
                        from utils.data_loader import get_zone_grouping_key
                        grouping_key = get_zone_grouping_key(matched_zone_key)
                        total_area_for_legacy_grouping = self._get_area_total_for_grouping_key(grouping_key)
                        logger.debug(f"Using matched zone '{matched_zone_key}' with grouping key '{grouping_key}', total area: {total_area_for_legacy_grouping}")
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
                equipment_type_lower = equipment_type.lower() if equipment_type else ''
                metric_lower = metric.lower() if metric else ''
                
                # Check multiple sources for category determination
                if ('light' in header_lower or 'light' in equipment_type_lower or 
                    'light' in metric_lower or equipment_type == 'LIGHTING'): 
                    category = 'lighting'
                elif ('heating' in header_lower or 'heating' in metric_lower or 
                      'heating' in equipment_type_lower): 
                    category = 'heating'
                elif ('cooling' in header_lower or 'cooling' in metric_lower or 
                      'cooling' in equipment_type_lower): 
                    category = 'cooling'
                
                logger.debug(f"Header: {header}, Equipment: {equipment_type}, Metric: {metric}, Category: {category}")

                if category and category in self.energy_data_by_area[full_zone_id_key]:
                    # Divide by zone multiplier to get per-zone energy consumption
                    # EnergyPlus output shows total energy for all multiplied zones
                    zone_multiplier = self.energy_data_by_area[full_zone_id_key].get('multiplier', 1)
                    per_zone_value = processed_value / zone_multiplier if zone_multiplier > 0 else processed_value
                    self.energy_data_by_area[full_zone_id_key][category] += per_zone_value
                    
                    # Apply zone multiplier for repeated zones
                elif category:
                    logger.warning(f"Category '{category}' derived from header '{header}' not pre-defined in energy_data_by_area structure for key '{full_zone_id_key}'. Value not added.")
                else:
                    logger.debug(f"No category identified for header '{header}' (equipment: {equipment_type}, metric: {metric})")

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
        logger.info(f"Energy data processing summary: {len(zone_keys_found)} zones found, {matched_headers} headers matched out of {total_headers_with_X} headers with 'X'")
        logger.info(f"Final energy_data_by_area contains {len(self.energy_data_by_area)} zones: {list(self.energy_data_by_area.keys())[:10]}{'...' if len(self.energy_data_by_area) > 10 else ''}")
        
        # Log grouping analysis
        if isinstance(all_zones_data_from_loader, dict):
            from utils.data_loader import determine_zone_groupings, get_zone_grouping_info
            zone_groupings = determine_zone_groupings(all_zones_data_from_loader)
            
            if zone_groupings:
                logger.info(f"Zone groupings found: {len(zone_groupings)} groups")
                for group_key, zones in zone_groupings.items():
                    logger.info(f"  Group '{group_key}': {zones}")
            else:
                logger.info("No zone groupings found - all zones are individual")
        
        if zone_keys_missing:
            logger.warning(f"Zone keys found in eplusout.csv but missing from IDF: {len(zone_keys_missing)} zones")
        
        if unmatched_headers:
            logger.warning(f"Headers with 'X' that didn't match regex pattern: {len(unmatched_headers)} headers")
            if len(unmatched_headers) <= 5:
                logger.warning(f"Sample unmatched headers: {unmatched_headers}")
            else:
                logger.warning(f"Sample unmatched headers: {unmatched_headers[:5]} ... and {len(unmatched_headers)-5} more")

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
    
    def _get_area_total_for_grouping_key(self, grouping_key: str) -> float:
        """
        Get the total floor area for zones that share the same grouping key.
        This supports the new zone structure rules where grouping is by 'b' value only.
        
        Examples:
        - Grouping key "EX" matches zones GRXEX:W, GRXEX:E, etc.
        - Grouping key "80" matches zones BLOCK80:ZONE1, BLOCK80:CORE, etc.
        """
        if not grouping_key:
            return 0.0
            
        try:
            if not self.area_parser or not self.area_parser.processed:
                return 0.0
            
            # Get all zones from DataLoader and sum areas for matching grouping keys
            all_zones_data = self.data_loader.get_zones()
            if not isinstance(all_zones_data, dict):
                return 0.0
            
            total_area = 0.0
            from utils.data_loader import get_zone_grouping_key
            
            for zone_id, zone_data in all_zones_data.items():
                zone_grouping_key = get_zone_grouping_key(zone_id)
                if zone_grouping_key == grouping_key:
                    zone_area = safe_float(zone_data.get('floor_area', 0.0), 0.0)
                    zone_multiplier = int(safe_float(zone_data.get('multiplier', 1), 1))
                    total_area += zone_area * zone_multiplier
            
            logger.debug(f"Total area for grouping key '{grouping_key}': {total_area}")
            return total_area
            
        except Exception as e:
            logger.error(f"Error getting total area for grouping_key '{grouping_key}': {e}. Returning 0.0.", exc_info=True)
            return 0.0
    
    def _get_area_total_for_grouping_key_from_zones(self, grouping_key: str, zone_list: list, all_zones_data: dict) -> float:
        """
        Get the total floor area for a specific list of zones that belong to a group.
        This is more precise than the general grouping key method.
        """
        if not zone_list or not all_zones_data:
            return 0.0
            
        try:
            total_area = 0.0
            
            for zone_id in zone_list:
                if zone_id in all_zones_data:
                    zone_data = all_zones_data[zone_id]
                    zone_area = safe_float(zone_data.get('floor_area', 0.0), 0.0)
                    zone_multiplier = int(safe_float(zone_data.get('multiplier', 1), 1))
                    total_area += zone_area * zone_multiplier
            
            logger.debug(f"Total area for group '{grouping_key}' with zones {zone_list}: {total_area}")
            return total_area
            
        except Exception as e:
            logger.error(f"Error getting total area for group '{grouping_key}': {e}. Returning 0.0.", exc_info=True)
            return 0.0
    
    def _apply_zone_grouping(self, all_zones_data_from_loader):
        """
        STAGE 2: Apply grouping logic after all individual zone data has been extracted.
        This creates grouped entries in energy_data_by_area based on the grouping rules.
        """
        if not isinstance(all_zones_data_from_loader, dict):
            logger.info("No zone data available for grouping analysis")
            return
            
        from utils.data_loader import determine_zone_groupings, get_zone_grouping_info
        
        # Determine which zones should be grouped
        zone_groupings = determine_zone_groupings(all_zones_data_from_loader)
        
        if not zone_groupings:
            logger.info("No zone groupings found - all zones remain individual")
            return
        
        logger.info(f"Applying zone groupings: {len(zone_groupings)} groups found")
        
        # Create grouped entries in energy_data_by_area
        grouped_zone_ids = set()
        
        for group_key, zone_list in zone_groupings.items():
            logger.info(f"Processing group '{group_key}' with zones: {zone_list}")
            
            # Initialize group data
            group_lighting = 0.0
            group_heating = 0.0
            group_cooling = 0.0
            group_total_area = 0.0
            group_location = None
            found_zones_in_group = []
            
            # Aggregate data from all zones in the group
            for zone_id in zone_list:
                if zone_id in self.energy_data_by_area:
                    zone_data = self.energy_data_by_area[zone_id]
                    
                    # Aggregate energy values
                    group_lighting += zone_data.get('lighting', 0.0)
                    group_heating += zone_data.get('heating', 0.0)
                    group_cooling += zone_data.get('cooling', 0.0)
                    
                    # Calculate area
                    zone_area = zone_data.get('individual_zone_floor_area', 0.0)
                    zone_multiplier = zone_data.get('multiplier', 1)
                    group_total_area += zone_area * zone_multiplier
                    
                    # Use location from first zone in group
                    if group_location is None:
                        group_location = zone_data.get('location', 'Unknown')
                    
                    found_zones_in_group.append(zone_id)
                    grouped_zone_ids.add(zone_id)
                    
                    logger.info(f"  Added zone '{zone_id}' to group '{group_key}': L={zone_data.get('lighting', 0.0)}, H={zone_data.get('heating', 0.0)}, C={zone_data.get('cooling', 0.0)}")
                    logger.info(f"  Zone '{zone_id}' individual values: area={zone_data.get('individual_zone_floor_area', 0.0)}, mult={zone_data.get('multiplier', 1)}")
            
            if found_zones_in_group:
                # Create group entry with special key
                group_entry_key = f"GROUP_{group_key}"
                
                # Get floor_id and area_id from first zone in group for reporting
                first_zone_data = self.energy_data_by_area.get(found_zones_in_group[0], {})
                group_floor_id = first_zone_data.get('floor_id_report', group_key)
                group_area_id = first_zone_data.get('area_id_report', group_key)
                
                self.energy_data_by_area[group_entry_key] = {
                    "lighting": group_lighting,
                    "heating": group_heating, 
                    "cooling": group_cooling,
                    "multiplier": 1,  # Groups don't have multipliers
                    "individual_zone_floor_area": group_total_area,  # For compatibility
                    "total_area": group_total_area,
                    "location": group_location,
                    "is_group": True,
                    "group_key": group_key,
                    "grouped_zones": found_zones_in_group,
                    "zone_name_report": ', '.join(found_zones_in_group),  # Store the zone IDs for display
                    "floor_id_report": group_floor_id,
                    "area_id_report": group_area_id,
                    "full_zone_id": group_entry_key
                }
                
                logger.info(f"Created group entry '{group_entry_key}': L={group_lighting:.1f}, H={group_heating:.1f}, C={group_cooling:.1f}, Area={group_total_area:.1f}")
            else:
                logger.warning(f"No energy data found for any zones in group '{group_key}': {zone_list}")
        
        logger.info(f"Zone grouping complete: {len(grouped_zone_ids)} individual zones grouped into {len(zone_groupings)} groups")

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

    def _calculate_natural_ventilation_bonus(self, zone_name: str) -> float:
        """
        Calculate natural ventilation bonus based on ventilation rate_ach from load parser.
        
        Bonus table:
        - Nac<1 → 0 points
        - 1≤ Nac<3 → 0.1 points  
        - 3≤ Nac<5 → 0.12 points
        - 5≤ Nac<10 → 0.16 points
        - 10≤ Nac → 0.20 points
        """
        if not self.load_parser:
            logger.error(f"LoadParser not available for zone '{zone_name}'. Natural ventilation bonus will be 0.")
            logger.error(f"self.load_parser is: {self.load_parser}")
            return 0.0
            
        logger.info(f"=== Natural ventilation calculation for zone: '{zone_name}' ===")
        logger.info(f"LoadParser available: {self.load_parser is not None}")
        logger.info(f"LoadParser type: {type(self.load_parser)}")
        
        try:
            # Get load data from load parser
            logger.info(f"Calling load_parser.get_parsed_zone_loads(include_core=True)")
            load_data = self.load_parser.get_parsed_zone_loads(include_core=True)
            logger.info(f"Load parser returned data for {len(load_data)} zones")
            logger.info(f"Load data keys (first 10): {list(load_data.keys())[:10]}")
            
            # Try multiple matching strategies
            matched_zone_key = None
            
            # Strategy 1: Exact match
            if zone_name in load_data:
                matched_zone_key = zone_name
                logger.info(f"Exact match found for zone '{zone_name}'")
            else:
                logger.info(f"No exact match for zone '{zone_name}'. Trying fuzzy matching...")
                
                # Strategy 2: Try to extract zone components for matching
                # Zone name might be like "ENERGY_2_01_Office" but load parser expects different format
                zone_parts = zone_name.split('_')
                if len(zone_parts) >= 3:
                    # Extract floor, area, zone name parts
                    potential_floor = zone_parts[1] if len(zone_parts) > 1 else ""
                    potential_area = zone_parts[2] if len(zone_parts) > 2 else ""
                    potential_zone = '_'.join(zone_parts[3:]) if len(zone_parts) > 3 else zone_parts[-1]
                    
                    logger.info(f"Extracted parts from '{zone_name}': floor={potential_floor}, area={potential_area}, zone={potential_zone}")
                    
                    # Strategy 3: Look for zones that contain these components
                    for load_zone_key in load_data.keys():
                        # Check if load zone contains the components
                        if (potential_floor in load_zone_key and 
                            potential_area in load_zone_key and 
                            potential_zone in load_zone_key):
                            matched_zone_key = load_zone_key
                            logger.info(f"Component match found: '{load_zone_key}' for zone '{zone_name}'")
                            break
                
                # Strategy 4: Fuzzy matching based on similarity
                if not matched_zone_key:
                    similar_zones = []
                    for load_zone_key in load_data.keys():
                        # Check if either zone name is contained in the other
                        if (zone_name.lower() in load_zone_key.lower() or 
                            load_zone_key.lower() in zone_name.lower()):
                            similar_zones.append(load_zone_key)
                    
                    if similar_zones:
                        matched_zone_key = similar_zones[0]  # Take first match
                        logger.info(f"Similarity match found: '{matched_zone_key}' for zone '{zone_name}' (from {similar_zones})")
                    else:
                        logger.error(f"No matching zone found for '{zone_name}' in load data. Available zones: {list(load_data.keys())[:10]}...")
                        return 0.0
            
            # Get ventilation rate_ach using the matched zone key
            zone_loads = load_data[matched_zone_key].get('loads', {})
            logger.info(f"Zone '{zone_name}' (matched to '{matched_zone_key}') - zone_loads keys: {list(zone_loads.keys()) if zone_loads else 'None'}")
            
            ventilation_data = zone_loads.get('ventilation', {}) if zone_loads else {}
            logger.info(f"Zone '{zone_name}' - ventilation_data keys: {list(ventilation_data.keys()) if ventilation_data else 'None'}")
            logger.info(f"Zone '{zone_name}' - full ventilation_data: {ventilation_data}")
            
            rate_ach = ventilation_data.get('rate_ach', 0.0) or 0.0
            logger.info(f"Zone '{zone_name}' - extracted rate_ach: {rate_ach} (type: {type(rate_ach)})")
            
            # Apply ceiling for values very close to integers (e.g., 0.9999 -> 1.0)
            # This handles floating-point precision issues where values should be whole numbers
            import math
            if abs(rate_ach - round(rate_ach)) < 0.01:  # If within 0.01 of a whole number
                rate_ach_adjusted = math.ceil(rate_ach)
                if rate_ach_adjusted != rate_ach:
                    logger.info(f"Zone '{zone_name}' - adjusting rate_ach from {rate_ach} to {rate_ach_adjusted} (ceiling applied)")
                    rate_ach = rate_ach_adjusted
            
            # Apply bonus table
            bonus = 0.0
            bonus_reason = ""
            if rate_ach < 1:
                bonus = 0.0
                bonus_reason = f"rate_ach ({rate_ach}) < 1"
            elif 1 <= rate_ach < 3:
                bonus = 0.1
                bonus_reason = f"1 ≤ rate_ach ({rate_ach}) < 3"
            elif 3 <= rate_ach < 5:
                bonus = 0.12
                bonus_reason = f"3 ≤ rate_ach ({rate_ach}) < 5"
            elif 5 <= rate_ach < 10:
                bonus = 0.16
                bonus_reason = f"5 ≤ rate_ach ({rate_ach}) < 10"
            else:  # rate_ach >= 10
                bonus = 0.20
                bonus_reason = f"rate_ach ({rate_ach}) ≥ 10"
                
            logger.info(f"Zone '{zone_name}' - BONUS RESULT: {bonus_reason} → bonus={bonus}")
            return bonus
                
        except Exception as e:
            logger.error(f"Error calculating natural ventilation bonus for zone '{zone_name}': {e}", exc_info=True)
            return 0.0

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

    def _create_table_row_for_zone(self, zone_name: str, data_for_zone: dict, model_year, table_data: list, safe_float):
        """Helper method to create a table row for an individual zone."""
        
        # Check if this is a zone from an expanded group
        logger.info(f"=== Individual zone data lookup for zone '{zone_name}' ===")
        logger.info(f"data_for_zone.is_group: {data_for_zone.get('is_group', False)}")
        logger.info(f"data_for_zone has 'grouped_zones': {'grouped_zones' in data_for_zone}")
        
        if data_for_zone.get('is_group', False) and 'grouped_zones' in data_for_zone:
            logger.info(f"Zone '{zone_name}' is from an expanded group")
            logger.info(f"Group contains zones: {data_for_zone.get('grouped_zones', [])}")
            
            # This zone is part of a group - use the original individual zone data
            logger.info(f"Looking up individual zone data for key: '{zone_name}'")
            logger.info(f"Total zones in energy_data_by_area: {len(self.energy_data_by_area)}")
            
            individual_zone_data = self.energy_data_by_area.get(zone_name, {})
            
            logger.info(f"Zone '{zone_name}' (from group): individual_zone_data found: {bool(individual_zone_data)}")
            if individual_zone_data:
                logger.info(f"Zone '{zone_name}': individual_zone_data keys: {list(individual_zone_data.keys())}")
                logger.info(f"Zone '{zone_name}': lighting={individual_zone_data.get('lighting', 'N/A')}, heating={individual_zone_data.get('heating', 'N/A')}, cooling={individual_zone_data.get('cooling', 'N/A')}")
                logger.info(f"Zone '{zone_name}': area={individual_zone_data.get('individual_zone_floor_area', 'N/A')}, multiplier={individual_zone_data.get('multiplier', 'N/A')}")
            else:
                # Try to find similar zone names in the data
                similar_zones = [k for k in self.energy_data_by_area.keys() if zone_name.lower() in k.lower() or k.lower() in zone_name.lower()]
                logger.error(f"Zone '{zone_name}': No individual zone data found!")
                logger.error(f"Zone '{zone_name}': Similar zones: {similar_zones[:3]}")
                logger.error(f"Zone '{zone_name}': All available zones: {list(self.energy_data_by_area.keys())}")
                
                # Try exact string match debugging
                exact_matches = [k for k in self.energy_data_by_area.keys() if k == zone_name]
                logger.error(f"Zone '{zone_name}': Exact matches: {exact_matches}")
                
                # Check for case sensitivity issues
                case_insensitive_matches = [k for k in self.energy_data_by_area.keys() if k.lower() == zone_name.lower()]
                logger.error(f"Zone '{zone_name}': Case insensitive matches: {case_insensitive_matches}")
            
            if individual_zone_data:
                # Use individual zone data
                current_zone_floor_area = safe_float(individual_zone_data.get('individual_zone_floor_area', 0.0), 0.0)
                abs_lighting = safe_float(individual_zone_data.get('lighting', 0.0), 0.0)
                abs_heating = safe_float(individual_zone_data.get('heating', 0.0), 0.0)
                abs_cooling = safe_float(individual_zone_data.get('cooling', 0.0), 0.0)
                zone_multiplier = individual_zone_data.get('multiplier', 1)
            else:
                # Fallback: try to use the group's total values divided by number of zones in group
                if 'grouped_zones' in data_for_zone:
                    num_zones_in_group = len(data_for_zone['grouped_zones'])
                    logger.warning(f"Fallback: Using group values divided by {num_zones_in_group} zones for zone '{zone_name}'")
                    # Use fallback values from the group data
                    current_zone_floor_area = safe_float(data_for_zone.get('individual_zone_floor_area', 0.0), 0.0) / num_zones_in_group if num_zones_in_group > 0 else 0.0
                    abs_lighting = safe_float(data_for_zone.get('lighting', 0.0), 0.0) / num_zones_in_group if num_zones_in_group > 0 else 0.0
                    abs_heating = safe_float(data_for_zone.get('heating', 0.0), 0.0) / num_zones_in_group if num_zones_in_group > 0 else 0.0 
                    abs_cooling = safe_float(data_for_zone.get('cooling', 0.0), 0.0) / num_zones_in_group if num_zones_in_group > 0 else 0.0
                    zone_multiplier = 1  # Groups don't have multipliers
                    logger.warning(f"Fallback values for zone '{zone_name}': lighting={abs_lighting:.1f}, heating={abs_heating:.1f}, cooling={abs_cooling:.1f}")
                else:
                    # Last resort: use zero values
                    current_zone_floor_area = 0.0
                    abs_lighting = 0.0
                    abs_heating = 0.0 
                    abs_cooling = 0.0
                    zone_multiplier = 1
            
            logger.info(f"Zone '{zone_name}' (from group): using individual values - area={current_zone_floor_area}, multiplier={zone_multiplier}, lighting={abs_lighting:.1f}, heating={abs_heating:.1f}, cooling={abs_cooling:.1f}")
            
        else:
            # Regular individual zone - use values directly
            current_zone_floor_area = safe_float(data_for_zone.get('individual_zone_floor_area', 0.0), 0.0)
            abs_lighting = safe_float(data_for_zone.get('lighting', 0.0), 0.0)
            abs_heating = safe_float(data_for_zone.get('heating', 0.0), 0.0)
            abs_cooling = safe_float(data_for_zone.get('cooling', 0.0), 0.0)
            zone_multiplier = data_for_zone.get('multiplier', 1)

        report_floor_id = data_for_zone.get('floor_id_report', 'N/A')
        report_area_id = data_for_zone.get('area_id_report', 'N/A')
        
        # Check if this is office ISO
        is_office_iso = isinstance(model_year, str) and 'office' in model_year.lower()
        
        # Check if this zone is part of a group for per-area calculations
        is_zone_from_group = data_for_zone.get('is_group', False) and 'grouped_zones' in data_for_zone
        
        if is_zone_from_group:
            # For zones in groups: use INDIVIDUAL zone values divided by GROUP total area
            group_total_area = safe_float(data_for_zone.get('total_area', 0.0), 0.0)
            
            logger.info(f"Zone '{zone_name}' (from group): Using individual zone values divided by GROUP total area")
            logger.info(f"Individual zone values - lighting:{abs_lighting:.1f}, heating:{abs_heating:.1f}, cooling:{abs_cooling:.1f}")
            logger.info(f"Group total area: {group_total_area:.1f}")
            
            if group_total_area > 0:
                val_lighting = abs_lighting / group_total_area
                val_heating = abs_heating / group_total_area
                val_cooling = abs_cooling / group_total_area
                val_total = (abs_lighting + abs_heating + abs_cooling) / group_total_area
                logger.info(f"Per-area values (individual/group_area) - lighting:{val_lighting:.3f}, heating:{val_heating:.3f}, cooling:{val_cooling:.3f}")
            else:
                logger.warning(f"Group area is 0 for zone '{zone_name}'. Using absolute individual zone values.")
                val_lighting = abs_lighting
                val_heating = abs_heating
                val_cooling = abs_cooling
                val_total = abs_lighting + abs_heating + abs_cooling
        elif is_office_iso:
            # Office ISO: use individual zone area for calculations
            if current_zone_floor_area > 0:
                val_lighting = abs_lighting / current_zone_floor_area
                val_heating = abs_heating / current_zone_floor_area
                val_cooling = abs_cooling / current_zone_floor_area
                val_total = (abs_lighting + abs_heating + abs_cooling) / current_zone_floor_area
            else:
                logger.debug(f"Office ISO: Individual zone area is 0 for zone '{zone_name}'. Energy values will be absolute.")
                val_lighting = abs_lighting
                val_heating = abs_heating
                val_cooling = abs_cooling
                val_total = abs_lighting + abs_heating + abs_cooling
        else:
            # Non-office individual zones: use individual zone area for calculations
            if current_zone_floor_area > 0:
                val_lighting = abs_lighting / current_zone_floor_area
                val_heating = abs_heating / current_zone_floor_area
                val_cooling = abs_cooling / current_zone_floor_area
                val_total = (abs_lighting + abs_heating + abs_cooling) / current_zone_floor_area
            else:
                logger.warning(f"Zone area is 0 for zone '{zone_name}'. Energy values in report will be absolute (not per m^2).")
                val_lighting = abs_lighting
                val_heating = abs_heating
                val_cooling = abs_cooling
                val_total = abs_lighting + abs_heating + abs_cooling

        # Calculate natural ventilation bonus (only for 2023 ISO)
        logger.info(f"=== Natural ventilation bonus check for zone '{zone_name}' ===")
        logger.info(f"Model year: {model_year} (type: {type(model_year)})")
        logger.info(f"Is 2023 model: {model_year == 2023}")
        
        if model_year == 2023:
            logger.info(f"Calculating natural ventilation bonus for 2023 ISO model, zone '{zone_name}'")
            natural_bonus = self._calculate_natural_ventilation_bonus(zone_name)
            logger.info(f"Natural ventilation bonus result for zone '{zone_name}': {natural_bonus}")
        else:
            natural_bonus = 0.0  # No bonus for non-2023 models
            logger.info(f"No natural ventilation bonus for non-2023 model (model_year={model_year})")
        
        # Determine group key for this zone
        group_key = None
        if data_for_zone.get('is_group', False):
            # This zone is from a group - extract the group key from the data
            group_key = data_for_zone.get('group_key')  # Use the group_key from the GROUP_ entry
        
        # Base row structure for all models
        row = {
            'floor_id_report': report_floor_id,
            'area_id_report': report_area_id,
            'zone_id': zone_name,  # Use individual zone name
            'zone_name_report': zone_name,  # Display individual zone name
            'group_key': group_key,  # Add group key for proper grouping in report generator
            'multiplier': zone_multiplier,
            'total_area': current_zone_floor_area,
            'lighting': val_lighting,  # per-m² values for table display
            'heating': val_heating,
            'cooling': val_cooling,
            'total': val_total,
            'location': data_for_zone.get('location', 'Unknown'),
            'model_csv_area_description': data_for_zone.get('location', 'Unknown'),
            'energy_consumption_model': '',
            'better_percent': '',
            'energy_rating': '',
        }
        
        # Add natural bonus column only for 2023 models
        if model_year == 2023:
            row['natural_bonus'] = natural_bonus
            
        table_data.append(row)

    def get_energy_rating_table_data(self, model_year=None) -> List[Dict[str, Any]]:
        """
        Get data for energy rating reports in table format.
        This method iterates over self.energy_data_by_area (keyed by full_zone_id)
        and extracts/calculates values for the rating table.
        Returns an empty list if not processed or if errors occur.
        """
        logger.info(f"EnergyRatingParser.get_energy_rating_table_data called with model_year: {model_year}")
        logger.info(f"EnergyRatingParser processed status: {self.processed}")
        logger.info(f"EnergyRatingParser energy_data_by_area has {len(self.energy_data_by_area)} entries")
        
        table_data: List[Dict[str, Any]] = []
        if not self.processed:
            logger.warning("Energy data not processed. Call process_output() first. Returning empty list for rating table.")
            return table_data
        if not self.energy_data_by_area:
            logger.warning("EnergyRatingParser.get_energy_rating_table_data: energy_data_by_area is empty")
            return table_data
        
        logger.info(f"EnergyRatingParser.get_energy_rating_table_data: Processing {len(self.energy_data_by_area)} zones")

        try:
            # Check if this is office ISO
            is_office_iso = isinstance(model_year, str) and 'office' in model_year.lower()
            
            # For office ISO: each zone is individual, for others: group by floor/area
            if is_office_iso:
                # Office ISO: no grouping needed, each zone is individual
                logger.info("Office ISO detected - using individual zone calculations")
            else:
                # Non-office: grouped zones already have correct total areas, so no need for complex summing
                floor_area_id_sums: Dict[tuple[str, str], float] = {}

            # Filter zones: show grouped zones + individual zones that are not part of any group
            filtered_zones = {}
            if is_office_iso:
                # Office ISO: show all individual zones (no grouping)
                filtered_zones = {k: v for k, v in self.energy_data_by_area.items() if not k.startswith('GROUP_')}
            else:
                # Non-office: show grouped zones + ungrouped individual zones
                # First, collect all zone IDs that are part of groups
                grouped_zone_ids = set()
                for zone_key, zone_data in self.energy_data_by_area.items():
                    if zone_key.startswith('GROUP_') and 'grouped_zones' in zone_data:
                        grouped_zone_ids.update(zone_data['grouped_zones'])
                
                # Include GROUP_ zones and individual zones not in any group
                for zone_key, zone_data in self.energy_data_by_area.items():
                    if zone_key.startswith('GROUP_'):
                        # Always include grouped zones
                        filtered_zones[zone_key] = zone_data
                    elif zone_key not in grouped_zone_ids:
                        # Include individual zones that are not part of any group
                        filtered_zones[zone_key] = zone_data
            
            logger.info(f"Filtered zones for table: {len(filtered_zones)} out of {len(self.energy_data_by_area)} total zones (office_iso={is_office_iso})")
            
            for full_zone_id_key, data_for_zone in filtered_zones.items():
                try:
                    # Check if this is a grouped zone that needs to be expanded
                    if full_zone_id_key.startswith('GROUP_') and 'grouped_zones' in data_for_zone:
                        # Expand group into individual rows, one for each zone
                        grouped_zone_list = data_for_zone['grouped_zones']
                        logger.info(f"=== Expanding group '{full_zone_id_key}' ===")
                        logger.info(f"Group will be expanded into {len(grouped_zone_list)} individual rows")
                        logger.info(f"Individual zones in group: {grouped_zone_list}")
                        logger.info(f"Group totals: L={data_for_zone.get('lighting', 0)}, H={data_for_zone.get('heating', 0)}, C={data_for_zone.get('cooling', 0)}")
                        
                        for i, individual_zone_name in enumerate(grouped_zone_list):
                            logger.info(f"Creating row {i+1}/{len(grouped_zone_list)} for individual zone: '{individual_zone_name}'")
                            # Create a row for each zone in the group with shared energy data
                            self._create_table_row_for_zone(
                                individual_zone_name, data_for_zone, model_year, table_data, safe_float
                            )
                    else:
                        # Regular individual zone
                        self._create_table_row_for_zone(
                            full_zone_id_key, data_for_zone, model_year, table_data, safe_float
                        )
                except (TypeError, KeyError) as e_row:
                    logger.error(f"Error creating table row for full_zone_id_key '{full_zone_id_key}': {e_row}. Skipping this zone.", exc_info=True)
                    continue
            logger.info(f"EnergyRatingParser.get_energy_rating_table_data: Returning {len(table_data)} rows")
            return table_data
        except Exception as e:
            logger.error(f"Unexpected error generating energy rating table data: {e}", exc_info=True)
            return []