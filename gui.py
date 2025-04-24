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
from parsers.schedule_parser import ScheduleExtractor
from parsers.settings_parser import SettingsExtractor
from parsers.load_parser import LoadExtractor
from parsers.materials_parser import MaterialsParser
from parsers.area_parser import AreaParser

class ProcessingManager:
    # Removed energyplus_dir from init
    def __init__(self, status_callback=None, progress_callback=None):
        self.status_callback = status_callback
        self.progress_callback = progress_callback
        # self.energyplus_dir = energyplus_dir # Removed
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

    # Added idd_path parameter, output_dir remains
    def process_idf(self, input_file: str, idd_path: str, output_dir: str) -> bool:
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

            # Create output directories
            for path in [settings_pdf_path, schedules_pdf_path, loads_pdf_path,
                        materials_pdf_path]:
                self.ensure_directory_exists(path)

            self.update_progress(0.1)
            self.update_status("Loading IDF file...")

            # Initialize handlers and load file
            data_loader = DataLoader()
            # Pass idd_path to DataLoader as well
            data_loader.load_file(input_file, idd_path=idd_path)

            # Initialize EppyHandler with the provided idd_path
            eppy_handler = EppyHandler(idd_path=idd_path)
            idf = eppy_handler.load_idf(input_file)

            self.update_progress(0.2)
            self.update_status("Initializing parsers...")

            # Initialize parsers
            # Pass data_loader AND input_file (for comment parsing)
            settings_extractor = SettingsExtractor(data_loader, idf_file_path=input_file)
            schedule_extractor = ScheduleExtractor(data_loader)
            load_extractor = LoadExtractor(data_loader)
            materials_extractor = MaterialsParser(data_loader)
            area_parser = AreaParser(data_loader)

            if self.is_cancelled:
                return False

            self.update_progress(0.3)
            self.update_status("Processing settings...")

            # Call the extractor's own process_idf method
            settings_extractor.process_idf(idf)
            # Remove the manual loop below:
            # settings_objects = eppy_handler.get_settings_objects(idf)
            # for obj_type, objects in settings_objects.items():
            #     for obj in objects:
            #         settings_extractor.process_eppy_object(obj_type, obj)

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

            self.update_progress(0.6)
            self.update_status("Extracting processed data...")

            # Get extracted data
            extracted_settings = settings_extractor.get_settings()
            extracted_schedules = schedule_extractor.get_parsed_unique_schedules()
            extracted_loads = load_extractor.get_parsed_zone_loads()
            extracted_element_data = materials_extractor.get_element_data()
            # extracted_areas = area_parser.get_parsed_areas() # Incorrect method call removed

            if self.is_cancelled:
                return False

            self.update_progress(0.7)
            self.update_status("Generating reports...")

            # Generate reports
            self.update_status("Generating Settings report...")
            generate_settings_report_pdf(extracted_settings, settings_pdf_path)
            self.update_status("Settings report generation attempted.")
            self.update_progress(0.75)

            self.update_status("Generating Schedules report...")
            generate_schedules_report_pdf(extracted_schedules, schedules_pdf_path)
            self.update_status("Schedules report generation attempted.")
            self.update_progress(0.8)

            self.update_status("Generating Loads report...")
            generate_loads_report_pdf(extracted_loads, loads_pdf_path)
            self.update_status("Loads report generation attempted.")
            self.update_progress(0.85)

            self.update_status("Generating Materials report...")
            generate_materials_report_pdf(extracted_element_data, materials_pdf_path)
            self.update_status("Materials report generation attempted.")
            self.update_progress(0.9)

            # Pass the area_parser instance and the specific zones output directory
            self.update_status("Generating Area reports...")
            zones_output_dir = os.path.join(base_output, "zones") # Create path for zones subfolder
            generate_area_reports(area_parser, output_dir=zones_output_dir) # Pass the new path
            self.update_status("Area reports generation attempted.")
            self.update_progress(1)

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
        self.geometry("700x550") # Increased size
        
        # Initialize variables
        self.input_file = tk.StringVar()
        self.weather_file = tk.StringVar()
        self.energyplus_dir = tk.StringVar()
        self.output_dir = tk.StringVar()
        self.is_processing = False
        self.settings_file = "settings.json"
        
        # Load saved settings
        self.load_settings()
        
        # Create GUI elements
        self.create_widgets()
        
        # Configure grid weights
        # --- Configure Grid Layout ---
        self.grid_columnconfigure(0, weight=1)
        # Configure rows (adjust weights as needed, maybe less weight for fixed elements)
        self.grid_rowconfigure(0, weight=0) # Input frame
        self.grid_rowconfigure(1, weight=0) # Weather frame
        self.grid_rowconfigure(2, weight=0) # Eplus frame
        self.grid_rowconfigure(3, weight=0) # Output frame
        self.grid_rowconfigure(4, weight=0) # Progress bar
        self.grid_rowconfigure(5, weight=1) # Status text (give it weight to expand)
        self.grid_rowconfigure(6, weight=0) # Button frame
    
    def create_widgets(self):
        # Input file selection
        # --- Input file selection ---
        input_frame = ctk.CTkFrame(self)
        input_frame.grid(row=0, column=0, padx=20, pady=(20, 5), sticky="ew")
        input_frame.grid_columnconfigure(1, weight=1) # Make entry expand

        input_label = ctk.CTkLabel(input_frame, text="Input IDF File:", width=120, anchor="w")
        input_label.grid(row=0, column=0, padx=(10, 5), pady=10)

        self.input_entry = ctk.CTkEntry(input_frame, textvariable=self.input_file)
        self.input_entry.grid(row=0, column=1, padx=5, pady=10, sticky="ew")

        input_button = ctk.CTkButton(input_frame, text="Browse", command=self.select_input_file, width=80)
        input_button.grid(row=0, column=2, padx=(5, 10), pady=10)

        # --- Weather file selection ---
        weather_frame = ctk.CTkFrame(self)
        weather_frame.grid(row=1, column=0, padx=20, pady=5, sticky="ew")
        weather_frame.grid_columnconfigure(1, weight=1)

        weather_label = ctk.CTkLabel(weather_frame, text="Weather EPW File:", width=120, anchor="w")
        weather_label.grid(row=0, column=0, padx=(10, 5), pady=10)

        self.weather_entry = ctk.CTkEntry(weather_frame, textvariable=self.weather_file)
        self.weather_entry.grid(row=0, column=1, padx=5, pady=10, sticky="ew")

        weather_button = ctk.CTkButton(weather_frame, text="Browse", command=self.select_weather_file, width=80)
        weather_button.grid(row=0, column=2, padx=(5, 10), pady=10)

        # --- EnergyPlus directory selection ---
        eplus_frame = ctk.CTkFrame(self)
        eplus_frame.grid(row=2, column=0, padx=20, pady=5, sticky="ew")
        eplus_frame.grid_columnconfigure(1, weight=1)

        eplus_label = ctk.CTkLabel(eplus_frame, text="EnergyPlus Dir:", width=120, anchor="w")
        eplus_label.grid(row=0, column=0, padx=(10, 5), pady=10)

        self.eplus_entry = ctk.CTkEntry(eplus_frame, textvariable=self.energyplus_dir)
        self.eplus_entry.grid(row=0, column=1, padx=5, pady=10, sticky="ew")

        eplus_button = ctk.CTkButton(eplus_frame, text="Browse", command=self.select_energyplus_dir, width=80)
        eplus_button.grid(row=0, column=2, padx=(5, 10), pady=10)

        # --- Output directory selection ---
        output_frame = ctk.CTkFrame(self)
        output_frame.grid(row=3, column=0, padx=20, pady=(5, 10), sticky="ew") # Adjusted row index
        output_frame.grid_columnconfigure(1, weight=1)

        output_label = ctk.CTkLabel(output_frame, text="Output Directory:", width=120, anchor="w")
        output_label.grid(row=0, column=0, padx=(10, 5), pady=10)

        self.output_entry = ctk.CTkEntry(output_frame, textvariable=self.output_dir)
        self.output_entry.grid(row=0, column=1, padx=5, pady=10, sticky="ew")

        output_button = ctk.CTkButton(output_frame, text="Browse", command=self.select_output_dir, width=80)
        output_button.grid(row=0, column=2, padx=(5, 10), pady=10)

        # --- Progress bar ---
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.set(0)
        self.progress_bar.grid(row=4, column=0, padx=20, pady=(10, 5), sticky="ew") # Adjusted row index

        # --- Status message ---
        self.status_text = ctk.CTkTextbox(self, height=150, wrap=tk.WORD) # Increased height
        self.status_text.grid(row=5, column=0, padx=20, pady=5, sticky="nsew") # Adjusted row index and sticky
        # Configure tags for colored text
        self.status_text.tag_config("error", foreground="red")
        self.status_text.tag_config("success", foreground="green")
        self.status_text.tag_config("warning", foreground="orange")
        # Determine default text color based on current appearance mode
        current_mode = ctk.get_appearance_mode()
        if current_mode == "Dark":
            info_fg_color = "gray90" # Or another light color suitable for dark mode
        else: # Light mode
            info_fg_color = "gray10" # Or another dark color suitable for light mode
        self.status_text.tag_config("info", foreground=info_fg_color)
        
        # --- Buttons frame ---
        button_frame = ctk.CTkFrame(self, fg_color="transparent") # Make frame transparent
        button_frame.grid(row=6, column=0, padx=20, pady=(10, 20), sticky="ew") # Adjusted row index
        button_frame.grid_columnconfigure((0, 1), weight=1) # Make buttons expand equally

        self.process_button = ctk.CTkButton(button_frame, text="Generate Reports", command=self.start_processing, height=35)
        self.process_button.grid(row=0, column=0, padx=(0, 5), pady=5, sticky="ew")

        self.cancel_button = ctk.CTkButton(button_frame, text="Cancel", command=self.cancel_processing, state="disabled", height=35)
        self.cancel_button.grid(row=0, column=1, padx=(5, 0), pady=5, sticky="ew")

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

    def select_weather_file(self):
        file_path = filedialog.askopenfilename(
            title="Select Weather EPW File",
            filetypes=[("EPW files", "*.epw"), ("All files", "*.*")]
        )
        if file_path:
            self.weather_file.set(file_path)
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
                    self.weather_file.set(settings.get('last_weather', ''))
                    self.energyplus_dir.set(settings.get('last_eplus_dir', ''))
                    self.output_dir.set(settings.get('last_output', ''))
        except Exception as e:
            self.show_status(f"Error loading settings: {str(e)}")

    def save_settings(self):
        try:
            settings = {
                'last_input': self.input_file.get(),
                'last_weather': self.weather_file.get(),
                'last_eplus_dir': self.energyplus_dir.get(),
                'last_output': self.output_dir.get()
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
        if not self.weather_file.get():
            messagebox.showerror("Error", "Please select a weather EPW file.")
            return False
        if not os.path.exists(self.weather_file.get()):
            messagebox.showerror("Error", "Selected weather EPW file does not exist.")
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
            energyplus_dir = self.energyplus_dir.get()
            idd_path = os.path.join(energyplus_dir, "Energy+.idd") # Construct idd_path here

            # Initialize processing manager (no energyplus_dir needed)
            processor = ProcessingManager(
                status_callback=self.show_status,
                progress_callback=lambda x: (
                    self.progress_var.set(x),
                    self.progress_bar.set(x),
                    self.update_idletasks()
                )
                # energyplus_dir=energyplus_dir # Removed
            )

            # Start processing
            self.show_status("Starting file processing...")

            # Call process_idf with input_file, idd_path, and output_dir
            success = processor.process_idf(input_file, idd_path, output_dir)
            
            # --- Run EnergyPlus Simulation ---
            if success and self.is_processing: # Only run if report generation was okay
                self.show_status("Starting EnergyPlus simulation...")
                energyplus_exe = os.path.join(energyplus_dir, "energyplus.exe")
                weather_file_path = self.weather_file.get() # Get weather file path
                
                # Define the output directory for EnergyPlus results inside the reports folder
                # Note: base_output is defined earlier as os.path.join(output_dir, "reports")
                # We need to ensure base_output is accessible here or redefine it.
                # Assuming base_output is accessible or we redefine it based on output_dir
                base_output_dir = os.path.join(output_dir, "reports") # Define base reports dir
                simulation_output_dir = os.path.join(base_output_dir, "simulation")
                os.makedirs(simulation_output_dir, exist_ok=True) # Ensure simulation dir exists

                # Switch progress bar to indeterminate mode for simulation
                self.progress_bar.configure(mode='indeterminate')
                self.progress_bar.start()
                self.update_idletasks() # Ensure GUI updates

                try:
                    # Use simulation_output_dir for the -d argument
                    subprocess.run([energyplus_exe, "-w", weather_file_path, "-r", "-d", simulation_output_dir, input_file], check=True)
                    self.show_status("EnergyPlus simulation completed successfully.")
                except subprocess.CalledProcessError as e:
                    self.show_status(f"EnergyPlus simulation failed: {e}", tag="error")
                    success = False # Mark overall process as failed if simulation fails
                except FileNotFoundError:
                    self.show_status(f"Error: energyplus.exe not found at {energyplus_exe}", tag="error")
                    success = False
                finally:
                    # Stop indeterminate mode and switch back to determinate
                    self.progress_bar.stop()
                    self.progress_bar.configure(mode='determinate')
                    # Optionally set progress back to 1 if simulation was part of the overall progress
                    # self.progress_bar.set(1.0) # Or leave it, as the main finally block resets it
                    self.update_idletasks() # Ensure GUI updates
            # --- End EnergyPlus Simulation ---

            if success and self.is_processing:
                messagebox.showinfo("Success", "File processing completed! Reports have been generated in the output directory.")
            elif not success and self.is_processing:
                messagebox.showerror("Error", "Processing was not completed successfully.")
                
        except FileNotFoundError as e:
            # Display the actual error message from the exception
            error_msg = f"Error: File not found - {str(e)}"
            self.show_status(error_msg)
            messagebox.showerror("File Not Found Error", error_msg)
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