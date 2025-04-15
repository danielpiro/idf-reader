import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
import json
import os
import threading
from pathlib import Path
import shutil
from datetime import datetime
import sys
from utils.data_loader import DataLoader
from utils.eppy_handler import EppyHandler
from generators.settings_report_generator import generate_settings_report_pdf
from generators.schedule_report_generator import generate_schedules_report_pdf
from generators.load_report_generator import generate_loads_report_pdf
from generators.area_report_generator import generate_area_reports
from generators.materials_report_generator import generate_materials_report_pdf
from generators.storage_report_generator import generate_storage_report_pdf
from parsers.schedule_parser import ScheduleExtractor
from parsers.settings_parser import SettingsExtractor
from parsers.load_parser import LoadExtractor
from parsers.materials_parser import MaterialsParser
from parsers.area_parser import AreaParser
from parsers.storage_parser import StorageParser

class ProcessingManager:
    def __init__(self, status_callback, progress_callback):
        self.status_callback = status_callback
        self.progress_callback = progress_callback
        self.is_cancelled = False

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

    def process_idf(self, input_file: str, output_dir: str) -> bool:
        try:
            # Initialize progress
            self.update_progress(0.0)
            self.update_status("Initializing...")

            # Setup output paths
            base_output = os.path.join(output_dir, "reports")
            settings_pdf_path = os.path.join(base_output, "settings.pdf")
            schedules_pdf_path = os.path.join(base_output, "schedules.pdf")
            loads_pdf_path = os.path.join(base_output, "loads.pdf")
            materials_pdf_path = os.path.join(base_output, "materials.pdf")
            storage_pdf_path = os.path.join(base_output, "zones", "storage.pdf")

            # Create output directories
            for path in [settings_pdf_path, schedules_pdf_path, loads_pdf_path,
                        materials_pdf_path, storage_pdf_path]:
                self.ensure_directory_exists(path)

            self.update_progress(0.1)
            self.update_status("Loading IDF file...")

            # Initialize handlers and load file
            data_loader = DataLoader()
            data_loader.load_file(input_file)
            
            eppy_handler = EppyHandler()
            idf = eppy_handler.load_idf(input_file)

            self.update_progress(0.2)
            self.update_status("Initializing parsers...")

            # Initialize parsers
            settings_extractor = SettingsExtractor(data_loader)
            schedule_extractor = ScheduleExtractor(data_loader)
            load_extractor = LoadExtractor(data_loader)
            materials_extractor = MaterialsParser(data_loader)
            area_parser = AreaParser(data_loader)
            storage_parser = StorageParser(data_loader)

            if self.is_cancelled:
                return False

            self.update_progress(0.3)
            self.update_status("Processing settings...")

            # Process settings
            settings_objects = eppy_handler.get_settings_objects(idf)
            for obj_type, objects in settings_objects.items():
                for obj in objects:
                    settings_extractor.process_eppy_object(obj_type, obj)

            self.update_progress(0.4)
            self.update_status("Processing schedules...")

            # Process schedules
            for schedule in eppy_handler.get_schedule_objects(idf):
                schedule_extractor.process_eppy_schedule(schedule)

            if self.is_cancelled:
                return False

            self.update_progress(0.5)
            self.update_status("Processing other data...")

            # Process other data
            load_extractor.process_idf(idf)
            materials_extractor.process_idf(idf)
            area_parser.process_idf(idf)
            storage_parser.process_idf(idf)

            self.update_progress(0.6)
            self.update_status("Extracting processed data...")

            # Get extracted data
            extracted_settings = settings_extractor.get_settings()
            extracted_schedules = schedule_extractor.get_parsed_unique_schedules()
            extracted_loads = load_extractor.get_parsed_zone_loads()
            extracted_element_data = materials_extractor.get_element_data()
            extracted_areas = area_parser.get_parsed_areas()
            extracted_storage = storage_parser.get_storage_zones()

            if self.is_cancelled:
                return False

            self.update_progress(0.7)
            self.update_status("Generating reports...")

            # Generate reports
            generate_settings_report_pdf(extracted_settings, settings_pdf_path)
            self.update_progress(0.75)

            generate_schedules_report_pdf(extracted_schedules, schedules_pdf_path)
            self.update_progress(0.8)

            generate_loads_report_pdf(extracted_loads, loads_pdf_path)
            self.update_progress(0.85)

            generate_materials_report_pdf(extracted_element_data, materials_pdf_path)
            self.update_progress(0.9)

            generate_area_reports(extracted_areas)
            self.update_progress(0.95)

            generate_storage_report_pdf(extracted_storage, storage_pdf_path)
            self.update_progress(1.0)

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

        # Configure window
        self.title("IDF File Processor")
        self.geometry("600x400")
        
        # Initialize variables
        self.input_file = tk.StringVar()
        self.output_dir = tk.StringVar()
        self.is_processing = False
        self.settings_file = "settings.json"
        
        # Load saved settings
        self.load_settings()
        
        # Create GUI elements
        self.create_widgets()
        
        # Configure grid weights
        self.grid_columnconfigure(0, weight=1)
        for i in range(7):
            self.grid_rowconfigure(i, weight=1)
    
    def create_widgets(self):
        # Input file selection
        input_frame = ctk.CTkFrame(self)
        input_frame.grid(row=0, column=0, padx=20, pady=(20,10), sticky="ew")
        
        input_label = ctk.CTkLabel(input_frame, text="Input IDF File:")
        input_label.pack(side=tk.LEFT, padx=5)
        
        self.input_entry = ctk.CTkEntry(input_frame, textvariable=self.input_file, width=300)
        self.input_entry.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        
        input_button = ctk.CTkButton(input_frame, text="Browse", command=self.select_input_file)
        input_button.pack(side=tk.RIGHT, padx=5)

        # Output directory selection
        output_frame = ctk.CTkFrame(self)
        output_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        
        output_label = ctk.CTkLabel(output_frame, text="Output Directory:")
        output_label.pack(side=tk.LEFT, padx=5)
        
        self.output_entry = ctk.CTkEntry(output_frame, textvariable=self.output_dir, width=300)
        self.output_entry.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        
        output_button = ctk.CTkButton(output_frame, text="Browse", command=self.select_output_dir)
        output_button.pack(side=tk.RIGHT, padx=5)

        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.set(0)
        self.progress_bar.grid(row=2, column=0, padx=20, pady=10, sticky="ew")

        # Status message
        self.status_text = ctk.CTkTextbox(self, height=100, wrap=tk.WORD)
        self.status_text.grid(row=3, column=0, padx=20, pady=10, sticky="ew")
        
        # Buttons frame
        button_frame = ctk.CTkFrame(self)
        button_frame.grid(row=4, column=0, padx=20, pady=(10,20), sticky="ew")
        
        self.process_button = ctk.CTkButton(button_frame, text="Process", command=self.start_processing)
        self.process_button.pack(side=tk.LEFT, padx=5, expand=True)
        
        self.cancel_button = ctk.CTkButton(button_frame, text="Cancel", command=self.cancel_processing, state="disabled")
        self.cancel_button.pack(side=tk.LEFT, padx=5, expand=True)

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

    def load_settings(self):
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                    self.input_file.set(settings.get('last_input', ''))
                    self.output_dir.set(settings.get('last_output', ''))
        except Exception as e:
            self.show_status(f"Error loading settings: {str(e)}")

    def save_settings(self):
        try:
            settings = {
                'last_input': self.input_file.get(),
                'last_output': self.output_dir.get()
            }
            with open(self.settings_file, 'w') as f:
                json.dump(settings, f)
        except Exception as e:
            self.show_status(f"Error saving settings: {str(e)}")

    def show_status(self, message):
        self.status_text.insert(tk.END, f"{datetime.now().strftime('%H:%M:%S')} - {message}\n")
        self.status_text.see(tk.END)

    def validate_inputs(self):
        if not self.input_file.get():
            messagebox.showerror("Error", "Please select an input IDF file.")
            return False
        if not self.output_dir.get():
            messagebox.showerror("Error", "Please select an output directory.")
            return False
        if not os.path.exists(self.input_file.get()):
            messagebox.showerror("Error", "Selected input file does not exist.")
            return False
        if not os.path.exists(self.output_dir.get()):
            try:
                os.makedirs(self.output_dir.get())
            except Exception as e:
                messagebox.showerror("Error", f"Could not create output directory: {str(e)}")
                return False
        return True

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
        try:
            input_file = self.input_file.get()
            output_dir = self.output_dir.get()

            # Initialize processing manager
            processor = ProcessingManager(
                status_callback=self.show_status,
                progress_callback=lambda x: (
                    self.progress_var.set(x),
                    self.progress_bar.set(x),
                    self.update_idletasks()
                )
            )

            # Start processing
            self.show_status("Starting file processing...")
            
            success = processor.process_idf(input_file, output_dir)
            
            if success and self.is_processing:
                messagebox.showinfo("Success", "File processing completed! Reports have been generated in the output directory.")
            elif not success and self.is_processing:
                messagebox.showerror("Error", "Processing was not completed successfully.")
                
        except FileNotFoundError as e:
            if "Energy+.idd" in str(e):
                self.show_status("Error: Energy+.idd file not found. Please ensure it's in the project root.")
                messagebox.showerror("Error", "Energy+.idd file not found. Please ensure it's in the project root.")
            else:
                self.show_status(f"Error: File not found - {str(e)}")
                messagebox.showerror("Error", f"File not found - {str(e)}")
        except Exception as e:
            self.show_status(f"Error during processing: {str(e)}")
            messagebox.showerror("Error", f"An error occurred during processing: {str(e)}")
        
        finally:
            self.is_processing = False
            self.process_button.configure(state="normal")
            self.cancel_button.configure(state="disabled")
            if not self.is_processing:
                self.progress_bar.set(0)

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