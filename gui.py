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
            self._ensure_directory_exists(os.path.join(dir_to_check, "dummy.txt"))
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
            energy_rating_parser.process_output()

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
            "lighting": parsers["lighting"].parse(),
            "area_loss": parsers["area_loss"].parse(),
        }

    def _generate_report_item(self, report_name: str, generation_function,
                              data, output_path: str, project_name: str, run_id: str,
                              is_generator_class: bool = False, **kwargs) -> bool:
        """
        Helper to generate a single report item.

        Args:
            report_name: Name of the report for status messages.
            generation_function: The function or class to generate the report.
            data: Data for the report (can be None if generator_class handles it).
            output_path: Path to save the report.
            project_name: Name of the project.
            run_id: Unique run ID.
            is_generator_class: True if generation_function is a class to be instantiated.
            **kwargs: Additional arguments for the generation_function.

        Returns:
            True if successful, False otherwise.
        """
        self.update_status(f"Generating {report_name} report...")
        success = False
        try:
            if is_generator_class:
                generator_instance = generation_function(data, output_path, project_name=project_name, run_id=run_id, **kwargs)
                if hasattr(generator_instance, 'generate_report'):
                     success = generator_instance.generate_report()
                elif 'output_filename' in kwargs and hasattr(generator_instance, 'generate_report'):
                     success = generator_instance.generate_report(output_filename=kwargs['output_filename'])

            else:
                generation_function(data, output_path, project_name=project_name, run_id=run_id, **kwargs)
                success = True

            if success:
                self.update_status(f"{report_name} report generated successfully.")
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
        progress_step = 0.7
        num_reports = 8
        progress_increment = (1.0 - progress_step) / num_reports

        self._generate_report_item("Settings", generate_settings_report_pdf, extracted_data["settings"], report_paths["settings"], project_name, run_id)
        progress_step += progress_increment; self.update_progress(progress_step)
        if self.is_cancelled: return

        self._generate_report_item("Schedules", generate_schedules_report_pdf, extracted_data["schedules"], report_paths["schedules"], project_name, run_id)
        progress_step += progress_increment; self.update_progress(progress_step)
        if self.is_cancelled: return

        self._generate_report_item("Loads", generate_loads_report_pdf, extracted_data["loads"], report_paths["loads"], project_name, run_id)
        progress_step += progress_increment; self.update_progress(progress_step)
        if self.is_cancelled: return

        self._generate_report_item("Materials", generate_materials_report_pdf, extracted_data["materials"], report_paths["materials"], project_name, run_id)
        progress_step += progress_increment; self.update_progress(progress_step)
        if self.is_cancelled: return

        self.update_status("Generating Area reports...")
        try:
            generate_area_reports(area_parser_instance, output_dir=report_paths["zones_dir"], project_name=project_name, run_id=run_id)
            self.update_status("Area reports generation attempted.")
        except Exception as e:
            error_message = f"Error generating Area reports: {type(e).__name__} - {str(e)}"
            self.update_status(error_message)
            logger.error(f"Exception in generate_area_reports: {e}", exc_info=True)
        progress_step += progress_increment; self.update_progress(progress_step)
        if self.is_cancelled: return

        self._generate_report_item("Glazing", generate_glazing_report_pdf, extracted_data["glazing"], report_paths["glazing"], project_name, run_id)
        progress_step += progress_increment; self.update_progress(progress_step)
        if self.is_cancelled: return

        self._generate_report_item("Lighting", LightingReportGenerator, extracted_data["lighting"], report_paths["lighting"], project_name, run_id, is_generator_class=True)
        progress_step += progress_increment; self.update_progress(progress_step)
        if self.is_cancelled: return

        self._generate_report_item("Area Loss", generate_area_loss_report_pdf, extracted_data["area_loss"], report_paths["area_loss"], project_name, run_id)
        progress_step += progress_increment; self.update_progress(progress_step)
        if self.is_cancelled: return

        self.update_status("Generating Energy Rating report (PDF)...")
        try:

            derived_model_year = None
            derived_model_area_definition = None

            if "2017" in iso_type_selection:
                derived_model_year = 2017
            elif "2023" in iso_type_selection:
                derived_model_year = 2023

            area_name_map_to_letter = {"א": "A", "ב": "B", "ג": "C", "ד": "D"}
            derived_model_area_definition = area_name_map_to_letter.get(city_area_name_selection)

            if derived_model_year and derived_model_area_definition:
                actual_selected_city_name = self.city_info.get('city', None)

                self.update_status(f"Energy Rating Report: Using City='{actual_selected_city_name}', Year={derived_model_year}, AreaDef='{derived_model_area_definition}'")
                energy_rating_gen = EnergyRatingReportGenerator(
                    energy_rating_parser_instance,
                    output_dir=base_output_dir_for_reports,
                    model_year=derived_model_year,
                    model_area_definition=derived_model_area_definition,
                    selected_city_name=actual_selected_city_name
                )
                success_er = energy_rating_gen.generate_report(output_filename=os.path.basename(report_paths["energy_rating"]))
                if success_er:
                    self.update_status("Energy Rating report generated successfully.")
                else:
                    self.update_status("Energy Rating report generation failed (check console for details).")
            else:
                self.update_status(f"Energy Rating Report: Could not determine model_year ('{derived_model_year}') or model_area_definition ('{derived_model_area_definition}') from ISO type '{iso_type_selection}' and city area '{city_area_name_selection}'. Skipping report.", "warning")
                logger.warning(f"Energy Rating Report: Skipping due to missing derived_model_year or derived_model_area_definition. ISO: {iso_type_selection}, City Area: {city_area_name_selection}")
        except Exception as e:
            error_message = f"Error generating Energy Rating PDF report: {type(e).__name__} - {str(e)}"
            self.update_status(error_message)
            logger.error(f"Exception in EnergyRatingReportGenerator: {e}", exc_info=True)
        self.update_progress(1.0)

    def process_idf(self, input_file: str, idd_path: str, output_dir: str) -> bool:
        """
        Main method to process an IDF file and generate all reports.

        Args:
            input_file: Path to the input IDF file.
            idd_path: Path to the Energy+.idd file.
            output_dir: Directory to save the output reports.

        Returns:
            True if processing was successful, False otherwise.
        """
        try:
            project_name = Path(input_file).stem
            run_id = datetime.now().strftime('%Y%m%d_%H%M%S')

            self.update_progress(0.0)
            self.update_status("Initializing...")

            report_paths = self._setup_output_paths(output_dir)
            base_reports_dir = os.path.join(output_dir, "reports")

            if self.is_cancelled: return False
            self.update_progress(0.1)

            data_loader, eppy_handler, idf = self._initialize_core_components(input_file, idd_path)

            if self.is_cancelled: return False
            self.update_progress(0.2)

            city_area_name = "א"
            if self.city_info and 'area_name' in self.city_info:
                city_area_name = self.city_info.get('area_name', "א")
                self.update_status(f"Using city area '{city_area_name}' for thermal loss calculations.")

            temp_materials_parser = MaterialsParser(data_loader)
            temp_area_parser = AreaParser(data_loader, temp_materials_parser, self.simulation_output_csv)

            parsers = self._initialize_parsers(data_loader, temp_area_parser, city_area_name)
            parsers["materials"] = temp_materials_parser
            parsers["area"] = temp_area_parser

            if self.is_cancelled: return False
            self.update_progress(0.3)

            self._process_data_sources(parsers, idf, eppy_handler, data_loader, self.simulation_output_csv)

            if self.is_cancelled: return False
            self.update_progress(0.6)

            extracted_data = self._extract_data_from_parsers(parsers)

            if self.is_cancelled: return False
            self.update_progress(0.7)

            current_iso_type = self.city_info.get('iso_type', '')
            current_city_area = self.city_info.get('area_name', '')

            self._generate_all_reports(
                extracted_data,
                report_paths,
                project_name,
                run_id,
                parsers["area"],
                parsers["energy_rating"],
                base_reports_dir,
                iso_type_selection=current_iso_type,
                city_area_name_selection=current_city_area
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
            raise
        except (IOError, OSError) as os_io_err:
            user_message = f"Error: File or system operation failed. Path: {getattr(os_io_err, 'filename', 'N/A')}. Details: {os_io_err.strerror}"
            self.update_status(user_message)
            logger.error(user_message, exc_info=True)
            raise
        except Exception as e:
            user_message = f"An unexpected error occurred during IDF processing: {type(e).__name__} - {str(e)}"
            self.update_status(user_message)
            logger.error(f"Unexpected error in process_idf: {e}", exc_info=True)
            raise

    def cancel(self):
        """Signals that the current processing should be cancelled."""
        self.is_cancelled = True
        self.update_status("Cancellation request received.")

class IDFProcessorGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.title("IDF Report Generator")
        self.geometry("900x800")

        self.input_file = tk.StringVar()
        self.output_dir = tk.StringVar()
        self.city = tk.StringVar()
        self.city_area_name = tk.StringVar()
        self.city_area_code = tk.StringVar()
        self.iso_type = tk.StringVar()
        self.energyplus_dir = tk.StringVar()
        self.is_processing = False
        self.settings_file = "settings.json"

        self.input_file.trace_add("write", self.check_inputs_complete)
        self.output_dir.trace_add("write", self.check_inputs_complete)
        self.city.trace_add("write", self.check_inputs_complete)
        self.iso_type.trace_add("write", self.check_inputs_complete)
        self.energyplus_dir.trace_add("write", self.check_inputs_complete)

        self.city_data = self.load_cities_from_csv()
        self.iso_types = [
            "RESIDNTIAL 2023",
            "RESIDNTIAL 2017",
            "HOTEL",
            "EDUCATION",
            "OFFICE",
            "CORE & ENVELOPE"
        ]

        self.create_widgets()
        self.load_settings()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=0)
        self.grid_rowconfigure(3, weight=0)
        self.grid_rowconfigure(4, weight=0)
        self.grid_rowconfigure(5, weight=0)
        self.grid_rowconfigure(6, weight=1)
        self.grid_rowconfigure(7, weight=0)

        self.check_inputs_complete()

    def load_cities_from_csv(self):
        """Load city data from the CSV file"""
        cities_data = {}
        csv_path = os.path.join('data', 'countries-selection.csv')

        try:
            if os.path.exists(csv_path):
                with open(csv_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        parts = [part.strip() for part in line.split(',')]
                        if len(parts) >= 3:
                            city_name = parts[0].strip()
                            area_name = parts[1].strip()
                            area_code = parts[2].strip()
                            cities_data[city_name] = {'area_name': area_name, 'area_code': area_code}
            else:
                self.show_status(f"Warning: City data file not found at '{csv_path}'. City-dependent features may be affected.")
        except FileNotFoundError:
            self.show_status(f"Error: City data file not found at '{csv_path}'. Please ensure 'data/countries-selection.csv' exists.")
            logger.error(f"FileNotFoundError for city data file: {csv_path}")
        except IOError as e:
            self.show_status(f"Error: Could not read city data file at '{csv_path}'. Reason: {e.strerror}")
            logger.error(f"IOError reading city data file {csv_path}: {e}", exc_info=True)
        except Exception as e:
            self.show_status(f"Error loading or parsing city data from '{csv_path}': {type(e).__name__} - {str(e)}")
            logger.error(f"Unexpected error loading city data from {csv_path}: {e}", exc_info=True)
        return cities_data

    def on_city_selected(self, event=None):
        """Handle city selection event"""
        selected_city = self.city.get()
        if selected_city in self.city_data:
            city_info = self.city_data[selected_city]
            self.city_area_name.set(city_info['area_name'])
            self.city_area_code.set(city_info['area_code'])
            self.show_status(f"Selected city: {selected_city}, Area: {city_info['area_name']}, Code: {city_info['area_code']}")
        else:
            self.city_area_name.set("")
            self.city_area_code.set("")

    def update_validation_indicators(self):
        """Update visual indicators for each input field based on validation"""
        has_input_file = bool(self.input_file.get())
        has_output_dir = bool(self.output_dir.get())
        has_eplus_dir = bool(self.energyplus_dir.get())
        has_city = bool(self.city.get())
        has_iso = bool(self.iso_type.get())

        self.input_entry.configure(
            border_color=("#2CC985" if has_input_file else "#E74C3C")
        )
        self.output_entry.configure(
            border_color=("#2CC985" if has_output_dir else "#E74C3C")
        )
        self.eplus_entry.configure(
            border_color=("#2CC985" if has_eplus_dir else "#E74C3C")
        )
        self.city_combobox.configure(
            border_color=("#2CC985" if has_city else "#E74C3C")
        )
        self.iso_combobox.configure(
            border_color=("#2CC985" if has_iso else "#E74C3C")
        )

    def _create_header_frame(self) -> ctk.CTkFrame:
        """Creates the header frame with the application title."""
        header_frame = ctk.CTkFrame(self, height=60, corner_radius=0)
        header_frame.grid(row=0, column=0, sticky="ew")
        header_frame.grid_columnconfigure(0, weight=1)
        header_frame.grid_propagate(False)

        app_title = ctk.CTkLabel(
            header_frame,
            text="IDF Report Generator",
            font=ctk.CTkFont(size=20, weight="bold"),
            anchor="center"
        )
        app_title.grid(row=0, column=0, padx=20, pady=15)
        return header_frame

    def _create_input_file_frame(self, parent_frame: ctk.CTkFrame) -> None:
        """Creates the frame for IDF input file selection."""
        input_frame = ctk.CTkFrame(parent_frame, corner_radius=10)
        input_frame.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="ew")
        input_frame.grid_columnconfigure(1, weight=1)

        input_label = ctk.CTkLabel(input_frame, text="Input IDF File:", width=120, anchor="w")
        input_label.grid(row=0, column=0, padx=(10, 5), pady=10)

        self.input_entry = ctk.CTkEntry(input_frame, textvariable=self.input_file, height=32)
        self.input_entry.grid(row=0, column=1, padx=5, pady=10, sticky="ew")

        input_button = ctk.CTkButton(
            input_frame, text="Browse", command=self.select_input_file, width=80, height=32,
            fg_color=("#3a7ebf", "#1f538d"), hover_color=("#2b5f8f", "#144272")
        )
        input_button.grid(row=0, column=2, padx=(5, 10), pady=10)

    def _create_energyplus_dir_frame(self, parent_frame: ctk.CTkFrame) -> None:
        """Creates the frame for EnergyPlus directory selection."""
        eplus_frame = ctk.CTkFrame(parent_frame, corner_radius=10)
        eplus_frame.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        eplus_frame.grid_columnconfigure(1, weight=1)

        eplus_label = ctk.CTkLabel(eplus_frame, text="EnergyPlus Dir:", width=120, anchor="w")
        eplus_label.grid(row=0, column=0, padx=(10, 5), pady=10)

        self.eplus_entry = ctk.CTkEntry(eplus_frame, textvariable=self.energyplus_dir, height=32)
        self.eplus_entry.grid(row=0, column=1, padx=5, pady=10, sticky="ew")

        eplus_button = ctk.CTkButton(
            eplus_frame, text="Browse", command=self.select_energyplus_dir, width=80, height=32,
            fg_color=("#3a7ebf", "#1f538d"), hover_color=("#2b5f8f", "#144272")
        )
        eplus_button.grid(row=0, column=2, padx=(5, 10), pady=10)

    def _create_output_dir_frame(self, parent_frame: ctk.CTkFrame) -> None:
        """Creates the frame for output directory selection."""
        output_frame = ctk.CTkFrame(parent_frame, corner_radius=10)
        output_frame.grid(row=2, column=0, padx=10, pady=5, sticky="ew")
        output_frame.grid_columnconfigure(1, weight=1)

        output_label = ctk.CTkLabel(output_frame, text="Output Directory:", width=120, anchor="w")
        output_label.grid(row=0, column=0, padx=(10, 5), pady=10)

        self.output_entry = ctk.CTkEntry(output_frame, textvariable=self.output_dir, height=32)
        self.output_entry.grid(row=0, column=1, padx=5, pady=10, sticky="ew")

        output_button = ctk.CTkButton(
            output_frame, text="Browse", command=self.select_output_dir, width=80, height=32,
            fg_color=("#3a7ebf", "#1f538d"), hover_color=("#2b5f8f", "#144272")
        )
        output_button.grid(row=0, column=2, padx=(5, 10), pady=10)

    def _create_city_selection_frame(self, parent_frame: ctk.CTkFrame) -> None:
        """Creates the frame for city selection."""
        city_frame = ctk.CTkFrame(parent_frame, corner_radius=10)
        city_frame.grid(row=3, column=0, padx=10, pady=5, sticky="ew")
        city_frame.grid_columnconfigure(1, weight=1)

        city_label = ctk.CTkLabel(city_frame, text="City:", width=120, anchor="w")
        city_label.grid(row=0, column=0, padx=(10, 5), pady=10)

        self.city_combobox = ctk.CTkComboBox(
            city_frame, values=list(self.city_data.keys()), variable=self.city,
            width=400, state="readonly", height=32, dropdown_hover_color=("#3a7ebf", "#1f538d")
        )
        self.city_combobox.grid(row=0, column=1, padx=5, pady=10, sticky="ew")
        self.city_combobox.bind("<<ComboboxSelected>>", self.on_city_selected)

    def _create_iso_type_frame(self, parent_frame: ctk.CTkFrame) -> None:
        """Creates the frame for ISO type selection."""
        iso_frame = ctk.CTkFrame(parent_frame, corner_radius=10)
        iso_frame.grid(row=4, column=0, padx=10, pady=5, sticky="ew")
        iso_frame.grid_columnconfigure(1, weight=1)

        iso_label = ctk.CTkLabel(iso_frame, text="ISO Type:", width=120, anchor="w")
        iso_label.grid(row=0, column=0, padx=(10, 5), pady=10)

        self.iso_combobox = ctk.CTkComboBox(
            iso_frame, values=self.iso_types, variable=self.iso_type,
            width=400, state="readonly", height=32, dropdown_hover_color=("#3a7ebf", "#1f538d")
        )
        self.iso_combobox.grid(row=0, column=1, padx=5, pady=10, sticky="ew")

    def _create_progress_frame(self, parent_frame: ctk.CTkFrame) -> None:
        """Creates the frame for the progress bar."""
        progress_frame = ctk.CTkFrame(parent_frame, corner_radius=10)
        progress_frame.grid(row=5, column=0, padx=10, pady=(15, 5), sticky="ew")
        progress_frame.grid_columnconfigure(0, weight=1)

        progress_label = ctk.CTkLabel(progress_frame, text="Processing Status:", anchor="w")
        progress_label.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="w")

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ctk.CTkProgressBar(
            progress_frame, height=15, corner_radius=5,
            progress_color=("#3a7ebf", "#1f538d"), fg_color=("#E0E0E0", "#2D2D2D")
        )
        self.progress_bar.set(0)
        self.progress_bar.grid(row=1, column=0, padx=10, pady=(5, 10), sticky="ew")

    def _create_status_log_frame(self, parent_frame: ctk.CTkFrame) -> None:
        """Creates the frame for the status log text area."""
        status_frame = ctk.CTkFrame(parent_frame, corner_radius=10)
        status_frame.grid(row=6, column=0, padx=10, pady=5, sticky="nsew")
        status_frame.grid_columnconfigure(0, weight=1)
        status_frame.grid_rowconfigure(1, weight=1)

        status_label = ctk.CTkLabel(status_frame, text="Log Messages:", anchor="w")
        status_label.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="w")

        self.status_text = ctk.CTkTextbox(
            status_frame, height=150, wrap=tk.WORD, corner_radius=5,
            border_width=1, border_color=("#CCCCCC", "#333333")
        )
        self.status_text.grid(row=1, column=0, padx=10, pady=(5, 10), sticky="nsew")

        self.status_text.tag_config("error", foreground="#E74C3C")
        self.status_text.tag_config("success", foreground="#2CC985")
        self.status_text.tag_config("warning", foreground="#F39C12")
        info_fg_color = "#CCCCCC" if ctk.get_appearance_mode() == "Dark" else "#333333"
        self.status_text.tag_config("info", foreground=info_fg_color)

    def _create_control_buttons_frame(self, parent_frame: ctk.CTkFrame) -> None:
        """Creates the frame for control buttons (Generate, Cancel)."""
        button_frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
        button_frame.grid(row=7, column=0, padx=10, pady=(15, 10), sticky="ew")
        button_frame.grid_columnconfigure((0, 1), weight=1)

        self.process_button = ctk.CTkButton(
            button_frame, text="Generate Reports", command=self.start_processing, height=40,
            font=ctk.CTkFont(size=14, weight="bold"), corner_radius=8, border_width=0,
            fg_color=("#3a7ebf", "#1f538d"), hover_color=("#2b5f8f", "#144272")
        )
        self.process_button.grid(row=0, column=0, padx=(0, 5), pady=5, sticky="ew")

        self.cancel_button = ctk.CTkButton(
            button_frame, text="Cancel", command=self.cancel_processing, state="disabled", height=40,
            font=ctk.CTkFont(size=14), corner_radius=8, border_width=0,
            fg_color=("#E74C3C", "#C0392B"), hover_color=("#C0392B", "#922B21")
        )
        self.cancel_button.grid(row=0, column=1, padx=(5, 0), pady=5, sticky="ew")

    def create_widgets(self) -> None:
        """Creates and configures all widgets for the GUI."""
        self.configure(fg_color=("#F0F0F0", "#2B2B2B"))

        self._create_header_frame()

        content_frame = ctk.CTkFrame(self)
        content_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        content_frame.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._create_input_file_frame(content_frame)
        self._create_energyplus_dir_frame(content_frame)
        self._create_output_dir_frame(content_frame)
        self._create_city_selection_frame(content_frame)
        self._create_iso_type_frame(content_frame)
        self._create_progress_frame(content_frame)
        self._create_status_log_frame(content_frame)
        self._create_control_buttons_frame(content_frame)

        content_frame.grid_rowconfigure(6, weight=1)

        self.show_status("Welcome to IDF Report Generator. Please select all required files to continue.")

    def select_input_file(self):
        file_path = filedialog.askopenfilename(
            title="Select IDF File",
            filetypes=[("IDF files", "*.idf"), ("All files", "*.*")]
        )
        if file_path:
            self.input_file.set(file_path)
            self.save_settings()

    def select_output_dir(self):
        dir_path = filedialog.askdirectory(title="Select Output Directory")
        if dir_path:
            self.output_dir.set(dir_path)
            self.save_settings()

    def select_energyplus_dir(self):
        dir_path = filedialog.askdirectory(title="Select EnergyPlus Installation Directory")
        if dir_path:
            self.energyplus_dir.set(dir_path)
            self.save_settings()

    def load_settings(self):
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                    self.input_file.set(settings.get('last_input', ''))
                    self.energyplus_dir.set(settings.get('last_eplus_dir', ''))
                    self.output_dir.set(settings.get('last_output', ''))

                    city = settings.get('last_city', '')
                    self.city.set(city)

                    stored_area_name = settings.get('last_city_area_name', '')
                    stored_area_code = settings.get('last_city_area_code', '')

                    if city and (not stored_area_name or not stored_area_code):
                        if city in self.city_data:
                            self.city_area_name.set(self.city_data[city]['area_name'])
                            self.city_area_code.set(self.city_data[city]['area_code'])
                            self.show_status(f"Initialized city: {city}, Area: {self.city_data[city]['area_name']}, Code: {self.city_data[city]['area_code']}")
                    else:
                        self.city_area_name.set(stored_area_name)
                        self.city_area_code.set(stored_area_code)

                    self.iso_type.set(settings.get('last_iso_type', ''))
        except FileNotFoundError:
            self.show_status(f"Info: Settings file '{self.settings_file}' not found. Using default values or creating a new one on save.")
        except json.JSONDecodeError as jde:
            self.show_status(f"Error: Could not parse settings file '{self.settings_file}'. File might be corrupted. Invalid JSON: {jde.msg}")
            logger.error(f"JSONDecodeError for settings file {self.settings_file}: {jde}", exc_info=True)
        except IOError as e:
            self.show_status(f"Error: Could not read settings file '{self.settings_file}'. Reason: {e.strerror}")
            logger.error(f"IOError reading settings file {self.settings_file}: {e}", exc_info=True)
        except Exception as e:
            self.show_status(f"Unexpected error loading settings from '{self.settings_file}': {type(e).__name__} - {str(e)}")
            logger.error(f"Unexpected error loading settings from {self.settings_file}: {e}", exc_info=True)

    def save_settings(self):
        try:
            settings = {
                'last_input': self.input_file.get(),
                'last_eplus_dir': self.energyplus_dir.get(),
                'last_output': self.output_dir.get(),
                'last_city': self.city.get(),
                'last_city_area_name': self.city_area_name.get(),
                'last_city_area_code': self.city_area_code.get(),
                'last_iso_type': self.iso_type.get()
            }
            with open(self.settings_file, 'w') as f:
                json.dump(settings, f, indent=4)
            self.show_status(f"Settings saved to '{self.settings_file}'.")
        except (IOError, OSError) as e:
            self.show_status(f"Error: Could not write settings to '{self.settings_file}'. Reason: {e.strerror}")
            logger.error(f"IOError/OSError saving settings to {self.settings_file}: {e}", exc_info=True)
        except Exception as e:
            self.show_status(f"Unexpected error saving settings to '{self.settings_file}': {type(e).__name__} - {str(e)}")
            logger.error(f"Unexpected error saving settings to {self.settings_file}: {e}", exc_info=True)

    def show_status(self, message, level="info"):
        timestamp = datetime.now().strftime('%H:%M:%S')
        full_message = f"{timestamp} - {message}\n"

        tag = level
        if level == "info":
            message_lower = message.lower()
            if "error" in message_lower or "failed" in message_lower:
                tag = "error"
            elif "success" in message_lower or "completed" in message_lower:
                tag = "success"
            elif "warning" in message_lower or "cancelled" in message_lower:
                tag = "warning"

        valid_tags = ["info", "error", "success", "warning"]
        if tag not in valid_tags:
            tag = "info"

        self.status_text.insert(tk.END, full_message, (tag,))
        self.status_text.see(tk.END)
        if tag == "error":
            logger.error(f"GUI Status: {message}")
        elif tag == "warning":
            logger.warning(f"GUI Status: {message}")

    def validate_inputs(self):
        if not self.input_file.get():
            messagebox.showerror("Error", "Please select an input IDF file.")
            return False
        if not os.path.exists(self.input_file.get()):
            messagebox.showerror("Error", "Selected input IDF file does not exist.")
            return False
        if not self.energyplus_dir.get():
            messagebox.showerror("Error", "Please select the EnergyPlus installation directory.")
            return False
        if not os.path.isdir(self.energyplus_dir.get()):
             messagebox.showerror("Error", "Selected EnergyPlus path is not a valid directory.")
             return False
        eplus_exe_path = os.path.join(self.energyplus_dir.get(), "energyplus.exe")
        eplus_idd_path = os.path.join(self.energyplus_dir.get(), "Energy+.idd")
        if not os.path.exists(eplus_exe_path):
            messagebox.showerror("Error", f"energyplus.exe not found in {self.energyplus_dir.get()}")
            return False
        if not os.path.exists(eplus_idd_path):
            messagebox.showerror("Error", f"Energy+.idd not found in {self.energyplus_dir.get()}")
            return False
        if not self.output_dir.get():
            messagebox.showerror("Error", "Please select an output directory.")
            return False
        if not os.path.exists(self.output_dir.get()):
            try:
                os.makedirs(self.output_dir.get())
                self.show_status(f"Created output directory: {self.output_dir.get()}", "info")
            except OSError as e:
                messagebox.showerror("Error", f"Could not create output directory '{self.output_dir.get()}'. Reason: {e.strerror}")
                logger.error(f"OSError creating output directory {self.output_dir.get()}: {e}", exc_info=True)
                return False
        if not self.city.get():
            messagebox.showerror("Error", "Please select a city.")
            return False
        if not self.iso_type.get():
            messagebox.showerror("Error", "Please select an ISO type.")
            return False
        return True

    def check_inputs_complete(self, *args):
        """Check if all inputs are complete and update the button state."""
        if not hasattr(self, 'process_button'):
            return

        all_inputs_complete = (
            self.input_file.get() and 
            self.output_dir.get() and 
            self.city.get() and 
            self.iso_type.get() and 
            self.energyplus_dir.get()
        )

        if all_inputs_complete:
            self.process_button.configure(state="normal")
            self.process_button.configure(fg_color=("#3a7ebf", "#1f538d"))
        else:
            self.process_button.configure(state="disabled")
            self.process_button.configure(fg_color=("#979DA2", "#565B5E"))

        if hasattr(self, 'input_entry'):
            self.update_validation_indicators()

    def start_processing(self):
        if not self.validate_inputs():
            return

        self.is_processing = True
        self.process_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")

        self.process_thread = threading.Thread(target=self.process_file)
        self.process_thread.start()

    def _get_user_inputs_for_processing(self) -> dict:
        """Gathers and returns necessary input values from UI fields."""
        input_file = self.input_file.get()
        output_dir = self.output_dir.get()
        energyplus_dir = self.energyplus_dir.get()
        idd_path = os.path.join(energyplus_dir, "Energy+.idd")
        energyplus_exe = os.path.join(energyplus_dir, "energyplus.exe")

        selected_city = self.city.get()
        selected_area_name = self.city_area_name.get()
        selected_area_code = self.city_area_code.get()
        selected_iso_type = self.iso_type.get()

        if selected_city and not selected_area_name:
            if selected_city in self.city_data:
                city_info_lookup = self.city_data[selected_city]
                self.city_area_name.set(city_info_lookup['area_name'])
                self.city_area_code.set(city_info_lookup['area_code'])
                selected_area_name = self.city_area_name.get()
                selected_area_code = self.city_area_code.get()
                self.show_status(f"Updated city information: {selected_city}, Area: {selected_area_name}, Code: {selected_area_code}")
            else:
                self.show_status("Error: Selected city data is incomplete. Please re-select the city.")
                return None

        return {
            "input_file": input_file,
            "output_dir": output_dir,
            "energyplus_dir": energyplus_dir,
            "idd_path": idd_path,
            "energyplus_exe": energyplus_exe,
            "city_info": {
                'city': selected_city,
                'area_name': selected_area_name,
                'area_code': selected_area_code,
            },
            "iso_type": selected_iso_type
        }

    def _determine_epw_file_path(self, city_info: dict, iso_type: str) -> str | None:
        """Determines the EPW file path based on city and ISO type."""
        area_name = city_info['area_name']
        area_code = city_info['area_code']

        if not area_name or not area_code:
            self.show_status("Error: City area name or code is missing for EPW selection.")
            return None

        if iso_type == "RESIDNTIAL 2023":
            epw_filename = f"{area_code}.epw"
            self.show_status(f"Using RESIDENTIAL 2023 standard - selecting weather file by area code: {area_code}")
        else:
            area_name_map = {"א": "a", "ב": "b", "ג": "c", "ד": "d"}
            latin_letter = area_name_map.get(area_name, area_name)
            epw_filename = f"{latin_letter}.epw"
            self.show_status(f"Using ISO type {iso_type} - selecting weather file: {epw_filename}")

        epw_file_path = os.path.join("data", epw_filename)
        self.show_status(f"Looking for weather file: {epw_file_path}")
        if not os.path.exists(epw_file_path):
            self.show_status(f"Error: Weather file {epw_file_path} not found. Please check that the file exists.")
            return None
        self.show_status(f"Using weather file: {epw_file_path} for {city_info['city']} (Area: {area_name}, Code: {area_code})")
        return epw_file_path

    def _ensure_idf_output_variables(self, idf_path: str, idd_path: str) -> bool:
        """Ensures required output variables are in the IDF for Energy Rating."""
        self.show_status("Ensuring required output variables for Energy Rating...")
        try:
            data_loader = DataLoader()
            output_variables_added = data_loader.ensure_output_variables(
                idf_path=idf_path,
                idd_path=idd_path
            )
            if output_variables_added:
                self.show_status("Required output variables ensured for Energy Rating system.")
                return True
            else:
                self.show_status("Warning: Failed to add required output variables. Energy Rating may not work correctly.", "warning")
                return False
        except FileNotFoundError as e:
            self.show_status(f"Warning: Could not find IDF/IDD for ensuring output variables: {e.filename}. Energy Rating may be affected.", "warning")
            logger.warning(f"FileNotFoundError in _ensure_idf_output_variables: {e}", exc_info=True)
            return False
        except (IOError, OSError) as e:
            self.show_status(f"Warning: File error when ensuring output variables for '{idf_path}': {e.strerror}. Energy Rating may be affected.", "warning")
            logger.warning(f"IOError/OSError in _ensure_idf_output_variables: {e}", exc_info=True)
            return False
        except Exception as e:
            self.show_status(f"Warning: Unexpected error ensuring output variables: {type(e).__name__} - {str(e)}. Energy Rating may be affected.", "warning")
            logger.warning(f"Unexpected error in _ensure_idf_output_variables: {e}", exc_info=True)
            return False

    def _run_energyplus_simulation(self, energyplus_exe: str, epw_file_path: str, simulation_output_dir: str, idf_path: str) -> str | None:
        """Runs the EnergyPlus simulation and returns the output CSV path if successful."""
        self.show_status("Starting EnergyPlus simulation...")
        self.progress_bar.configure(mode='indeterminate')
        self.progress_bar.start()
        self.update_idletasks()

        output_csv_path = os.path.join(simulation_output_dir, "eplustbl.csv")
        simulation_successful = False

        try:
            subprocess.run(
                [energyplus_exe, "-w", epw_file_path, "-r", "-d", simulation_output_dir, idf_path],
                check=True, capture_output=True, text=True, encoding='utf-8', errors='ignore'
            )
            if os.path.exists(output_csv_path):
                self.show_status(f"EnergyPlus simulation successful. Output CSV: {output_csv_path}")
                simulation_successful = True
                try:
                    with open(output_csv_path, 'r', encoding='utf-8') as f:
                        if not f.readline():
                             self.show_status(f"Warning: Simulation output file {output_csv_path} appears to be empty.")
                             simulation_successful = False
                except IOError as read_err:
                    self.show_status(f"Warning: Simulation output file '{output_csv_path}' generated but could not be read. Reason: {read_err.strerror}", "warning")
                    logger.warning(f"IOError reading simulation output {output_csv_path}: {read_err}", exc_info=True)
                    simulation_successful = False
                except Exception as read_err:
                    self.show_status(f"Warning: Unexpected error checking simulation output file '{output_csv_path}': {type(read_err).__name__} - {str(read_err)}", "warning")
                    logger.warning(f"Unexpected error checking simulation output {output_csv_path}: {read_err}", exc_info=True)
                    simulation_successful = False
            else:
                self.show_status(f"Simulation finished, but required output file not found: {output_csv_path}", "error")
        except subprocess.CalledProcessError as e:
            error_detail = e.stderr.strip() if e.stderr else "No stderr output."
            last_error_line = error_detail.splitlines()[-1] if error_detail and error_detail.strip() else "No specific error message in stderr."
            self.show_status(f"EnergyPlus simulation failed (return code {e.returncode}). Error: {last_error_line}", "error")
            logger.error(f"EnergyPlus CalledProcessError. Return code: {e.returncode}. Stderr: {error_detail}", exc_info=True)
        except FileNotFoundError:
            self.show_status(f"Error: energyplus.exe not found at '{energyplus_exe}'. Please check EnergyPlus directory path.", "error")
            logger.error(f"FileNotFoundError for energyplus.exe at {energyplus_exe}")
        except Exception as sim_e:
            self.show_status(f"An unexpected error occurred during the simulation phase: {type(sim_e).__name__} - {str(sim_e)}", "error")
            logger.error(f"Unexpected error during _run_energyplus_simulation: {sim_e}", exc_info=True)
        finally:
            self.progress_bar.stop()
            self.progress_bar.configure(mode='determinate')
            self.progress_bar.set(0)
            self.update_idletasks()

        return output_csv_path if simulation_successful else None

    def _initiate_report_processing(self, input_file: str, idd_path: str, output_dir: str,
                                   simulation_csv_path: str, city_details: dict, iso_type: str) -> bool:
        """Initializes and runs the ProcessingManager for report generation."""
        self.show_status("Simulation complete. Starting IDF processing and report generation...")
        self.processor = ProcessingManager(
            status_callback=self.show_status,
            progress_callback=lambda x: (
                self.progress_bar.set(x),
                self.update_idletasks()
            ),
            simulation_output_csv=simulation_csv_path
        )
        self.processor.city_info = {**city_details, 'iso_type': iso_type}

        idf_processing_success = self.processor.process_idf(input_file, idd_path, output_dir)

        if self.processor.is_cancelled:
            self.show_status("Processing cancelled during IDF stage.")
            return False
        return idf_processing_success

    def process_file(self):
        """Orchestrates the file processing workflow."""
        try:
            user_inputs = self._get_user_inputs_for_processing()
            if not user_inputs:
                return

            input_file = user_inputs["input_file"]
            output_dir = user_inputs["output_dir"]
            idd_path = user_inputs["idd_path"]
            energyplus_exe = user_inputs["energyplus_exe"]
            city_info = user_inputs["city_info"]
            iso_type = user_inputs["iso_type"]

            epw_file_path = self._determine_epw_file_path(city_info, iso_type)
            if not epw_file_path:
                return

            self._ensure_idf_output_variables(input_file, idd_path)
            if not self.is_processing: return

            reports_dir = os.path.join(output_dir, "reports")
            simulation_output_dir = os.path.join(reports_dir, "simulation_output")
            try:
                os.makedirs(simulation_output_dir, exist_ok=True)
            except OSError as e:
                self.show_status(f"Error creating simulation output directory '{simulation_output_dir}': {e.strerror}", "error")
                logger.error(f"OSError creating directory {simulation_output_dir}: {e}", exc_info=True)
                return

            simulation_csv_path = None
            if self.is_processing:
                simulation_csv_path = self._run_energyplus_simulation(
                    energyplus_exe, epw_file_path, simulation_output_dir, input_file
                )

            if not self.is_processing:
                self.show_status("Processing cancelled after simulation attempt.", "warning")
                return

            if simulation_csv_path:
                idf_processing_success = self._initiate_report_processing(
                    input_file, idd_path, output_dir, simulation_csv_path, city_info, iso_type
                )
                if not self.is_processing:
                    self.show_status("Processing cancelled during report generation stage.", "warning")
                    return

                if idf_processing_success:
                    self.show_status("IDF processing and report generation completed successfully!", "success")
                    messagebox.showinfo("Success", "Processing completed! Reports generated.")
                else:
                    self.show_status("IDF processing or report generation failed. Check messages above.", "error")
                    messagebox.showerror("Error", "IDF Processing or report generation failed.")
            else:
                self.show_status("Skipping report generation due to simulation failure or missing output.", "error")
                messagebox.showerror("Error", "Simulation failed or did not produce output. Cannot proceed with report generation.")

        except Exception as e:
            self.show_status(f"A critical error occurred in the processing thread: {type(e).__name__} - {str(e)}", "error")
            logger.critical(f"Critical error in IDFProcessorGUI.process_file thread: {e}", exc_info=True)
            if self.is_processing :
                 messagebox.showerror("Critical Error", f"A critical error occurred: {str(e)}. Please check the log for details.")
        finally:
            self.after(0, self._finalize_processing_attempt)

    def _finalize_processing_attempt(self):
        """Resets UI elements after a processing attempt (success, failure, or cancellation)."""
        self.is_processing = False
        self.process_button.configure(state="normal")
        self.cancel_button.configure(state="disabled")
        self.progress_bar.configure(mode='determinate')
        self.progress_bar.set(0)
        self.update_idletasks()
        if hasattr(self, 'processor'):
            del self.processor

    def cancel_processing(self) -> None:
        """
        Cancels the ongoing processing. Sets the processing flag to False,
        updates the status log, and calls the cancel method on the
        ProcessingManager instance if it exists.
        """
        self.is_processing = False
        self.show_status("Cancellation request received. Attempting to stop processing...", "warning")
        if self.processor:
            self.processor.cancel()

    def run(self) -> None:
        """Starts the Tkinter main event loop."""
        self.mainloop()

if __name__ == "__main__":
    app = IDFProcessorGUI()
    app.run()
