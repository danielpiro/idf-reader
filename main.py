import argparse
import sys
import os
import time
from pathlib import Path
from utils.data_loader import DataLoader
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

def ensure_directory_exists(file_path: str) -> None:
    """
    Ensure the directory for the given file path exists.
    Create it if it doesn't exist.
    
    Args:
        file_path: Path to the file
    """
    directory = os.path.dirname(file_path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory)

def main():
    """
    Main function to parse IDF using DataLoader, extract settings, schedules, loads,
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

    # Create output directories
    for path in [settings_pdf_path, schedules_pdf_path, loads_pdf_path, 
                materials_pdf_path]:
        ensure_directory_exists(path)

    try:
        start_time = time.time()
        
        # Initialize handlers and load IDF file once
        print("Loading IDF file...")
        load_start = time.time()
        eppy_handler = EppyHandler(idd_path=args.idd)
        idf = eppy_handler.load_idf(idf_file_path)
        
        data_loader = DataLoader()
        data_loader.load_file(idf_file_path, args.idd)
        load_time = time.time() - load_start
        print(f"  File loaded in {load_time:.2f}s")
        
        print("\nProcessing IDF data...")
        
        # Group parsers by data dependencies
        print("  Initializing parsers...")
        parsers = {
            'core': {
                'settings': SettingsExtractor(data_loader),
                'materials': MaterialsParser(data_loader),
            },
            'dependent': {
                'schedules': ScheduleExtractor(data_loader),
                'loads': LoadExtractor(data_loader),
                'areas': AreaParser(data_loader),
            }
        }
        
        # Process core data first (settings and materials)
        print("  Processing core data...")
        core_start = time.time()
        
        # Process settings using the new process_idf method
        settings_start = time.time()
        parsers['core']['settings'].process_idf(idf)
        settings_time = time.time() - settings_start
        print(f"    Settings processed in {settings_time:.2f}s")
        
        # Process materials
        materials_start = time.time()
        parsers['core']['materials'].process_idf(idf)
        materials_time = time.time() - materials_start
        print(f"    Materials processed in {materials_time:.2f}s")
        
        core_time = time.time() - core_start
        print(f"    Core processing completed in {core_time:.2f}s")
        
        # Process dependent data (schedules, loads, areas)
        print("  Processing dependent data...")
        dependent_start = time.time()
        
        schedule_start = time.time()
        for schedule in eppy_handler.get_schedule_objects(idf):
            parsers['dependent']['schedules'].process_eppy_schedule(schedule)
        schedule_time = time.time() - schedule_start
        print(f"    Schedules processed in {schedule_time:.2f}s")
        
        for parser in ['loads', 'areas']:
            parser_start = time.time()
            parsers['dependent'][parser].process_idf(idf)
            parser_time = time.time() - parser_start
            print(f"    {parser.capitalize()} processed in {parser_time:.2f}s")
            
        dependent_time = time.time() - dependent_start
        print(f"    Total dependent processing: {dependent_time:.2f}s")
            
        # Cache status report
        cache_status = data_loader.get_cache_status()
        print("\nData Cache Status:")
        for section, loaded in cache_status.items():
            status = "✓ Loaded" if loaded else "✗ Not loaded"
            print(f"  {section.capitalize():<12} {status}")
        
        # Extract data and generate reports
        print("\nGenerating reports...")
        reports_start = time.time()
        
        # Group reports by data dependencies
        report_groups = [
            {
                'name': 'Core Reports',
                'reports': [
                    {
                        'type': 'settings',
                        'data': parsers['core']['settings'].get_settings(),
                        'generator': generate_settings_report_pdf,
                        'path': settings_pdf_path
                    },
                    {
                        'type': 'materials',
                        'data': parsers['core']['materials'].get_element_data(),
                        'generator': generate_materials_report_pdf,
                        'path': materials_pdf_path
                    }
                ]
            },
            {
                'name': 'Zone Reports',
                'reports': [
                    {
                        'type': 'schedules',
                        'data': parsers['dependent']['schedules'].get_parsed_unique_schedules(),
                        'generator': generate_schedules_report_pdf,
                        'path': schedules_pdf_path
                    },
                    {
                        'type': 'loads',
                        'data': parsers['dependent']['loads'].get_parsed_zone_loads(),
                        'generator': generate_loads_report_pdf,
                        'path': loads_pdf_path
                    }
                ]
            }
        ]
        
        # Generate reports by group
        for group in report_groups:
            print(f"  Processing {group['name']}...")
            for report in group['reports']:
                print(f"    Generating {report['type']} report...")
                success = report['generator'](report['data'], report['path'])
                gen_time = time.time() - reports_start
                status = "successfully" if success else "failed"
                print(f"      Report generation {status} in {gen_time:.2f}s")
                reports_start = time.time()  # Reset for next report
                
        # Handle special reports (areas)
        print("  Processing Special Reports...")
        
        print("    Generating area reports...")
        # Pass the full AreaParser instance instead of just the parsed data
        # This ensures the DataLoader is available for element type detection
        areas_success = generate_area_reports(parsers['dependent']['areas'])
        print(f"      Area reports generation {'successful' if areas_success else 'failed'}")
            
        # Print total execution time
        total_time = time.time() - start_time
        print(f"\nTotal execution time: {total_time:.2f}s")

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