import os
from utils.logging_config import get_logger
from pathlib import Path
from datetime import datetime
from utils.data_loader import DataLoader
from utils.eppy_handler import EppyHandler
from generators.settings_report_generator import generate_settings_report_pdf
from generators.schedule_report_generator import generate_schedules_report_pdf
from generators.load_report_generator import generate_loads_report_pdf
from generators.area_report_generator import generate_area_reports
from generators.materials_report_generator import generate_materials_report_pdf
from generators.glazing_report_generator import generate_glazing_report_pdf
from generators.lighting_report_generator import LightingReportGenerator
from generators.area_loss_report_generator import generate_area_loss_report_pdf
from generators.natural_ventilation_report_generator import generate_natural_ventilation_report
from generators.automatic_error_detection_report_generator import generate_automatic_error_detection_report
from parsers.area_loss_parser import AreaLossParser
from parsers.automatic_error_detection_parser import AutomaticErrorDetectionParser
from generators.energy_rating_report_generator import EnergyRatingReportGenerator
from parsers.energy_rating_parser import EnergyRatingParser
from parsers.schedule_parser import ScheduleExtractor
from parsers.settings_parser import SettingsExtractor
from parsers.load_parser import LoadExtractor
from parsers.materials_parser import MaterialsParser
from parsers.area_parser import AreaParser
from parsers.glazing_parser import GlazingParser
from parsers.lighting_parser import LightingParser

logger = get_logger(__name__)


class ProcessingManager:
    """
    Manages the processing of IDF files, including parsing, data extraction,
    and report generation.
    """
    def __init__(self, status_callback=None, progress_callback=None, simulation_output_csv=None):
        """
        Initializes the ProcessingManager.

        Args:
            status_callback: Optional callback function for status updates.
            progress_callback: Optional callback function for progress updates.
            simulation_output_csv: Optional path to the simulation output CSV file.
        """
        self.status_callback = status_callback
        self.progress_callback = progress_callback
        self.is_cancelled = False
        self.simulation_output_csv = simulation_output_csv
        self.city_info = {}

    def update_status(self, message: str) -> None:
        """Sends a status update message via the callback."""
        if self.status_callback:
            self.status_callback(message)

    def update_progress(self, value: float) -> None:
        """Sends a progress update value (0.0 to 1.0) via the callback."""
        if self.progress_callback:
            self.progress_callback(value)

    def _ensure_directory_exists(self, file_path: str) -> None:
        """Ensures the directory for the given file path exists."""
        directory = os.path.dirname(file_path)
        if directory and not os.path.exists(directory):
            try:
                os.makedirs(directory)
                self.update_status(f"תיקייה נוצרה בהצלחה: {directory}")
            except OSError as e:
                error_message = f"שגיאה: לא ניתן ליצור תיקייה '{directory}'. סיבה: {e.strerror}"
                self.update_status(error_message)
                logger.error(f"OSError creating directory {directory}: {e}", exc_info=True)
                raise
        elif directory and os.path.exists(directory) and not os.path.isdir(directory):
            error_message = f"שגיאה: נתיב '{directory}' קיים אך אינו תיקייה."
            self.update_status(error_message)
            logger.error(error_message)
            raise OSError(error_message)

    def _setup_output_paths(self, output_dir: str, run_id: str = None) -> dict:
        """
        Sets up and returns a dictionary of output paths for reports.
        Creates a unique reports folder for each run to prevent overriding.

        Args:
            output_dir: The base directory for output.
            run_id: Unique identifier for this run (timestamp-based).

        Returns:
            A dictionary mapping report names to their full output paths.
        """
        if run_id:
            base_output = os.path.join(output_dir, f"reports-{run_id}")
        else:
            # Fallback to timestamped folder if no run_id provided
            from datetime import datetime
            timestamp = datetime.now().strftime('%d-%m-%Y-%H-%M-%S')
            base_output = os.path.join(output_dir, f"reports-{timestamp}")
        paths = {
            "settings": os.path.join(base_output, "settings.pdf"),
            "schedules": os.path.join(base_output, "schedules.pdf"),
            "loads": os.path.join(base_output, "loads.pdf"),
            "materials": os.path.join(base_output, "materials.pdf"),
            "glazing": os.path.join(base_output, "glazing.pdf"),
            "lighting": os.path.join(base_output, "lighting.pdf"),
            "area_loss": os.path.join(base_output, "area-loss.pdf"),
            "energy_rating": os.path.join(base_output, "energy-rating.pdf"),
            "natural_ventilation": os.path.join(base_output, "natural-ventilation.pdf"),
            "automatic_error_detection": os.path.join(base_output, "automatic-validation.pdf"),
            "zones_dir": os.path.join(base_output, "zones")
        }
        for path_key, path_value in paths.items():
            dir_to_check = path_value if path_key.endswith("_dir") else os.path.dirname(path_value)
            self._ensure_directory_exists(os.path.join(dir_to_check, "dummy.txt")) # Create dir with a dummy file
        return paths

    def _initialize_core_components(self, input_file: str, idd_path: str):
        """
        Initializes DataLoader, EppyHandler, and loads the IDF.

        Args:
            input_file: Path to the IDF file.
            idd_path: Path to the IDD file.

        Returns:
            Tuple: (DataLoader instance, EppyHandler instance, IDF object)
        """
        self.update_status("טוען קובץ IDF...")
        data_loader = DataLoader()
        data_loader.load_file(input_file, idd_path=idd_path)
        eppy_handler = EppyHandler(idd_path=idd_path)
        idf = eppy_handler.load_idf(input_file)
        return data_loader, eppy_handler, idf

    def _get_climate_zone_from_city_info(self) -> str:
        """
        Extract climate zone from city_info based on area name.
        Maps Hebrew area names to Latin letters for validation.
        
        Returns:
            str: Climate zone letter (A, B, C, D), defaults to 'A'
        """
        if not hasattr(self, 'city_info') or not self.city_info:
            return 'A'
            
        area_name = self.city_info.get('area_name', '')
        
        # Map Hebrew area names to Latin letters for validation
        # This matches the mapping from gui.py
        area_name_map_to_latin = {"א": "A", "ב": "B", "ג": "C", "ד": "D"}
        climate_zone = area_name_map_to_latin.get(area_name, 'A')
        
        logger.info(f"Climate zone mapping: area_name='{area_name}' -> climate_zone='{climate_zone}'")
        return climate_zone
    
    def _initialize_parsers(self, data_loader: DataLoader, area_parser_for_loss: 'AreaParser', city_area_name: str) -> dict:
        """
        Initializes all required parsers.

        Args:
            data_loader: Initialized DataLoader instance.
            area_parser_for_loss: Initialized AreaParser, needed for AreaLossParser.
            city_area_name: The city area name for thermal loss calculations.

        Returns:
            A dictionary of initialized parser instances.
        """
        self.update_status("מאתחל מנתחים...")
        parsers = {
            "settings": SettingsExtractor(data_loader),
            "schedule": ScheduleExtractor(data_loader),
            "load": LoadExtractor(data_loader),
            "materials": MaterialsParser(data_loader),
            "glazing": GlazingParser(
                constructions_glazing_cache=data_loader._constructions_glazing_cache,
                window_simple_glazing_cache=data_loader._window_simple_glazing_cache,
                window_glazing_cache=data_loader._window_glazing_cache,
                window_gas_cache=data_loader._window_gas_cache,
                window_shade_cache=data_loader._window_shade_cache,
                window_shading_control_cache=data_loader._window_shading_control_cache,
                windows_cache=data_loader.get_raw_windows_cache(),
                simulation_output_csv=self.simulation_output_csv,
                frame_divider_cache=data_loader._frame_divider_cache
            ),
            "area": area_parser_for_loss,
            "lighting": LightingParser(data_loader),
            "area_loss": AreaLossParser(area_parser_for_loss, city_area_name),
            "energy_rating": EnergyRatingParser(data_loader, area_parser_for_loss),
            "automatic_error_detection": AutomaticErrorDetectionParser(data_loader, self._get_climate_zone_from_city_info(), area_parser_for_loss)
        }
        return parsers

    def _process_data_sources(self, parsers: dict, idf, eppy_handler: EppyHandler, data_loader: DataLoader, simulation_output_csv: str):
        """
        Processes data using the initialized parsers.
        """
        self.update_status("מעבד הגדרות...")
        parsers["settings"].process_idf()
        if self.is_cancelled: return

        self.update_status("מעבד לוחות זמנים...")
        for schedule_obj in eppy_handler.get_schedule_objects(idf):
            parsers["schedule"].process_eppy_schedule(schedule_obj)
        if self.is_cancelled: return

        self.update_status("מעבד נתונים נוספים (עומסים, חומרים, אזורים)...")
        parsers["load"].process_idf(idf)
        parsers["materials"].process_idf(idf)
        parsers["area"].process_idf(idf)
        parsers["lighting"].parse()
        parsers["glazing"].parse_glazing_data()

        if self.is_cancelled: return

        self.update_status("מעבד נתוני דירוג אנרגיה...")
        energy_rating_parser = parsers["energy_rating"]
        if simulation_output_csv:
            energy_rating_parser.process_output(simulation_output_csv)
        else:
            # This case might be problematic if simulation_output_csv is essential
            self.update_status("אזהרה: לא סופק קובץ CSV של תוצאות סימולציה לדירוג אנרגיה. התוצאות עלולות להיות חלקיות.")
            energy_rating_parser.process_output() # Or handle this case differently

        self.update_status("מעבד נתוני בדיקה אוטומטית...")
        try:
            # Get ISO type from city_info for validation
            raw_iso_type = self.city_info.get('iso_type', 'Office') if hasattr(self, 'city_info') and self.city_info else 'Office'
            # Extract the year from ISO type (e.g., "RESIDENTIAL 2017" -> "2017")
            if "2017" in str(raw_iso_type):
                current_iso_type = "2017"
            elif "2023" in str(raw_iso_type):
                current_iso_type = "2023"
            else:
                current_iso_type = "Office"
            logger.info(f"Automatic validation: Raw ISO type '{raw_iso_type}' -> Mapped to '{current_iso_type}'")
            parsers["automatic_error_detection"].process_idf(idf, current_iso_type)
            self.update_status("נתוני בדיקה אוטומטית עובדו בהצלחה")
        except Exception as e:
            error_message = f"Failed processing automatic validation data: {type(e).__name__} - {str(e)}"
            self.update_status(error_message)
            logger.error(f"Exception in automatic error detection processing: {e}", exc_info=True)
        if self.is_cancelled: return

    def _extract_data_from_parsers(self, parsers: dict) -> dict:
        """
        Extracts processed data from parsers.
        """
        self.update_status("מחלץ נתונים מעובדים...")
        return {
            "settings": parsers["settings"].get_settings(),
            "schedules": parsers["schedule"].get_parsed_unique_schedules(),
            "loads": parsers["load"].get_parsed_zone_loads(),
            "materials": parsers["materials"].get_element_data(),
            "glazing": parsers["glazing"].parsed_glazing_data,
            "lighting": parsers["lighting"].parse(), # Ensure this returns data
            "area_loss": parsers["area_loss"].parse(), # Ensure this returns data
            "automatic_error_detection": parsers["automatic_error_detection"].get_error_detection_data(),
        }

    def _generate_report_item(self, report_name: str, generation_function,
                              data, output_path: str, project_name: str, run_id: str,
                              city_name: str = "N/A", area_name: str = "N/A",
                              is_generator_class: bool = False, **kwargs) -> bool:
        """
        Helper to generate a single report item.
        """
        self.update_status(f"יוצר דוח {report_name}...")
        success = False
        try:
            if is_generator_class:
                # Pass data to the constructor if the class expects it
                generator_instance = generation_function(data, output_path, project_name=project_name, run_id=run_id,
                                                       city_name=city_name, area_name=area_name, **kwargs)
                if hasattr(generator_instance, 'generate_report'):
                     success = generator_instance.generate_report() # Assumes generate_report doesn't need output_filename
                # elif 'output_filename' in kwargs and hasattr(generator_instance, 'generate_report'):
                #      success = generator_instance.generate_report(output_filename=kwargs['output_filename'])
                else:
                    self.update_status(f"מחלקת יוצר {report_name} אינה כוללת מתוד generate_report.")
                    return False
            else:
                result = generation_function(data, output_path, project_name=project_name, run_id=run_id,
                                 city_name=city_name, area_name=area_name, **kwargs)
                # Capture the return value if it's a boolean, otherwise assume success
                success = result if isinstance(result, bool) else True

            if success:
                self.update_status(f"דוח {report_name} נוצר בהצלחה ב-{output_path}")
            else:
                self.update_status(f"יצירת דוח {report_name} נכשלה (בדוק את הקונסול).")
            return success
        except Exception as e:
            error_message = f"Error generating {report_name} report: {type(e).__name__} - {str(e)}"
            self.update_status(error_message)
            logger.error(f"Exception in _generate_report_item for {report_name}: {e}", exc_info=True)
            return False

    def _generate_all_reports(self, extracted_data: dict, report_paths: dict,
                              project_name: str, run_id: str,
                              area_parser_instance: 'AreaParser',
                              energy_rating_parser_instance: 'EnergyRatingParser',
                              base_output_dir_for_reports: str,
                              iso_type_selection: str,
                              city_area_name_selection: str,
                              data_loader: 'DataLoader'  # Add data_loader parameter
                              ) -> None:
        """
        Generates all PDF reports.
        """
        self.update_status("יוצר דוחות...")
        progress_step = 0.7 # Initial progress after parsing
        num_reports = 10 # Updated number of main report generation steps (added automatic error detection)
        progress_increment = (1.0 - progress_step) / num_reports

        city_name_hebrew = self.city_info.get('city', 'N/A') if hasattr(self, 'city_info') and self.city_info else 'N/A'
        
        # Determine the correct area name for display based on model year
        # This ensures all reports show consistent area definitions
        derived_model_year = None
        if "2017" in self.city_info.get('iso_type', ''):
            derived_model_year = 2017
        elif "2023" in self.city_info.get('iso_type', ''):
            derived_model_year = 2023
        elif "OFFICE" in self.city_info.get('iso_type', '').upper():
            derived_model_year = "office"
        
        # Use appropriate area names for report metadata
        if derived_model_year == 2023:
            # For 2023 models, use numeric area code (1-8) directly
            area_code = self.city_info.get('area_code', '') if hasattr(self, 'city_info') and self.city_info else ''
            area_name_for_reports = area_code if area_code else 'N/A'
        else:
            # For 2017/office models, use Hebrew area name directly
            area_name_for_reports = city_area_name_selection if city_area_name_selection else 'N/A'

        # Settings
        self._generate_report_item("Settings", generate_settings_report_pdf, extracted_data["settings"], report_paths["settings"], project_name, run_id, city_name_hebrew, area_name_for_reports)
        progress_step += progress_increment; self.update_progress(progress_step)
        if self.is_cancelled: return

        # Schedules
        self._generate_report_item("Schedules", generate_schedules_report_pdf, extracted_data["schedules"], report_paths["schedules"], project_name, run_id, city_name_hebrew, area_name_for_reports)
        progress_step += progress_increment; self.update_progress(progress_step)
        if self.is_cancelled: return

        # Loads
        self._generate_report_item("Loads", generate_loads_report_pdf, extracted_data["loads"], report_paths["loads"], project_name, run_id, city_name_hebrew, area_name_for_reports)
        progress_step += progress_increment; self.update_progress(progress_step)
        if self.is_cancelled: return

        # Materials
        self._generate_report_item("Materials", generate_materials_report_pdf, extracted_data["materials"], report_paths["materials"], project_name, run_id, city_name_hebrew, area_name_for_reports)
        progress_step += progress_increment; self.update_progress(progress_step)
        if self.is_cancelled: return

        # Area (Zones) - Use base zone grouping to ensure related zones are in same file
        self.update_status("יוצר דוחות אזורים (איזורים) עם קיבוץ אזור בסיס...")
        try:
            from generators.area_report_generator import generate_area_reports_by_base_zone
            generate_area_reports_by_base_zone(area_parser_instance, output_dir=report_paths["zones_dir"], project_name=project_name, run_id=run_id, city_name=city_name_hebrew, area_name=area_name_for_reports)
            self.update_status("ניסה ליצור דוחות אזורים עם קיבוץ אזור בסיס.")
        except Exception as e:
            error_message = f"Error generating Area (Zones) reports with base zone grouping: {type(e).__name__} - {str(e)}"
            self.update_status(error_message)
            logger.error(f"Exception in generate_area_reports_by_base_zone: {e}", exc_info=True)
        progress_step += progress_increment; self.update_progress(progress_step)
        if self.is_cancelled: return

        # Glazing
        self._generate_report_item("Glazing", generate_glazing_report_pdf, extracted_data["glazing"], report_paths["glazing"], project_name, run_id, city_name_hebrew, area_name_for_reports)
        progress_step += progress_increment; self.update_progress(progress_step)
        if self.is_cancelled: return

        # Lighting
        self._generate_report_item("Lighting", LightingReportGenerator, extracted_data["lighting"], report_paths["lighting"], project_name, run_id, city_name_hebrew, area_name_for_reports, is_generator_class=True)
        progress_step += progress_increment; self.update_progress(progress_step)
        if self.is_cancelled: return
        
        # TODO: Re-enable area-loss report generation later
        # Area Loss
        # self._generate_report_item("Area Loss", generate_area_loss_report_pdf, extracted_data["area_loss"], report_paths["area_loss"], project_name, run_id, city_name_hebrew, area_name_for_reports)
        progress_step += progress_increment; self.update_progress(progress_step)
        if self.is_cancelled: return

        # Natural Ventilation
        ventilation_data = data_loader.get_natural_ventilation_data()
        self._generate_report_item("Natural Ventilation", generate_natural_ventilation_report, ventilation_data, report_paths["natural_ventilation"], project_name, run_id, city_name_hebrew, area_name_for_reports)
        progress_step += progress_increment; self.update_progress(progress_step)
        if self.is_cancelled: return

        # Automatic Validation
        self._generate_report_item("Automatic Validation", generate_automatic_error_detection_report, extracted_data["automatic_error_detection"], report_paths["automatic_error_detection"], project_name, run_id, city_name_hebrew, area_name_for_reports)
        progress_step += progress_increment; self.update_progress(progress_step)
        if self.is_cancelled: return

        # Energy Rating
        self.update_status("יוצר דוח דירוג אנרגיה (PDF)...")
        try:
            derived_model_year = None
            derived_model_area_definition = None

            if "2017" in iso_type_selection:
                derived_model_year = 2017
            elif "2023" in iso_type_selection: # Assuming "RESIDNTIAL 2023" implies 2023
                derived_model_year = 2023
            elif "OFFICE" in iso_type_selection.upper():
                derived_model_year = "office"  # Special case for office buildings
            
            # For 2023, use numeric area code; for others, use Latin letters (for model calculations)
            if derived_model_year == 2023:
                # For 2023 models, use the numeric area code directly
                area_code = self.city_info.get('area_code', '') if hasattr(self, 'city_info') and self.city_info else ''
                derived_model_area_definition = area_code
                self.update_status(f"דירוג אנרגיה: משתמש בקוד אזור מספרי '{area_code}' למודל 2023")
            else:
                # For 2017 and office models, map Hebrew area name to Latin letter (for model calculations only)
                area_name_map_to_letter = {"א": "A", "ב": "B", "ג": "C", "ד": "D"}
                derived_model_area_definition = area_name_map_to_letter.get(city_area_name_selection)
                self.update_status(f"דירוג אנרגיה: משתמש באות אזור לטינית '{derived_model_area_definition}' למודל {derived_model_year}")

            if derived_model_year and derived_model_area_definition:
                actual_selected_city_name = self.city_info.get('city', None) # This is the Hebrew city name from GUI

                self.update_status(f"דוח דירוג אנרגיה: משתמש בעיר='{actual_selected_city_name}', שנה={derived_model_year}, הגדרת אזור='{derived_model_area_definition}'")
                
                energy_rating_gen = EnergyRatingReportGenerator(
                    energy_rating_parser=energy_rating_parser_instance,
                    output_dir=base_output_dir_for_reports,
                    model_year=derived_model_year,
                    model_area_definition=derived_model_area_definition,
                    selected_city_name=actual_selected_city_name,
                    project_name=project_name,
                    run_id=run_id,
                    area_name=area_name_for_reports
                )
                # The output_filename is relative to output_dir in the generator
                success_er = energy_rating_gen.generate_report(output_filename=os.path.basename(report_paths["energy_rating"]))
                if success_er:
                    self.update_status(f"דוח דירוג אנרגיה נוצר בהצלחה ב-{report_paths['energy_rating']}")
                else:
                    self.update_status("יצירת דוח דירוג אנרגיה נכשלה (בדוק את הקונסול לפרטים).")

                # Generate total energy rating report
                try:
                    total_rating_path = energy_rating_gen.generate_total_energy_rating_report(output_filename="total-energy-rating.pdf")
                    if total_rating_path:
                        self.update_status(f"דוח דירוג אנרגיה כולל נוצר בהצלחה ב-{total_rating_path}")
                    else:
                        self.update_status("יצירת דוח דירוג אנרגיה כולל נכשלה (בדוק את הקונסול לפרטים).")
                except Exception as e_total:
                    error_message = f"Error generating Total Energy Rating PDF report: {type(e_total).__name__} - {str(e_total)}"
                    self.update_status(error_message)
                    logger.error(f"Exception in Total Energy Rating report generation: {e_total}", exc_info=True)

            else:
                msg = (f"Energy Rating Report: Could not determine model_year ('{derived_model_year}') "
                       f"or model_area_definition ('{derived_model_area_definition}') from ISO type "
                       f"'{iso_type_selection}' and city area '{city_area_name_selection}'. Skipping report.")
                self.update_status(msg) # Removed "warning" tag to avoid GUI coloring issues if not a real warning
                logger.warning(msg)
        except Exception as e:
            error_message = f"Error generating Energy Rating PDF report: {type(e).__name__} - {str(e)}"
            self.update_status(error_message)
            logger.error(f"Exception in EnergyRatingReportGenerator: {e}", exc_info=True)
        
        self.update_progress(1.0)

    def _convert_area_name_to_hebrew(self, area_name: str) -> str:
        """Convert area name to Hebrew for display in reports metadata."""
        area_name_to_hebrew = {
            "A": "א", "B": "ב", "C": "ג", "D": "ד",
            "1": "א", "2": "ב", "3": "ג", "4": "ד",
            "a": "א", "b": "ב", "c": "ג", "d": "ד"
        }
        return area_name_to_hebrew.get(str(area_name), area_name)

    def process_idf(self, input_file: str, idd_path: str, output_dir: str, run_id: str = None) -> bool:
        """
        Main method to process an IDF file and generate all reports.
        
        Args:
            input_file: Path to the IDF file
            idd_path: Path to the IDD file
            output_dir: Base output directory
            run_id: Optional pre-generated run ID. If None, will generate one.
        """
        try:
            project_name = Path(input_file).stem
            if run_id is None:
                run_id = datetime.now().strftime('%d-%m-%Y-%H-%M-%S')

            self.update_progress(0.0)
            self.update_status("מאתחל...")

            report_paths = self._setup_output_paths(output_dir, run_id)
            base_reports_dir = os.path.join(output_dir, f"reports-{run_id}") # Used by EnergyRatingGenerator

            if self.is_cancelled: return False
            self.update_progress(0.1)

            data_loader, eppy_handler, idf = self._initialize_core_components(input_file, idd_path)

            if self.is_cancelled: return False
            self.update_progress(0.2)

            # Determine city_area_name for AreaLossParser (e.g., "א", "ב", "ג", "ד")
            # This should come from the GUI selection, passed via self.city_info
            city_area_name_for_loss = "א" # Default
            if self.city_info and 'area_name' in self.city_info:
                city_area_name_for_loss = self.city_info.get('area_name', "א")
                self.update_status(f"משתמש באזור עיר '{city_area_name_for_loss}' לחישובי אובדני חום.")
            
            # Initialize parsers that depend on each other or simulation output
            temp_materials_parser = MaterialsParser(data_loader) # Needed by AreaParser
            # AreaParser might need simulation_output_csv if it uses it for something
            temp_area_parser = AreaParser(data_loader, temp_materials_parser, self.simulation_output_csv)

            parsers = self._initialize_parsers(data_loader, temp_area_parser, city_area_name_for_loss)
            # Ensure the already initialized parsers are used
            parsers["materials"] = temp_materials_parser
            parsers["area"] = temp_area_parser


            if self.is_cancelled: return False
            self.update_progress(0.3)

            self._process_data_sources(parsers, idf, eppy_handler, data_loader, self.simulation_output_csv)

            if self.is_cancelled: return False
            self.update_progress(0.6) # Progress after parsing

            extracted_data = self._extract_data_from_parsers(parsers)

            if self.is_cancelled: return False
            self.update_progress(0.7) # Progress before report generation

            # Get ISO type and city area name from self.city_info (set by GUI)
            current_iso_type = self.city_info.get('iso_type', '')
            current_city_area_name = self.city_info.get('area_name', '') # This is "א", "ב", etc.

            self._generate_all_reports(
                extracted_data,
                report_paths,
                project_name,
                run_id,
                parsers["area"], # Pass the AreaParser instance
                parsers["energy_rating"], # Pass the EnergyRatingParser instance
                base_reports_dir,
                iso_type_selection=current_iso_type,
                city_area_name_selection=current_city_area_name,
                data_loader=data_loader  # Pass data_loader to _generate_all_reports
            )

            if self.is_cancelled:
                self.update_status("העיבוד בוטל במהלך יצירת הדוחות.")
                return False

            self.update_status("העיבוד הושלם בהצלחה!")
            return True
        except FileNotFoundError as fnf_err:
            user_message = f"Error: A required file was not found. Path: {fnf_err.filename}. Details: {fnf_err.strerror}"
            self.update_status(user_message)
            logger.error(user_message, exc_info=True)
            # raise # Re-raising might crash the GUI thread, consider returning False
            return False
        except (IOError, OSError) as os_io_err:
            user_message = f"Error: File or system operation failed. Path: {getattr(os_io_err, 'filename', 'N/A')}. Details: {os_io_err.strerror}"
            self.update_status(user_message)
            logger.error(user_message, exc_info=True)
            # raise
            return False
        except Exception as e:
            user_message = f"An unexpected error occurred during IDF processing: {type(e).__name__} - {str(e)}"
            self.update_status(user_message)
            logger.error(f"Unexpected error in process_idf: {e}", exc_info=True)
            # raise
            return False

    def cancel(self):
        """Signals that the current processing should be cancelled."""
        self.is_cancelled = True
        self.update_status("בקשה לביטול התקבלה.")