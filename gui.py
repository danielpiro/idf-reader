import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
import json
import os
import subprocess
import threading
import logging
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
from parsers.area_loss_parser import AreaLossParser
from generators.energy_rating_report_generator import EnergyRatingReportGenerator
from parsers.energy_rating_parser import EnergyRatingParser
from parsers.schedule_parser import ScheduleExtractor
from parsers.settings_parser import SettingsExtractor
from parsers.load_parser import LoadExtractor
from parsers.materials_parser import MaterialsParser
from parsers.area_parser import AreaParser
from parsers.glazing_parser import GlazingParser
from parsers.lighting_parser import LightingParser

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')


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
                self.update_status(f"Successfully created directory: {directory}")
            except OSError as e:
                error_message = f"Error: Could not create directory '{directory}'. Reason: {e.strerror}"
                self.update_status(error_message)
                logger.error(f"OSError creating directory {directory}: {e}", exc_info=True)
                raise
        elif directory and os.path.exists(directory) and not os.path.isdir(directory):
            error_message = f"Error: Path '{directory}' exists but is not a directory."
            self.update_status(error_message)
            logger.error(error_message)
            raise OSError(error_message)

    def _setup_output_paths(self, output_dir: str) -> dict:
        """
        Sets up and returns a dictionary of output paths for reports.

        Args:
            output_dir: The base directory for output.

        Returns:
            A dictionary mapping report names to their full output paths.
        """
        base_output = os.path.join(output_dir, "reports")
        paths = {
            "settings": os.path.join(base_output, "settings.pdf"),
            "schedules": os.path.join(base_output, "schedules.pdf"),
            "loads": os.path.join(base_output, "loads.pdf"),
            "materials": os.path.join(base_output, "materials.pdf"),
            "glazing": os.path.join(base_output, "glazing.pdf"),
            "lighting": os.path.join(base_output, "lighting.pdf"),
            "area_loss": os.path.join(base_output, "area-loss.pdf"),
            "energy_rating": os.path.join(base_output, "energy-rating.pdf"),
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
        self.update_status("Loading IDF file...")
        data_loader = DataLoader()
        data_loader.load_file(input_file, idd_path=idd_path)
        eppy_handler = EppyHandler(idd_path=idd_path)
        idf = eppy_handler.load_idf(input_file)
        return data_loader, eppy_handler, idf

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
        self.update_status("Initializing parsers...")
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
            "energy_rating": EnergyRatingParser(data_loader, area_parser_for_loss)
        }
        return parsers

    def _process_data_sources(self, parsers: dict, idf, eppy_handler: EppyHandler, data_loader: DataLoader, simulation_output_csv: str):
        """
        Processes data using the initialized parsers.
        """
        self.update_status("Processing settings...")
        parsers["settings"].process_idf()
        if self.is_cancelled: return

        self.update_status("Processing schedules...")
        for schedule_obj in eppy_handler.get_schedule_objects(idf):
            parsers["schedule"].process_eppy_schedule(schedule_obj)
        if self.is_cancelled: return

        self.update_status("Processing other data (loads, materials, area)...")
        parsers["load"].process_idf(idf)
        parsers["materials"].process_idf(idf)
        parsers["area"].process_idf(idf)
        parsers["lighting"].parse()
        parsers["glazing"].parse_glazing_data()

        if self.is_cancelled: return

        self.update_status("Processing energy rating data...")
        energy_rating_parser = parsers["energy_rating"]
        if simulation_output_csv:
            energy_rating_parser.process_output(simulation_output_csv)
        else:
            # This case might be problematic if simulation_output_csv is essential
            self.update_status("Warning: No simulation output CSV provided for EnergyRatingParser. Results may be incomplete.")
            energy_rating_parser.process_output() # Or handle this case differently

    def _extract_data_from_parsers(self, parsers: dict) -> dict:
        """
        Extracts processed data from parsers.
        """
        self.update_status("Extracting processed data...")
        return {
            "settings": parsers["settings"].get_settings(),
            "schedules": parsers["schedule"].get_parsed_unique_schedules(),
            "loads": parsers["load"].get_parsed_zone_loads(),
            "materials": parsers["materials"].get_element_data(),
            "glazing": parsers["glazing"].parsed_glazing_data,
            "lighting": parsers["lighting"].parse(), # Ensure this returns data
            "area_loss": parsers["area_loss"].parse(), # Ensure this returns data
        }

    def _generate_report_item(self, report_name: str, generation_function,
                              data, output_path: str, project_name: str, run_id: str,
                              city_name: str = "N/A", area_name: str = "N/A",
                              is_generator_class: bool = False, **kwargs) -> bool:
        """
        Helper to generate a single report item.
        """
        self.update_status(f"Generating {report_name} report...")
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
                    self.update_status(f"Generator class {report_name} does not have a generate_report method.")
                    return False
            else:
                generation_function(data, output_path, project_name=project_name, run_id=run_id,
                                 city_name=city_name, area_name=area_name, **kwargs)
                success = True

            if success:
                self.update_status(f"{report_name} report generated successfully at {output_path}")
            else:
                self.update_status(f"{report_name} report generation failed or returned False (check console).")
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
                              city_area_name_selection: str
                              ) -> None:
        """
        Generates all PDF reports.
        """
        self.update_status("Generating reports...")
        progress_step = 0.7 # Initial progress after parsing
        num_reports = 8 # Number of main report generation steps
        progress_increment = (1.0 - progress_step) / num_reports

        city_name_hebrew = self.city_info.get('city', 'N/A') if hasattr(self, 'city_info') and self.city_info else 'N/A'
        area_name_hebrew = city_area_name_selection if city_area_name_selection else 'N/A'

        # Settings
        self._generate_report_item("Settings", generate_settings_report_pdf, extracted_data["settings"], report_paths["settings"], project_name, run_id, city_name_hebrew, area_name_hebrew)
        progress_step += progress_increment; self.update_progress(progress_step)
        if self.is_cancelled: return

        # Schedules
        self._generate_report_item("Schedules", generate_schedules_report_pdf, extracted_data["schedules"], report_paths["schedules"], project_name, run_id, city_name_hebrew, area_name_hebrew)
        progress_step += progress_increment; self.update_progress(progress_step)
        if self.is_cancelled: return

        # Loads
        self._generate_report_item("Loads", generate_loads_report_pdf, extracted_data["loads"], report_paths["loads"], project_name, run_id, city_name_hebrew, area_name_hebrew)
        progress_step += progress_increment; self.update_progress(progress_step)
        if self.is_cancelled: return

        # Materials
        self._generate_report_item("Materials", generate_materials_report_pdf, extracted_data["materials"], report_paths["materials"], project_name, run_id, city_name_hebrew, area_name_hebrew)
        progress_step += progress_increment; self.update_progress(progress_step)
        if self.is_cancelled: return

        # Area (Zones)
        self.update_status("Generating Area (Zones) reports...")
        try:
            generate_area_reports(area_parser_instance, output_dir=report_paths["zones_dir"], project_name=project_name, run_id=run_id, city_name=city_name_hebrew, area_name=area_name_hebrew)
            self.update_status("Area (Zones) reports generation attempted.")
        except Exception as e:
            error_message = f"Error generating Area (Zones) reports: {type(e).__name__} - {str(e)}"
            self.update_status(error_message)
            logger.error(f"Exception in generate_area_reports: {e}", exc_info=True)
        progress_step += progress_increment; self.update_progress(progress_step)
        if self.is_cancelled: return

        # Glazing
        self._generate_report_item("Glazing", generate_glazing_report_pdf, extracted_data["glazing"], report_paths["glazing"], project_name, run_id, city_name_hebrew, area_name_hebrew)
        progress_step += progress_increment; self.update_progress(progress_step)
        if self.is_cancelled: return

        # Lighting
        self._generate_report_item("Lighting", LightingReportGenerator, extracted_data["lighting"], report_paths["lighting"], project_name, run_id, city_name_hebrew, area_name_hebrew, is_generator_class=True)
        progress_step += progress_increment; self.update_progress(progress_step)
        if self.is_cancelled: return
        
        # Area Loss
        self._generate_report_item("Area Loss", generate_area_loss_report_pdf, extracted_data["area_loss"], report_paths["area_loss"], project_name, run_id, city_name_hebrew, area_name_hebrew)
        progress_step += progress_increment; self.update_progress(progress_step)
        if self.is_cancelled: return

        # Energy Rating
        self.update_status("Generating Energy Rating report (PDF)...")
        try:
            derived_model_year = None
            derived_model_area_definition = None

            if "2017" in iso_type_selection:
                derived_model_year = 2017
            elif "2023" in iso_type_selection: # Assuming "RESIDNTIAL 2023" implies 2023
                derived_model_year = 2023
            
            # Map Hebrew area name (א,ב,ג,ד) to Latin letter (A,B,C,D)
            area_name_map_to_letter = {"א": "A", "ב": "B", "ג": "C", "ד": "D"}
            derived_model_area_definition = area_name_map_to_letter.get(city_area_name_selection)

            if derived_model_year and derived_model_area_definition:
                actual_selected_city_name = self.city_info.get('city', None) # This is the Hebrew city name from GUI

                self.update_status(f"Energy Rating Report: Using City='{actual_selected_city_name}', Year={derived_model_year}, AreaDef='{derived_model_area_definition}'")
                
                energy_rating_gen = EnergyRatingReportGenerator(
                    energy_rating_parser=energy_rating_parser_instance,
                    output_dir=base_output_dir_for_reports,
                    model_year=derived_model_year,
                    model_area_definition=derived_model_area_definition,
                    selected_city_name=actual_selected_city_name,
                    project_name=project_name,
                    run_id=run_id,
                    area_name=area_name_hebrew
                )
                # The output_filename is relative to output_dir in the generator
                success_er = energy_rating_gen.generate_report(output_filename=os.path.basename(report_paths["energy_rating"]))
                if success_er:
                    self.update_status(f"Energy Rating report generated successfully at {report_paths['energy_rating']}")
                else:
                    self.update_status("Energy Rating report generation failed (check console for details).")

                # Generate total energy rating report
                try:
                    total_rating_path = energy_rating_gen.generate_total_energy_rating_report(output_filename="total_energy_rating.pdf")
                    if total_rating_path:
                        self.update_status(f"Total Energy Rating report generated successfully at {total_rating_path}")
                    else:
                        self.update_status("Total Energy Rating report generation failed (check console for details).")
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


    def process_idf(self, input_file: str, idd_path: str, output_dir: str) -> bool:
        """
        Main method to process an IDF file and generate all reports.
        """
        try:
            project_name = Path(input_file).stem
            run_id = datetime.now().strftime('%Y%m%d_%H%M%S')

            self.update_progress(0.0)
            self.update_status("Initializing...")

            report_paths = self._setup_output_paths(output_dir)
            base_reports_dir = os.path.join(output_dir, "reports") # Used by EnergyRatingGenerator

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
                self.update_status(f"Using city area '{city_area_name_for_loss}' for thermal loss calculations.")
            
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
                city_area_name_selection=current_city_area_name
            )

            if self.is_cancelled:
                self.update_status("Processing cancelled during report generation.")
                return False

            self.update_status("Processing completed successfully!")
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
        self.update_status("Cancellation request received.")


class IDFProcessorGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.title("🏗️ IDF Report Generator")
        self.geometry("1200x900")
        self.minsize(800, 600)

        self.primary_color = "#1f2937"
        self.secondary_color = "#374151"
        self.accent_color = "#3b82f6"
        self.success_color = "#10b981"
        self.warning_color = "#f59e0b"
        self.error_color = "#ef4444"
        self.text_color = "#f9fafb"
        self.info_text_color_light = "#374151" # Dark gray for light mode
        self.info_text_color_dark = "#9ca3af"  # Light gray for dark mode
        
        self.input_file = tk.StringVar()
        self.output_dir = tk.StringVar()
        self.city = tk.StringVar()
        self.city_area_name = tk.StringVar() # Stores "א", "ב", "ג", "ד"
        self.city_area_code = tk.StringVar() # Stores "1", "2", "3", "4"
        self.iso_type = tk.StringVar()
        self.energyplus_dir = tk.StringVar()
        self.is_processing = False
        self.settings_file = "settings.json"
        self.processing_manager = None # Will hold ProcessingManager instance

        self.input_file.trace_add("write", self.check_inputs_complete)
        self.output_dir.trace_add("write", self.check_inputs_complete)
        self.city.trace_add("write", self.check_inputs_complete)
        self.iso_type.trace_add("write", self.check_inputs_complete)
        self.energyplus_dir.trace_add("write", self.check_inputs_complete)

        self.city_data = self.load_cities_from_csv()
        self.iso_types = [
            "RESIDNTIAL 2023", "RESIDNTIAL 2017", "HOTEL",
            "EDUCATION", "OFFICE", "CORE & ENVELOPE"
        ]

        self.create_widgets()
        self.load_settings()
        self.setup_layout()
        self.check_inputs_complete() # Initial check
        self.bind("<<AppearanceModeChanged>>", self._update_info_tag_color)


    def _update_info_tag_color(self, event=None):
        """Updates the info tag color when appearance mode changes."""
        if hasattr(self, 'status_text'):
            current_mode = ctk.get_appearance_mode()
            info_fg_color = self.info_text_color_dark if current_mode == "Dark" else self.info_text_color_light
            self.status_text.tag_config("info", foreground=info_fg_color)


    def setup_layout(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0) 
        self.grid_rowconfigure(1, weight=1)

    def load_cities_from_csv(self):
        cities_data = {}
        csv_path = os.path.join('data', 'countries-selection.csv')
        try:
            if os.path.exists(csv_path):
                with open(csv_path, 'r', encoding='utf-8') as f:
                    next(f) # Skip header row if present
                    for line in f:
                        parts = [part.strip() for part in line.split(',')]
                        if len(parts) >= 3:
                            city_name, area_name, area_code = parts[0], parts[1], parts[2]
                            cities_data[city_name] = {'area_name': area_name, 'area_code': area_code}
            else:
                self.after(100, lambda: self.show_status(f"Warning: City data file not found at '{csv_path}'.", "warning"))
        except Exception as e:
            logger.error(f"Error loading city data from {csv_path}: {e}", exc_info=True)
            self.after(100, lambda: self.show_status(f"Error loading city data: {e}", "error"))
        return cities_data

    def on_city_selected(self, event=None): # event is passed by Combobox
        selected_city_name = self.city.get()
        if selected_city_name in self.city_data:
            info = self.city_data[selected_city_name]
            self.city_area_name.set(info['area_name'])
            self.city_area_code.set(info['area_code'])
            self.show_status(f"Selected city: {selected_city_name}, Area: {info['area_name']}, Code: {info['area_code']}")
        else:
            self.city_area_name.set("")
            self.city_area_code.set("")
        self.save_settings() # Save on change
        self.check_inputs_complete()


    def update_validation_indicators(self):
        # Ensure widgets exist before configuring
        if not all(hasattr(self, w_name) for w_name in ['input_entry', 'output_entry', 'eplus_entry', 'city_combobox', 'iso_combobox']):
            return

        valid_style = {"border_color": self.success_color}
        invalid_style = {"border_color": self.error_color}

        self.input_entry.configure(**(valid_style if self.input_file.get() and os.path.exists(self.input_file.get()) else invalid_style))
        self.output_entry.configure(**(valid_style if self.output_dir.get() and os.path.isdir(self.output_dir.get()) else invalid_style))
        self.eplus_entry.configure(**(valid_style if self.energyplus_dir.get() and os.path.isdir(self.energyplus_dir.get()) else invalid_style))
        self.city_combobox.configure(**(valid_style if self.city.get() else invalid_style))
        self.iso_combobox.configure(**(valid_style if self.iso_type.get() else invalid_style))

    def _create_modern_header(self) -> ctk.CTkFrame:
        header_frame = ctk.CTkFrame(self, height=80, corner_radius=0, fg_color=self.primary_color)
        header_frame.grid(row=0, column=0, sticky="ew")
        header_frame.grid_columnconfigure(0, weight=1)
        header_frame.grid_propagate(False)
        ctk.CTkLabel(header_frame, text="🏗️ IDF Report Generator", font=ctk.CTkFont(size=32, weight="bold"), text_color=self.text_color).pack(pady=(10,0))
        ctk.CTkLabel(header_frame, text="Professional Building Energy Analysis & Reporting Suite", font=ctk.CTkFont(size=14), text_color=("#94a3b8", "#cbd5e1")).pack(pady=(0,10))
        return header_frame

    def _create_file_input_row(self, parent, row_idx, label_text, var, cmd, entry_attr_name):
        row_frame = ctk.CTkFrame(parent, fg_color="transparent")
        row_frame.grid(row=row_idx, column=0, padx=20, pady=8, sticky="ew")
        row_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(row_frame, text=label_text, font=ctk.CTkFont(size=14, weight="bold"), width=180, anchor="w").grid(row=0, column=0, padx=(0,15), pady=5)
        entry = ctk.CTkEntry(row_frame, textvariable=var, height=40, corner_radius=8, border_width=2, font=ctk.CTkFont(size=12))
        entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        setattr(self, entry_attr_name, entry)
        ctk.CTkButton(row_frame, text="Browse", command=cmd, width=100, height=40, corner_radius=8, font=ctk.CTkFont(size=12, weight="bold"), fg_color=self.accent_color, hover_color=("#2563eb", "#1d4ed8")).grid(row=0, column=2, padx=(5,0), pady=5)

    def _create_input_section(self, parent) -> ctk.CTkFrame:
        section = ctk.CTkFrame(parent, corner_radius=15)
        section.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(section, text="📁 File Configuration", font=ctk.CTkFont(size=18, weight="bold"), anchor="w").grid(row=0, column=0, padx=20, pady=(20,10), sticky="w")
        self._create_file_input_row(section, 1, "📄 Input IDF File:", self.input_file, self.select_input_file, "input_entry")
        self._create_file_input_row(section, 2, "⚡ EnergyPlus Dir:", self.energyplus_dir, self.select_energyplus_dir, "eplus_entry")
        self._create_file_input_row(section, 3, "📂 Output Dir:", self.output_dir, self.select_output_dir, "output_entry")
        return section

    def _create_scrollable_selection_row(self, parent, row_idx, label_text, values, var, cmd, combo_attr_name):
        ctk.CTkLabel(parent, text=label_text, font=ctk.CTkFont(size=14, weight="bold"), width=180, anchor="w").grid(row=row_idx, column=0, padx=(20,15), pady=10, sticky="w")
        combobox = ctk.CTkComboBox(parent, values=values, variable=var, command=cmd, width=300, height=40, corner_radius=8, border_width=2, font=ctk.CTkFont(size=12), dropdown_font=ctk.CTkFont(size=11), state="readonly", justify="left")
        combobox.grid(row=row_idx, column=1, padx=(0,20), pady=10, sticky="ew")
        setattr(self, combo_attr_name, combobox)


    def _create_selection_section(self, parent) -> ctk.CTkFrame:
        section = ctk.CTkFrame(parent, corner_radius=15)
        section.grid_columnconfigure(1, weight=1) # Allow combobox to expand
        ctk.CTkLabel(section, text="⚙️ Analysis Configuration", font=ctk.CTkFont(size=18, weight="bold"), anchor="w").grid(row=0, column=0, columnspan=2, padx=20, pady=(20,15), sticky="w")
        self._create_scrollable_selection_row(section, 1, "🏙️ City:", sorted(list(self.city_data.keys())), self.city, self.on_city_selected, "city_combobox")
        self._create_scrollable_selection_row(section, 2, "📋 ISO Type:", self.iso_types, self.iso_type, lambda x: self.save_settings(), "iso_combobox") # Save on change
        return section

    def _create_progress_section(self, parent) -> ctk.CTkFrame:
        section = ctk.CTkFrame(parent, corner_radius=15)
        section.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(section, text="📊 Processing Status", font=ctk.CTkFont(size=18, weight="bold"), anchor="w").grid(row=0, column=0, padx=20, pady=(20,10), sticky="w")
        self.progress_bar = ctk.CTkProgressBar(section, height=20, corner_radius=10, progress_color=self.success_color, fg_color=("#e5e7eb", "#374151"))
        self.progress_bar.set(0)
        self.progress_bar.grid(row=1, column=0, padx=20, pady=(0,15), sticky="ew")
        return section

    def _create_log_section(self, parent) -> ctk.CTkFrame:
        section = ctk.CTkFrame(parent, corner_radius=15)
        section.grid_columnconfigure(0, weight=1)
        section.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(section, text="📋 Activity Log", font=ctk.CTkFont(size=18, weight="bold"), anchor="w").grid(row=0, column=0, padx=20, pady=(20,10), sticky="w")
        self.status_text = ctk.CTkTextbox(section, height=200, corner_radius=10, border_width=1, font=ctk.CTkFont(family="Consolas", size=11), wrap=tk.WORD)
        self.status_text.grid(row=1, column=0, padx=20, pady=(0,20), sticky="nsew")
        
        self.status_text.tag_config("error", foreground=self.error_color)
        self.status_text.tag_config("success", foreground=self.success_color)
        self.status_text.tag_config("warning", foreground=self.warning_color)
        
        # Set initial info tag color
        self._update_info_tag_color()
        return section

    def _create_control_section(self, parent) -> ctk.CTkFrame:
        section = ctk.CTkFrame(parent, fg_color="transparent")
        section.grid_columnconfigure((0,1), weight=1)
        self.process_button = ctk.CTkButton(section, text="🚀 Generate Reports", command=self.start_processing, height=50, corner_radius=12, font=ctk.CTkFont(size=16, weight="bold"), fg_color=self.accent_color, hover_color=("#2563eb", "#1d4ed8"))
        self.process_button.grid(row=0, column=0, padx=(0,10), pady=10, sticky="ew")
        self.cancel_button = ctk.CTkButton(section, text="⏹️ Cancel", command=self.cancel_processing, state="disabled", height=50, corner_radius=12, font=ctk.CTkFont(size=16, weight="bold"), fg_color=self.error_color, hover_color=("#dc2626", "#b91c1c"))
        self.cancel_button.grid(row=0, column=1, padx=(10,0), pady=10, sticky="ew")
        return section

    def create_widgets(self) -> None:
        self.configure(fg_color=("#f8fafc", "#0f172a"))
        self._create_modern_header()
        main_scroll = ctk.CTkScrollableFrame(self, corner_radius=0, fg_color="transparent")
        main_scroll.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0,20))
        main_scroll.grid_columnconfigure(0, weight=1)

        input_section = self._create_input_section(main_scroll)
        input_section.grid(row=0, column=0, sticky="ew", pady=(0,20))
        selection_section = self._create_selection_section(main_scroll)
        selection_section.grid(row=1, column=0, sticky="ew", pady=(0,20))
        progress_section = self._create_progress_section(main_scroll)
        progress_section.grid(row=2, column=0, sticky="ew", pady=(0,20))
        log_section = self._create_log_section(main_scroll)
        log_section.grid(row=3, column=0, sticky="nsew", pady=(0,20))
        control_section = self._create_control_section(main_scroll)
        control_section.grid(row=4, column=0, sticky="ew")
        main_scroll.grid_rowconfigure(3, weight=1) # Log section expands
        self.show_status("🎉 Welcome! Configure fields to begin.")


    def select_input_file(self):
        path = filedialog.askopenfilename(title="Select IDF File", filetypes=[("IDF files", "*.idf"), ("All files", "*.*")])
        if path: self.input_file.set(path); self.save_settings()

    def select_output_dir(self):
        path = filedialog.askdirectory(title="Select Output Directory")
        if path: self.output_dir.set(path); self.save_settings()

    def select_energyplus_dir(self):
        path = filedialog.askdirectory(title="Select EnergyPlus Installation Directory")
        if path: self.energyplus_dir.set(path); self.save_settings()

    def load_settings(self):
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f: settings = json.load(f)
                self.input_file.set(settings.get('last_input', ''))
                self.energyplus_dir.set(settings.get('last_eplus_dir', ''))
                self.output_dir.set(settings.get('last_output', ''))
                self.city.set(settings.get('last_city', ''))
                # Trigger on_city_selected if city is loaded to populate area_name/code
                if self.city.get(): self.on_city_selected()
                self.iso_type.set(settings.get('last_iso_type', ''))
        except Exception as e:
            logger.error(f"Error loading settings: {e}", exc_info=True)
            self.show_status(f"Error loading settings: {e}", "error")

    def save_settings(self):
        try:
            settings = {
                'last_input': self.input_file.get(), 'last_eplus_dir': self.energyplus_dir.get(),
                'last_output': self.output_dir.get(), 'last_city': self.city.get(),
                'last_iso_type': self.iso_type.get()
            }
            with open(self.settings_file, 'w') as f: json.dump(settings, f, indent=4)
            # self.show_status("Settings saved.") # Can be too noisy
        except Exception as e:
            logger.error(f"Error saving settings: {e}", exc_info=True)
            self.show_status(f"Error saving settings: {e}", "error")
        self.check_inputs_complete()


    def show_status(self, message, level="info"):
        timestamp = datetime.now().strftime('%H:%M:%S')
        emoji_map = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "error": "❌"}
        
        # Auto-detect level
        msg_lower = message.lower()
        if level == "info":
            if any(err_word in msg_lower for err_word in ["error", "failed", "could not"]): level = "error"
            elif any(succ_word in msg_lower for succ_word in ["success", "completed", "generated"]): level = "success"
            elif any(warn_word in msg_lower for warn_word in ["warning", "cancelled", "skipping"]): level = "warning"

        emoji = emoji_map.get(level, "ℹ️")
        self.status_text.insert(tk.END, f"{timestamp} {emoji} {message}\n", (level,))
        self.status_text.see(tk.END)
        if level == "error": logger.error(f"GUI: {message}")
        elif level == "warning": logger.warning(f"GUI: {message}")
        else: logger.info(f"GUI: {message}")


    def validate_inputs(self):
        validations = [
            (self.input_file.get(), "Please select an input IDF file."),
            (os.path.exists(self.input_file.get()), f"Input IDF file not found: {self.input_file.get()}"),
            (self.energyplus_dir.get(), "Please select the EnergyPlus installation directory."),
            (os.path.isdir(self.energyplus_dir.get()), "EnergyPlus path is not a valid directory."),
            (os.path.exists(os.path.join(self.energyplus_dir.get(), "energyplus.exe")), f"energyplus.exe not found in {self.energyplus_dir.get()}"),
            (os.path.exists(os.path.join(self.energyplus_dir.get(), "Energy+.idd")), f"Energy+.idd not found in {self.energyplus_dir.get()}"),
            (self.output_dir.get(), "Please select an output directory."),
            (self.city.get(), "Please select a city."),
            (self.iso_type.get(), "Please select an ISO type.")
        ]
        for condition, msg in validations:
            if not condition: messagebox.showerror("Input Error", msg); return False
        
        if not os.path.exists(self.output_dir.get()):
            try: os.makedirs(self.output_dir.get()); self.show_status(f"Created output directory: {self.output_dir.get()}")
            except OSError as e: messagebox.showerror("Error", f"Could not create output dir: {e.strerror}"); return False
        elif not os.path.isdir(self.output_dir.get()):
             messagebox.showerror("Input Error", f"Output path '{self.output_dir.get()}' is not a directory."); return False
        return True

    def check_inputs_complete(self, *args):
        if not hasattr(self, 'process_button'): return # Widgets not created yet

        complete = all([
            self.input_file.get(), self.output_dir.get(), self.city.get(),
            self.iso_type.get(), self.energyplus_dir.get()
        ])
        
        button_state = "normal" if complete else "disabled"
        button_fg_color = self.accent_color if complete else ("#9ca3af", "#6b7280")
        button_text = "🚀 Generate Reports" if complete else "🚀 Complete Config First"

        self.process_button.configure(state=button_state, fg_color=button_fg_color, text=button_text)
        self.update_validation_indicators()


    def start_processing(self):
        if not self.validate_inputs(): return
        self.is_processing = True
        self.process_button.configure(state="disabled", text="🔄 Processing...")
        self.cancel_button.configure(state="normal")
        self.save_settings() # Save current valid settings before processing

        # Prepare for ProcessingManager
        user_inputs = self._get_user_inputs_for_processing()
        if not user_inputs: # Should be caught by validate_inputs, but as a safeguard
            self.reset_gui_state(); return

        # Create simulation output directory within the main output directory
        simulation_run_dir = os.path.join(user_inputs["output_dir"], f"simulation_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        try:
            os.makedirs(simulation_run_dir, exist_ok=True)
            self.show_status(f"Simulation output will be in: {simulation_run_dir}")
        except OSError as e:
            self.show_status(f"Error creating simulation directory '{simulation_run_dir}': {e.strerror}", "error")
            self.reset_gui_state(); return

        self.process_thread = threading.Thread(target=self.process_file_thread_target, args=(user_inputs, simulation_run_dir))
        self.process_thread.start()

    def _get_user_inputs_for_processing(self) -> dict | None:
        # This data is now mostly for the ProcessingManager, E+ run uses its own logic
        selected_city = self.city.get()
        city_details = self.city_data.get(selected_city, {})
        
        return {
            "input_file": self.input_file.get(),
            "output_dir": self.output_dir.get(), # Main output for reports
            "energyplus_dir": self.energyplus_dir.get(),
            "idd_path": os.path.join(self.energyplus_dir.get(), "Energy+.idd"),
            "energyplus_exe": os.path.join(self.energyplus_dir.get(), "energyplus.exe"),
            "city_info": { # For ProcessingManager
                'city': selected_city, # Hebrew name
                'area_name': city_details.get('area_name', ''), # "א", "ב", etc.
                'area_code': city_details.get('area_code', ''), # "1", "2", etc.
                'iso_type': self.iso_type.get() # Pass ISO type here
            }
        }

    def _determine_epw_file_path(self, city_info_from_gui: dict, iso_type_from_gui: str) -> str | None:
        area_name = city_info_from_gui.get('area_name') # "א", "ב", etc.
        area_code = city_info_from_gui.get('area_code') # "1", "2", etc.

        if not area_name or not area_code:
            self.show_status("Error: City area name or code missing for EPW selection.", "error")
            return None

        epw_filename = ""
        if iso_type_from_gui == "RESIDNTIAL 2023":
            epw_filename = f"{area_code}.epw" # e.g., "1.epw"
            self.show_status(f"RESIDNTIAL 2023: Using EPW by area code: {epw_filename}")
        else: # For other ISO types, use area_name (א -> a.epw)
            area_name_map_to_latin = {"א": "a", "ב": "b", "ג": "c", "ד": "d"}
            latin_letter = area_name_map_to_latin.get(area_name)
            if not latin_letter:
                self.show_status(f"Error: Cannot map area name '{area_name}' to EPW file letter.", "error")
                return None
            epw_filename = f"{latin_letter}.epw"
            self.show_status(f"ISO type {iso_type_from_gui}: Using EPW by area letter: {epw_filename}")
        
        epw_file_path = Path("data") / epw_filename
        if not epw_file_path.exists():
            self.show_status(f"Error: Weather file {epw_file_path} not found.", "error")
            return None
        self.show_status(f"Using weather file: {epw_file_path}")
        return str(epw_file_path)

    def _ensure_idf_output_variables(self, idf_path: str, idd_path: str) -> bool:
        self.show_status("Ensuring required IDF output variables...")
        try:
            data_loader = DataLoader() # Create a temporary loader
            # No need to load the full IDF here, just use the utility method
            modified = data_loader.ensure_output_variables(idf_path, idd_path)
            if modified:
                self.show_status("IDF output variables ensured/updated.")
            else:
                self.show_status("IDF output variables already present or no changes made.")
            return True # Assume success if no exception
        except Exception as e:
            self.show_status(f"Warning: Error ensuring IDF output variables: {e}. Energy Rating might be affected.", "warning")
            logger.error(f"Error in _ensure_idf_output_variables: {e}", exc_info=True)
            return False # Indicate failure

    def _run_energyplus_simulation(self, energyplus_exe: str, epw_file_path: str, simulation_output_dir: str, idf_path: str) -> str | None:
        self.show_status("Starting EnergyPlus simulation...")
        self.progress_bar.configure(mode='indeterminate'); self.progress_bar.start()
        self.update_idletasks()

        output_csv_path = os.path.join(simulation_output_dir, "eplustbl.csv")
        simulation_successful = False
        try:
            # Ensure the IDF has necessary output variables before running
            if not self._ensure_idf_output_variables(idf_path, os.path.join(os.path.dirname(energyplus_exe), "Energy+.idd")):
                 self.show_status("Skipping simulation due to issues with IDF output variables.", "warning")
                 return None # Critical step failed

            cmd = [energyplus_exe, "-w", epw_file_path, "-r", "-d", simulation_output_dir, idf_path]
            self.show_status(f"Running E+ command: {' '.join(cmd)}")
            
            process = subprocess.run(cmd, check=True, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            
            if process.stdout: logger.info(f"E+ STDOUT:\n{process.stdout}")
            if process.stderr: logger.warning(f"E+ STDERR:\n{process.stderr}") # E+ often uses stderr for info

            if os.path.exists(output_csv_path):
                # Check if CSV is empty or too small (basic check)
                if os.path.getsize(output_csv_path) > 100: # Arbitrary small size
                    self.show_status(f"EnergyPlus simulation successful. Output: {output_csv_path}")
                    simulation_successful = True
                else:
                    self.show_status(f"Warning: Simulation output file {output_csv_path} is very small or empty.", "warning")
            else:
                self.show_status(f"Simulation finished, but output file not found: {output_csv_path}", "error")
        
        except subprocess.CalledProcessError as e:
            error_detail = e.stderr.strip() if e.stderr else "No stderr output."
            stdout_detail = e.stdout.strip() if e.stdout else "No stdout output."
            logger.error(f"E+ CalledProcessError. RC: {e.returncode}. STDOUT:\n{stdout_detail}\nSTDERR:\n{error_detail}", exc_info=True)
            
            # Try to find a more specific error message
            specific_error = "Unknown simulation error."
            for line in reversed(error_detail.splitlines()): # Check stderr first
                if "**FATAL**" in line or "**SEVERE**" in line: specific_error = line.strip(); break
            if specific_error == "Unknown simulation error.": # Then check stdout
                 for line in reversed(stdout_detail.splitlines()):
                    if "**FATAL**" in line or "**SEVERE**" in line: specific_error = line.strip(); break
            if specific_error == "Unknown simulation error." and error_detail: # Fallback
                specific_error = error_detail.splitlines()[-1].strip() if error_detail.splitlines() else "No specific error in stderr."

            self.show_status(f"EnergyPlus simulation failed (RC {e.returncode}). Error: {specific_error}", "error")
        except FileNotFoundError:
            self.show_status(f"Error: energyplus.exe not found at '{energyplus_exe}'.", "error")
            logger.error(f"FileNotFoundError for energyplus.exe at {energyplus_exe}")
        except Exception as sim_e:
            self.show_status(f"Unexpected error during simulation: {type(sim_e).__name__} - {str(sim_e)}", "error")
            logger.error(f"Unexpected error in _run_energyplus_simulation: {sim_e}", exc_info=True)
        finally:
            self.progress_bar.stop(); self.progress_bar.configure(mode='determinate'); self.progress_bar.set(0)
            self.update_idletasks()
        return output_csv_path if simulation_successful else None

    def process_file_thread_target(self, user_inputs: dict, simulation_run_dir: str):
        """Target for the processing thread."""
        try:
            # 1. Determine EPW file
            epw_file = self._determine_epw_file_path(user_inputs["city_info"], user_inputs["city_info"]["iso_type"])
            if not epw_file:
                self.show_status("EPW file determination failed. Aborting.", "error")
                self.reset_gui_state(); return

            # 2. Run EnergyPlus Simulation
            simulation_output_csv = self._run_energyplus_simulation(
                user_inputs["energyplus_exe"],
                epw_file,
                simulation_run_dir, # E+ output goes here
                user_inputs["input_file"]
            )
            if not simulation_output_csv:
                self.show_status("EnergyPlus simulation failed or produced no output. Report generation may be incomplete.", "warning")
                # Decide if to proceed or abort. For now, proceed with None CSV.
            
            # 3. Initialize ProcessingManager
            self.processing_manager = ProcessingManager(
                status_callback=self.show_status,
                progress_callback=lambda p: self.progress_bar.set(p),
                simulation_output_csv=simulation_output_csv # Pass it, can be None
            )
            # Pass city_info (including iso_type) to ProcessingManager
            self.processing_manager.city_info = user_inputs["city_info"]


            # 4. Process IDF and Generate Reports
            success = self.processing_manager.process_idf(
                user_inputs["input_file"],
                user_inputs["idd_path"],
                user_inputs["output_dir"] # Reports go to main output dir
            )
            if success:
                self.show_status("All reports generated successfully!", "success")
                # Optionally open the output directory
                try:
                    if os.name == 'nt': # Windows
                        os.startfile(os.path.join(user_inputs["output_dir"], "reports"))
                    elif os.name == 'posix': # macOS, Linux
                        subprocess.run(['open', os.path.join(user_inputs["output_dir"], "reports")], check=False)
                except Exception as e_open:
                    logger.warning(f"Could not open output directory: {e_open}")
            else:
                self.show_status("Processing finished with errors or was cancelled.", "warning")

        except Exception as e:
            self.show_status(f"Critical error in processing thread: {e}", "error")
            logger.error(f"Critical error in processing thread: {e}", exc_info=True)
        finally:
            self.reset_gui_state()

    def reset_gui_state(self):
        """Resets GUI elements after processing or cancellation."""
        self.is_processing = False
        self.process_button.configure(state="normal", text="🚀 Generate Reports")
        self.cancel_button.configure(state="disabled")
        self.progress_bar.set(0)
        if self.processing_manager:
            self.processing_manager.is_cancelled = False # Reset for next run
        self.check_inputs_complete() # Re-evaluate button state

    def cancel_processing(self):
        if self.is_processing and self.processing_manager:
            self.show_status("Attempting to cancel processing...", "warning")
            self.processing_manager.cancel()
            # Note: Thread cancellation is cooperative. E+ simulation might not stop immediately.
        else:
            self.show_status("No active process to cancel.", "info")
        self.reset_gui_state()


if __name__ == "__main__":
    app = IDFProcessorGUI()
    app.mainloop()
