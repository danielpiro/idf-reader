import argparse
import sys
from utils.eppy_handler import EppyHandler
from generators.pdf_generator import generate_schedules_pdf, generate_settings_pdf
from parsers.schedule_parser import ScheduleExtractor
from parsers.settings_parser import SettingsExtractor

def main():
    """
    Main function to parse IDF using eppy, extract settings and schedules, 
    and generate separate PDF reports.
    """
    # Set up argument parser
    parser = argparse.ArgumentParser(
        description="Parse an EnergyPlus IDF file and generate separate PDF reports for settings and schedule timelines."
    )
    parser.add_argument(
        "idf_file",
        help="Path to the input IDF file."
    )
    parser.add_argument(
        "--idd",
        help="Path to the Energy+.idd file (optional)."
    )

    args = parser.parse_args()

    idf_file_path = args.idf_file
    settings_pdf_path = "output/settings.pdf"
    schedules_pdf_path = "output/schedules.pdf"

    try:
        # Initialize eppy handler and load IDF
        eppy_handler = EppyHandler(idd_path=args.idd)
        idf = eppy_handler.load_idf(idf_file_path)
        
        # Process settings
        settings_extractor = SettingsExtractor()
        settings_objects = eppy_handler.get_settings_objects(idf)
        for obj_type, objects in settings_objects.items():
            for obj in objects:
                settings_extractor.process_eppy_object(obj_type, obj)

        # Process schedules
        schedule_extractor = ScheduleExtractor()
        for schedule in eppy_handler.get_schedule_objects(idf):
            schedule_extractor.process_eppy_schedule(schedule)

        # Get the extracted data
        extracted_settings = settings_extractor.get_settings()
        extracted_schedules = schedule_extractor.get_parsed_unique_schedules()
    
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

    except FileNotFoundError as e:
        if "Energy+.idd" in str(e):
            print("Error: Energy+.idd file not found. Please provide path using --idd or place it in the project root.")
        else:
            print(f"Error: Input IDF file not found at '{idf_file_path}'")
        sys.exit(1)
    except ImportError as import_err:
        if 'reportlab' in str(import_err).lower():
            print("Error: 'reportlab' library required - install with: pip install reportlab")
        elif 'eppy' in str(import_err).lower():
            print("Error: 'eppy' library required - install with: pip install eppy")
        else:
            print(f"An unexpected import error occurred: {import_err}")
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()