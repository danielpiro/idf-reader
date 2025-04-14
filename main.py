import argparse
import sys
from utils.eppy_handler import EppyHandler
from generators.settings_report_generator import generate_settings_report_pdf
from generators.schedule_report_generator import generate_schedules_report_pdf
from generators.load_report_generator import generate_loads_report_pdf
from generators.area_report_generator import generate_area_reports
from generators.materials_report_generator import generate_materials_report_pdf
from parsers.schedule_parser import ScheduleExtractor
from parsers.settings_parser import SettingsExtractor
from parsers.load_parser import LoadExtractor
from parsers.materials_parser import MaterialsParser
from parsers.area_parser import AreaParser

def main():
    """
    Main function to parse IDF using eppy, extract settings, schedules, loads,
    and materials, then generate separate PDF reports.
    """
    # Set up argument parser
    parser = argparse.ArgumentParser(
        description="Parse an EnergyPlus IDF file and generate separate PDF reports."
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
    loads_pdf_path = "output/loads.pdf"
    materials_pdf_path = "output/materials.pdf"

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

        # Process zone loads
        load_extractor = LoadExtractor()
        load_extractor.process_idf(idf)

        # Process materials and constructions
        materials_extractor = MaterialsParser()
        materials_extractor.process_idf(idf)
        
        # Process areas
        area_parser = AreaParser()
        area_parser.process_idf(idf)

        # Get the extracted data
        extracted_settings = settings_extractor.get_settings()
        extracted_schedules = schedule_extractor.get_parsed_unique_schedules()
        extracted_loads = load_extractor.get_parsed_zone_loads()
        extracted_element_data = materials_extractor.get_element_data()
        extracted_areas = area_parser.get_parsed_areas()
    
        # Generate Reports
        print(f"Generating settings report: {settings_pdf_path}")
        settings_success = generate_settings_report_pdf(extracted_settings, settings_pdf_path)
        if not settings_success:
            print("Error: Settings PDF generation failed")
        else:
            print("  Settings report generated successfully.")

        print(f"Generating schedules report: {schedules_pdf_path}")
        schedules_success = generate_schedules_report_pdf(extracted_schedules, schedules_pdf_path)
        if not schedules_success:
            print("Error: Schedules PDF generation failed")
        else:
            print("  Schedules report generated successfully.")

        print(f"Generating loads report: {loads_pdf_path}")
        loads_success = generate_loads_report_pdf(extracted_loads, loads_pdf_path)
        if not loads_success:
            print("Error: Loads PDF generation failed")
        else:
            print("  Loads report generated successfully.")

        print(f"Generating materials report: {materials_pdf_path}")
        materials_success = generate_materials_report_pdf(extracted_element_data, materials_pdf_path)
        if not materials_success:
            print("Error: Materials PDF generation failed")
        else:
            print("  Materials report generated successfully.")

        # Generate area reports
        print("Generating area reports...")
        areas_success = generate_area_reports(extracted_areas)
        if not areas_success:
            print("Error: Areas PDF generation failed")
        else:
            print("  Area reports generated successfully in output directory")

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