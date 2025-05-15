import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
import json
import os
import subprocess
import threading
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
from parsers.eplustbl_reader import read_glazing_data_from_csv
from parsers.lighting_parser import LightingParser

class ProcessingManager:
    def __init__(self, status_callback=None, progress_callback=None, simulation_output_csv=None):
        self.status_callback = status_callback
        self.progress_callback = progress_callback
        self.is_cancelled = False
        self.simulation_output_csv = simulation_output_csv

    def update_status(self, message):
        if self.status_callback:
            self.status_callback(message)

    def update_progress(self, value):
        if self.progress_callback:
            self.progress_callback(value)

    def ensure_directory_exists(self, file_path: str) -> None:
        directory = os.path.dirname(file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)

    def process_idf(self, input_file: str, idd_path: str, output_dir: str) -> bool:
        try:
            project_name = Path(input_file).stem
            run_id = datetime.now().strftime('%Y%m%d_%H%M%S')
            self.update_progress(0.0)
            self.update_status("Initializing...")
            base_output = os.path.join(output_dir, "reports")
            settings_pdf_path = os.path.join(base_output, "settings.pdf")
            schedules_pdf_path = os.path.join(base_output, "schedules.pdf")
            loads_pdf_path = os.path.join(base_output, "loads.pdf")
            materials_pdf_path = os.path.join(base_output, "materials.pdf")
            glazing_pdf_path = os.path.join(base_output, "glazing.pdf")
            lighting_pdf_path = os.path.join(base_output, "lighting.pdf")
            area_loss_pdf_path = os.path.join(base_output, "area-loss.pdf")
            energy_rating_pdf_path = os.path.join(base_output, "energy-rating.pdf")
            for path in [settings_pdf_path, schedules_pdf_path, loads_pdf_path,
                        materials_pdf_path, glazing_pdf_path, lighting_pdf_path, area_loss_pdf_path,
                        energy_rating_pdf_path]:
                self.ensure_directory_exists(path)
            self.update_progress(0.1)
            self.update_status("Loading IDF file...")
            data_loader = DataLoader()
            data_loader.load_file(input_file, idd_path=idd_path)
            eppy_handler = EppyHandler(idd_path=idd_path)
            idf = eppy_handler.load_idf(input_file)
            self.update_progress(0.2)
            self.update_status("Initializing parsers...")
            settings_extractor = SettingsExtractor(data_loader)
            schedule_extractor = ScheduleExtractor(data_loader)
            load_extractor = LoadExtractor(data_loader)
            materials_extractor = MaterialsParser(data_loader)
            glazing_parser = GlazingParser(
                constructions_glazing_cache=data_loader._constructions_glazing_cache,
                window_simple_glazing_cache=data_loader._window_simple_glazing_cache,
                window_glazing_cache=data_loader._window_glazing_cache,
                window_gas_cache=data_loader._window_gas_cache,
                window_shade_cache=data_loader._window_shade_cache,
                window_shading_control_cache=data_loader._window_shading_control_cache,
                windows_cache=data_loader.get_raw_windows_cache(),
                simulation_output_csv=self.simulation_output_csv,
                frame_divider_cache=data_loader._frame_divider_cache
            )
            parsed_glazing = glazing_parser.parse_glazing_data()
            simulation_output_csv = self.simulation_output_csv
            if simulation_output_csv and os.path.exists(simulation_output_csv):
                csv_glazing_data = read_glazing_data_from_csv(simulation_output_csv)
                matched_constructions = 0
                glazing_keys_lower = {k.lower(): k for k in parsed_glazing.keys()}
                for construction_name, csv_data in csv_glazing_data.items():
                    if construction_name in parsed_glazing:
                        if 'system_details' not in parsed_glazing[construction_name]:
                            parsed_glazing[construction_name]['system_details'] = {}
                        parsed_glazing[construction_name]['system_details'].update(csv_data)
                        matched_constructions += 1
                    elif construction_name.lower() in glazing_keys_lower:
                        actual_key = glazing_keys_lower[construction_name.lower()]
                        if 'system_details' not in parsed_glazing[actual_key]:
                            parsed_glazing[actual_key]['system_details'] = {}
                        parsed_glazing[actual_key]['system_details'].update(csv_data)
                        matched_constructions += 1
                self.update_status(f"Glazing data updated from CSV for {matched_constructions} constructions")
            area_parser = AreaParser(data_loader, parsed_glazing, materials_extractor)
            lighting_parser = LightingParser(data_loader)
            city_area_name = "א"
            if hasattr(self, 'city_info') and self.city_info and 'area_name' in self.city_info:
                city_area_name = self.city_info.get('area_name', "א")
                self.update_status(f"Using city area '{city_area_name}' for thermal loss calculations")
            area_loss_parser = AreaLossParser(area_parser, city_area_name)
            if self.is_cancelled:
                return False
            self.update_progress(0.3)
            self.update_status("Processing settings...")
            settings_extractor.process_idf()
            self.update_progress(0.4)
            self.update_status("Processing schedules...")
            for schedule in eppy_handler.get_schedule_objects(idf):
                schedule_extractor.process_eppy_schedule(schedule)
            if self.is_cancelled:
                return False
            self.update_progress(0.5)
            self.update_status("Processing other data...")
            load_extractor.process_idf(idf)
            materials_extractor.process_idf(idf)
            area_parser.process_idf(idf)
            parsed_lighting = lighting_parser.parse()
            self.update_progress(0.6)
            self.update_status("Extracting processed data...")
            extracted_settings = settings_extractor.get_settings()
            extracted_schedules = schedule_extractor.get_parsed_unique_schedules()
            extracted_loads = load_extractor.get_parsed_zone_loads()
            extracted_element_data = materials_extractor.get_element_data()
            extracted_glazing_data = glazing_parser.parsed_glazing_data
            extracted_lighting_data = parsed_lighting
            extracted_area_loss_data = area_loss_parser.parse()
            energy_rating_parser = EnergyRatingParser(data_loader, area_parser)
            if self.simulation_output_csv:
                energy_rating_parser.process_output(self.simulation_output_csv)
            else:
                energy_rating_parser.process_output()
            if self.is_cancelled:
                return False
            self.update_progress(0.7)
            self.update_status("Generating reports...")
            self.update_status("Generating Settings report...")
            generate_settings_report_pdf(
                extracted_settings,
                settings_pdf_path,
                project_name=project_name,
                run_id=run_id
            )
            self.update_status("Settings report generation attempted.")
            self.update_progress(0.75)
            self.update_status("Generating Schedules report...")
            generate_schedules_report_pdf(
                extracted_schedules,
                schedules_pdf_path,
                project_name=project_name,
                run_id=run_id
            )
            self.update_status("Schedules report generation attempted.")
            self.update_progress(0.8)
            self.update_status("Generating Loads report...")
            generate_loads_report_pdf(
                extracted_loads,
                loads_pdf_path,
                project_name=project_name,
                run_id=run_id
            )
            self.update_status("Loads report generation attempted.")
            self.update_progress(0.85)
            self.update_status("Generating Materials report...")
            generate_materials_report_pdf(
                extracted_element_data,
                materials_pdf_path,
                project_name=project_name,
                run_id=run_id
            )
            self.update_status("Materials report generation attempted.")
            self.update_progress(0.9)
            self.update_status("Generating Area reports...")
            zones_output_dir = os.path.join(base_output, "zones")
            generate_area_reports(
                area_parser,
                output_dir=zones_output_dir,
                project_name=project_name,
                run_id=run_id
            )
            self.update_status("Area reports generation attempted.")
            self.update_progress(0.95)
            self.update_status("Generating Glazing report (PDF)...")
            try:
                success_glazing = generate_glazing_report_pdf(
                    extracted_glazing_data,
                    glazing_pdf_path,
                    project_name=project_name,
                    run_id=run_id
                )
                if success_glazing:
                    self.update_status("Glazing report generated successfully.")
                else:
                    self.update_status("Glazing report generation failed (check console for details).")
            except Exception as e:
                self.update_status(f"Error generating Glazing PDF report: {e}")
            self.update_progress(0.98)
            self.update_status("Generating Lighting report (PDF)...")
            try:
                lighting_generator = LightingReportGenerator(
                    extracted_lighting_data,
                    lighting_pdf_path,
                    project_name=project_name,
                    run_id=run_id
                )
                success_lighting = lighting_generator.generate_report()
                if success_lighting:
                    self.update_status("Lighting report generated successfully.")
                else:
                    self.update_status("Lighting report generation failed (check console for details).")
            except Exception as e:
                self.update_status(f"Error generating Lighting PDF report: {e}")
            self.update_progress(1.0)
            self.update_status("Generating Area Loss report (PDF)...")
            try:
                success_area_loss = generate_area_loss_report_pdf(
                    extracted_area_loss_data,
                    area_loss_pdf_path,
                    project_name=project_name,
                    run_id=run_id
                )
                if success_area_loss:
                    self.update_status("Area Loss report generated successfully.")
                else:
                    self.update_status("Area Loss report generation failed (check console for details).")
            except Exception as e:
                self.update_status(f"Error generating Area Loss PDF report: {e}")
            self.update_status("Generating Energy Rating report (PDF)...")
            try:
                energy_rating_generator = EnergyRatingReportGenerator(
                    energy_rating_parser,
                    output_dir=base_output
                )
                success_energy_rating = energy_rating_generator.generate_report(
                    output_filename="energy-rating.pdf"
                )
                if success_energy_rating:
                    self.update_status("Energy Rating report generated successfully.")
                else:
                    self.update_status("Energy Rating report generation failed (check console for details).")
            except Exception as e:
                self.update_status(f"Error generating Energy Rating PDF report: {e}")
            self.update_status("Processing completed successfully!")
            return True
        except Exception as e:
            self.update_status(f"Error: {str(e)}")
            raise

    def cancel(self):
        self.is_cancelled = True

class IDFProcessorGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- Appearance Settings ---
        ctk.set_appearance_mode("System")  # Modes: "System" (default), "Dark", "Light"
        ctk.set_default_color_theme("blue") # Themes: "blue" (default), "green", "dark-blue"

        # --- Configure window ---
        self.title("IDF Report Generator")
        self.geometry("900x800") # Increased height and width for better visibility
        
        # Initialize variables
        self.input_file = tk.StringVar()
        self.output_dir = tk.StringVar()
        self.city = tk.StringVar()
        self.city_area_name = tk.StringVar() # To store area name
        self.city_area_code = tk.StringVar() # To store area code
        self.iso_type = tk.StringVar() # Changed from 'iso' to 'iso_type' for clarity
        self.energyplus_dir = tk.StringVar()
        self.is_processing = False
        self.settings_file = "settings.json"
        
        # Add trace callbacks to all variables to update button state when they change
        self.input_file.trace_add("write", self.check_inputs_complete)
        self.output_dir.trace_add("write", self.check_inputs_complete)
        self.city.trace_add("write", self.check_inputs_complete)
        self.iso_type.trace_add("write", self.check_inputs_complete)
        self.energyplus_dir.trace_add("write", self.check_inputs_complete)
        
        # Initialize city data and ISO types
        self.city_data = self.load_cities_from_csv()
        self.iso_types = [
            "RESIDNTIAL 2023",
            "RESIDNTIAL 2017",
            "HOTEL",
            "EDUCATION",
            "OFFICE",
            "CORE & ENVELOPE"
        ]
        
        # Create GUI elements
        self.create_widgets()
        self.load_settings()
        
        # Configure grid weights
        # --- Configure Grid Layout ---
        self.grid_columnconfigure(0, weight=1)
        # Configure rows (adjust weights as needed, maybe less weight for fixed elements)
        self.grid_rowconfigure(0, weight=0) # Input frame
        self.grid_rowconfigure(1, weight=0) # Eplus frame
        self.grid_rowconfigure(2, weight=0) # Output frame
        self.grid_rowconfigure(3, weight=0) # City frame
        self.grid_rowconfigure(4, weight=0) # ISO frame
        self.grid_rowconfigure(5, weight=0) # Progress bar
        self.grid_rowconfigure(6, weight=1) # Status text (give it weight to expand)
        self.grid_rowconfigure(7, weight=0) # Button frame
        
        # Check initial button state
        self.check_inputs_complete()

    def load_cities_from_csv(self):
        """Load city data from the CSV file"""
        cities_data = {}
        # Updated path to use the new data directory
        csv_path = os.path.join('data', 'countries-selection.csv')
        
        try:
            if os.path.exists(csv_path):
                with open(csv_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        # Split by comma and strip whitespace
                        parts = [part.strip() for part in line.split(',')]
                        if len(parts) >= 3:
                            city_name = parts[0].strip()
                            area_name = parts[1].strip()
                            area_code = parts[2].strip()
                            cities_data[city_name] = {'area_name': area_name, 'area_code': area_code}
            else:
                self.show_status(f"Warning: City data file not found at {csv_path}")
        except Exception as e:
            self.show_status(f"Error loading city data: {str(e)}")
            
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
        # Check if each field has a valid value
        has_input_file = bool(self.input_file.get())
        has_output_dir = bool(self.output_dir.get())
        has_eplus_dir = bool(self.energyplus_dir.get())
        has_city = bool(self.city.get())
        has_iso = bool(self.iso_type.get())
        
        # Set border colors based on validation (green for valid, red for invalid)
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

    def create_widgets(self):
        # Set main app appearance
        self.configure(fg_color=("#F0F0F0", "#2B2B2B"))  # Light/Dark mode colors
        
        # Create a header frame with title
        header_frame = ctk.CTkFrame(self, height=60, corner_radius=0)
        header_frame.grid(row=0, column=0, sticky="ew")
        header_frame.grid_columnconfigure(0, weight=1)
        header_frame.grid_propagate(False)  # Force the frame to keep its size
        
        # App title
        app_title = ctk.CTkLabel(
            header_frame, 
            text="IDF Report Generator",
            font=ctk.CTkFont(size=20, weight="bold"),
            anchor="center"
        )
        app_title.grid(row=0, column=0, padx=20, pady=15)
        
        # Main content frame
        content_frame = ctk.CTkFrame(self)
        content_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        content_frame.grid_columnconfigure(0, weight=1)
        
        # Create shadow effect for frames
        self.grid_rowconfigure(1, weight=1)
        
        # --- Input file selection ---
        input_frame = ctk.CTkFrame(content_frame, corner_radius=10)
        input_frame.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="ew")
        input_frame.grid_columnconfigure(1, weight=1)

        input_label = ctk.CTkLabel(input_frame, text="Input IDF File:", width=120, anchor="w")
        input_label.grid(row=0, column=0, padx=(10, 5), pady=10)

        self.input_entry = ctk.CTkEntry(input_frame, textvariable=self.input_file, height=32)
        self.input_entry.grid(row=0, column=1, padx=5, pady=10, sticky="ew")

        input_button = ctk.CTkButton(
            input_frame, 
            text="Browse", 
            command=self.select_input_file, 
            width=80,
            height=32,
            fg_color=("#3a7ebf", "#1f538d"),
            hover_color=("#2b5f8f", "#144272")
        )
        input_button.grid(row=0, column=2, padx=(5, 10), pady=10)

        # --- EnergyPlus directory selection ---
        eplus_frame = ctk.CTkFrame(content_frame, corner_radius=10)
        eplus_frame.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        eplus_frame.grid_columnconfigure(1, weight=1)

        eplus_label = ctk.CTkLabel(eplus_frame, text="EnergyPlus Dir:", width=120, anchor="w")
        eplus_label.grid(row=0, column=0, padx=(10, 5), pady=10)

        self.eplus_entry = ctk.CTkEntry(eplus_frame, textvariable=self.energyplus_dir, height=32)
        self.eplus_entry.grid(row=0, column=1, padx=5, pady=10, sticky="ew")

        eplus_button = ctk.CTkButton(
            eplus_frame, 
            text="Browse", 
            command=self.select_energyplus_dir, 
            width=80,
            height=32,
            fg_color=("#3a7ebf", "#1f538d"),
            hover_color=("#2b5f8f", "#144272")
        )
        eplus_button.grid(row=0, column=2, padx=(5, 10), pady=10)

        # --- Output directory selection ---
        output_frame = ctk.CTkFrame(content_frame, corner_radius=10)
        output_frame.grid(row=2, column=0, padx=10, pady=5, sticky="ew")
        output_frame.grid_columnconfigure(1, weight=1)

        output_label = ctk.CTkLabel(output_frame, text="Output Directory:", width=120, anchor="w")
        output_label.grid(row=0, column=0, padx=(10, 5), pady=10)

        self.output_entry = ctk.CTkEntry(output_frame, textvariable=self.output_dir, height=32)
        self.output_entry.grid(row=0, column=1, padx=5, pady=10, sticky="ew")

        output_button = ctk.CTkButton(
            output_frame, 
            text="Browse", 
            command=self.select_output_dir, 
            width=80,
            height=32,
            fg_color=("#3a7ebf", "#1f538d"),
            hover_color=("#2b5f8f", "#144272")
        )
        output_button.grid(row=0, column=2, padx=(5, 10), pady=10)

        # --- City selection ---
        city_frame = ctk.CTkFrame(content_frame, corner_radius=10)
        city_frame.grid(row=3, column=0, padx=10, pady=5, sticky="ew")
        city_frame.grid_columnconfigure(1, weight=1)

        city_label = ctk.CTkLabel(city_frame, text="City:", width=120, anchor="w")
        city_label.grid(row=0, column=0, padx=(10, 5), pady=10)

        # Create combobox for city selection with enhanced appearance
        self.city_combobox = ctk.CTkComboBox(
            city_frame, 
            values=list(self.city_data.keys()),
            variable=self.city,
            width=400,
            state="readonly",
            height=32,
            dropdown_hover_color=("#3a7ebf", "#1f538d")
        )
        self.city_combobox.grid(row=0, column=1, padx=5, pady=10, sticky="ew")
        self.city_combobox.bind("<<ComboboxSelected>>", self.on_city_selected)

        # --- ISO selection ---
        iso_frame = ctk.CTkFrame(content_frame, corner_radius=10)
        iso_frame.grid(row=4, column=0, padx=10, pady=5, sticky="ew")
        iso_frame.grid_columnconfigure(1, weight=1)

        iso_label = ctk.CTkLabel(iso_frame, text="ISO Type:", width=120, anchor="w")
        iso_label.grid(row=0, column=0, padx=(10, 5), pady=10)

        # Create combobox for ISO type selection with enhanced appearance
        self.iso_combobox = ctk.CTkComboBox(
            iso_frame, 
            values=self.iso_types,
            variable=self.iso_type,
            width=400,
            state="readonly",
            height=32,
            dropdown_hover_color=("#3a7ebf", "#1f538d")
        )
        self.iso_combobox.grid(row=0, column=1, padx=5, pady=10, sticky="ew")

        # --- Progress section ---
        progress_frame = ctk.CTkFrame(content_frame, corner_radius=10)
        progress_frame.grid(row=5, column=0, padx=10, pady=(15, 5), sticky="ew")
        progress_frame.grid_columnconfigure(0, weight=1)
        
        # Progress label
        progress_label = ctk.CTkLabel(progress_frame, text="Processing Status:", anchor="w")
        progress_label.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="w")

        # Progress bar with enhanced appearance
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ctk.CTkProgressBar(
            progress_frame,
            height=15,
            corner_radius=5,
            progress_color=("#3a7ebf", "#1f538d"),
            fg_color=("#E0E0E0", "#2D2D2D")
        )
        self.progress_bar.set(0)
        self.progress_bar.grid(row=1, column=0, padx=10, pady=(5, 10), sticky="ew")

        # --- Status message with better styling ---
        status_frame = ctk.CTkFrame(content_frame, corner_radius=10)
        status_frame.grid(row=6, column=0, padx=10, pady=5, sticky="nsew")
        status_frame.grid_columnconfigure(0, weight=1)
        status_frame.grid_rowconfigure(1, weight=1)
        
        # Status label
        status_label = ctk.CTkLabel(status_frame, text="Log Messages:", anchor="w")
        status_label.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="w")
        
        # Status text with scrollbar
        self.status_text = ctk.CTkTextbox(
            status_frame, 
            height=150, 
            wrap=tk.WORD,
            corner_radius=5,
            border_width=1,
            border_color=("#CCCCCC", "#333333")
        )
        self.status_text.grid(row=1, column=0, padx=10, pady=(5, 10), sticky="nsew")
        
        # Configure tags for colored text
        self.status_text.tag_config("error", foreground="#E74C3C")
        self.status_text.tag_config("success", foreground="#2CC985")
        self.status_text.tag_config("warning", foreground="#F39C12")
        
        # Determine default text color based on current appearance mode
        current_mode = ctk.get_appearance_mode()
        if current_mode == "Dark":
            info_fg_color = "#CCCCCC" # Light color for dark mode
        else: # Light mode
            info_fg_color = "#333333" # Dark color for light mode
        self.status_text.tag_config("info", foreground=info_fg_color)
        
        # --- Buttons frame with enhanced appearance ---
        button_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        button_frame.grid(row=7, column=0, padx=10, pady=(15, 10), sticky="ew")
        button_frame.grid_columnconfigure((0, 1), weight=1)

        # Generate Reports button with enhanced appearance
        self.process_button = ctk.CTkButton(
            button_frame, 
            text="Generate Reports", 
            command=self.start_processing, 
            height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            corner_radius=8,
            border_width=0,
            fg_color=("#3a7ebf", "#1f538d"),  # Normal color
            hover_color=("#2b5f8f", "#144272")  # Hover color
        )
        self.process_button.grid(row=0, column=0, padx=(0, 5), pady=5, sticky="ew")

        # Cancel button with enhanced appearance
        self.cancel_button = ctk.CTkButton(
            button_frame, 
            text="Cancel", 
            command=self.cancel_processing, 
            state="disabled", 
            height=40,
            font=ctk.CTkFont(size=14),
            corner_radius=8,
            border_width=0,
            fg_color=("#E74C3C", "#C0392B"),  # Red for cancel
            hover_color=("#C0392B", "#922B21")  # Darker red on hover
        )
        self.cancel_button.grid(row=0, column=1, padx=(5, 0), pady=5, sticky="ew")
        
        # Update content_frame to take any remaining space
        content_frame.grid_rowconfigure(6, weight=1)
        
        # Show initial status
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
            # Optionally validate existence of key files here or in main validation
            self.save_settings()

    def load_settings(self):
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                    self.input_file.set(settings.get('last_input', ''))
                    self.energyplus_dir.set(settings.get('last_eplus_dir', ''))
                    self.output_dir.set(settings.get('last_output', ''))
                    
                    # Load city and ISO selections
                    city = settings.get('last_city', '')
                    self.city.set(city)
                    
                    # Check if area name/code are stored and valid
                    stored_area_name = settings.get('last_city_area_name', '')
                    stored_area_code = settings.get('last_city_area_code', '')
                    
                    # If we have a city but not area info, get area info from city data
                    if city and (not stored_area_name or not stored_area_code):
                        if city in self.city_data:
                            self.city_area_name.set(self.city_data[city]['area_name'])
                            self.city_area_code.set(self.city_data[city]['area_code'])
                            self.show_status(f"Initialized city: {city}, Area: {self.city_data[city]['area_name']}, Code: {self.city_data[city]['area_code']}")
                    else:
                        # Use stored values
                        self.city_area_name.set(stored_area_name)
                        self.city_area_code.set(stored_area_code)
                    
                    # Set ISO type
                    self.iso_type.set(settings.get('last_iso_type', ''))
        except Exception as e:
            self.show_status(f"Error loading settings: {str(e)}")

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
                json.dump(settings, f)
        except Exception as e:
            self.show_status(f"Error saving settings: {str(e)}")

    def show_status(self, message):
        timestamp = datetime.now().strftime('%H:%M:%S')
        full_message = f"{timestamp} - {message}\n"
        
        # Determine tag based on message content
        tag = "info" # Default tag
        message_lower = message.lower()
        if "error" in message_lower or "failed" in message_lower:
            tag = "error"
        elif "success" in message_lower or "completed" in message_lower:
            tag = "success"
        elif "warning" in message_lower or "cancelled" in message_lower:
            tag = "warning"
            
        # Insert message with the determined tag
        self.status_text.insert(tk.END, full_message, (tag,))
        self.status_text.see(tk.END)

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
        # Check for essential EnergyPlus files
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
            except Exception as e:
                messagebox.showerror("Error", f"Could not create output directory: {str(e)}")
                return False
        # Validate city selection
        if not self.city.get():
            messagebox.showerror("Error", "Please select a city.")
            return False
        # Validate ISO type selection
        if not self.iso_type.get():
            messagebox.showerror("Error", "Please select an ISO type.")
            return False
        return True

    def check_inputs_complete(self, *args):
        """Check if all inputs are complete and update the button state."""
        # Only proceed if process_button has been created
        if not hasattr(self, 'process_button'):
            return
            
        # Check if all required fields have values
        all_inputs_complete = (
            self.input_file.get() and 
            self.output_dir.get() and 
            self.city.get() and 
            self.iso_type.get() and 
            self.energyplus_dir.get()
        )
        
        # Update button state based on input completion
        if all_inputs_complete:
            self.process_button.configure(state="normal")
            # Apply a highlighted style when the button is available
            self.process_button.configure(fg_color=("#3a7ebf", "#1f538d"))  # Normal/Hover colors
        else:
            self.process_button.configure(state="disabled")
            # Apply a muted style when the button is disabled
            self.process_button.configure(fg_color=("#979DA2", "#565B5E"))  # Grayed out colors
        
        # Update validation indicators
        if hasattr(self, 'input_entry'):
            self.update_validation_indicators()

    def start_processing(self):
        if not self.validate_inputs():
            return
            
        self.is_processing = True
        self.process_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        
        # Start processing in a separate thread
        self.process_thread = threading.Thread(target=self.process_file)
        self.process_thread.start()

    def process_file(self):
        simulation_successful = False
        output_csv_path = None
        processor = None # Initialize processor to None
        try:
            # --- Get Initial Paths ---
            input_file = self.input_file.get()
            output_dir = self.output_dir.get()
            energyplus_dir = self.energyplus_dir.get()
            idd_path = os.path.join(energyplus_dir, "Energy+.idd")
            energyplus_exe = os.path.join(energyplus_dir, "energyplus.exe")

            # --- Get city and ISO type selections ---
            selected_city = self.city.get()
            selected_area_name = self.city_area_name.get()
            selected_area_code = self.city_area_code.get()
            selected_iso_type = self.iso_type.get()
            
            # --- Validate area name before determining EPW file ---
            if not selected_area_name:
                # Trigger city selection again to ensure area name is set
                if selected_city in self.city_data:
                    city_info = self.city_data[selected_city]
                    self.city_area_name.set(city_info['area_name'])
                    self.city_area_code.set(city_info['area_code'])
                    selected_area_name = self.city_area_name.get()
                    selected_area_code = self.city_area_code.get()
                    self.show_status(f"Updated city information: {selected_city}, Area: {selected_area_name}, Code: {selected_area_code}")
                else:
                    self.show_status("Error: Selected city does not have area information. Please select a valid city.")
                    return
            
            # --- Determine EPW file based on area name or code depending on ISO type ---
            if selected_iso_type == "RESIDNTIAL 2023":
                # For RESIDENTIAL 2023, use the area code (1-8) for the epw file
                epw_filename = f"{selected_area_code}.epw"
                self.show_status(f"Using RESIDENTIAL 2023 standard - selecting weather file by area code: {selected_area_code}")
            else:
                # For other ISO types, use Latin letters (a, b, c, d) instead of the area name
                # Map area names to corresponding Latin letters
                area_name_map = {
                    "א": "a",
                    "ב": "b",
                    "ג": "c",
                    "ד": "d"
                }
                # Get the Latin letter equivalent or fallback to the area name if not in map
                latin_letter = area_name_map.get(selected_area_name, selected_area_name)
                epw_filename = f"{latin_letter}.epw"
                self.show_status(f"Using ISO type {selected_iso_type} - selecting weather file: {epw_filename}")
                
            epw_file_path = os.path.join("data", epw_filename)
            
            self.show_status(f"Looking for weather file: {epw_file_path}")
            if not os.path.exists(epw_file_path):
                self.show_status(f"Error: Weather file {epw_file_path} not found. Please check that the file exists.")
                return
            
            self.show_status(f"Using weather file: {epw_file_path} for {selected_city} (Area: {selected_area_name}, Code: {selected_area_code})")
            self.show_status(f"Using ISO type: {selected_iso_type}")

            # --- Ensure Required Output Variables for Energy Rating ---
            self.show_status("Ensuring required output variables for Energy Rating...")
            try:
                data_loader = DataLoader()
                output_variables_added = data_loader.ensure_output_variables(
                    idf_path=input_file,
                    idd_path=idd_path
                )
                if output_variables_added:
                    self.show_status("Required output variables ensured for Energy Rating system.")
                else:
                    self.show_status("Warning: Failed to add required output variables. Energy Rating may not work correctly.")
            except Exception as e:
                self.show_status(f"Warning: Error adding output variables: {e}. Energy Rating may not work correctly.")

            # --- Simulation Output Directory ---
            # Create a dedicated subdirectory for simulation output inside the reports folder
            reports_dir = os.path.join(output_dir, "reports")
            os.makedirs(reports_dir, exist_ok=True)  # Ensure reports dir exists
            simulation_output_dir = os.path.join(reports_dir, "simulation_output")
            os.makedirs(simulation_output_dir, exist_ok=True)

            # --- Run EnergyPlus Simulation First ---
            self.show_status("Starting EnergyPlus simulation...")
            self.progress_bar.configure(mode='indeterminate') # Indicate busy state
            self.progress_bar.start()
            self.update_idletasks()

            try:
                # Run simulation with the selected weather file
                sim_result = subprocess.run(
                    [energyplus_exe, "-w", epw_file_path, "-r", "-d", simulation_output_dir, input_file],
                    check=True, capture_output=True, text=True, encoding='utf-8', errors='ignore'
                )

                # Check for the specific output file needed
                output_csv_path = os.path.join(simulation_output_dir, "eplustbl.csv")
                if os.path.exists(output_csv_path):
                    self.show_status(f"EnergyPlus simulation successful. Output CSV: {output_csv_path}")
                    simulation_successful = True
                    # Optional: Basic check if file is readable
                    try:
                        with open(output_csv_path, 'r', encoding='utf-8') as f:
                            f.readline() # Try reading the first line
                        print(f"Successfully opened and read header from {output_csv_path}.")
                    except Exception as read_err:
                        print(f"Warning: Could not read output file {output_csv_path}: {read_err}")
                        self.show_status(f"Simulation output file generated but may be corrupted: {read_err}")
                        # simulation_successful = False # Decide if this is critical

                else:
                    self.show_status(f"Simulation finished, but required output file not found: {output_csv_path}")
                    simulation_successful = False

            except subprocess.CalledProcessError as e:
                self.show_status(f"EnergyPlus simulation failed (return code {e.returncode}).")
                print("--- EnergyPlus Error Output ---")
                print(e.stderr) # Print stderr for debugging
                print("-----------------------------")
                # Try to show a relevant part of the error message
                last_error_line = e.stderr.strip().splitlines()[-1] if e.stderr else "No error output captured."
                self.show_status(f"EnergyPlus Error: {last_error_line}")
                simulation_successful = False
            except FileNotFoundError:
                self.show_status(f"Error: energyplus.exe not found at {energyplus_exe}")
                simulation_successful = False
            except Exception as sim_e: # Catch other potential errors
                 self.show_status(f"Error during simulation phase: {sim_e}")
                 simulation_successful = False
            finally:
                # Stop indeterminate mode and reset progress for potential IDF processing
                self.progress_bar.stop()
                self.progress_bar.configure(mode='determinate')
                self.progress_bar.set(0)
                self.update_idletasks()
            # --- End EnergyPlus Simulation ---
            
            # --- Process IDF File (only if simulation was successful and not cancelled) ---
            if simulation_successful and self.is_processing:
                self.show_status("Simulation complete. Starting IDF processing and report generation...")

                # Initialize processing manager, passing the simulation output path
                processor = ProcessingManager(
                    status_callback=self.show_status,
                    progress_callback=lambda x: (
                        self.progress_bar.set(x),
                        self.update_idletasks()
                    ),
                    simulation_output_csv=output_csv_path # Pass the path here
                )

                # Store city and ISO information for use in report generation
                processor.city_info = {
                    'city': selected_city,
                    'area_name': selected_area_name,
                    'area_code': selected_area_code,
                    'iso_type': selected_iso_type
                }

                # Call process_idf
                idf_processing_success = processor.process_idf(input_file, idd_path, output_dir)

                # Check for cancellation during IDF processing
                if processor and processor.is_cancelled: # Check if processor exists
                     self.show_status("Processing cancelled during IDF stage.")
                     idf_processing_success = False

                # Final status based on IDF processing outcome
                if idf_processing_success and self.is_processing:
                    self.show_status("IDF processing and report generation completed successfully!")
                    messagebox.showinfo("Success", "Processing completed! Reports generated.")
                elif not (processor and processor.is_cancelled) and self.is_processing: # Avoid double message if cancelled
                     self.show_status("IDF processing failed. Check messages above.")
                     messagebox.showerror("Error", "IDF Processing failed.")

            elif not simulation_successful and self.is_processing:
                 self.show_status("Skipping IDF processing due to simulation failure.")
                 messagebox.showerror("Error", "Simulation failed. Cannot proceed.")
            elif not self.is_processing:
                 # Already cancelled before or during simulation
                 self.show_status("Processing was cancelled.")
            # --- End IDF Processing ---

        except FileNotFoundError as e: # Catch FileNotFoundError earlier if needed
            error_msg = f"Error: Required file not found - {str(e)}"
            self.show_status(error_msg)
            messagebox.showerror("File Not Found Error", error_msg)
        except Exception as e: # General catch-all for unexpected errors
            self.show_status(f"An unexpected error occurred: {str(e)}")
            import traceback
            traceback.print_exc() # Log detailed traceback to console
            messagebox.showerror("Error", f"An unexpected error occurred: {str(e)}")

        finally:
            # --- Final Cleanup ---
            self.is_processing = False # Ensure processing flag is reset
            self.process_button.configure(state="normal")
            self.cancel_button.configure(state="disabled")
            # Reset progress bar in the finally block to ensure it happens
            self.progress_bar.configure(mode='determinate')
            self.progress_bar.set(0)
            self.update_idletasks()

    def cancel_processing(self):
        self.is_processing = False
        self.show_status("Cancelling processing...")
        # Signal the processor to cancel
        if hasattr(self, 'processor'):
            self.processor.cancel()

    def run(self):
        self.mainloop()

if __name__ == "__main__":
    app = IDFProcessorGUI()
    app.run()