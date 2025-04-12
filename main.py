import argparse
import sys
# import pprint # Debug import removed again
from idf_parser import parse_idf
from settings_parser import SettingsExtractor, TARGET_COMMENT_KEYS, TARGET_OBJECT_KEYWORDS  # Import known settings keys
from schedule_parser import ScheduleExtractor  # Import schedule extractor
from load_parser import LoadExtractor  # Import load extractor
from zone_schedule_parser import ZoneScheduleParser # Import zone-schedule parser
from zone_load_data_parser import ZoneLoadDataExtractor # Import zone load data parser
from pdf_generator import generate_settings_pdf, generate_schedules_pdf  # Import separate generators
from loads_report_generator import generate_loads_report_pdf # Import loads report generator

def main():
    """
    Main function to parse IDF, extract settings and schedules, and generate separate PDF reports.
    """
    # Set up argument parser
    parser = argparse.ArgumentParser(
        description="Parse an EnergyPlus IDF file and generate separate PDF reports for settings and schedule timelines."
    )
    parser.add_argument(
        "idf_file",
        help="Path to the input IDF file."
    )
    # Removed output argument as filenames are fixed (settings.pdf, schedules.pdf)

    args = parser.parse_args()

    idf_file_path = args.idf_file
    # Output filenames are now fixed
    settings_pdf_path = "settings.pdf"
    schedules_pdf_path = "schedules.pdf"


    # Instantiate the settings extractor
    settings_extractor = SettingsExtractor()
    schedule_extractor = ScheduleExtractor()  # Instantiate schedule extractor
    load_extractor = LoadExtractor()  # Instantiate load extractor
    zone_schedule_parser = ZoneScheduleParser() # Instantiate zone-schedule parser
    zone_load_data_extractor = ZoneLoadDataExtractor() # Instantiate zone load data parser

    # Parse the IDF file and extract settings
    try:
        # Pass known settings keys to the parser
        # Pass both comment keys and object keywords to the parser
        target_keys = set(TARGET_COMMENT_KEYS) | set(TARGET_OBJECT_KEYWORDS)
        for element_type, identifier, data, current_zone_id in parse_idf(idf_file_path, settings_keys=target_keys):
            # Process element with all relevant extractors
            settings_extractor.process_element(element_type, identifier, data) # Settings parser doesn't need zone_id
            schedule_extractor.process_element(element_type, identifier, data) # Schedule parser doesn't need zone_id
            load_extractor.process_element(element_type, identifier, data)     # Load parser doesn't need zone_id
            zone_schedule_parser.process_element(element_type, identifier, data, current_zone_id) # Zone-schedule parser needs zone_id
            zone_load_data_extractor.process_element(element_type, identifier, data, current_zone_id) # Zone load data parser needs zone_id

        # Get the extracted settings and schedules
        extracted_settings = settings_extractor.get_settings()
        extracted_schedules = schedule_extractor.get_parsed_unique_schedules() # Get schedule data

        # Get unique zone IDs
        zone_ids = load_extractor.get_unique_zone_ids()
        # Prints for zone IDs and schedules-by-zone removed as requested.
        # We still need zone_ids for the loads report.
        zone_ids = load_extractor.get_unique_zone_ids()
        # We don't currently use schedules_by_zone for the loads report.
        # schedules_by_zone = zone_schedule_parser.get_schedules_by_zone()

        # --- Post-processing: Link Setpoint Schedules ---
        zone_load_data = zone_load_data_extractor.get_zone_load_data()
        setpoint_links = zone_load_data_extractor.get_setpoint_schedule_links()

        for zone_id, data_dict in zone_load_data.items():
            thermostat_name = data_dict.get('thermostat_setpoint_object_name')
            if thermostat_name and thermostat_name in setpoint_links:
                links = setpoint_links[thermostat_name]
                data_dict['heating_setpoint_schedule'] = links.get('heating')
                data_dict['cooling_setpoint_schedule'] = links.get('cooling')
                # print(f"  Linked setpoints for Zone {zone_id} via {thermostat_name}") # Optional Debug
            # else:
                # print(f"  No setpoint link found for Zone {zone_id} (Thermostat: {thermostat_name})") # Optional Debug

        # --- Generate Reports ---

        # Generate reports quietly unless there's an error
        settings_success = generate_settings_pdf(extracted_settings, settings_pdf_path)
        if not settings_success:
            print("Error: Settings PDF generation failed")
    except FileNotFoundError:
        print(f"Error: Input IDF file not found at '{idf_file_path}'")
        sys.exit(1) # Exit with error code
    except ImportError as import_err:
         # Catch missing reportlab
         if 'reportlab' in str(import_err).lower():
             print("Error: 'reportlab' library required - install with: pip install reportlab")
         # Removed matplotlib check
         else:
              print(f"An unexpected import error occurred: {import_err}")
         sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()