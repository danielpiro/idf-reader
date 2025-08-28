"""
Extracts and processes energy consumption and rating information from EnergyPlus output files.
"""
from typing import Dict, Any, List, Optional
import re
import csv
import os
import logging
from parsers.area_parser import AreaParser
from .utils import safe_float
from .base_parser import CSVOutputParser

logger = logging.getLogger(__name__)


class EnergyRatingParser(CSVOutputParser):
    """
    Processes energy consumption data from EnergyPlus output files (eplusout.csv).
    Uses area data from AreaParser for energy per area calculations.
    """
    def __init__(self, data_loader, area_parser: AreaParser, csv_path: Optional[str] = None):
        try:
            super().__init__(data_loader, csv_path, "EnergyRatingParser")
            
            if area_parser is None:
                raise ValueError("AreaParser instance cannot be None.")

            self.area_parser = area_parser
            self.energy_data_by_area: Dict[str, Dict[str, Any]] = {}
            # No complex regex patterns needed - using simple containment checks
        except ValueError as ve:
            self.logger.error(f"Initialization error in EnergyRatingParser: {ve}", exc_info=True)
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error during EnergyRatingParser initialization: {e}", exc_info=True)
            self.energy_data_by_area = {}
            self.processed = False
            raise

    def process_idf(self, idf=None) -> None:
        """
        Process IDF data. For EnergyRatingParser, this delegates to process_output 
        which handles CSV output processing from EnergyPlus simulation.
        
        Args:
            idf: Optional IDF object (not used for CSV output processing)
        """
        try:
            self.process_output()
        except Exception as e:
            self.logger.error(f"Error in EnergyRatingParser process_idf: {e}", exc_info=True)
            self.processed = False
            raise

    def process_output(self, output_file_path: Optional[str] = None) -> None:
        """
        Process EnergyPlus output file (eplusout.csv) to extract energy consumption data.
        """
        self.logger.info("ENERGY RATING DEBUG - Starting process_output")
        
        # Log available zones from area_parser for comparison
        if self.area_parser and self.area_parser.processed and self.area_parser.areas_by_zone:
            area_parser_zones = list(self.area_parser.areas_by_zone.keys())
            self.logger.info(f"ENERGY RATING DEBUG - Area parser has {len(area_parser_zones)} zones available")
            self.logger.info(f"ENERGY RATING DEBUG - Sample area parser zones: {area_parser_zones[:5]}")
        else:
            self.logger.warning("ENERGY RATING DEBUG - Area parser not available or not processed")
        
        if self.processed:
            return
        # No pattern validation needed for containment-based approach

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
                        self.logger.warning("Could not automatically find eplusout.csv based on IDF path or fallback locations.")
                else:
                    self.logger.warning("IDF path not available from DataLoader, cannot automatically find eplusout.csv.")
            else:
                final_output_file_path = output_file_path

            if final_output_file_path and os.path.basename(final_output_file_path).lower() == "eplustbl.csv":
                candidate_out = os.path.join(os.path.dirname(final_output_file_path), "eplusout.csv")
                if os.path.exists(candidate_out):
                    final_output_file_path = candidate_out
                else:
                    self.logger.warning(f"eplustbl.csv provided, but eplusout.csv not found in the same directory ({os.path.dirname(final_output_file_path)}).")

            if not final_output_file_path or not os.path.exists(final_output_file_path):
                self.logger.error(f"PROCESS_OUTPUT DEBUG - EnergyPlus output file (eplusout.csv) not found. Tried path: {final_output_file_path if final_output_file_path else 'auto-detection failed'}.")
                # Log all candidate paths that were tried
                if 'candidate_paths' in locals():
                    for i, path in enumerate(candidate_paths):
                        exists = os.path.exists(path)
                self.processed = False
                return
            

            if not self.area_parser.processed:
                try:
                    self.area_parser.process_idf(None)
                except Exception as ap_e:
                    self.logger.error(f"Error processing area data via AreaParser: {ap_e}. Energy processing may be incomplete.", exc_info=True)
            else:
                pass

            with open(final_output_file_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)
                headers = next(reader, None)
                if headers is None:
                    self.logger.error(f"CSV file '{final_output_file_path}' is empty or has no headers.")
                    self.processed = False
                    return

                # Log a sample of headers to see what we're working with
                sample_headers = headers[:5] + (['...'] if len(headers) > 5 else [])

                last_row = None
                for row in reader:
                    last_row = row

                if not last_row:
                    self.logger.error(f"No data rows found in EnergyPlus output file '{final_output_file_path}'.")
                    self.processed = False
                    return

                self._process_headers_and_values(headers, last_row)
            self._calculate_totals()
            self.processed = True

        except FileNotFoundError:
            self.logger.error(f"EnergyPlus output file not found (should have been caught earlier): {final_output_file_path}", exc_info=True)
            self.processed = False
        except StopIteration:
            self.logger.error(f"CSV file '{final_output_file_path}' seems to be empty after headers.", exc_info=True)
            self.processed = False
        except csv.Error as csv_e:
            self.logger.error(f"CSV formatting error in '{final_output_file_path}': {csv_e}", exc_info=True)
            self.processed = False
        except ValueError as val_e:
            self.logger.error(f"ValueError during processing of '{final_output_file_path}': {val_e}", exc_info=True)
            self.processed = False
        except RuntimeError as run_e:
            self.logger.error(f"RuntimeError during processing of '{final_output_file_path}': {run_e}", exc_info=True)
            self.processed = False
        except Exception as e:
            self.logger.error(f"Unexpected error processing EnergyPlus output file '{final_output_file_path}': {e}", exc_info=True)
            self.processed = False

    def _process_headers_and_values(self, headers: List[str], values: List[str]) -> None:
        """
        Process headers to extract zone information and corresponding values.
        """
        self.logger.info(f"ENERGY RATING DEBUG - Processing {len(headers)} headers and {len(values)} values")
        
        self.energy_data_by_area = {}
        if not headers or not values:
            self.logger.warning("Headers or values list is empty in _process_headers_and_values. Skipping.")
            return
        
        # Track which zones we find in the CSV headers
        found_zones = set()
        processed_zones = set()
        skipped_headers = []
        # No pattern validation needed for containment-based approach

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
                # Log all headers to see what we're filtering out
                if i <= 10:  # Log first 10 headers for debugging
                    pass
                # Simple containment check - zone_id + energy type
                zones = self.data_loader.get_zones() if hasattr(self.data_loader, 'get_zones') else {}
                matched_zone_key = None
                
                # Find zone that appears in the header
                for zone_name in zones.keys():
                    if zone_name in header:
                        matched_zone_key = zone_name
                        found_zones.add(zone_name)
                        break
                
                # Check for energy type in header
                header_lower = header.lower()
                has_energy_type = ('light' in header_lower or 
                                 'heating' in header_lower or 
                                 'cooling' in header_lower)
                
                # Skip if no zone found or no energy type
                if not matched_zone_key or not has_energy_type:
                    continue
                
                # Check if this is a RunPeriod measurement
                if "(RunPeriod)" not in header:
                    continue
                
                total_headers_with_X += 1
                matched_headers += 1
                
                # Extract zone details from DataLoader
                zone_data = zones[matched_zone_key]
                
                # Apply correct floor and zone extraction rules
                floor, zone_name_from_header = self._extract_floor_and_zone(matched_zone_key)
                area_id_from_header = zone_data.get('area_id', matched_zone_key)

                value_str = values[i] if i < len(values) else "0.0"
                value = safe_float(value_str, 0.0)
                processed_value = self._process_value(value, header.lower())

                # Use the matched zone key directly
                full_zone_id_key = matched_zone_key
                zone_keys_found.add(full_zone_id_key)

                if full_zone_id_key not in self.energy_data_by_area:
                    zone_multiplier = 1
                    individual_zone_floor_area = 0.0

                    
                    # If we found a matching zone, get its data from area_parser (which has CSV-corrected values)
                    if matched_zone_key and self.area_parser and self.area_parser.processed:
                        # Try to get from area_parser first (has CSV-corrected values)
                        area_parser_zones = self.area_parser.areas_by_zone
                        if matched_zone_key in area_parser_zones:
                            ap_zone_data = area_parser_zones[matched_zone_key]
                            zone_multiplier = int(ap_zone_data.get('multiplier', 1))
                            individual_zone_floor_area = safe_float(ap_zone_data.get('floor_area', 0.0), 0.0)
                            self.logger.debug(f"Using area_parser zone data for '{matched_zone_key}': floor_area={individual_zone_floor_area}")
                        elif matched_zone_key in all_zones_data_from_loader:
                            # Fallback to data_loader if not in area_parser
                            dl_zone_data = all_zones_data_from_loader[matched_zone_key]
                            zone_multiplier = int(dl_zone_data.get('multiplier', 1))
                            individual_zone_floor_area = safe_float(dl_zone_data.get('floor_area', 0.0), 0.0)
                            self.logger.warning(f"Using data_loader zone data for '{matched_zone_key}' (not found in area_parser): floor_area={individual_zone_floor_area}")
                    elif matched_zone_key and isinstance(all_zones_data_from_loader, dict) and matched_zone_key in all_zones_data_from_loader:
                        # Fallback when area_parser not available
                        dl_zone_data = all_zones_data_from_loader[matched_zone_key]
                        zone_multiplier = int(dl_zone_data.get('multiplier', 1))
                        individual_zone_floor_area = safe_float(dl_zone_data.get('floor_area', 0.0), 0.0)
                        self.logger.warning(f"Using data_loader zone data for '{matched_zone_key}' (area_parser not processed): floor_area={individual_zone_floor_area}")
                    else:
                        # No matching zone found from CSV parsing, try direct DataLoader lookup
                        direct_zone_lookup = None
                        if area_id_from_header in all_zones_data_from_loader:
                            direct_zone_lookup = area_id_from_header
                        
                        # For standard patterns, try simple containment check
                        if not direct_zone_lookup:
                            for zone_name in all_zones_data_from_loader.keys():
                                # Check if zone contains the floor and area parts
                                # Handle floor mapping: '00' might map to '01', '01' to '01', '02' to '02' etc.
                                floor_matches = (
                                    floor in zone_name or 
                                    (floor == '00' and '01' in zone_name) or  # Floor 00 might be Floor 01
                                    (floor == '01' and '01' in zone_name) or
                                    (floor == '02' and '02' in zone_name)
                                )
                                area_matches = area_id_from_header in zone_name
                                
                                if floor_matches and area_matches:
                                    direct_zone_lookup = zone_name
                                    break
                        
                        if direct_zone_lookup:
                            # Try area_parser first, then fallback to data_loader
                            if self.area_parser and self.area_parser.processed and direct_zone_lookup in self.area_parser.areas_by_zone:
                                ap_zone_data = self.area_parser.areas_by_zone[direct_zone_lookup]
                                zone_multiplier = int(ap_zone_data.get('multiplier', 1))
                                individual_zone_floor_area = safe_float(ap_zone_data.get('floor_area', 0.0), 0.0)
                                self.logger.debug(f"Using area_parser zone data for direct lookup '{direct_zone_lookup}': floor_area={individual_zone_floor_area}")
                            else:
                                dl_zone_data = all_zones_data_from_loader[direct_zone_lookup]
                                zone_multiplier = int(dl_zone_data.get('multiplier', 1))
                                individual_zone_floor_area = safe_float(dl_zone_data.get('floor_area', 0.0), 0.0)
                                self.logger.warning(f"Using data_loader zone data for direct lookup '{direct_zone_lookup}': floor_area={individual_zone_floor_area}")
                        else:
                            # Try fuzzy matching by looking for zones that contain parts of the key
                            fuzzy_match = None
                            for zone_name in all_zones_data_from_loader.keys():
                                if area_id_from_header in zone_name or zone_name in area_id_from_header:
                                    fuzzy_match = zone_name
                                    break
                            
                            if fuzzy_match:
                                # Try area_parser first, then fallback to data_loader
                                if self.area_parser and self.area_parser.processed and fuzzy_match in self.area_parser.areas_by_zone:
                                    ap_zone_data = self.area_parser.areas_by_zone[fuzzy_match]
                                    zone_multiplier = int(ap_zone_data.get('multiplier', 1))
                                    individual_zone_floor_area = safe_float(ap_zone_data.get('floor_area', 0.0), 0.0)
                                    self.logger.debug(f"Using area_parser zone data for fuzzy match '{fuzzy_match}': floor_area={individual_zone_floor_area}")
                                else:
                                    dl_zone_data = all_zones_data_from_loader[fuzzy_match]
                                    zone_multiplier = int(dl_zone_data.get('multiplier', 1))
                                    individual_zone_floor_area = safe_float(dl_zone_data.get('floor_area', 0.0), 0.0)
                                    self.logger.warning(f"Using data_loader zone data for fuzzy match '{fuzzy_match}': floor_area={individual_zone_floor_area}")
                            else:
                                # Still no match, use defaults
                                zone_keys_missing.add(full_zone_id_key)
                                self.logger.warning(f"EnergyRatingParser: No matching zone found for '{full_zone_id_key}'. Using defaults for multiplier/floor_area.")

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
                    
                    # Track successful zone processing
                    if matched_zone_key:
                        processed_zones.add(matched_zone_key)

                # Determine energy category from header
                if 'light' in header_lower: 
                    category = 'lighting'
                elif 'heating' in header_lower: 
                    category = 'heating'
                elif 'cooling' in header_lower: 
                    category = 'cooling'
                else:
                    continue  # Skip if not a recognized energy type

                # Add energy value to the appropriate category
                if category in self.energy_data_by_area[full_zone_id_key]:
                    # Divide by zone multiplier to get per-zone energy consumption
                    # EnergyPlus output shows total energy for all multiplied zones
                    zone_multiplier = self.energy_data_by_area[full_zone_id_key].get('multiplier', 1)
                    per_zone_value = processed_value / zone_multiplier if zone_multiplier > 0 else processed_value
                    self.energy_data_by_area[full_zone_id_key][category] += per_zone_value

            except IndexError:
                self.logger.error(f"IndexError while processing header '{header}' at index {i}. Values list length: {len(values)}. Skipping.", exc_info=True)
                continue
            except (TypeError, ValueError) as e_val:
                self.logger.error(f"ValueError/TypeError processing header '{header}' or its value: {e_val}. Skipping.", exc_info=True)
                continue
            except Exception as e:
                self.logger.error(f"Unexpected error processing header '{header}': {e}. Skipping this header.", exc_info=True)
                continue
        
        # Report comprehensive processing results
        self.logger.info(f"ENERGY RATING DEBUG - Zone processing summary:")
        self.logger.info(f"  - Found {len(found_zones)} unique zones in CSV headers")
        self.logger.info(f"  - Processed {len(processed_zones)} zones successfully") 
        self.logger.info(f"  - Created energy data for {len(self.energy_data_by_area)} zone entries")
        self.logger.info(f"  - Skipped {len(skipped_headers)} headers")
        
        if found_zones:
            self.logger.info(f"ENERGY RATING DEBUG - Found zones: {sorted(list(found_zones))[:10]}...")
            
        # Compare with area_parser zones
        if self.area_parser and self.area_parser.processed and self.area_parser.areas_by_zone:
            area_parser_zones = set(self.area_parser.areas_by_zone.keys())
            missing_from_energy = area_parser_zones - found_zones
            extra_in_energy = found_zones - area_parser_zones
            
            if missing_from_energy:
                self.logger.warning(f"ENERGY RATING DEBUG - {len(missing_from_energy)} zones in area_parser but NOT found in energy CSV: {sorted(list(missing_from_energy))[:10]}...")
            if extra_in_energy:
                self.logger.info(f"ENERGY RATING DEBUG - {len(extra_in_energy)} zones found in energy CSV but not in area_parser: {sorted(list(extra_in_energy))[:5]}...")
        
        if zone_keys_missing:
            self.logger.warning(f"Zone keys found in eplusout.csv but missing from IDF: {len(zone_keys_missing)} zones")
        
        if unmatched_headers:
            self.logger.warning(f"Headers with 'X' that didn't match regex pattern: {len(unmatched_headers)} headers")
            # Show first few unmatched headers for debugging
            sample_unmatched = unmatched_headers[:3]

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
                self.logger.warning(f"Header '{header_lower}' did not match known energy categories for unit conversion. Original value: {value} returned.")
                processed_val = value

            return processed_val
        except TypeError:
            self.logger.error(f"Cannot process non-numeric value '{value}' for header '{header_lower}'. Returning 0.0.", exc_info=True)
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
                    self.logger.debug(f"Total area for grouping related to '{full_zone_id_key}' is {total_area_group}. Per-area values will be set to absolute energy values (or 0 if energy is 0).")
                    data_for_zone['lighting_per_area'] = lighting
                    data_for_zone['heating_per_area'] = heating
                    data_for_zone['cooling_per_area'] = cooling
                    data_for_zone['total_per_area'] = data_for_zone['total']

            except (TypeError, KeyError, ZeroDivisionError) as e:
                self.logger.error(f"Error calculating totals for zone '{full_zone_id_key}': {e}. Data for this zone might be incomplete.", exc_info=True)
                data_for_zone.setdefault('total', 0.0)
                data_for_zone.setdefault('lighting_per_area', 0.0)
                data_for_zone.setdefault('heating_per_area', 0.0)
                data_for_zone.setdefault('cooling_per_area', 0.0)
                data_for_zone.setdefault('total_per_area', 0.0)
            except Exception as e_unexp:
                 self.logger.critical(f"Unexpected error calculating totals for {e_unexp}.", exc_info=True)

    def _get_area_total_for_area_id(self, area_id: str) -> float:
        """
        Get the total floor area for a specific area ID from AreaParser.
        Returns 0.0 if area_id is not found or an error occurs.
        """
        if not area_id:
            self.logger.warning("_get_area_total_for_area_id called with empty area_id. Returning 0.0.")
            return 0.0
        try:
            if not self.area_parser or not self.area_parser.processed:
                self.logger.warning(f"AreaParser not available or not processed when getting total for area_id '{area_id}'. Returning 0.0.")
                return 0.0

            area_totals = self.area_parser.get_area_totals(area_id)
            result = safe_float(area_totals.get("total_floor_area", 0.0), 0.0)
            return result
        except AttributeError:
            self.logger.error(f"AttributeError accessing AreaParser for area_id '{area_id}'. Returning 0.0.", exc_info=True)
            return 0.0
        except Exception as e:
            self.logger.error(f"Error getting total area for area_id '{area_id}': {e}. Returning 0.0.", exc_info=True)
            return 0.0

    def _extract_floor_and_zone(self, zone_id: str) -> tuple[str, str]:
        """
        Extract floor and zone based on zone ID format.
        Rules (for energy report columns only):
        - A:BXC → floor = A, zone = BXC
        - A:B → floor = A, zone = B  
        - A → floor = A, zone = A
        """
        if not zone_id:
            return 'Unknown', 'Unknown'
        
        try:
            # Check for patterns with colon
            if ':' in zone_id:
                # Split on colon: A:BXC becomes ['A', 'BXC']
                colon_parts = zone_id.split(':', 1)  # Split on first colon only
                if len(colon_parts) >= 2:
                    floor = colon_parts[0]  # A (floor)
                    zone = colon_parts[1]   # BXC (zone - everything after colon)
                    self.logger.debug(f"Parsed colon format '{zone_id}': floor='{floor}', zone='{zone}'")
                    return floor, zone
                # Fallback if parsing fails
                return zone_id, zone_id
            
            # Check for A pattern (no : and no X)
            else:
                # Both floor and zone are the same
                return zone_id, zone_id
                
        except Exception as e:
            self.logger.error(f"Error extracting floor and zone from '{zone_id}': {e}")
            return 'Unknown', 'Unknown'

    def _determine_location(self, area_id: str) -> str:
        """
        Determine the location type for an area ID using AreaParser's H-value data.
        Falls back to intelligent floor detection based on the building structure.
        For the CSV model lookup, we need to map to valid location types.
        """
        
        if not area_id:
            self.logger.warning("_determine_location called with empty area_id. Returning default location.")
            return "Intermediate Floor & Intermediate ceiling"
        
        try:
            # First try to get location from AreaParser H-values
            if self.area_parser and self.area_parser.processed:
                area_h_values = self.area_parser.get_area_h_values()
                if area_h_values:
                    
                    # Debug: log all area_ids in H-values
                    h_value_area_ids = [area_data.get('area_id', 'None') for area_data in area_h_values]
                    
                    # Try direct match first
                    for area_data in area_h_values:
                        h_area_id = area_data.get('area_id', '')
                        if h_area_id == area_id:
                            location = area_data.get('location', '')
                            if location and location != 'Unknown':
                                return location
                    
                    # Try flexible matching - handle different area_id formats
                    # area_id from header might be '01', but H-value might have '00:01'  
                    for area_data in area_h_values:
                        h_area_id = area_data.get('area_id', '')
                        
                        # Check if header area_id matches the end of H-value area_id 
                        # Handle formats like '01' matching '00X01:01' or '00:01'
                        if ':' in h_area_id and h_area_id.endswith(f':{area_id}'):
                            location = area_data.get('location', '')
                            if location and location != 'Unknown':
                                return location
                                
                        # Also check if header area_id contains H-value area_id (e.g., '00:01XLIVING' contains '00:01')
                        if h_area_id in area_id:
                            location = area_data.get('location', '')
                            if location and location != 'Unknown':
                                return location
                else:
                    pass

            # Enhanced fallback logic using floor information
            # Try to get floor information from the data loader or area parser
            floor_info = None
            
            # Try to get floor information from the data loader zone data
            if self.data_loader:
                zones = self.data_loader.get_zones()
                # Look for zones that contain this area_id
                for zone_name, zone_data in zones.items():
                    zone_area_id = zone_data.get('area_id', '')
                    if zone_area_id == area_id:
                        # Try to extract floor from zone name or data
                        if ':' in zone_name:
                            floor_part = zone_name.split(':')[0]
                            if floor_part.isdigit():
                                floor_info = int(floor_part)
                                break
            
            # Determine location based on floor information
            if floor_info is not None:
                if floor_info == 0:  # Ground floor
                    result = "Ground Floor & Intermediate ceiling"
                    return result
                elif floor_info >= 1 and floor_info <= 4:  # Middle floors
                    result = "Intermediate Floor & Intermediate ceiling"
                    return result
                elif floor_info >= 5:  # Upper floors
                    result = "External Floor & External ceiling"
                    return result
            
            # Fallback: try to infer from area_id pattern
            if area_id and len(area_id) >= 2:
                # For patterns like "01", "02", etc.
                if area_id.isdigit():
                    area_num = int(area_id)
                    if area_num <= 5:
                        result = "Ground Floor & Intermediate ceiling"
                        return result
                    elif area_num <= 15:
                        result = "Intermediate Floor & Intermediate ceiling"
                        return result
                    else:
                        result = "External Floor & External ceiling"
                        return result
                
                # For patterns like "E342", "A338", etc.
                first_char = area_id[0].upper()
                if first_char in ['A', 'B', '0', '1']:
                    result = "Ground Floor & Intermediate ceiling"
                    return result
                elif first_char in ['C', 'D', 'E', 'F']:
                    result = "Intermediate Floor & Intermediate ceiling"
                    return result
                elif first_char in ['G', 'H']:
                    result = "External Floor & External ceiling"
                    return result
            
            # Default fallback
            result = "Intermediate Floor & Intermediate ceiling"
            return result
            
        except Exception as e:
            self.logger.error(f"Error determining location for area_id '{area_id}': {e}. Using default.", exc_info=True)
            return "Intermediate Floor & Intermediate ceiling"

    def get_raw_energy_data_by_full_zone_id(self) -> Dict[str, Dict[str, Any]]:
        """
        Get the processed energy data, keyed by full_zone_id, containing absolute energy values.
        Returns an empty dictionary if not processed.
        """
        if not self.processed:
            self.logger.warning("Energy data not processed yet. Call process_output() first. Returning empty dict for raw energy data.")
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
            self.logger.warning("Energy data not processed yet. Call process_output() first. Returning empty dict for get_energy_data_by_area.")
            return {}
        return self.energy_data_by_area

    def get_energy_rating_table_data(self, model_year=None, model_area_definition=None) -> List[Dict[str, Any]]:
        """
        Get data for energy rating reports in table format.
        This method iterates over self.energy_data_by_area (keyed by full_zone_id)
        and extracts/calculates values for the rating table.
        Returns an empty list if not processed or if errors occur.
        """
        
        table_data: List[Dict[str, Any]] = []
        if not self.processed:
            self.logger.warning("GET_ENERGY_RATING_TABLE_DATA DEBUG - Energy data not processed. Call process_output() first. Returning empty list for rating table.")
            return table_data
        if not self.energy_data_by_area:
            self.logger.warning(f"GET_ENERGY_RATING_TABLE_DATA DEBUG - No energy data available. energy_data_by_area is empty")
            return table_data
        
        # Log first few zone keys and their data for debugging
        for i, (zone_key, zone_data) in enumerate(list(self.energy_data_by_area.items())[:3]):
            pass

        try:
            # Check if this is office ISO
            is_office_iso = isinstance(model_year, str) and 'office' in model_year.lower()
            
            # For office ISO: each zone is individual, for others: group by floor/area
            if is_office_iso:
                # Office ISO: no grouping needed, each zone is individual
                # For office mode, we can use area_parser zones directly if available
                if self.area_parser and self.area_parser.processed and self.area_parser.areas_by_zone:
                    self.logger.info(f"OFFICE MODE DEBUG - Using area_parser zones directly for office ISO mode")
                    # Process zones directly from area_parser for office mode
                    for zone_id, area_zone_data in self.area_parser.areas_by_zone.items():
                        if zone_id not in self.energy_data_by_area:
                            # Create energy data entry for zone if it doesn't exist from CSV parsing
                            floor_area = safe_float(area_zone_data.get('floor_area', 0.0), 0.0)
                            multiplier = safe_float(area_zone_data.get('multiplier', 1.0), 1.0)
                            
                            # Extract floor and zone using correct parsing
                            floor_id, zone_name = self._extract_floor_and_zone(zone_id)
                            
                            # Create a basic entry with zero energy values - will be updated if CSV data exists
                            self.energy_data_by_area[zone_id] = {
                                'individual_zone_floor_area': floor_area,
                                'multiplier': multiplier,
                                'abs_lighting': 0.0,
                                'abs_heating': 0.0, 
                                'abs_cooling': 0.0,
                                'floor_id_report': floor_id,
                                'area_id_report': zone_name,  # Use the extracted zone (B from A:BXC)
                            }
                            self.logger.info(f"OFFICE MODE DEBUG - Added zone '{zone_id}' from area_parser: floor_area={floor_area}, multiplier={multiplier}")
                        else:
                            # Update existing entry with correct area_parser values
                            floor_area = safe_float(area_zone_data.get('floor_area', 0.0), 0.0)
                            multiplier = safe_float(area_zone_data.get('multiplier', 1.0), 1.0)
                            self.energy_data_by_area[zone_id]['individual_zone_floor_area'] = floor_area
                            self.energy_data_by_area[zone_id]['multiplier'] = multiplier
                            self.logger.info(f"OFFICE MODE DEBUG - Updated zone '{zone_id}' with area_parser values: floor_area={floor_area}, multiplier={multiplier}")
                else:
                    self.logger.warning("OFFICE MODE DEBUG - area_parser not available, using CSV-parsed zones for office mode")
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
                    # Use floor_area * multiplier to match area report calculation
                    individual_floor_area = safe_float(data_for_zone.get('individual_zone_floor_area', 0.0), 0.0)
                    multiplier = safe_float(data_for_zone.get('multiplier', 1.0), 1.0)
                    current_zone_floor_area = individual_floor_area * multiplier

                    abs_lighting = safe_float(data_for_zone.get('lighting', 0.0), 0.0)
                    abs_heating = safe_float(data_for_zone.get('heating', 0.0), 0.0)
                    abs_cooling = safe_float(data_for_zone.get('cooling', 0.0), 0.0)
                    abs_total = safe_float(data_for_zone.get('total', 0.0), 0.0)

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
                            self.logger.debug(f"Office ISO: Individual zone area is 0 for zone '{full_zone_id_key}'. Energy values will be absolute.")
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
                            self.logger.warning(f"Correct total floor area for group ('{report_floor_id}', '{report_area_id}') is {correct_total_floor_area_for_group} for zone '{full_zone_id_key}'. Energy values in report will be absolute (not per m^2).")
                            val_lighting = abs_lighting
                            val_heating = abs_heating
                            val_cooling = abs_cooling
                            val_total = abs_lighting + abs_heating + abs_cooling

                    # Get CSV model values for energy_consumption_model, better_percent, and energy_rating
                    energy_consumption_model_value = 'N/A'
                    better_percent_value = 'N/A'
                    energy_rating_value = 'N/A'
                    
                    area_location_for_csv = data_for_zone.get('location', 'Unknown')
                    if area_location_for_csv and area_location_for_csv != 'Unknown' and model_year is not None and model_area_definition is not None:
                        try:
                            from utils.data_loader import get_energy_consumption
                            
                            # Determine ISO type for CSV lookup
                            if isinstance(model_year, str) and 'office' in model_year.lower():
                                iso_type_for_lookup = f"MODEL_YEAR_{model_year}"
                            else:
                                iso_type_for_lookup = f"ISO_TYPE_{model_year}_{model_area_definition}"
                            
                            
                            # Get energy consumption from CSV model
                            energy_consumption_model_value = get_energy_consumption(
                                iso_type_input=iso_type_for_lookup,
                                area_location_input=area_location_for_csv,
                                area_definition_input=model_area_definition
                            )
                            
                            
                            # Calculate improvement percentage if we have the model value
                            if energy_consumption_model_value > 0 and val_total > 0:
                                improvement_percent = ((energy_consumption_model_value - val_total) / energy_consumption_model_value) * 100
                                better_percent_value = f"{improvement_percent:.1f}%"
                                
                                
                                # Determine energy rating based on improvement percentage
                                # Using standard rating thresholds
                                if improvement_percent >= 40:
                                    energy_rating_value = "A+"
                                elif improvement_percent >= 30:
                                    energy_rating_value = "A"
                                elif improvement_percent >= 20:
                                    energy_rating_value = "B"
                                elif improvement_percent >= 10:
                                    energy_rating_value = "C"
                                elif improvement_percent >= 0:
                                    energy_rating_value = "D"
                                elif improvement_percent >= -10:
                                    energy_rating_value = "E"
                                else:
                                    energy_rating_value = "F"
                                    
                            
                        except Exception as e:
                            self.logger.warning(f"Could not get CSV model values for location '{area_location_for_csv}': {e}")
                    
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
                        'energy_consumption_model': energy_consumption_model_value,
                        'better_percent': better_percent_value,
                        'energy_rating': energy_rating_value,
                    }
                    
                    # Filter out zones with zero energy sum - exclude from both display and calculations
                    energy_sum = val_lighting + val_heating + val_cooling
                    if energy_sum <= 0:
                        self.logger.info(f"ZERO ENERGY FILTER: Excluding zone '{full_zone_id_key}' with zero energy sum ({energy_sum}) from energy rating")
                        continue  # Skip this zone entirely
                    
                    table_data.append(row)
                    # Log first few rows for debugging
                    if len(table_data) <= 3:
                        pass
                except (TypeError, KeyError) as e_row:
                    self.logger.error(f"Error creating table row for full_zone_id_key '{full_zone_id_key}': {e_row}. Skipping this zone.", exc_info=True)
                    continue
            return table_data
        except Exception as e:
            self.logger.error(f"Unexpected error generating energy rating table data: {e}", exc_info=True)
            return []