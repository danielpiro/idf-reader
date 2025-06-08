import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
import json
import os
import sys
import subprocess
import threading
import logging
from pathlib import Path
from datetime import datetime
# Imports for ProcessingManager are now in processing_manager.py
# Keep GUI specific imports here
from utils.data_loader import DataLoader # Still needed for IDFProcessorGUI._ensure_idf_output_variables

def fix_hebrew_text_display(text):
    """
    Fix Hebrew text display for GUI components.
    Handles the RTL text ordering issue where Hebrew words appear in reverse order.
    """
    if not text:
        return text
    
    # Check if text contains Hebrew characters
    contains_hebrew = any('\u0590' <= char <= '\u05FF' for char in text)
    
    if contains_hebrew:
        # The issue is that tkinter displays RTL text with reversed word order
        # For mixed Hebrew-English text like "תל אביב - יפו", we need to handle this carefully
        
        # Split by whitespace to handle word order
        parts = text.split()
        
        # Check each part to see if it's Hebrew or punctuation/Latin
        hebrew_parts = []
        latin_parts = []
        
        for part in parts:
            if any('\u0590' <= char <= '\u05FF' for char in part):
                hebrew_parts.append(part)
            else:
                latin_parts.append(part)
        
        # If we have a mix of Hebrew and non-Hebrew parts, we need to reorder
        if hebrew_parts and latin_parts:
            # For cases like "תל אביב - יפו", reverse the overall order
            return ' '.join(reversed(parts))
        else:
            # Pure Hebrew text might need different handling
            if len(parts) > 1:
                # Multiple Hebrew words - reverse their order
                return ' '.join(reversed(parts))
            else:
                # Single Hebrew word - keep as is
                return text
    else:
        return text

# Logger for the GUI part
logger = logging.getLogger(__name__)
# Ensure basicConfig is called, but if main.py or another entry point handles it,
# this might be redundant or could be configured more centrally.
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')

from processing_manager import ProcessingManager


class IDFProcessorGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.title("🏗️ IDF Report Generator")
        self.geometry("1400x800")
        self.minsize(1200, 700)

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
        
        # Use the same pattern as data_loader.py for consistency
        # This handles both development and PyInstaller bundled environments correctly
        try:
            # First try PyInstaller bundle path
            base_path = sys._MEIPASS
            csv_path = os.path.join(base_path, 'data', 'countries-selection.csv')
        except AttributeError:
            # Development environment - use relative path from this file
            csv_path = Path(__file__).resolve().parent / "data" / "countries-selection.csv"
        
        try:
            if os.path.exists(csv_path):
                with open(csv_path, 'r', encoding='utf-8') as f:
                    # Skip header row if present (check if first line contains non-city data)
                    first_line = f.readline().strip()
                    if not any(char in first_line for char in 'אבגדהוזחטיכלמנסעפצקרשת'):  # Hebrew characters
                        # Contains header, don't reset to beginning
                        pass
                    else:
                        # No header, reset to beginning
                        f.seek(0)
                    
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

    def on_city_selected(self, selected_value=None): # selected_value is passed by Combobox
        # Use the passed value or get from variable if called directly
        selected_city_name = selected_value if selected_value else self.city.get()
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
        if not all(hasattr(self, w_name) for w_name in ['input_entry', 'output_entry', 'eplus_entry', 'city_search_entry', 'iso_combobox']):
            return

        valid_style = {"border_color": self.success_color}
        invalid_style = {"border_color": self.error_color}

        self.input_entry.configure(**(valid_style if self.input_file.get() and os.path.exists(self.input_file.get()) else invalid_style))
        self.output_entry.configure(**(valid_style if self.output_dir.get() and os.path.isdir(self.output_dir.get()) else invalid_style))
        self.eplus_entry.configure(**(valid_style if self.energyplus_dir.get() and os.path.isdir(self.energyplus_dir.get()) else invalid_style))
        self.city_search_entry.configure(**(valid_style if self.city.get() else invalid_style))
        self.iso_combobox.configure(**(valid_style if self.iso_type.get() else invalid_style))

    def _create_modern_header(self) -> ctk.CTkFrame:
        header_frame = ctk.CTkFrame(self, height=60, corner_radius=0, fg_color=self.primary_color)
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

    def _create_city_selection_row(self, parent, row_idx):
        """Creates a fast city selection with search and scrollable listbox."""
        ctk.CTkLabel(parent, text="🏙️ City:", font=ctk.CTkFont(size=14, weight="bold"), width=180, anchor="w").grid(row=row_idx, column=0, padx=(20,15), pady=10, sticky="w")
        
        # Create container frame for the city selection
        city_frame = ctk.CTkFrame(parent, fg_color="transparent")
        city_frame.grid(row=row_idx, column=1, padx=(0,20), pady=10, sticky="ew")
        city_frame.grid_columnconfigure(0, weight=1)
        
        # Create search entry
        self.city_search_entry = ctk.CTkEntry(
            city_frame,
            placeholder_text="Type to search cities...",
            width=300,
            height=40,
            corner_radius=8,
            border_width=2,
            font=ctk.CTkFont(size=12)
        )
        self.city_search_entry.grid(row=0, column=0, sticky="ew")
        self.city_search_entry.bind('<KeyRelease>', self._on_city_search)
        self.city_search_entry.bind('<Button-1>', self._show_city_dropdown)
        
        # Create dropdown frame (initially hidden)
        self.city_dropdown_frame = ctk.CTkFrame(city_frame, height=200, corner_radius=8, border_width=1)
        
        # Create scrollable frame inside dropdown
        self.city_scrollable_frame = ctk.CTkScrollableFrame(
            self.city_dropdown_frame,
            height=180,
            corner_radius=0,
            scrollbar_button_color=("#CCCCCC", "#333333"),
            scrollbar_button_hover_color=("#AAAAAA", "#555555")
        )
        self.city_scrollable_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Store city names and create buttons
        self.city_names = sorted(list(self.city_data.keys()))
        self.city_buttons = []
        self._create_city_buttons()
        
        # Set city_entry attribute for compatibility with validation
        self.city_entry = self.city_search_entry
        
        # Track dropdown visibility
        self.city_dropdown_visible = False
        
        # Bind click outside to hide dropdown
        self.bind('<Button-1>', self._on_click_outside_city)
    
    def _create_city_buttons(self, filtered_cities=None):
        """Create city selection buttons."""
        # Clear existing buttons
        for button in self.city_buttons:
            button.destroy()
        self.city_buttons.clear()
        
        # Use filtered cities or all cities
        cities_to_show = filtered_cities if filtered_cities is not None else self.city_names
        
        # Limit to first 100 for performance
        cities_to_show = cities_to_show[:100]
        
        for city in cities_to_show:
            # Fix Hebrew text display for city names
            display_text = fix_hebrew_text_display(city)
            button = ctk.CTkButton(
                self.city_scrollable_frame,
                text=display_text,
                height=30,
                corner_radius=5,
                fg_color="transparent",
                hover_color=("#f0f0f0", "#2a2a2a"),
                text_color=("black", "white"),
                anchor="w",
                command=lambda c=city: self._select_city(c)
            )
            button.pack(fill="x", pady=1, padx=2)
            self.city_buttons.append(button)
    
    def _on_city_search(self, event):
        """Handle city search input."""
        search_text = self.city_search_entry.get().strip().lower()
        
        if not search_text:
            # Show all cities (limited)
            self._create_city_buttons()
        else:
            # Filter cities based on search
            filtered = [city for city in self.city_names if search_text in city.lower()]
            self._create_city_buttons(filtered)
        
        # Show dropdown if not visible
        if not self.city_dropdown_visible:
            self._show_city_dropdown()
    
    def _show_city_dropdown(self, event=None):
        """Show the city dropdown."""
        if not self.city_dropdown_visible:
            self.city_dropdown_frame.grid(row=1, column=0, sticky="ew", pady=(5,0))
            self.city_dropdown_visible = True
    
    def _hide_city_dropdown(self):
        """Hide the city dropdown."""
        if self.city_dropdown_visible:
            self.city_dropdown_frame.grid_forget()
            self.city_dropdown_visible = False
    
    def _select_city(self, city_name):
        """Handle city selection."""
        # Fix Hebrew text display for the selected city
        display_text = fix_hebrew_text_display(city_name)
        self.city_search_entry.delete(0, tk.END)
        self.city_search_entry.insert(0, display_text)
        self.city.set(city_name)  # Keep original value for processing
        self._hide_city_dropdown()
        self.on_city_selected(city_name)
    
    def _on_click_outside_city(self, event):
        """Hide dropdown when clicking outside."""
        # Check if click is outside the city selection area
        if hasattr(self, 'city_dropdown_frame') and self.city_dropdown_visible:
            widget = event.widget
            # Walk up the widget tree to see if we're inside city selection
            while widget:
                if widget == self.city_search_entry or widget == self.city_dropdown_frame:
                    return  # Click is inside, don't hide
                widget = widget.master
            # Click is outside, hide dropdown
            self._hide_city_dropdown()

    def _create_scrollable_selection_row(self, parent, row_idx, label_text, values, var, cmd, combo_attr_name):
        ctk.CTkLabel(parent, text=label_text, font=ctk.CTkFont(size=14, weight="bold"), width=180, anchor="w").grid(row=row_idx, column=0, padx=(20,15), pady=10, sticky="w")
        combobox = ctk.CTkComboBox(parent, values=values, variable=var, command=cmd, width=300, height=40, corner_radius=8, border_width=2, font=ctk.CTkFont(size=12), dropdown_font=ctk.CTkFont(size=11), state="readonly", justify="left")
        combobox.grid(row=row_idx, column=1, padx=(0,20), pady=10, sticky="ew")
        setattr(self, combo_attr_name, combobox)


    def _create_selection_section(self, parent) -> ctk.CTkFrame:
        section = ctk.CTkFrame(parent, corner_radius=15)
        section.grid_columnconfigure(1, weight=1) # Allow entry/combobox to expand
        ctk.CTkLabel(section, text="⚙️ Analysis Configuration", font=ctk.CTkFont(size=18, weight="bold"), anchor="w").grid(row=0, column=0, columnspan=2, padx=20, pady=(20,15), sticky="w")
        self._create_city_selection_row(section, 1)
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
        self.status_text = ctk.CTkTextbox(section, height=150, corner_radius=10, border_width=1, font=ctk.CTkFont(family="Consolas", size=11), wrap=tk.WORD)
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
        
        # Create main container with two columns
        main_container = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        main_container.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0,20))
        main_container.grid_columnconfigure((0,1), weight=1)
        main_container.grid_rowconfigure(1, weight=1)

        # Left column
        left_frame = ctk.CTkFrame(main_container, fg_color="transparent")
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0,10))
        left_frame.grid_columnconfigure(0, weight=1)
        
        input_section = self._create_input_section(left_frame)
        input_section.grid(row=0, column=0, sticky="ew", pady=(0,15))
        selection_section = self._create_selection_section(left_frame)
        selection_section.grid(row=1, column=0, sticky="ew", pady=(0,15))
        control_section = self._create_control_section(left_frame)
        control_section.grid(row=2, column=0, sticky="ew")

        # Right column
        right_frame = ctk.CTkFrame(main_container, fg_color="transparent")
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(10,0))
        right_frame.grid_columnconfigure(0, weight=1)
        right_frame.grid_rowconfigure(1, weight=1)
        
        progress_section = self._create_progress_section(right_frame)
        progress_section.grid(row=0, column=0, sticky="ew", pady=(0,15))
        log_section = self._create_log_section(right_frame)
        log_section.grid(row=1, column=0, sticky="nsew")
        
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
                
                # Load city and display with proper Hebrew text handling
                last_city = settings.get('last_city', '')
                self.city.set(last_city)
                if last_city and hasattr(self, 'city_search_entry'):
                    display_text = fix_hebrew_text_display(last_city)
                    self.city_search_entry.delete(0, tk.END)
                    self.city_search_entry.insert(0, display_text)
                
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

        # Create simulation output directory within the reports directory
        reports_dir = os.path.join(user_inputs["output_dir"], "reports")
        simulation_dir = os.path.join(reports_dir, "simulation")
        try:
            os.makedirs(simulation_dir, exist_ok=True)
            self.show_status(f"Simulation output will be in: {simulation_dir}")
        except OSError as e:
            self.show_status(f"Error creating simulation directory '{simulation_dir}': {e.strerror}", "error")
            self.reset_gui_state(); return

        self.process_thread = threading.Thread(target=self.process_file_thread_target, args=(user_inputs, simulation_dir))
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

    def process_file_thread_target(self, user_inputs: dict, simulation_dir: str):
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
                simulation_dir, # E+ output goes to simulation subdirectory
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
