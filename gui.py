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
import shutil
# Imports for ProcessingManager are now in processing_manager.py
# Keep GUI specific imports here
from utils.data_loader import DataLoader # Still needed for IDFProcessorGUI._ensure_idf_output_variables
from utils.path_utils import (
    get_data_file_path, get_data_directory, list_data_files,
    contains_non_ascii, create_safe_path_for_energyplus,
    create_safe_output_dir_for_energyplus, move_simulation_files_back,
    normalize_path_for_energyplus
)

def fix_hebrew_text_display(text):
    """
    Fix Hebrew text display for GUI components.
    Since we now have proper RTL support, just return the text as-is.
    Hebrew text should display naturally with RTL alignment.
    """
    if not text:
        return text
    
    # With proper RTL support (justify='right'), Hebrew text should display correctly
    # No need to manipulate the text content - let the UI handle RTL rendering
    return text

# Hebrew text display helper - moved from separate functions

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

        # Debug: Check what data files are available
        try:
            data_dir = get_data_directory()
            available_files = list_data_files()
            logger.info(f"Data directory found at: {data_dir}")
            logger.info(f"Available data files: {available_files}")
        except Exception as e:
            logger.error(f"Error checking data directory: {e}")
        
        self.city_data = self.load_cities_from_csv()
        self.iso_types = [
            "RESIDNTIAL 2023", "RESIDNTIAL 2017", "HOTEL",
            "EDUCATION", "OFFICE", "CORE & ENVELOPE"
        ]

        # Initialize city-related variables
        self.city_names = []
        self.city_display_names = []

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
        
        try:
            # Use robust path utility that handles all environments
            csv_path = get_data_file_path('countries-selection.csv')
            
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
                        
        except FileNotFoundError as e:
            logger.error(f"City data file not found: {e}", exc_info=True)
            self.after(100, lambda: self.show_status(f"Error: City data file not found. {e}", "error"))
        except Exception as e:
            logger.error(f"Error loading city data: {e}", exc_info=True)
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
        if not all(hasattr(self, w_name) for w_name in ['input_entry', 'output_entry', 'eplus_entry', 'city_entry', 'iso_combobox']):
            return

        valid_style = {"border_color": self.success_color}
        invalid_style = {"border_color": self.error_color}

        self.input_entry.configure(**(valid_style if self.input_file.get() and os.path.exists(self.input_file.get()) else invalid_style))
        self.output_entry.configure(**(valid_style if self.output_dir.get() and os.path.isdir(self.output_dir.get()) else invalid_style))
        self.eplus_entry.configure(**(valid_style if self.energyplus_dir.get() and os.path.isdir(self.energyplus_dir.get()) else invalid_style))
        self.city_entry.configure(**(valid_style if self.city.get() else invalid_style))
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
        """Creates a lightning-fast autocomplete city selection."""
        ctk.CTkLabel(parent, text="🏙️ City:", font=ctk.CTkFont(size=14, weight="bold"), width=180, anchor="w").grid(row=row_idx, column=0, padx=(20,15), pady=10, sticky="w")
        
        # Prepare city data for autocomplete
        self.city_names = sorted(list(self.city_data.keys()))
        self.city_display_names = [fix_hebrew_text_display(city) for city in self.city_names]
        
        # Create container for autocomplete
        city_container = ctk.CTkFrame(parent, fg_color="transparent")
        city_container.grid(row=row_idx, column=1, padx=(0,20), pady=10, sticky="ew")
        city_container.grid_columnconfigure(0, weight=1)
        
        # Create autocomplete entry with RTL support
        self.city_entry = ctk.CTkEntry(
            city_container,
            placeholder_text="הקלד שם עיר...",  # Hebrew placeholder
            width=300,
            height=40,
            corner_radius=8,
            border_width=2,
            font=ctk.CTkFont(size=12)
        )
        self.city_entry.grid(row=0, column=0, sticky="ew")
        
        # Simple and effective RTL configuration
        def configure_rtl():
            try:
                entry_widget = self.city_entry._entry
                # Force right alignment and RTL behavior
                entry_widget.configure(justify='right')
                # Set initial cursor position to right
                entry_widget.icursor('end')
            except Exception as e:
                logger.warning(f"Could not configure RTL: {e}")
        
        # Apply RTL configuration after widget is fully created
        self.after(10, configure_rtl)
        
        # Create autocomplete listbox (initially hidden)
        self.city_autocomplete_frame = ctk.CTkFrame(city_container, height=150, corner_radius=8, border_width=1)
        
        # Use native tkinter Listbox with RTL support for Hebrew
        import tkinter as tk
        self.city_listbox = tk.Listbox(
            self.city_autocomplete_frame,
            height=8,
            font=("Segoe UI", 11),  # Better font for Hebrew
            selectmode=tk.SINGLE,
            activestyle='none',
            borderwidth=0,
            highlightthickness=0,
            relief='flat',
            justify='right',  # RTL alignment for Hebrew text
            exportselection=False  # Prevent selection conflicts
        )
        self.city_listbox.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Simple RTL maintenance
        def maintain_rtl():
            """Ensure RTL alignment is maintained during typing"""
            try:
                entry_widget = self.city_entry._entry
                current_justify = entry_widget.cget('justify')
                if current_justify != 'right':
                    entry_widget.configure(justify='right')
            except:
                pass
        
        # Periodically maintain RTL alignment
        def periodic_rtl_check():
            maintain_rtl()
            self.after(500, periodic_rtl_check)  # Check every 500ms
        
        self.after(100, periodic_rtl_check)

        # Bind events for autocomplete
        self.city_entry.bind('<KeyRelease>', self._on_city_autocomplete)
        self.city_entry.bind('<Button-1>', self._on_city_entry_click)
        self.city_entry.bind('<FocusIn>', self._on_city_entry_focus)
        self.city_entry.bind('<FocusOut>', self._on_city_entry_unfocus)
        self.city_entry.bind('<Down>', self._on_city_entry_down)
        self.city_entry.bind('<Up>', self._on_city_entry_up)
        self.city_entry.bind('<Return>', self._on_city_entry_return)
        self.city_entry.bind('<Escape>', self._hide_city_autocomplete)
        
        self.city_listbox.bind('<Double-Button-1>', self._on_city_listbox_select)
        self.city_listbox.bind('<Return>', self._on_city_listbox_select)
        self.city_listbox.bind('<Button-1>', self._on_city_listbox_click)
        
        # Autocomplete state
        self._autocomplete_visible = False
        self._current_matches = []
        self._selected_index = -1
        self._ignore_focus_out = False
        
    def _on_city_autocomplete(self, event):
        """Handle real-time autocomplete as user types."""
        if event.keysym in ['Up', 'Down', 'Return', 'Escape']:
            return
            
        search_text = self.city_entry.get().strip()
        
        # Show results even with very short input for better UX
        if len(search_text) < 1:
            self._hide_city_autocomplete()
            return
        
        # Very flexible search - match anywhere in the text
        search_lower = search_text.lower()
        all_matches = []
        
        for i, city_name in enumerate(self.city_names):
            city_lower = city_name.lower()
            display_lower = self.city_display_names[i].lower()
            
            # Calculate match score for better sorting
            score = 0
            
            # Highest score: exact start match
            if city_lower.startswith(search_lower) or display_lower.startswith(search_lower):
                score = 100
            # High score: word start match
            elif (any(word.startswith(search_lower) for word in city_lower.split()) or
                  any(word.startswith(search_lower) for word in display_lower.split())):
                score = 80
            # Medium score: contains match
            elif search_lower in city_lower or search_lower in display_lower:
                score = 60
            # Low score: partial character match (very flexible)
            elif any(char in city_lower for char in search_lower) or any(char in display_lower for char in search_lower):
                score = 20
            
            if score > 0:
                all_matches.append((score, city_name, self.city_display_names[i]))
        
        # Sort by score (highest first) and take top 15
        all_matches.sort(key=lambda x: x[0], reverse=True)
        self._current_matches = [(match[1], match[2]) for match in all_matches[:15]]
        
        if self._current_matches:
            self._show_city_autocomplete()
            
            # Update listbox efficiently with RTL text
            self.city_listbox.delete(0, tk.END)
            for _, display_name in self._current_matches:
                self.city_listbox.insert(tk.END, display_name)
        else:
            self._hide_city_autocomplete()
    
    def _on_city_entry_down(self, event):
        """Handle down arrow - select next item in list."""
        if self._autocomplete_visible and self._current_matches:
            self._selected_index = min(self._selected_index + 1, len(self._current_matches) - 1)
            self.city_listbox.selection_clear(0, tk.END)
            self.city_listbox.selection_set(self._selected_index)
            self.city_listbox.see(self._selected_index)
        elif not self._autocomplete_visible:
            self._on_city_entry_click()
        return "break"
    
    def _on_city_entry_up(self, event):
        """Handle up arrow - select previous item in list."""
        if self._autocomplete_visible and self._current_matches:
            self._selected_index = max(self._selected_index - 1, 0)
            self.city_listbox.selection_clear(0, tk.END)
            self.city_listbox.selection_set(self._selected_index)
            self.city_listbox.see(self._selected_index)
        return "break"
    
    def _on_city_entry_return(self, event):
        """Handle Enter key - select current item."""
        if self._autocomplete_visible and self._current_matches:
            if self._selected_index >= 0 and self._selected_index < len(self._current_matches):
                self._select_city_from_autocomplete(self._selected_index)
            elif self._current_matches:
                self._select_city_from_autocomplete(0)  # Select first match
        return "break"
    
    def _on_city_entry_click(self, event=None):
        """Show autocomplete when clicking on entry."""
        if self.city_entry.get().strip():
            self._on_city_autocomplete(type('Event', (), {'keysym': 'Click'})())
    
    def _on_city_entry_focus(self, event):
        """Show autocomplete when entry gets focus."""
        self._ignore_focus_out = False
        if self.city_entry.get().strip():
            self.after(10, lambda: self._on_city_autocomplete(type('Event', (), {'keysym': 'Focus'})()))
    
    def _on_city_entry_unfocus(self, event):
        """Hide autocomplete when entry loses focus."""
        if not self._ignore_focus_out:
            self.after(100, self._hide_city_autocomplete)  # Delay to allow clicks
    
    def _on_city_listbox_click(self, event):
        """Handle click on listbox item."""
        self._ignore_focus_out = True
        selection = self.city_listbox.curselection()
        if selection:
            self._select_city_from_autocomplete(selection[0])
    
    def _on_city_listbox_select(self, event):
        """Handle double-click or Enter on listbox item."""
        selection = self.city_listbox.curselection()
        if selection:
            self._select_city_from_autocomplete(selection[0])
    
    def _select_city_from_autocomplete(self, index):
        """Select a city from the autocomplete list."""
        if 0 <= index < len(self._current_matches):
            original_city, display_name = self._current_matches[index]
            
            # Clear and insert text
            self.city_entry.delete(0, tk.END)
            self.city_entry.insert(0, display_name)
            
            # Maintain RTL alignment after selection
            try:
                entry_widget = self.city_entry._entry
                entry_widget.configure(justify='right')
                entry_widget.icursor(tk.END)
            except:
                pass
            
            self.city.set(original_city)
            self._hide_city_autocomplete()
            self.on_city_selected(original_city)
    
    def _show_city_autocomplete(self):
        """Show the autocomplete dropdown."""
        if not self._autocomplete_visible:
            self.city_autocomplete_frame.grid(row=1, column=0, sticky="ew", pady=(2,0))
            self._autocomplete_visible = True
            self._selected_index = -1
    
    def _hide_city_autocomplete(self, event=None):
        """Hide the autocomplete dropdown."""
        if self._autocomplete_visible:
            self.city_autocomplete_frame.grid_forget()
            self._autocomplete_visible = False
            self._selected_index = -1
            self._ignore_focus_out = False

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
                if last_city and hasattr(self, 'city_entry'):
                    display_text = fix_hebrew_text_display(last_city)
                    self.city_entry.delete(0, tk.END)
                    self.city_entry.insert(0, display_text)
                    
                    # Set cursor to end for RTL text
                    try:
                        self.city_entry._entry.icursor(tk.END)
                    except:
                        pass
                
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
        
        # Use robust path utility for EPW files
        try:
            epw_file_path = get_data_file_path(epw_filename)
            self.show_status(f"Using weather file: {epw_file_path}")
            return epw_file_path
        except FileNotFoundError as e:
            # Provide debugging information
            try:
                available_files = list_data_files()
                epw_files = [f for f in available_files if f.endswith('.epw')]
                self.show_status(f"Error: Weather file {epw_filename} not found. Available EPW files: {epw_files}. {e}", "error")
            except:
                self.show_status(f"Error: Weather file {epw_filename} not found. {e}", "error")
            return None

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
        
        # Variables for cleanup
        safe_idf_path = idf_path
        idf_cleanup = None
        safe_output_dir = simulation_output_dir
        needs_move_back = False
        temp_output_files = []
        
        try:
            # Ensure the IDF has necessary output variables before running
            if not self._ensure_idf_output_variables(idf_path, os.path.join(os.path.dirname(energyplus_exe), "Energy+.idd")):
                 self.show_status("Skipping simulation due to issues with IDF output variables.", "warning")
                 return None # Critical step failed

            # Check if paths contain Hebrew/Unicode characters and create safe copies if needed
            if contains_non_ascii(idf_path):
                self.show_status("IDF path contains Unicode/Hebrew characters, creating ASCII-safe copy for EnergyPlus...")
                safe_idf_path, idf_cleanup = create_safe_path_for_energyplus(idf_path)
                self.show_status(f"Using safe IDF path: {safe_idf_path}")
            
            if contains_non_ascii(simulation_output_dir):
                self.show_status("Output directory path contains Unicode/Hebrew characters, using temporary ASCII-safe directory...")
                safe_output_dir, needs_move_back = create_safe_output_dir_for_energyplus(simulation_output_dir)
                self.show_status(f"Using safe output directory: {safe_output_dir}")
                # Update the expected output path
                temp_output_csv_path = os.path.join(safe_output_dir, "eplustbl.csv")
            else:
                temp_output_csv_path = output_csv_path

            # Normalize paths for EnergyPlus compatibility
            normalized_epw = normalize_path_for_energyplus(epw_file_path)
            normalized_output_dir = normalize_path_for_energyplus(safe_output_dir)
            normalized_idf = normalize_path_for_energyplus(safe_idf_path)
            
            cmd = [energyplus_exe, "-w", normalized_epw, "-r", "-d", normalized_output_dir, normalized_idf]
            self.show_status(f"Running E+ command with normalized paths: {' '.join(cmd)}")
            
            process = subprocess.run(cmd, check=True, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            
            if process.stdout: logger.info(f"E+ STDOUT:\n{process.stdout}")
            if process.stderr: logger.warning(f"E+ STDERR:\n{process.stderr}") # E+ often uses stderr for info

            # Check if simulation produced output in the temporary location
            if os.path.exists(temp_output_csv_path):
                # Check if CSV is empty or too small (basic check)
                if os.path.getsize(temp_output_csv_path) > 100: # Arbitrary small size
                    simulation_successful = True
                    
                    # If we used a temporary directory, move files back to the original location
                    if needs_move_back:
                        self.show_status("Moving simulation output files back to original Unicode directory...")
                        if move_simulation_files_back(safe_output_dir, simulation_output_dir):
                            self.show_status("Successfully moved simulation files to original directory.")
                        else:
                            self.show_status("Warning: Some issues occurred while moving simulation files back.", "warning")
                    
                    self.show_status(f"EnergyPlus simulation successful. Output: {output_csv_path}")
                else:
                    self.show_status(f"Warning: Simulation output file {temp_output_csv_path} is very small or empty.", "warning")
            else:
                self.show_status(f"Simulation finished, but output file not found: {temp_output_csv_path}", "error")
        
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
            # Clean up temporary IDF file
            if idf_cleanup:
                idf_cleanup()
                self.show_status("Cleaned up temporary IDF file.")
            
            # Clean up temporary output directory if something went wrong
            if needs_move_back and not simulation_successful and os.path.exists(safe_output_dir):
                try:
                    shutil.rmtree(safe_output_dir)
                except OSError as e:
                    logger.warning(f"Could not remove temporary output directory {safe_output_dir}: {e}")
            
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
