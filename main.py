import argparse
import sys
from idf_parser import parse_idf
from settings_parser import SettingsExtractor, TARGET_COMMENT_KEYS, TARGET_OBJECT_KEYWORDS
from schedule_parser import ScheduleExtractor
from load_parser import LoadExtractor
from zone_schedule_parser import ZoneScheduleParser
from zone_load_data_parser import ZoneLoadDataExtractor
from pdf_generator import generate_settings_pdf, generate_schedules_pdf
from loads_report_generator import generate_loads_report_pdf

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

    args = parser.parse_args()

    idf_file_path = args.idf_file
    settings_pdf_path = "output/settings.pdf"
    schedules_pdf_path = "output/schedules.pdf"
    loads_pdf_path = "output/loads.pdf"

    # Instantiate all extractors
    settings_extractor = SettingsExtractor()
    schedule_extractor = ScheduleExtractor()
    load_extractor = LoadExtractor()
    zone_schedule_parser = ZoneScheduleParser()
    zone_load_data_extractor = ZoneLoadDataExtractor()

    try:
        # Parse the IDF file and pass all elements to all extractors
        for element_type, identifier, data, current_zone_id in parse_idf(idf_file_path):
            # Process element with all extractors
            settings_extractor.process_element(element_type, identifier, data)
            schedule_extractor.process_element(element_type, identifier, data)
            load_extractor.process_element(element_type, identifier, data)
            zone_schedule_parser.process_element(element_type, identifier, data, current_zone_id)
            zone_load_data_extractor.process_element(element_type, identifier, data, current_zone_id)

        # Get the extracted data
        extracted_settings = settings_extractor.get_settings()
        extracted_schedules = schedule_extractor.get_parsed_unique_schedules()
        zone_ids = load_extractor.get_unique_zone_ids()

        # Post-processing: Link Setpoint Schedules
        zone_load_data = zone_load_data_extractor.get_zone_load_data()
        setpoint_links = zone_load_data_extractor.get_setpoint_schedule_links()

        for zone_id, data_dict in zone_load_data.items():
            thermostat_name = data_dict.get('thermostat_setpoint_object_name')
            if thermostat_name and thermostat_name in setpoint_links:
                links = setpoint_links[thermostat_name]
                data_dict['heating_setpoint_schedule'] = links.get('heating')
                data_dict['cooling_setpoint_schedule'] = links.get('cooling')

        # Generate Reports
        print(f"Generating settings report: {settings_pdf_path}")
        settings_success = generate_settings_pdf(extracted_settings, settings_pdf_path)
        if not settings_success:
            print("Error: Settings PDF generation failed")
        else:
            print("  Settings report generated successfully.")

        print(f"Generating schedules report: {schedules_pdf_path}")
        schedules_success = generate_schedules_pdf(extracted_schedules, schedules_pdf_path)
        if not schedules_success:
            print("Error: Schedules PDF generation failed")
        else:
            print("  Schedules report generated successfully.")

        print(f"Generating loads report: {loads_pdf_path}")
        loads_success = generate_loads_report_pdf(zone_ids, zone_load_data, loads_pdf_path)
        if not loads_success:
            print("Error: Loads PDF generation failed")
        else:
            print("  Loads report generated successfully.")

    except FileNotFoundError:
        print(f"Error: Input IDF file not found at '{idf_file_path}'")
        sys.exit(1)
    except ImportError as import_err:
        if 'reportlab' in str(import_err).lower():
            print("Error: 'reportlab' library required - install with: pip install reportlab")
        else:
            print(f"An unexpected import error occurred: {import_err}")
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()