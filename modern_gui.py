import flet as ft
import json
import os
import threading
from datetime import datetime, timedelta
from pathlib import Path

from utils.logging_config import get_logger
from utils.sentry_config import capture_exception_with_context, add_breadcrumb, set_user_context
from utils.path_utils import (
    get_data_file_path, get_data_directory, list_data_files,
    contains_non_ascii, create_safe_path_for_energyplus,
    create_safe_output_dir_for_energyplus, move_simulation_files_back,
    normalize_path_for_energyplus
)
from processing_manager import ProcessingManager
from utils.data_loader import DataLoader
from utils.update_manager import UpdateManager
from utils.license_manager import license_manager, check_license_on_startup
from utils.license_dialog import LicenseDialog, show_startup_license_check
from version import get_version

logger = get_logger(__name__)

class ModernIDFProcessorGUI:
    def __init__(self):
        self.page = None
        self.processing_manager = None
        self.is_processing = False
        self.settings_file = "settings.json"
        
        # Form data
        self.input_file = ""
        self.output_dir = ""
        self.energyplus_dir = ""
        self.selected_city = ""
        self.selected_iso = ""
        self.city_area_name = ""
        self.city_area_code = ""
        
        # Consultant data
        self.consultant_company = ""
        self.consultant_engineer = ""
        self.consultant_phone = ""
        self.consultant_email = ""
        self.tester_company = ""
        self.tester_engineer = ""
        self.tester_phone = ""
        self.tester_email = ""
        
        # Optional project fields
        self.project_gush = ""
        self.project_helka = ""
        
        # Update manager
        self.update_manager = UpdateManager(status_callback=self.show_status)
        self.update_dialog = None
        self.current_version = get_version()
        
        # License management
        self.license_dialog = None
        self.license_status = None
        self.daily_usage_count = 0
        
        # Load city data
        self.city_data = self.load_cities_from_csv()
        self.iso_types = [
            "מגורים 2023", "מגורים 2017", "מלון (בקרוב)",
            "חינוך (בקרוב)", "משרדים", "מעטפת ומבנה (בקרוב)"
        ]
        self.iso_types_english = [
            "RESIDNTIAL 2023", "RESIDNTIAL 2017", "HOTEL (Coming Soon)",
            "EDUCATION (Coming Soon)", "OFFICE", "CORE & ENVELOPE (Coming Soon)"
        ]
        # Map Hebrew to English for backend processing
        self.iso_map = dict(zip(self.iso_types, self.iso_types_english))
        self.disabled_iso_types = {
            "מלון (בקרוב)", "חינוך (בקרוב)", "מעטפת ומבנה (בקרוב)"
        }
        
        # UI Components (will be initialized in build_ui)
        self.input_file_field = None
        self.output_dir_field = None
        self.energyplus_dir_field = None
        self.city_field = None
        self.iso_dropdown = None
        self.process_button = None
        self.progress_bar = None
        self.status_text = None
        self.energyplus_progress = None
        self.reports_progress = None
        
        # Animation control
        self.animation_timer = None
        self.is_animating_energyplus = False
        self.is_animating_reports = False
        self.animation_step = 0
        self.animation_start_time = 0
        
        # Queue system
        self.job_queue = []  # List of job dictionaries
        self.current_job_index = -1  # Index of currently running job (-1 if none)
        self.max_queue_size = 10
        self.queue_container = None
        self.queue_worker_thread = None
        self.stop_queue_processing = False
        
        # Window settings (will be loaded in load_settings)
        self.window_settings = {
            'width': None,
            'height': None,
            'maximized': False,
            'position_x': None,
            'position_y': None
        }
        
        # Debouncing for window settings saves
        self._save_timer = None

    def load_cities_from_csv(self):
        """Load city data from CSV file."""
        cities_data = {}
        try:
            csv_path = get_data_file_path('countries-selection.csv')
            with open(csv_path, 'r', encoding='utf-8') as f:
                first_line = f.readline().strip()
                if not any(char in first_line for char in 'אבגדהוזחטיכלמנסעפצקרשת'):
                    pass  # Has header
                else:
                    f.seek(0)  # No header, reset to beginning
                
                for line in f:
                    parts = [part.strip() for part in line.split(',')]
                    if len(parts) >= 3:
                        city_name, area_name, area_code = parts[0], parts[1], parts[2]
                        cities_data[city_name] = {'area_name': area_name, 'area_code': area_code}
        except Exception as e:
            logger.error(f"Error loading city data: {e}")
        return cities_data

    def _get_default_input_file(self):
        """Get default input file path."""
        # Try to find a test file in the project
        test_file = os.path.join('tests', 'in.idf')
        if os.path.exists(test_file):
            return os.path.abspath(test_file)
        return ''

    def _get_default_energyplus_dir(self):
        """Get default EnergyPlus directory."""
        # Common EnergyPlus installation paths
        common_paths = [
            'C:/EnergyPlusV9-4-0',
            'C:/EnergyPlusV22-2-0',
            'C:/EnergyPlusV23-1-0',
            'C:/EnergyPlusV24-1-0',
            'C:/Program Files/EnergyPlusV9-4-0',
            'C:/Program Files/EnergyPlusV22-2-0',
            'C:/Program Files/EnergyPlusV23-1-0',
            'C:/Program Files/EnergyPlusV24-1-0'
        ]
        
        for path in common_paths:
            if os.path.exists(path):
                return path
        return ''

    def _get_default_output_dir(self):
        """Get default output directory."""
        # Use user's Documents folder or Desktop as default
        try:
            # Try Documents folder first
            documents = os.path.expanduser('~/Documents')
            if os.path.exists(documents):
                return documents
            
            # Fall back to Desktop
            desktop = os.path.expanduser('~/Desktop')
            if os.path.exists(desktop):
                return desktop
                
            # Last resort - current directory
            return os.getcwd()
        except Exception:
            return os.getcwd()

    def add_job_to_queue(self, job_data):
        """Add a new job to the processing queue."""
        if len(self.job_queue) >= self.max_queue_size:
            self.show_status(f"תור עבודות מלא! מקסימום {self.max_queue_size} עבודות בתור", "warning")
            return False
        
        job = {
            'id': len(self.job_queue) + 1,
            'input_file': job_data['input_file'],
            'output_dir': job_data['output_dir'],
            'project_name': job_data.get('project_name', ''),
            'city': job_data['city'],
            'iso_type': job_data['iso_type'],
            'consultant_data': job_data.get('consultant_data', {}),
            'project_data': job_data.get('project_data', {}),
            'status': 'pending',  # pending, running, completed, failed
            'created_time': datetime.now().strftime("%H:%M:%S"),
            'start_time': None,
            'end_time': None,
            'error_message': None
        }
        
        self.job_queue.append(job)
        self.update_queue_display()
        self.update_form_validation()  # Update button text
        
        # Start queue processing if not already running
        if not self.is_processing and self.current_job_index == -1:
            self.start_queue_processing()
        
        return True
    
    def remove_job_from_queue(self, job_id):
        """Remove a job from the queue (only if not running)."""
        for i, job in enumerate(self.job_queue):
            if job['id'] == job_id:
                if job['status'] == 'running':
                    self.show_status("לא ניתן להסיר עבודה שרצה כעת", "warning")
                    return False
                
                self.job_queue.pop(i)
                # Adjust current_job_index if needed
                if i <= self.current_job_index:
                    self.current_job_index -= 1
                
                self.update_queue_display()
                self.update_form_validation()  # Update button text
                return True
        return False
    
    def clear_completed_jobs(self):
        """Remove all completed and failed jobs from the queue."""
        self.job_queue = [job for job in self.job_queue if job['status'] in ['pending', 'running']]
        # Reset current_job_index if queue was cleared
        running_jobs = [i for i, job in enumerate(self.job_queue) if job['status'] == 'running']
        self.current_job_index = running_jobs[0] if running_jobs else -1
        self.update_queue_display()
        self.update_form_validation()  # Update button text
    
    def get_queue_status(self):
        """Get current queue status summary."""
        if not self.job_queue:
            return "תור ריק"
        
        pending = sum(1 for job in self.job_queue if job['status'] == 'pending')
        running = sum(1 for job in self.job_queue if job['status'] == 'running')
        completed = sum(1 for job in self.job_queue if job['status'] == 'completed')
        failed = sum(1 for job in self.job_queue if job['status'] == 'failed')
        
        return f"ממתין: {pending} | רץ: {running} | הושלם: {completed} | נכשל: {failed}"
    
    def start_queue_processing(self):
        """Start processing jobs in the queue sequentially."""
        if self.queue_worker_thread and self.queue_worker_thread.is_alive():
            return  # Already processing
        
        self.stop_queue_processing = False
        self.queue_worker_thread = threading.Thread(target=self._process_queue_worker, daemon=True)
        self.queue_worker_thread.start()
    
    def stop_queue_processing_func(self):
        """Stop queue processing after current job completes."""
        self.stop_queue_processing = True
        if self.processing_manager:
            self.processing_manager.is_cancelled = True
    
    def _process_queue_worker(self):
        """Worker thread that processes jobs in the queue sequentially."""
        while not self.stop_queue_processing:
            # Find next pending job
            next_job_index = -1
            for i, job in enumerate(self.job_queue):
                if job['status'] == 'pending':
                    next_job_index = i
                    break
            
            if next_job_index == -1:
                # No more pending jobs
                self.current_job_index = -1
                self.is_processing = False
                if self.process_button:
                    self.process_button.disabled = False
                    self.process_button.text = "הוסף לתור"
                    if self.page:
                        self.page.update()
                break
            
            # Process the next job
            self.current_job_index = next_job_index
            job = self.job_queue[next_job_index]
            
            try:
                job['status'] = 'running'
                job['start_time'] = datetime.now().strftime("%H:%M:%S")
                self.update_queue_display()
                
                # Set GUI form values for this job
                self.input_file = job['input_file']
                self.output_dir = job['output_dir']
                self.selected_city = job['city']
                self.selected_iso = job['iso_type']
                
                # Process the job using existing process_files logic
                success = self._process_single_job(job)
                
                if success:
                    job['status'] = 'completed'
                    job['end_time'] = datetime.now().strftime("%H:%M:%S")
                    self.show_status(f"עבודה #{job['id']} הושלמה בהצלחה", "success")
                else:
                    job['status'] = 'failed'
                    job['end_time'] = datetime.now().strftime("%H:%M:%S")
                    job['error_message'] = "שגיאה בעיבוד"
                    self.show_status(f"עבודה #{job['id']} נכשלה", "error")
                
            except Exception as e:
                job['status'] = 'failed'
                job['end_time'] = datetime.now().strftime("%H:%M:%S")
                job['error_message'] = str(e)
                logger.error(f"Error processing job {job['id']}: {e}", exc_info=True)
                self.show_status(f"עבודה #{job['id']} נכשלה: {str(e)}", "error")
            
            finally:
                self.update_queue_display()
                # Small delay between jobs
                import time
                time.sleep(1)
        
        self.current_job_index = -1
        self.is_processing = False
    
    def _process_single_job(self, job):
        """Process a single job from the queue."""
        try:
            self.is_processing = True
            
            # Generate run ID
            run_id = datetime.now().strftime('%d-%m-%Y-%H-%M-%S')
            reports_dir = os.path.join(job['output_dir'], f"reports-{run_id}")
            simulation_dir = os.path.join(reports_dir, "simulation")
            
            os.makedirs(simulation_dir, exist_ok=True)
            self.show_status(f"מעבד עבודה #{job['id']}: {os.path.basename(job['input_file'])}")
            
            # Determine EPW file
            epw_file = self.determine_epw_file()
            if not epw_file:
                self.show_status(f"עבודה #{job['id']}: קביעת קובץ EPW נכשלה", "error")
                return False
            
            # Run EnergyPlus simulation
            simulation_output_csv = self.run_energyplus_simulation(epw_file, simulation_dir)
            if not simulation_output_csv:
                self.show_status(f"עבודה #{job['id']}: סימולציה נכשלה, ממשיך בלי נתוני סימולציה", "warning")
            
            # Initialize ProcessingManager
            self.processing_manager = ProcessingManager(
                status_callback=self.show_status,
                progress_callback=self.update_progress,
                simulation_output_csv=simulation_output_csv
            )
            
            # Set city info
            self.processing_manager.city_info = {
                'city': job['city'],
                'area_name': self.city_area_name,
                'area_code': self.city_area_code,
                'iso_type': job['iso_type']
            }
            
            # Set consultant and project data
            consultant_data = job.get('consultant_data', {})
            self.processing_manager.consultant_data = {
                'consultant_company': consultant_data.get('consultant_company', ''),
                'consultant_engineer': consultant_data.get('consultant_engineer', ''),
                'consultant_phone': consultant_data.get('consultant_phone', ''),
                'consultant_email': consultant_data.get('consultant_email', ''),
                'tester_company': consultant_data.get('tester_company', ''),
                'tester_engineer': consultant_data.get('tester_engineer', ''),
                'tester_phone': consultant_data.get('tester_phone', ''),
                'tester_email': consultant_data.get('tester_email', ''),
                'project_gush': job.get('project_data', {}).get('project_gush', ''),
                'project_helka': job.get('project_data', {}).get('project_helka', ''),
                'iso_type': job['iso_type']
            }
            
            # Process IDF and generate reports
            self.show_status(f"עבודה #{job['id']}: מתחיל עיבוד IDF ויצירת דוחות...")
            self.start_progress_animation("reports")
            
            english_iso = self.iso_map.get(job['iso_type'], job['iso_type'])
            self.processing_manager.city_info['iso_type'] = english_iso
            
            success = self.processing_manager.process_idf(
                job['input_file'],
                os.path.join(self.energyplus_dir, "Energy+.idd"),
                job['output_dir'],
                run_id,
                self.energyplus_dir
            )
            
            if success:
                self.show_status(f"עבודה #{job['id']} הושלמה בהצלחה!", "success")
                return True
            else:
                self.show_status(f"עבודה #{job['id']} נכשלה בעיבוד", "error")
                return False
                
        except Exception as e:
            self.show_status(f"עבודה #{job['id']}: שגיאה קריטית - {str(e)}", "error")
            logger.error(f"Critical error in job {job['id']}: {e}", exc_info=True)
            return False
        
        finally:
            self.stop_progress_animation()
            self.is_processing = False
    
    def update_queue_display(self):
        """Update the queue display UI."""
        if not self.queue_container or not self.page:
            return
        
        # Clear existing queue items
        self.queue_container.content.controls.clear()
        
        # Add header
        header = ft.Row([
            ft.Text("תור עבודות", size=18, weight=ft.FontWeight.BOLD, rtl=True),
            ft.Text(self.get_queue_status(), size=14, color=ft.Colors.GREY_600, rtl=True)
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        self.queue_container.content.controls.append(header)
        
        # Add queue items
        if not self.job_queue:
            empty_msg = ft.Container(
                content=ft.Text("אין עבודות בתור", size=14, color=ft.Colors.GREY_500, rtl=True),
                padding=20,
                alignment=ft.alignment.center
            )
            self.queue_container.content.controls.append(empty_msg)
        else:
            for i, job in enumerate(self.job_queue):
                job_item = self._create_queue_item(job, i)
                self.queue_container.content.controls.append(job_item)
        
        self.page.update()
    
    def _create_queue_item(self, job, index):
        """Create a visual item for the queue display."""
        # Status indicators
        status_colors = {
            'pending': ft.Colors.ORANGE,
            'running': ft.Colors.BLUE,
            'completed': ft.Colors.GREEN,
            'failed': ft.Colors.RED
        }
        
        status_icons = {
            'pending': ft.Icons.SCHEDULE,
            'running': ft.Icons.PLAY_CIRCLE,
            'completed': ft.Icons.CHECK_CIRCLE,
            'failed': ft.Icons.ERROR
        }
        
        status_texts = {
            'pending': 'ממתין',
            'running': 'רץ',
            'completed': 'הושלם',
            'failed': 'נכשל'
        }
        
        # Job info
        file_name = os.path.basename(job['input_file'])
        time_text = job['created_time']
        if job['start_time']:
            time_text = f"התחיל: {job['start_time']}"
        if job['end_time']:
            time_text = f"סיים: {job['end_time']}"
        
        # Create job item
        job_row = ft.Container(
            content=ft.Row([
                # Status indicator
                ft.Icon(
                    status_icons[job['status']], 
                    color=status_colors[job['status']], 
                    size=20
                ),
                # Job info
                ft.Column([
                    ft.Text(f"#{job['id']}: {file_name}", size=14, weight=ft.FontWeight.W_500, rtl=True),
                    ft.Text(f"{status_texts[job['status']]} • {time_text}", size=12, color=ft.Colors.GREY_600, rtl=True)
                ], spacing=2, expand=True),
                # Remove button (only for pending jobs)
                ft.IconButton(
                    icon=ft.Icons.DELETE,
                    icon_color=ft.Colors.RED_400,
                    icon_size=16,
                    tooltip="הסר מהתור",
                    on_click=lambda e, job_id=job['id']: self._remove_job_click(job_id),
                    visible=job['status'] == 'pending'
                )
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            padding=ft.padding.symmetric(horizontal=10, vertical=8),
            border=ft.border.all(1, ft.Colors.GREY_300),
            border_radius=8,
            bgcolor=ft.Colors.GREY_50 if job['status'] == 'running' else None
        )
        
        return job_row
    
    def _remove_job_click(self, job_id):
        """Handle remove job button click."""
        self.remove_job_from_queue(job_id)

    def load_settings(self):
        """Load saved settings from JSON file."""
        try:
            # Set default values first
            self.input_file = self._get_default_input_file()
            self.energyplus_dir = self._get_default_energyplus_dir()
            self.output_dir = self._get_default_output_dir()
            self.selected_city = ''
            self.selected_iso = ''
            
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                
                # Load paths, but validate they exist
                input_path = settings.get('last_input', '')
                if input_path and os.path.exists(input_path):
                    self.input_file = input_path
                
                eplus_path = settings.get('last_eplus_dir', '')
                if eplus_path and os.path.exists(eplus_path):
                    self.energyplus_dir = eplus_path
                
                output_path = settings.get('last_output', '')
                if output_path and os.path.exists(output_path):
                    self.output_dir = output_path
                
                self.selected_city = settings.get('last_city', '')
                self.selected_iso = settings.get('last_iso_type', '')
                
                # Load consultant data
                consultant_data = settings.get('consultant_data', {})
                self.consultant_company = consultant_data.get('consultant_company', '')
                self.consultant_engineer = consultant_data.get('consultant_engineer', '')
                self.consultant_phone = consultant_data.get('consultant_phone', '')
                self.consultant_email = consultant_data.get('consultant_email', '')
                self.tester_company = consultant_data.get('tester_company', '')
                self.tester_engineer = consultant_data.get('tester_engineer', '')
                self.tester_phone = consultant_data.get('tester_phone', '')
                self.tester_email = consultant_data.get('tester_email', '')
                
                # Load optional project fields
                project_data = settings.get('project_data', {})
                self.project_gush = project_data.get('project_gush', '')
                self.project_helka = project_data.get('project_helka', '')
                
                # Load window settings
                self.window_settings = settings.get('window', {
                    'width': 1400,  # Default width
                    'height': 1000,  # Default height
                    'maximized': False,  # Default to normal window
                    'position_x': None,
                    'position_y': None
                })
                
                # Update city area info if city is loaded
                if self.selected_city and self.selected_city in self.city_data:
                    info = self.city_data[self.selected_city]
                    self.city_area_name = info['area_name']
                    self.city_area_code = info['area_code']
                    
        except Exception as e:
            logger.error(f"Error loading settings: {e}")
            # Default window settings if loading fails
            self.window_settings = {
                'width': 1400,  # Default width
                'height': 1000,  # Default height
                'maximized': False,
                'position_x': None,
                'position_y': None
            }

    def save_settings(self):
        """Save current settings to JSON file."""
        try:
            # Get current window state if page is available
            window_settings = getattr(self, 'window_settings', {})
            if self.page:
                try:
                    window_settings = {
                        'width': getattr(self.page.window, 'width', 1400),
                        'height': getattr(self.page.window, 'height', 1000),
                        'maximized': getattr(self.page.window, 'maximized', False),
                        'position_x': getattr(self.page.window, 'left', None),
                        'position_y': getattr(self.page.window, 'top', None)
                    }
                    logger.info(f"Saving window settings: {window_settings}")
                except Exception as e:
                    logger.warning(f"Could not read window properties: {e}")
            
            settings = {
                'last_input': self.input_file,
                'last_eplus_dir': self.energyplus_dir,
                'last_output': self.output_dir,
                'last_city': self.selected_city,
                'last_iso_type': self.selected_iso,
                'consultant_data': {
                    'consultant_company': self.consultant_company,
                    'consultant_engineer': self.consultant_engineer,
                    'consultant_phone': self.consultant_phone,
                    'consultant_email': self.consultant_email,
                    'tester_company': self.tester_company,
                    'tester_engineer': self.tester_engineer,
                    'tester_phone': self.tester_phone,
                    'tester_email': self.tester_email
                },
                'project_data': {
                    'project_gush': self.project_gush,
                    'project_helka': self.project_helka
                },
                'window': window_settings
            }
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving settings: {e}")
    
    def _debounced_save_settings(self):
        """Save settings with debouncing to avoid excessive saves."""
        # Cancel any existing timer
        if self._save_timer:
            self._save_timer.cancel()
        
        # Start a new timer for 1 second delay
        self._save_timer = threading.Timer(1.0, self.save_settings)
        self._save_timer.start()

    def on_window_event(self, e):
        """Handle window events like resize, move, maximize."""
        try:
            logger.debug(f"Window event: {e.event_type}")  # Changed to debug level
            if e.event_type == "resized" or e.event_type == "moved" or e.event_type == "maximized":
                # Use debounced save for frequent events
                self._debounced_save_settings()
            elif e.event_type == "close":
                # Save immediately when window is closing
                self.save_settings()
        except Exception as ex:
            logger.error(f"Error handling window event: {ex}")
    
    def on_page_close(self, e):
        """Handle page close event."""
        try:
            logger.info("Page closing, saving settings...")
            self.save_settings()
        except Exception as ex:
            logger.error(f"Error saving settings on close: {ex}")

    def show_status(self, message, level="info"):
        """Display status message with appropriate styling."""
        if not self.status_text:
            return
            
        timestamp = datetime.now().strftime('%H:%M:%S')
        
        # Choose color based on level
        color_map = {
            "info": ft.Colors.BLUE_700,
            "success": ft.Colors.GREEN_700,
            "warning": ft.Colors.ORANGE_700,
            "error": ft.Colors.RED_700
        }
        
        # Auto-detect level
        msg_lower = message.lower()
        if level == "info":
            if any(err_word in msg_lower for err_word in ["error", "failed", "could not"]):
                level = "error"
            elif any(succ_word in msg_lower for succ_word in ["success", "completed", "generated"]):
                level = "success"
            elif any(warn_word in msg_lower for warn_word in ["warning", "cancelled", "skipping"]):
                level = "warning"

        color = color_map.get(level, ft.Colors.BLUE_700)
        
        # Add message to status display
        if hasattr(self.status_text, 'controls'):
            self.status_text.controls.append(
                ft.Container(
                    content=ft.Row([
                        ft.Text(timestamp, size=12, color=ft.Colors.GREY_600),
                        ft.Text(message, size=12, color=color, expand=True)
                    ]),
                    padding=ft.padding.symmetric(vertical=2)
                )
            )
            # Keep only last 50 messages
            if len(self.status_text.controls) > 50:
                self.status_text.controls = self.status_text.controls[-50:]
            
            # Scroll to bottom
            if self.page:
                self.page.update()

        # Log message
        if level == "error":
            logger.error(f"GUI: {message}")
        elif level == "warning":
            logger.warning(f"GUI: {message}")
        else:
            logger.info(f"GUI: {message}")
    
    def show_status_safe(self, message, level="info"):
        """Thread-safe version of show_status for background threads."""
        try:
            # For Flet, we can safely call UI updates from any thread
            # as long as we handle exceptions gracefully
            self.show_status(message, level)
        except Exception as e:
            # Log errors but don't crash the background thread
            logger.error(f"Error updating UI status: {e}")
    
    def show_snackbar(self, message, bgcolor=None):
        """Show a snackbar notification."""
        try:
            if not self.page:
                return
            
            # Default colors based on message content
            if bgcolor is None:
                if any(word in message for word in ["error", "שגיאה", "נכשל"]):
                    bgcolor = ft.Colors.RED_500
                elif any(word in message for word in ["success", "הצלחה", "הושלם"]):
                    bgcolor = ft.Colors.GREEN_500
                elif any(word in message for word in ["warning", "אזהרה"]):
                    bgcolor = ft.Colors.ORANGE_500
                else:
                    bgcolor = ft.Colors.BLUE_500
            
            snack = ft.SnackBar(
                content=ft.Text(message, color=ft.Colors.WHITE),
                bgcolor=bgcolor
            )
            self.page.snack_bar = snack
            snack.open = True
            self.page.update()
        except Exception as e:
            logger.error(f"Error showing snackbar: {e}")

    def update_progress(self, value):
        """Update reports progress bar."""
        # Stop animation when we get actual progress updates
        if self.is_animating_reports:
            self.stop_progress_animation()
        
        if self.reports_progress:
            self.reports_progress.value = value
            if self.page:
                self.page.update()

    def start_progress_animation(self, progress_bar_type="reports"):
        """Start modern indeterminate loading animation for the specified progress bar."""
        self.stop_progress_animation()
        
        if progress_bar_type == "energyplus":
            self.is_animating_energyplus = True
        else:
            self.is_animating_reports = True
            
        self.animation_step = 0
        import time
        self.animation_start_time = time.time()
        self._animate_progress_bar(progress_bar_type)
    
    def stop_progress_animation(self):
        """Stop the progress bar animation."""
        if self.animation_timer:
            self.animation_timer.cancel()
            self.animation_timer = None
        self.is_animating_energyplus = False
        self.is_animating_reports = False
        
        # Reset colors to default when stopping animation
        try:
            if self.energyplus_progress and hasattr(self.energyplus_progress, 'color'):
                self.energyplus_progress.color = ft.Colors.PRIMARY
            if self.reports_progress and hasattr(self.reports_progress, 'color'):
                self.reports_progress.color = ft.Colors.PRIMARY
        except:
            pass  # Ignore if color reset fails
    
    def _animate_progress_bar(self, progress_bar_type):
        """Internal method to create modern indeterminate loading animation."""
        import math
        import time
        
        if progress_bar_type == "energyplus" and not self.is_animating_energyplus:
            return
        if progress_bar_type == "reports" and not self.is_animating_reports:
            return
        
        # Get elapsed time for smooth animation
        elapsed_time = time.time() - self.animation_start_time
        
        # Consistent smooth indeterminate animation (Material Design style)
        cycle_duration = 2.5  # Each cycle takes 2.5 seconds for smooth feel
        cycle_position = (elapsed_time % cycle_duration) / cycle_duration  # 0 to 1
        
        # Single consistent pattern: smooth traveling wave
        if cycle_position < 0.4:
            # Growing phase: progress grows from 0 to 70%
            progress_value = (cycle_position / 0.4) * 0.7
        elif cycle_position < 0.6:
            # Hold phase: stays at 70% briefly
            progress_value = 0.7
        else:
            # Shrinking phase: shrinks from 70% back to 0
            shrink_position = (cycle_position - 0.6) / 0.4
            progress_value = 0.7 * (1 - shrink_position)
        
        # Ensure progress value is in valid range
        progress_value = max(0.05, min(0.95, progress_value))
        
        # Add very subtle color animation synchronized with progress
        color_intensity = 0.9 + 0.1 * math.sin(cycle_position * 2 * math.pi)  # Very gentle pulse
        
        try:
            target_progress_bar = None
            if progress_bar_type == "energyplus" and self.energyplus_progress:
                target_progress_bar = self.energyplus_progress
            elif progress_bar_type == "reports" and self.reports_progress:
                target_progress_bar = self.reports_progress
            
            if target_progress_bar:
                target_progress_bar.value = progress_value
                # Add subtle opacity animation for modern feel
                try:
                    # Only apply color animation if the progress bar supports it
                    if hasattr(target_progress_bar, 'color') and hasattr(ft.Colors, 'with_opacity'):
                        target_progress_bar.color = ft.Colors.with_opacity(color_intensity, ft.Colors.PRIMARY)
                except:
                    pass  # Fallback to basic animation if color animation fails
                
            if self.page:
                self.page.update()
        except Exception as e:
            logger.error(f"Error updating progress animation: {e}")
        
        # Schedule next animation frame with higher frequency for smoothness
        if (progress_bar_type == "energyplus" and self.is_animating_energyplus) or \
           (progress_bar_type == "reports" and self.is_animating_reports):
            self.animation_timer = threading.Timer(0.05, lambda: self._animate_progress_bar(progress_bar_type))
            self.animation_timer.start()

    def create_file_picker_field(self, label, file_type="file", on_result=None):
        """Create a modern file picker field."""
        
        def on_picker_result(e: ft.FilePickerResultEvent):
            selected_path = None
            
            # Handle file selection
            if e.files and len(e.files) > 0:
                selected_path = e.files[0].path
            # Handle directory selection  
            elif e.path:
                selected_path = e.path
            
            if selected_path:
                text_field.value = selected_path
                if on_result:
                    on_result(selected_path)
                if self.page:
                    self.page.update()
                logger.info(f"Path selected via browse: {selected_path}")
        
        # Create file picker
        file_picker = ft.FilePicker(on_result=on_picker_result)
        self.page.overlay.append(file_picker)
        
        # Create text field with manual input support
        def on_text_change(e):
            if on_result and e.control.value:
                path = e.control.value.strip()
                # Validate IDF file extension if it's a file type field
                if file_type == "file" and path and not path.lower().endswith('.idf'):
                    # Show warning but still save the path (user might be typing)
                    if len(path) > 4:  # Only warn if it looks like a complete path
                        self.show_status("רק קבצי IDF מתוכלים (.idf)", "warning")
                on_result(path)
        
        text_field = ft.TextField(
            label=label,
            expand=True,
            border_radius=12,
            filled=True,
            border_color=ft.Colors.OUTLINE_VARIANT,
            focused_border_color=ft.Colors.PRIMARY,
            text_align=ft.TextAlign.RIGHT,  # RTL support
            rtl=True,
            on_change=on_text_change
        )
        
        # Create browse button
        def on_browse_click(e):
            if file_type == "file":
                # Only allow IDF files for file selection
                file_picker.pick_files(
                    dialog_title=f"בחר {label}",
                    file_type=ft.FilePickerFileType.CUSTOM,
                    allowed_extensions=["idf"]
                )
            elif file_type == "folder":
                file_picker.get_directory_path(dialog_title=f"בחר {label}")
            else:
                # Default to IDF files only
                file_picker.pick_files(
                    dialog_title=f"בחר {label}",
                    file_type=ft.FilePickerFileType.CUSTOM,
                    allowed_extensions=["idf"]
                )
        
        browse_btn = ft.ElevatedButton(
            "עיון",
            icon=ft.Icons.FOLDER_OPEN,
            on_click=on_browse_click,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=12),
            )
        )
        
        return ft.Row([text_field, browse_btn], spacing=10), text_field

    def create_city_autocomplete(self):
        """Create modern city autocomplete field with Hebrew support."""
        # Create a scrollable suggestions list
        self.suggestions_list = ft.Column(
            spacing=1,
            scroll=ft.ScrollMode.AUTO
        )
        
        city_field = ft.TextField(
            label="עיר",
            hint_text="הקלד שם עיר... (לדוגמה: בת)",
            expand=True,
            border_radius=12,
            filled=True,
            border_color=ft.Colors.OUTLINE_VARIANT,
            focused_border_color=ft.Colors.PRIMARY,
            text_align=ft.TextAlign.RIGHT,  # RTL support
            rtl=True,
            label_style=ft.TextStyle(),
            hint_style=ft.TextStyle(),
            on_change=self.on_city_change,
            on_focus=self.on_city_focus,
            on_blur=self.on_city_blur
        )
        
        # Container for suggestions dropdown
        self.suggestions_container = ft.Container(
            content=self.suggestions_list,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=8,
            bgcolor=ft.Colors.SURFACE,
            padding=8,
            visible=False,
            height=200,  # Fixed height with scrolling
            width=None  # Will expand to match parent
        )
        
        # Container to wrap text field and suggestions
        autocomplete_container = ft.Column([
            city_field,
            self.suggestions_container
        ], spacing=2, tight=True)
        
        return autocomplete_container, city_field

    def on_city_change(self, e):
        """Handle city field changes with autocomplete."""
        search_text = e.control.value.strip()
        self.selected_city = search_text
        
        # Update area info if exact match found
        if search_text in self.city_data:
            info = self.city_data[search_text]
            self.city_area_name = info['area_name']
            self.city_area_code = info['area_code']
            self.show_status(f"נבחרה עיר: {search_text}, אזור: {info['area_name']}, קוד: {info['area_code']}")
        
        # Show autocomplete suggestions
        self.update_city_suggestions(search_text)
        
        self._debounced_save_settings()
        self.update_form_validation()
    
    def on_city_focus(self, e):
        """Handle city field focus to show suggestions."""
        search_text = e.control.value.strip()
        if search_text:  # Only show suggestions if there's already text
            self.update_city_suggestions(search_text)
    
    def on_city_blur(self, e):
        """Handle city field blur to hide suggestions after a delay."""
        # Use a small delay to allow clicking on suggestions
        import threading
        def hide_suggestions():
            import time
            time.sleep(0.3)  # Slightly longer delay to allow clicking
            if hasattr(self, 'suggestions_container'):
                self.suggestions_container.visible = False
                if self.page:
                    self.page.update()
        
        threading.Thread(target=hide_suggestions, daemon=True).start()
    
    def update_city_suggestions(self, search_text):
        """Update autocomplete suggestions based on search text."""
        if not hasattr(self, 'suggestions_list') or not hasattr(self, 'suggestions_container'):
            return
        
        # Clear existing suggestions
        self.suggestions_list.controls.clear()
        
        if search_text and len(search_text) >= 1:
            # Filter cities that contain the search text (case-insensitive)
            matches = []
            search_lower = search_text.lower()
            
            for city in self.city_data.keys():
                if search_lower in city.lower():
                    matches.append(city)
            
            # Sort matches so that cities starting with the search text come first
            matches.sort(key=lambda city: (
                not city.lower().startswith(search_lower),  # Starts with search text first
                city.lower()  # Then alphabetical
            ))
            
            # Limit to 8 items to fit nicely in the dropdown
            matches = matches[:8]
            
            if matches:
                for city in matches:
                    # Create suggestion button with hover effect
                    suggestion_btn = ft.Container(
                        content=ft.Text(
                            city,
                            size=14,
                            color=ft.Colors.ON_SURFACE,
                            text_align=ft.TextAlign.RIGHT,
                            rtl=True
                        ),
                        padding=ft.padding.symmetric(horizontal=12, vertical=8),
                        border_radius=6,
                        ink=True,  # Ripple effect
                        on_click=lambda e, city_name=city: self.select_city_from_suggestion(city_name),
                        bgcolor=ft.Colors.TRANSPARENT,
                        border=ft.border.all(1, ft.Colors.TRANSPARENT)
                    )
                    
                    # Add hover effect
                    def on_hover(e, container=suggestion_btn):
                        container.bgcolor = ft.Colors.PRIMARY_CONTAINER if e.data == "true" else ft.Colors.TRANSPARENT
                        container.update()
                    
                    suggestion_btn.on_hover = on_hover
                    self.suggestions_list.controls.append(suggestion_btn)
                
                # Show suggestions dropdown
                self.suggestions_container.visible = True
            else:
                # No matches found
                no_results = ft.Container(
                    content=ft.Text(
                        "לא נמצאו עיירות התואמות לחיפוש",
                        size=12,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                        text_align=ft.TextAlign.RIGHT,
                        rtl=True,
                        italic=True
                    ),
                    padding=ft.padding.all(12)
                )
                self.suggestions_list.controls.append(no_results)
                self.suggestions_container.visible = True
        else:
            # Hide suggestions if search text is empty or too short
            self.suggestions_container.visible = False
        
        if self.page:
            self.page.update()
    
    def select_city_from_suggestion(self, city_name):
        """Handle selection of a city from suggestions."""
        self.city_field.value = city_name
        self.selected_city = city_name
        
        # Update area info
        if city_name in self.city_data:
            info = self.city_data[city_name]
            self.city_area_name = info['area_name']
            self.city_area_code = info['area_code']
            self.show_status(f"נבחרה עיר: {city_name}, אזור: {info['area_name']}, קוד: {info['area_code']}")
        
        # Hide suggestions
        self.suggestions_container.visible = False
        
        self._debounced_save_settings()
        self.update_form_validation()
        
        if self.page:
            self.page.update()

    def create_consultant_section(self):
        """Create consultant data input section."""
        
        def on_consultant_field_change(field_name):
            def handler(e):
                setattr(self, field_name, e.control.value)
                self._debounced_save_settings()
            return handler
        
        # Thermal Consultant fields
        consultant_company_field = ft.TextField(
            label="חברה",
            value=self.consultant_company,
            on_change=on_consultant_field_change('consultant_company'),
            text_align=ft.TextAlign.RIGHT,
            rtl=True,
            border_radius=8,
            filled=True,
            expand=True
        )
        
        consultant_engineer_field = ft.TextField(
            label="מהנדס אחראי",
            value=self.consultant_engineer,
            on_change=on_consultant_field_change('consultant_engineer'),
            text_align=ft.TextAlign.RIGHT,
            rtl=True,
            border_radius=8,
            filled=True,
            expand=True
        )
        
        consultant_phone_field = ft.TextField(
            label="טלפון",
            value=self.consultant_phone,
            on_change=on_consultant_field_change('consultant_phone'),
            text_align=ft.TextAlign.LEFT,
            rtl=False,
            border_radius=8,
            filled=True,
            expand=True
        )
        
        consultant_email_field = ft.TextField(
            label="דוא\"ל",
            value=self.consultant_email,
            on_change=on_consultant_field_change('consultant_email'),
            text_align=ft.TextAlign.LEFT,
            rtl=False,
            border_radius=8,
            filled=True,
            expand=True
        )
        
        # Thermal Tester fields
        tester_company_field = ft.TextField(
            label="חברה",
            value=self.tester_company,
            on_change=on_consultant_field_change('tester_company'),
            text_align=ft.TextAlign.RIGHT,
            rtl=True,
            border_radius=8,
            filled=True,
            expand=True
        )
        
        tester_engineer_field = ft.TextField(
            label="בודק מוסמך",
            value=self.tester_engineer,
            on_change=on_consultant_field_change('tester_engineer'),
            text_align=ft.TextAlign.RIGHT,
            rtl=True,
            border_radius=8,
            filled=True,
            expand=True
        )
        
        tester_phone_field = ft.TextField(
            label="טלפון",
            value=self.tester_phone,
            on_change=on_consultant_field_change('tester_phone'),
            text_align=ft.TextAlign.LEFT,
            rtl=False,
            border_radius=8,
            filled=True,
            expand=True
        )
        
        tester_email_field = ft.TextField(
            label="דוא\"ל",
            value=self.tester_email,
            on_change=on_consultant_field_change('tester_email'),
            text_align=ft.TextAlign.LEFT,
            rtl=False,
            border_radius=8,
            filled=True,
            expand=True
        )
        
        # Create expandable sections
        consultant_section_content = ft.ExpansionTile(
            title=ft.Text("יועץ תרמי מוסמך", weight=ft.FontWeight.BOLD, rtl=True),
            subtitle=ft.Text("פרטי היועץ יוצגו בדוח (אופציונלי)", size=12, color=ft.Colors.GREY_600, rtl=True),
            initially_expanded=False,
            controls=[
                ft.Container(
                    content=ft.Column([
                        ft.Row([consultant_company_field, consultant_engineer_field], spacing=10),
                        ft.Row([consultant_phone_field, consultant_email_field], spacing=10)
                    ], spacing=10),
                    padding=ft.padding.all(10)
                )
            ]
        )
        
        tester_section_content = ft.ExpansionTile(
            title=ft.Text("בודק תרמי מוסמך", weight=ft.FontWeight.BOLD, rtl=True),
            subtitle=ft.Text("פרטי הבודק יוצגו בדוח (אופציונלי)", size=12, color=ft.Colors.GREY_600, rtl=True),
            initially_expanded=False,
            controls=[
                ft.Container(
                    content=ft.Column([
                        ft.Row([tester_company_field, tester_engineer_field], spacing=10),
                        ft.Row([tester_phone_field, tester_email_field], spacing=10)
                    ], spacing=10),
                    padding=ft.padding.all(10)
                )
            ]
        )
        
        # Optional project fields
        project_gush_field = ft.TextField(
            label="גוש (אופציונלי)",
            value=self.project_gush,
            on_change=on_consultant_field_change('project_gush'),
            text_align=ft.TextAlign.RIGHT,
            rtl=True,
            border_radius=8,
            filled=True,
            expand=True
        )
        
        project_helka_field = ft.TextField(
            label="חלקה (אופציונלי)",
            value=self.project_helka,
            on_change=on_consultant_field_change('project_helka'),
            text_align=ft.TextAlign.RIGHT,
            rtl=True,
            border_radius=8,
            filled=True,
            expand=True
        )
        
        # Create project section
        project_section_content = ft.ExpansionTile(
            title=ft.Text("פרטי פרויקט נוספים", weight=ft.FontWeight.BOLD, rtl=True),
            subtitle=ft.Text("פרטים נוספים לדוח (אופציונלי)", size=12, color=ft.Colors.GREY_600, rtl=True),
            initially_expanded=False,
            controls=[
                ft.Container(
                    content=ft.Row([project_gush_field, project_helka_field], spacing=10),
                    padding=ft.padding.all(10)
                )
            ]
        )
        
        return ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Text("נתוני הצוות המקצועי", size=18, weight=ft.FontWeight.BOLD, rtl=True, text_align=ft.TextAlign.RIGHT),
                    consultant_section_content,
                    tester_section_content,
                    project_section_content
                ], spacing=8, scroll=ft.ScrollMode.AUTO),
                padding=15,
                expand=True
            ),
            elevation=2
        )

    def create_iso_dropdown(self):
        """Create modern ISO type dropdown with disabled options."""
        
        def on_iso_change(e):
            selected = e.control.value
            if selected in self.disabled_iso_types:
                # Reset selection and show warning
                e.control.value = ""
                self.selected_iso = ""
                self.show_status(f"'{selected}' עדיין לא זמין. אנא בחר סוג ISO זמין.", "warning")
            else:
                self.selected_iso = selected
                self._debounced_save_settings()
            
            self.update_form_validation()
            if self.page:
                self.page.update()
        
        # Create dropdown options with styling for disabled items
        options = []
        for iso_type in self.iso_types:
            is_disabled = iso_type in self.disabled_iso_types
            options.append(
                ft.dropdown.Option(
                    text=iso_type,
                    disabled=is_disabled
                )
            )
        
        dropdown = ft.Dropdown(
            label="סוג ISO",
            options=options,
            border_radius=12,
            filled=True,
            border_color=ft.Colors.OUTLINE_VARIANT,
            focused_border_color=ft.Colors.PRIMARY,
            label_style=ft.TextStyle(),
            text_style=ft.TextStyle(size=14),
            # alignment=ft.alignment.center_right,  # RTL alignment - deprecated
            on_change=on_iso_change
        )
        
        return dropdown

    def update_form_validation(self):
        """Update form validation and button state."""
        if not self.process_button:
            return
        
        # Check license status first
        license_status = license_manager.get_license_status()
        is_licensed = license_status["status"] == license_manager.STATUS_VALID
        
        logger.info(f"UPDATE_FORM_VALIDATION: License status = {license_status}")
        logger.info(f"UPDATE_FORM_VALIDATION: Is licensed = {is_licensed}")
        
        if not is_licensed:
            # No valid license - show activation message
            logger.info("UPDATE_FORM_VALIDATION: Setting button to activation mode")
            self.process_button.disabled = False  # Keep button clickable
            self.process_button.text = "הפעל רישיון - לחץ על מקש הנעילה"
            self.process_button.icon = ft.Icons.LOCK
            if self.page:
                self.page.update()
            return
            
        # Check if all required fields are filled and valid
        is_valid = all([
            self.input_file and os.path.exists(self.input_file),
            self.output_dir,
            self.energyplus_dir and os.path.isdir(self.energyplus_dir),
            self.selected_city,
            self.selected_iso and self.selected_iso not in self.disabled_iso_types
        ])
        
        logger.info(f"UPDATE_FORM_VALIDATION: Licensed user - form valid = {is_valid}")
        self.process_button.disabled = not is_valid
        
        # Update button text based on queue status
        if not is_valid:
            self.process_button.text = "השלם הגדרות"
            self.process_button.icon = ft.Icons.SETTINGS
        elif len(self.job_queue) >= self.max_queue_size:
            self.process_button.text = "תור מלא"
            self.process_button.icon = ft.Icons.QUEUE
            self.process_button.disabled = True
        else:
            self.process_button.text = f"הוסף לתור ({len(self.job_queue)}/{self.max_queue_size})"
            self.process_button.icon = ft.Icons.ADD_TO_QUEUE
        
        logger.info(f"UPDATE_FORM_VALIDATION: Button text set to: {self.process_button.text}")
        
        if self.page:
            self.page.update()

    def validate_inputs(self):
        """Validate all inputs before processing."""
        validations = [
            (self.input_file, "אנא בחר קובץ IDF קלט."),
            (os.path.exists(self.input_file), f"קובץ IDF לא נמצא: {self.input_file}"),
            (self.energyplus_dir, "אנא בחר תיקיית התקנת EnergyPlus."),
            (os.path.isdir(self.energyplus_dir), "נתיב EnergyPlus אינו תיקייה תקינה."),
            (os.path.exists(os.path.join(self.energyplus_dir, "energyplus.exe")), f"energyplus.exe לא נמצא ב- {self.energyplus_dir}"),
            (os.path.exists(os.path.join(self.energyplus_dir, "Energy+.idd")), f"Energy+.idd לא נמצא ב- {self.energyplus_dir}"),
            (self.output_dir, "אנא בחר תיקיית פלט."),
            (self.selected_city, "אנא בחר עיר."),
            (self.selected_iso, "אנא בחר סוג ISO."),
            (self.selected_iso not in self.disabled_iso_types, f"סוג ה-ISO שנבחר '{self.selected_iso}' עדיין לא זמין.")
        ]
        
        for condition, msg in validations:
            if not condition:
                self.show_status(msg, "error")
                return False
        
        # Create output directory if it doesn't exist
        if not os.path.exists(self.output_dir):
            try:
                os.makedirs(self.output_dir)
                self.show_status(f"נוצרה תיקיית פלט: {self.output_dir}")
            except OSError as e:
                self.show_status(f"לא ניתן ליצור תיקיית פלט: {e}", "error")
                return False
        
        return True

    def check_license_and_usage(self) -> bool:
        """Check license status and usage limits before processing."""
        try:
            # Check current license status
            status = license_manager.get_license_status()
            self.license_status = status
            
            # If valid professional/enterprise license, allow unlimited usage
            if (status["status"] == license_manager.STATUS_VALID and 
                status.get("type") in [license_manager.LICENSE_PROFESSIONAL, license_manager.LICENSE_ENTERPRISE]):
                return True
            
            # For free tier or expired licenses, check daily limits
            return self.check_daily_usage_limit()
            
        except Exception as e:
            logger.error(f"License check error: {e}")
            self.show_status(f"שגיאה בבדיקת רישיון: {e}")
            return False
    
    def check_daily_usage_limit(self) -> bool:
        """Check if user has exceeded daily usage limit for free tier."""
        try:
            # Load usage data
            usage_file = Path(license_manager.app_data_dir) / "daily_usage.json"
            today = datetime.now().strftime("%Y-%m-%d")
            
            usage_data = {}
            if usage_file.exists():
                with open(usage_file, 'r', encoding='utf-8') as f:
                    usage_data = json.load(f)
            
            # Get today's usage
            daily_usage = usage_data.get(today, 0)
            
            # Free tier limit: 3 files per day
            free_tier_limit = 3
            
            if daily_usage >= free_tier_limit:
                self.show_license_limit_dialog()
                return False
            
            # Update usage count
            usage_data[today] = daily_usage + 1
            self.daily_usage_count = usage_data[today]
            
            # Clean old usage data (keep last 30 days)
            cutoff_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            usage_data = {k: v for k, v in usage_data.items() if k >= cutoff_date}
            
            # Save updated usage
            with open(usage_file, 'w', encoding='utf-8') as f:
                json.dump(usage_data, f, indent=2)
            
            # Show remaining usage
            remaining = free_tier_limit - self.daily_usage_count
            if remaining > 0:
                self.show_status(f"נותרו {remaining} עיבודים היום במצב חינמי")
            
            return True
            
        except Exception as e:
            logger.error(f"Usage limit check error: {e}")
            return True  # Allow processing if check fails
    
    def show_license_limit_dialog(self):
        """Show dialog when daily limit is reached."""
        def upgrade_license(e):
            dialog.open = False
            self.page.update()
            self.show_license_dialog()
        
        def close_dialog(e):
            dialog.open = False
            self.page.update()
        
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("הגעת למגבלה היומית", size=20, weight=ft.FontWeight.BOLD, rtl=True, text_align=ft.TextAlign.RIGHT),
            content=ft.Container(
                content=ft.Column([
                    ft.Text(
                        "הגעת למגבלה של 3 קבצים ביום במצב החינמי.",
                        size=16,
                        rtl=True,
                        text_align=ft.TextAlign.RIGHT
                    ),
                    ft.Text(
                        "שדרג לרישיון מקצועי לעיבוד ללא הגבלה ותכונות מתקדמות.",
                        size=14,
                        color=ft.colors.GREY_600,
                        rtl=True,
                        text_align=ft.TextAlign.RIGHT
                    ),
                    ft.Divider(),
                    ft.Text("היתרונות של הרישיון המקצועי:", size=14, weight=ft.FontWeight.BOLD, rtl=True, text_align=ft.TextAlign.RIGHT),
                    ft.Text("• עיבוד ללא הגבלה", size=12, rtl=True, text_align=ft.TextAlign.RIGHT),
                    ft.Text("• כל סוגי הדוחות", size=12, rtl=True, text_align=ft.TextAlign.RIGHT),
                    ft.Text("• ייצוא Excel ו-PDF", size=12, rtl=True, text_align=ft.TextAlign.RIGHT),
                    ft.Text("• תמיכה טכנית מועדפת", size=12, rtl=True, text_align=ft.TextAlign.RIGHT),
                ]),
                width=400,
                height=250
            ),
            actions=[
                ft.TextButton("סגור", on_click=close_dialog),
                ft.ElevatedButton(
                    "שדרג לרישיון מקצועי",
                    icon=ft.icons.UPGRADE,
                    on_click=upgrade_license,
                    style=ft.ButtonStyle(
                        bgcolor=ft.colors.GREEN_600,
                        color=ft.colors.WHITE
                    )
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )
        
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()
    
    def show_license_dialog(self):
        """Show license management dialog."""
        logger.info("=" * 80)
        logger.info("=== SHOW_LICENSE_DIALOG CALLED FROM MAIN UI ===")
        logger.info(f"Page controls before dialog: {len(self.page.controls)}")
        logger.info(f"Page overlay before dialog: {len(self.page.overlay)}")
        
        try:
            if not self.page:
                logger.error("Page is None - cannot show license dialog")
                return
            
            # Log current page state in detail
            for i, control in enumerate(self.page.controls):
                logger.info(f"  Control {i}: {type(control).__name__} visible={getattr(control, 'visible', True)}")
            
            logger.info("Creating LicenseDialog instance")
            # Use safe callback for UI refresh after license activation
            logger.info("Using safe callback for license UI updates")
            self.license_dialog = LicenseDialog(self.page, self.on_license_changed)
            logger.info("Calling show_license_dialog method")
            self.license_dialog.show_license_dialog()
            
            logger.info("License dialog creation completed")
            logger.info(f"Page controls after dialog creation: {len(self.page.controls)}")
            logger.info(f"Page overlay after dialog creation: {len(self.page.overlay)}")
            logger.info("=" * 80)
            
        except Exception as e:
            logger.error(f"Error showing license dialog: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self.show_status(f"שגיאה בהצגת חלון הרישיון: {e}")
    
    def on_license_changed(self):
        """Called when license status changes."""
        try:
            logger.info("=" * 60)
            logger.info("=== MODERN_GUI ON_LICENSE_CHANGED CALLED ===")
            logger.info(f"Page controls count BEFORE: {len(self.page.controls) if self.page and self.page.controls else 0}")
            logger.info(f"Page overlay count BEFORE: {len(self.page.overlay) if self.page and self.page.overlay else 0}")
            
            # Track if page controls exist before processing
            had_controls_before = self.page and self.page.controls and len(self.page.controls) > 0
            logger.info(f"Had controls before: {had_controls_before}")
            
            # Refresh license status (read-only operation)
            logger.info("Refreshing license status...")
            
            # Force a completely fresh check - clear any cache if needed
            if hasattr(license_manager, '_cached_status'):
                delattr(license_manager, '_cached_status')
            
            # Wait a moment to ensure license file is written
            import time
            time.sleep(0.1)
            
            # Force re-read of license file
            old_status = self.license_status
            self.license_status = license_manager.get_license_status()
            logger.info(f"Old license status: {old_status}")
            logger.info(f"New license status: {self.license_status}")
            
            # Also store it in instance for debugging
            self._last_license_check = self.license_status
            logger.info(f"Stored license status in instance: {self._last_license_check}")
            
            # Verify license file exists
            license_file_exists = license_manager.license_file.exists()
            logger.info(f"License file exists: {license_file_exists}")
            if license_file_exists:
                logger.info(f"License file path: {license_manager.license_file}")
                logger.info(f"License file size: {license_manager.license_file.stat().st_size} bytes")
            
            # Update UI elements for new license status
            logger.info("Updating UI elements for new license status")
            self.update_ui_for_license()
            
            # Update button state after license change
            logger.info("Updating form validation after license change")
            self.update_form_validation()
            
            # Force UI update
            logger.info("Forcing page update after license change")
            if self.page:
                self.page.update()
            
            # Directly update button as final step
            logger.info("Final button update check...")
            if self.process_button:
                final_status = license_manager.get_license_status()
                final_licensed = final_status["status"] == license_manager.STATUS_VALID
                logger.info(f"Final button update - licensed: {final_licensed}")
                logger.info(f"Final button update - status: {final_status}")
                
                if final_licensed:
                    # Force button to normal state
                    self.process_button.text = "השלם הגדרות"
                    self.process_button.icon = ft.Icons.SETTINGS
                    logger.info("Button forced to licensed state")
                else:
                    # Keep in activation state
                    self.process_button.text = "הפעל רישיון - לחץ על מקש הנעילה"
                    self.process_button.icon = ft.Icons.LOCK
                    logger.info("Button kept in activation state")
                
                if self.page:
                    self.page.update()
                    logger.info("Final page update completed")
            
            # Refresh license button if it exists
            logger.info("Refreshing license-dependent UI elements")
            if hasattr(self, 'license_button') and self.license_button:
                # Recreate license button with new status
                old_button = self.license_button
                new_button = self.create_license_button()
                
                # Find and replace the button in the UI
                # This is a simple approach - you can make it more sophisticated
                logger.info("Updated license button with new status")
            
            # Only show status if page is stable
            if had_controls_before and self.page and self.page.controls:
                logger.info("Page appears stable - showing status update")
                self.show_status("סטטוס הרישיון עודכן")
            else:
                logger.warning("Page unstable - skipping status update")
            
            logger.info(f"Page controls count AFTER: {len(self.page.controls) if self.page and self.page.controls else 0}")
            logger.info(f"Page overlay count AFTER: {len(self.page.overlay) if self.page and self.page.overlay else 0}")
            
            # Verify page integrity
            if had_controls_before and (not self.page.controls or len(self.page.controls) == 0):
                logger.error("*** BUG DETECTED: PAGE CONTROLS DISAPPEARED IN ON_LICENSE_CHANGED! ***")
                logger.error("This should not happen - the callback should not clear page controls")
            else:
                logger.info("Page integrity maintained")
            
            logger.info("=== MODERN_GUI ON_LICENSE_CHANGED COMPLETED ===")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"License change handling error: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def update_ui_for_license(self):
        """Update UI elements based on current license status."""
        try:
            if not hasattr(self, 'license_status') or not self.license_status:
                return
            
            license_type = self.license_status.get("type", license_manager.LICENSE_FREE)
            is_valid = self.license_status.get("status") == license_manager.STATUS_VALID
            
            # Update status text or badges if needed
            # This can be expanded based on your UI needs
            
        except Exception as e:
            logger.error(f"UI update error: {e}")

    def on_start_processing(self, e):
        """Add job to processing queue."""
        # Check license status first
        license_status = license_manager.get_license_status()
        is_licensed = license_status["status"] == license_manager.STATUS_VALID
        
        if not is_licensed:
            # No valid license - show license dialog
            self.show_license_dialog()
            return
        
        if not self.validate_inputs():
            return
        
        # Check license and usage limits
        if not self.check_license_and_usage():
            return
        
        # Prepare job data
        job_data = {
            'input_file': self.input_file,
            'output_dir': self.output_dir,
            'project_name': os.path.basename(self.input_file).replace('.idf', ''),
            'city': self.selected_city,
            'iso_type': self.selected_iso,
            'consultant_data': {
                'consultant_company': self.consultant_company,
                'consultant_engineer': self.consultant_engineer,
                'consultant_phone': self.consultant_phone,
                'consultant_email': self.consultant_email,
                'tester_company': self.tester_company,
                'tester_engineer': self.tester_engineer,
                'tester_phone': self.tester_phone,
                'tester_email': self.tester_email,
            },
            'project_data': {
                'project_gush': self.project_gush,
                'project_helka': self.project_helka,
            }
        }
        
        # Add job to queue
        success = self.add_job_to_queue(job_data)
        if success:
            self.show_status(f"עבודה נוספה לתור: {os.path.basename(self.input_file)}", "success")
            self.save_settings()
        else:
            self.show_status("לא ניתן להוסיף עבודה לתור", "error")

    def process_files(self):
        """Process files in background thread."""
        try:
            # Generate run ID
            run_id = datetime.now().strftime('%d-%m-%Y-%H-%M-%S')
            reports_dir = os.path.join(self.output_dir, f"reports-{run_id}")
            simulation_dir = os.path.join(reports_dir, "simulation")
            
            os.makedirs(simulation_dir, exist_ok=True)
            self.show_status(f"נוצרו תיקיות פלט עבור ריצה: {run_id}")
            
            # Determine EPW file
            epw_file = self.determine_epw_file()
            if not epw_file:
                self.show_status("קביעת קובץ EPW נכשלה. מבטל.", "error")
                self.reset_gui_state()
                return
            
            # Run EnergyPlus simulation
            simulation_output_csv = self.run_energyplus_simulation(epw_file, simulation_dir)
            if not simulation_output_csv:
                self.show_status("סימולציית EnergyPlus נכשלה או שקבצי הפלט לא נמצאו. הדוחות יופקו בלי נתוני סימולציה.", "warning")
            
            # Initialize ProcessingManager
            self.processing_manager = ProcessingManager(
                status_callback=self.show_status,
                progress_callback=self.update_progress,
                simulation_output_csv=simulation_output_csv
            )
            
            # Set city info
            self.processing_manager.city_info = {
                'city': self.selected_city,
                'area_name': self.city_area_name,
                'area_code': self.city_area_code,
            }
            
            # Set consultant data
            self.processing_manager.consultant_data = {
                'consultant_company': self.consultant_company,
                'consultant_engineer': self.consultant_engineer,
                'consultant_phone': self.consultant_phone,
                'consultant_email': self.consultant_email,
                'tester_company': self.tester_company,
                'tester_engineer': self.tester_engineer,
                'tester_phone': self.tester_phone,
                'tester_email': self.tester_email,
                'project_gush': self.project_gush,
                'project_helka': self.project_helka,
                'iso_type': self.selected_iso
            }
            
            # Process IDF and generate reports
            self.show_status("מתחיל עיבוד IDF ויצירת דוחות...")
            # Start loading animation for reports progress
            self.start_progress_animation("reports")
            
            # Convert Hebrew ISO selection back to English for processing
            english_iso = self.iso_map.get(self.selected_iso, self.selected_iso)
            self.processing_manager.city_info['iso_type'] = english_iso
            
            success = self.processing_manager.process_idf(
                self.input_file,
                os.path.join(self.energyplus_dir, "Energy+.idd"),
                self.output_dir,
                run_id,
                self.energyplus_dir
            )
            
            if success:
                self.show_status("כל הדוחות נוצרו בהצלחה!", "success")
                # Try to open output directory and bring it to front
                try:
                    if os.name == 'nt':  # Windows
                        import subprocess
                        # Use explorer to open folder and bring it to front
                        subprocess.Popen(['explorer', reports_dir])
                    else:
                        # For non-Windows systems, use default file manager
                        os.startfile(reports_dir)
                except Exception as e:
                    logger.warning(f"Could not open output directory: {e}")
            else:
                self.show_status("העיבוד הסתיים עם שגיאות.", "warning")
                
        except Exception as e:
            self.show_status(f"שגיאה קריטית בעיבוד: {e}", "error")
            logger.error(f"Critical error in processing: {e}", exc_info=True)
            capture_exception_with_context(e, error_type="gui_processing", 
                                         input_file=self.input_file, 
                                         output_dir=self.output_dir)
        finally:
            self.reset_gui_state()

    def determine_epw_file(self):
        """Determine the appropriate EPW file based on city and ISO type."""
        if not self.city_area_name or not self.city_area_code:
            self.show_status("שגיאה: חסר שם אזור עיר או קוד לבחירת EPW.", "error")
            return None
        
        # Convert Hebrew ISO back to English for EPW determination
        english_iso = self.iso_map.get(self.selected_iso, self.selected_iso)
        if english_iso == "RESIDNTIAL 2023":
            epw_filename = f"{self.city_area_code}.epw"
        else:
            area_name_map = {"א": "a", "ב": "b", "ג": "c", "ד": "d"}
            latin_letter = area_name_map.get(self.city_area_name)
            if not latin_letter:
                self.show_status(f"שגיאה: לא ניתן למפות שם אזור '{self.city_area_name}' לקובץ EPW.", "error")
                return None
            epw_filename = f"{latin_letter}.epw"
        
        try:
            epw_file_path = get_data_file_path(epw_filename)
            self.show_status(f"משתמש בקובץ מזג אוויר: {epw_file_path}")
            return epw_file_path
        except FileNotFoundError as e:
            self.show_status(f"שגיאה: קובץ מזג אוויר {epw_filename} לא נמצא. {e}", "error")
            return None

    def _inject_output_variables_to_user_idf(self):
        """Directly inject OUTPUT:VARIABLE entries into user's IDF file."""
        try:
            # Read the current IDF file
            with open(self.input_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Add required output variables at the end using exact format specified
            additional_content = """
! Required Output:Variable entries for energy rating
OUTPUT:VARIABLE,
    *,                        !- Key Value
    Zone Ideal Loads Supply Air Total Cooling Energy,    !- Variable Name
    RunPeriod;                !- Reporting Frequency

OUTPUT:VARIABLE,
    *,                        !- Key Value
    Zone Ideal Loads Supply Air Total Heating Energy,    !- Variable Name
    RunPeriod;                !- Reporting Frequency

OUTPUT:VARIABLE,
    *,                        !- Key Value
    Lights Electricity Energy,    !- Variable Name
    RunPeriod;                !- Reporting Frequency
"""
            
            # Write back to the same file
            with open(self.input_file, 'w', encoding='utf-8') as f:
                f.write(content + additional_content)
            
            logger.info(f"Injected 3 OUTPUT:VARIABLE entries directly into IDF: {self.input_file}")
            self.show_status("הוזרקו 3 משתני OUTPUT:VARIABLE לקובץ IDF")
            
        except Exception as e:
            logger.error(f"Failed to inject output variables into IDF: {e}")
            self.show_status(f"שגיאה בהזרקת משתני פלט: {e}", "error")
            raise

    
    def _ensure_idf_output_variables(self, idf_path):
        """Ensure required IDF output variables are present."""
        self.show_status("מוודא משתני פלט נדרשים ב-IDF...")
        try:
            from utils.data_loader import DataLoader
            data_loader = DataLoader(energyplus_path=self.energyplus_dir)  # Create a temporary loader with EnergyPlus path
            # No need to load the full IDF here, just use the utility method
            idd_path = os.path.join(self.energyplus_dir, "Energy+.idd")
            modified = data_loader.ensure_output_variables(idf_path, energyplus_path=self.energyplus_dir)
            if modified:
                self.show_status("משתני פלט IDF הוודאו/עודכנו")
            else:
                self.show_status("משתני פלט IDF כבר קיימים או לא בוצעו שינויים")
            return True  # Assume success if no exception
        except Exception as e:
            self.show_status(f"אזהרה: שגיאה בהבטחת משתני פלט IDF: {e}. דירוג אנרגיה עלול להיפגע", "warning")
            logger.error(f"Error in _ensure_idf_output_variables: {e}", exc_info=True)
            return False  # Indicate failure

    def run_energyplus_simulation(self, epw_file, simulation_dir):
        """Run EnergyPlus simulation using the same logic as original GUI."""
        import os  # Explicit import to avoid scope issues
        self.show_status("מתחיל סימולציית EnergyPlus...")
        
        # Start loading animation for EnergyPlus progress
        self.start_progress_animation("energyplus")
        
        output_csv_path = os.path.join(simulation_dir, "eplustbl.csv")
        simulation_successful = False
        
        # Variables for cleanup
        safe_idf_path = self.input_file
        idf_cleanup = None
        safe_output_dir = simulation_dir
        needs_move_back = False
        
        try:
            # Inject OUTPUT:VARIABLE entries directly into user's IDF file
            self.show_status("מזריק משתני פלט נדרשים ל-IDF לפני סימולציה...")
            self._inject_output_variables_to_user_idf()
            
            if self.energyplus_progress:
                self.energyplus_progress.value = 0.2
                if self.page:
                    self.page.update()

            # Check if paths contain Hebrew/Unicode characters and create safe copies if needed
            if contains_non_ascii(self.input_file):
                self.show_status("נתיב IDF מכיל תווי Unicode/עברית, יוצר עותק ASCII בטוח עבור EnergyPlus...")
                safe_idf_path, idf_cleanup = create_safe_path_for_energyplus(self.input_file)
                self.show_status(f"משתמש בנתיב IDF בטוח: {safe_idf_path}")
            
            if contains_non_ascii(simulation_dir):
                self.show_status("תיקיית הפלט מכילה תווי Unicode/עברית, משתמש בתיקייה זמנית ASCII בטוחה...")
                from utils.path_utils import create_safe_output_dir_for_energyplus
                safe_output_dir, needs_move_back = create_safe_output_dir_for_energyplus(simulation_dir)
                self.show_status(f"משתמש בתיקיית פלט בטוחה: {safe_output_dir}")
                # Update the expected output path
                temp_output_csv_path = os.path.join(safe_output_dir, "eplustbl.csv")
            else:
                temp_output_csv_path = output_csv_path

            if self.energyplus_progress:
                self.energyplus_progress.value = 0.4
                if self.page:
                    self.page.update()

            # Normalize paths for EnergyPlus compatibility
            from utils.path_utils import normalize_path_for_energyplus
            normalized_epw = normalize_path_for_energyplus(epw_file)
            normalized_output_dir = normalize_path_for_energyplus(safe_output_dir)
            normalized_idf = normalize_path_for_energyplus(safe_idf_path)
            
            energyplus_exe = os.path.join(self.energyplus_dir, "energyplus.exe")
            cmd = [energyplus_exe, "-w", normalized_epw, "-r", "-d", normalized_output_dir, normalized_idf]
            self.show_status(f"מריץ פקודת E+ עם נתיבים מנורמלים: {' '.join(cmd[:3])}...")
            
            if self.energyplus_progress:
                self.energyplus_progress.value = 0.6
                if self.page:
                    self.page.update()
            
            import subprocess
            process = subprocess.run(
                cmd, 
                check=True, 
                capture_output=True, 
                text=True, 
                encoding='utf-8', 
                errors='ignore'
            )
            
            if process.stdout: 
                logger.info(f"E+ STDOUT:\n{process.stdout}")
            if process.stderr: 
                logger.warning(f"E+ STDERR:\n{process.stderr}")  # E+ often uses stderr for info

            if self.energyplus_progress:
                self.energyplus_progress.value = 0.9
                if self.page:
                    self.page.update()

            # Check if simulation produced output in the temporary location
            if os.path.exists(temp_output_csv_path):
                # Check if CSV is empty or too small (basic check)
                if os.path.getsize(temp_output_csv_path) > 100:  # Arbitrary small size
                    simulation_successful = True
                    
                    # If we used a temporary directory, move files back to the original location
                    if needs_move_back:
                        self.show_status("מעביר קבצי פלט של סימולציה בחזרה לתיקיית Unicode המקורית...")
                        from utils.path_utils import move_simulation_files_back
                        if move_simulation_files_back(safe_output_dir, simulation_dir):
                            self.show_status("העברת קבצי סימולציה לתיקייה המקורית הושלמה בהצלחה")
                        else:
                            self.show_status("אזהרה: חלו בעיות בהעברת קבצי סימולציה", "warning")
                    
                    # Stop animation and set final progress
                    self.stop_progress_animation()
                    if self.energyplus_progress:
                        self.energyplus_progress.value = 1.0
                        if self.page:
                            self.page.update()
                    
                    self.show_status(f"סימולציית EnergyPlus הצליחה. פלט: {output_csv_path}")
                else:
                    self.show_status(f"אזהרה: קובץ פלט הסימולציה {temp_output_csv_path} קטן מדי או ריק", "warning")
            else:
                self.show_status(f"הסימולציה הסתיימה, אבל קובץ הפלט לא נמצא: {temp_output_csv_path}", "error")
        
        except subprocess.CalledProcessError as e:
            error_detail = e.stderr.strip() if e.stderr else "No stderr output."
            stdout_detail = e.stdout.strip() if e.stdout else "No stdout output."
            logger.error(f"E+ CalledProcessError. RC: {e.returncode}. STDOUT:\n{stdout_detail}\nSTDERR:\n{error_detail}", exc_info=True)
            
            # Try to find a more specific error message
            specific_error = "Unknown simulation error."
            for line in reversed(error_detail.splitlines()):  # Check stderr first
                if "**FATAL**" in line or "**SEVERE**" in line: 
                    specific_error = line.strip()
                    break
            if specific_error == "Unknown simulation error.":  # Then check stdout
                for line in reversed(stdout_detail.splitlines()):
                    if "**FATAL**" in line or "**SEVERE**" in line: 
                        specific_error = line.strip()
                        break
            if specific_error == "Unknown simulation error." and error_detail:  # Fallback
                specific_error = error_detail.splitlines()[-1].strip() if error_detail.splitlines() else "No specific error in stderr."

            self.show_status(f"סימולציית EnergyPlus נכשלה (RC {e.returncode}). שגיאה: {specific_error}", "error")
        
        except FileNotFoundError:
            self.show_status(f"שגיאה: energyplus.exe לא נמצא ב-'{os.path.join(self.energyplus_dir, 'energyplus.exe')}'", "error")
            logger.error(f"FileNotFoundError for energyplus.exe at {os.path.join(self.energyplus_dir, 'energyplus.exe')}")
        except Exception as sim_e:
            self.show_status(f"שגיאה לא צפויה במהלך הסימולציה: {type(sim_e).__name__} - {str(sim_e)}", "error")
            logger.error(f"Unexpected error in run_energyplus_simulation: {sim_e}", exc_info=True)
        finally:
            # Always stop the progress animation
            self.stop_progress_animation()
            
            # Clean up temporary IDF file (Unicode/Hebrew handling)
            if idf_cleanup:
                idf_cleanup()
                self.show_status("ניקוי קובץ IDF זמני")
            
            # Clean up temporary output directory if something went wrong
            if needs_move_back and not simulation_successful and os.path.exists(safe_output_dir):
                try:
                    import shutil
                    shutil.rmtree(safe_output_dir)
                    logger.info(f"Cleaned up temporary output directory: {safe_output_dir}")
                except OSError as e:
                    logger.warning(f"Could not remove temporary output directory {safe_output_dir}: {e}")
        
        return output_csv_path if simulation_successful else None

    def reset_gui_state(self):
        """Reset GUI state after processing."""
        # Stop any running animations
        self.stop_progress_animation()
        
        self.is_processing = False
        if self.process_button:
            self.process_button.disabled = False
            self.process_button.text = "צור דוחות"
        
        if self.energyplus_progress:
            self.energyplus_progress.value = 0
        if self.reports_progress:
            self.reports_progress.value = 0
        
        if self.page:
            self.page.update()

    def build_ui(self, page: ft.Page):
        """Build the modern UI."""
        self.page = page
        page.title = "מחולל דוחות IDF"
        page.theme_mode = ft.ThemeMode.SYSTEM
        page.rtl = True  # Enable RTL layout for the entire page
        
        # Load settings first
        self.load_settings()
        
        # Apply window settings
        logger.info(f"Applying window settings: {self.window_settings}")
        
        # Always set size and position first
        page.window.width = self.window_settings.get('width', 1400)
        page.window.height = self.window_settings.get('height', 1000)
        logger.info(f"Set window size: {page.window.width}x{page.window.height}")
        
        # Set position if saved
        if self.window_settings.get('position_x') is not None:
            page.window.left = self.window_settings.get('position_x')
        if self.window_settings.get('position_y') is not None:
            page.window.top = self.window_settings.get('position_y')
        
        # Set maximized state (explicitly set to False to ensure normal window)
        maximized_setting = self.window_settings.get('maximized', False)
        page.window.maximized = maximized_setting
        logger.info(f"Set window maximized: {maximized_setting}")
        
        # Set minimum window size
        page.window.min_width = 1000
        page.window.min_height = 800
        page.padding = 20
        page.spacing = 20
        
        # Add window event handlers
        page.on_window_event = self.on_window_event
        page.on_close = self.on_page_close
        
        # Set custom application icon
        try:
            # Try to set icon using assets directory (works better with Flet)
            page.window.icon = "logo.ico"
            logger.info("Window icon set using assets: logo.ico")
        except Exception as e:
            # Fallback to absolute path
            try:
                from utils.path_utils import get_data_file_path
                ico_path = get_data_file_path('logo.ico')
                if ico_path and os.path.exists(ico_path):
                    page.window.icon = ico_path
                    logger.info(f"Window icon set using absolute path: {ico_path}")
                else:
                    logger.warning("Could not find logo.ico file")
            except Exception as fallback_e:
                logger.error(f"Error setting window icon: {e}, fallback error: {fallback_e}")
        
        # Set modern theme
        page.theme = ft.Theme(
            color_scheme_seed=ft.Colors.BLUE,
            use_material3=True
        )
        
        # Create header with logo and better centering
        logo_element = None
        try:
            from utils.path_utils import get_data_file_path
            logo_path = get_data_file_path('logo.ico')
            if logo_path and os.path.exists(logo_path):
                logo_element = ft.Image(
                    src=logo_path,
                    width=80,
                    height=80,
                    fit=ft.ImageFit.CONTAIN
                )
            else:
                # Fallback to utils.logo_utils if available
                from utils.logo_utils import get_gui_logo_path
                logo_path = get_gui_logo_path()
                if logo_path and os.path.exists(logo_path):
                    logo_element = ft.Image(
                        src=logo_path,
                        width=80,
                        height=80,
                        fit=ft.ImageFit.CONTAIN
                    )
        except Exception as e:
            logger.warning(f"Could not load logo for header: {e}")
        
        header_content = [
            ft.Container(
                content=ft.Row([
                    logo_element if logo_element else ft.Icon(
                        ft.Icons.ARCHITECTURE, 
                        size=80, 
                        color=ft.Colors.PRIMARY
                    ),
                    ft.Column([
                        ft.Text(
                            "מחולל דוחות IDF",
                            size=36,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.PRIMARY,
                            text_align=ft.TextAlign.CENTER,
                        ),
                        ft.Text(
                            "חבילת ניתוח ודיווח אנרגיה מקצועית למבנים",
                            size=18,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                            text_align=ft.TextAlign.CENTER,
                        )
                    ], 
                    spacing=5,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    expand=True),
                    ft.Column([
                        ft.Row([
                            (logger.info("Creating license button..."), self.create_license_button())[1],
                            (logger.info("Creating update button..."), self.create_update_menu_button())[1],
                        ], spacing=10, alignment=ft.MainAxisAlignment.CENTER),
                        ft.Text(f"v{self.current_version}", size=10, color=ft.Colors.ON_SURFACE_VARIANT)
                    ], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
                ], 
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=20
                ),
                alignment=ft.alignment.center,
                width=float("inf")
            ),
            ft.Divider(height=10, color=ft.Colors.TRANSPARENT)
        ]
        
        header = ft.Container(
            content=ft.Column(
                header_content,
                spacing=8, 
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER
            ),
            padding=ft.padding.symmetric(vertical=30, horizontal=20),
            alignment=ft.alignment.center,
            bgcolor=ft.Colors.SURFACE,
            border_radius=15,
            margin=ft.margin.only(bottom=20)
        )
        
        # Create file selection section
        input_row, self.input_file_field = self.create_file_picker_field(
            "קובץ IDF קלט", 
            "file",
            lambda path: setattr(self, 'input_file', path) or self._debounced_save_settings() or self.update_form_validation()
        )
        
        eplus_row, self.energyplus_dir_field = self.create_file_picker_field(
            "תיקיית EnergyPlus",
            "folder", 
            lambda path: setattr(self, 'energyplus_dir', path) or self._debounced_save_settings() or self.update_form_validation()
        )
        
        output_row, self.output_dir_field = self.create_file_picker_field(
            "תיקיית פלט",
            "folder",
            lambda path: setattr(self, 'output_dir', path) or self._debounced_save_settings() or self.update_form_validation()
        )
        
        # Set initial values
        if self.input_file:
            self.input_file_field.value = self.input_file
        if self.energyplus_dir:
            self.energyplus_dir_field.value = self.energyplus_dir
        if self.output_dir:
            self.output_dir_field.value = self.output_dir
        
        file_section = ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Text("הגדרת קבצים", size=20, weight=ft.FontWeight.BOLD, rtl=True, text_align=ft.TextAlign.RIGHT),
                    input_row,
                    eplus_row,
                    output_row
                ], spacing=15, scroll=ft.ScrollMode.AUTO),
                padding=20,
                expand=True  # Let container expand to fill available space
            ),
            elevation=2
        )
        
        # Create analysis configuration section
        city_autocomplete_container, self.city_field = self.create_city_autocomplete()
        # Note: suggestions_container is already stored in create_city_autocomplete method
        
        if self.selected_city:
            self.city_field.value = self.selected_city
            
        self.iso_dropdown = self.create_iso_dropdown()
        if self.selected_iso:
            self.iso_dropdown.value = self.selected_iso
        
        config_section = ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Text("הגדרת ניתוח", size=20, weight=ft.FontWeight.BOLD, rtl=True, text_align=ft.TextAlign.RIGHT),
                    city_autocomplete_container,
                    self.iso_dropdown,
                    ft.Container(height=50)  # Better spacing
                ], spacing=15, scroll=ft.ScrollMode.AUTO),
                padding=20,
                expand=True
            ),
            elevation=2
        )
        
        # Create progress section
        self.energyplus_progress = ft.ProgressBar(
            width=400,
            height=12,
            border_radius=8,
            value=0,
            bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.PRIMARY),
            color=ft.Colors.PRIMARY
        )
        
        self.reports_progress = ft.ProgressBar(
            width=400,
            height=12,
            border_radius=8,
            value=0,
            bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.PRIMARY),
            color=ft.Colors.PRIMARY
        )
        
        progress_section = ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Text("סטטוס עיבוד", size=20, weight=ft.FontWeight.BOLD, rtl=True, text_align=ft.TextAlign.RIGHT),
                    ft.Column([
                        ft.Text("סימולציית EnergyPlus", size=14, weight=ft.FontWeight.W_500, rtl=True, text_align=ft.TextAlign.RIGHT),
                        self.energyplus_progress
                    ], spacing=5),
                    ft.Column([
                        ft.Text("עיבוד IDF ודוחות", size=14, weight=ft.FontWeight.W_500, rtl=True, text_align=ft.TextAlign.RIGHT),
                        self.reports_progress
                    ], spacing=5),
                    ft.Container(height=20)  # Spacing
                ], spacing=15, scroll=ft.ScrollMode.AUTO),
                padding=20,
                expand=True
            ),
            elevation=2
        )
        
        # Create queue section
        self.queue_container = ft.Container(
            content=ft.Column([
                # Queue items will be added here by update_queue_display()
            ], spacing=8, scroll=ft.ScrollMode.AUTO),
            padding=20
        )
        
        queue_section = ft.Card(
            content=ft.Container(
                content=ft.Column([
                    # Queue controls
                    ft.Row([
                        ft.Row([
                            ft.IconButton(
                                icon=ft.Icons.CLEAR_ALL,
                                tooltip="נקה עבודות מושלמות",
                                icon_color=ft.Colors.ORANGE,
                                on_click=lambda e: self.clear_completed_jobs()
                            ),
                            ft.IconButton(
                                icon=ft.Icons.STOP,
                                tooltip="עצור עיבוד תור",
                                icon_color=ft.Colors.RED,
                                on_click=lambda e: self.stop_queue_processing_func()
                            )
                        ])
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    
                    # Queue display container (scrollable)
                    ft.Container(
                        content=self.queue_container,
                        expand=True
                    )
                ], spacing=10, scroll=ft.ScrollMode.AUTO),
                padding=15,
                expand=True
            ),
            elevation=2
        )
        
        # Create status section
        self.status_text = ft.Column(
            scroll=ft.ScrollMode.AUTO,
            spacing=2,
            expand=True  # Allow status text to expand
        )
        
        status_section = ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Text("יומן פעילות", size=20, weight=ft.FontWeight.BOLD, rtl=True, text_align=ft.TextAlign.RIGHT),
                    ft.Container(
                        content=self.status_text,
                        border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                        border_radius=8,
                        padding=10,
                        expand=True  # Let status container expand
                    )
                ], spacing=15, scroll=ft.ScrollMode.AUTO),
                padding=20,
                expand=True
            ),
            elevation=2
        )
        
        # Create action button with improved styling
        self.process_button = ft.ElevatedButton(
            "צור דוחות",
            icon=ft.Icons.ROCKET_LAUNCH,
            height=60,
            width=300,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.PRIMARY,
                color=ft.Colors.ON_PRIMARY,
                shape=ft.RoundedRectangleBorder(radius=15),
                text_style=ft.TextStyle(size=18, weight=ft.FontWeight.BOLD),
                elevation=4,
                shadow_color=ft.Colors.PRIMARY_CONTAINER,
                padding=ft.padding.symmetric(horizontal=30, vertical=15)
            ),
            on_click=self.on_start_processing
        )
        
        # Create a centered button section
        button_section = ft.Container(
            content=ft.Card(
                content=ft.Container(
                    content=ft.Column([
                        ft.Container(
                            content=self.process_button,
                            alignment=ft.alignment.center
                        ),
                    ], spacing=15, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=25,
                    height=150
                ),
                elevation=3
            ),
            alignment=ft.alignment.center,
            margin=ft.margin.symmetric(vertical=10)
        )
        
        # Create consultant data section
        consultant_section = self.create_consultant_section()
        
        # 2x3 Grid layout - Equal sized cards
        card_height = 400  # Fixed height for all cards
        card_spacing = 15
        
        # Top row: 3 cards
        top_row = ft.Row([
            ft.Container(content=file_section, expand=True, height=card_height),
            ft.Container(content=config_section, expand=True, height=card_height),
            ft.Container(content=consultant_section, expand=True, height=card_height)
        ], spacing=card_spacing, expand=True)
        
        # Bottom row: 3 cards  
        bottom_row = ft.Row([
            ft.Container(content=progress_section, expand=True, height=card_height),
            ft.Container(content=status_section, expand=True, height=card_height),
            ft.Container(content=queue_section, expand=True, height=card_height)
        ], spacing=card_spacing, expand=True)
        
        main_content = ft.Container(
            content=ft.Column([
                top_row,
                bottom_row
            ], spacing=card_spacing, expand=True),
            expand=True
        )
        
        # Add everything to page with scrollable main area
        page.add(
            header,
            ft.Container(
                content=main_content,
                expand=True
            ),
            button_section
        )
        
        # Initial validation and welcome message
        self.update_form_validation()
        self.show_status(f"ברוכים הבאים! גרסה {self.current_version} - הגדירו את כל השדות כדי להתחיל בעיבוד.")
        
        # Initialize queue display
        self.update_queue_display()
        
        # Check for updates automatically if enabled
        if self.update_manager.should_check_for_updates():
            self.check_for_updates_background()
        
        # Save initial window state
        self.save_settings()

    def check_for_updates_background(self):
        """Check for updates in background."""
        def check_worker():
            try:
                update_info = self.update_manager.check_for_updates()
                if update_info:
                    # Update available - show notification dialog
                    self.show_update_dialog(update_info)
            except Exception as e:
                logger.error(f"Error checking for updates: {e}")
        
        threading.Thread(target=check_worker, daemon=True).start()
    
    def check_for_updates_manual(self):
        """Manually check for updates (force check)."""
        def check_worker():
            try:
                self.show_status("מתחבר לשרת עדכונים...", "info")
                update_info = self.update_manager.check_for_updates(force=True)
                
                if update_info:
                    new_version = update_info.get("version", "")
                    self.show_status(f"נמצא עדכון זמין לגרסה {new_version}!", "success")
                    self.show_update_dialog(update_info)
                else:
                    self.show_status("האפליקציה מעודכנת לגרסה האחרונה", "success")
            except Exception as e:
                logger.error(f"Error checking for updates: {e}")
                self.show_status(f"שגיאה בבדיקת עדכונים: {e}", "error")
        
        threading.Thread(target=check_worker, daemon=True).start()
    
    def show_update_dialog(self, update_info):
        """Show update available dialog."""
        if not self.page:
            return
        
        new_version = update_info.get("version", "")
        release_notes = update_info.get("release_notes", "אין מידע זמין")
        
        # Create update dialog content
        def close_dialog(e):
            if self.update_dialog:
                self.update_dialog.open = False
                self.page.update()
        
        def install_update(e):
            close_dialog(e)
            self.install_update(update_info)
        
        def remind_later(e):
            close_dialog(e)
            self.show_status("הזכרו לי מאוחר יותר על העדכון", "info")
        
        # Truncate release notes if too long
        if len(release_notes) > 300:
            release_notes = release_notes[:300] + "..."
        
        self.update_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.SYSTEM_UPDATE, size=28, color=ft.Colors.BLUE_600),
                    ft.Text(f"עדכון זמין - גרסה {new_version}", size=22, weight=ft.FontWeight.BOLD, rtl=True, text_align=ft.TextAlign.RIGHT),
                ], spacing=10, alignment=ft.MainAxisAlignment.CENTER),
                padding=ft.padding.only(bottom=15)
            ),
            content=ft.Container(
                content=ft.Card(
                    content=ft.Container(
                        content=ft.Column([
                            ft.Container(
                                content=ft.Row([
                                    ft.Icon(ft.Icons.INFO_OUTLINE, size=18, color=ft.Colors.BLUE_600),
                                    ft.Text("פרטי עדכון", size=16, weight=ft.FontWeight.BOLD, rtl=True, text_align=ft.TextAlign.RIGHT),
                                ], spacing=8),
                                margin=ft.margin.only(bottom=10)
                            ),
                            ft.Container(
                                content=ft.Column([
                                    ft.Text(
                                        f"גרסה נוכחית: {self.current_version}",
                                        text_align=ft.TextAlign.RIGHT,
                                        rtl=True,
                                        size=14,
                                        color=ft.Colors.GREY_700
                                    ),
                                    ft.Text(
                                        f"גרסה חדשה: {new_version}",
                                        text_align=ft.TextAlign.RIGHT,
                                        rtl=True,
                                        weight=ft.FontWeight.BOLD,
                                        size=14,
                                        color=ft.Colors.GREEN_600
                                    ),
                                ], spacing=5),
                                margin=ft.margin.only(bottom=15)
                            ),
                            ft.Container(
                                content=ft.Text("מה חדש:", weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.RIGHT, rtl=True, size=14),
                                margin=ft.margin.only(bottom=8)
                            ),
                            ft.Container(
                                content=ft.Text(
                                    release_notes if release_notes.strip() else "אין מידע זמין על השינויים",
                                    text_align=ft.TextAlign.RIGHT,
                                    rtl=True,
                                    size=12,
                                    color=ft.Colors.GREY_700
                                ),
                                bgcolor=ft.Colors.GREY_50,
                                padding=12,
                                border_radius=8,
                                height=90,
                                border=ft.border.all(1, ft.Colors.GREY_200)
                            )
                        ], spacing=5),
                        padding=20,
                        border_radius=12
                    ),
                    elevation=3,
                    surface_tint_color=ft.Colors.BLUE_50
                ),
                width=500,
                height=250
            ),
            actions=[
                ft.Container(
                    content=ft.Row([
                        ft.ElevatedButton(
                            "התקן עכשיו",
                            icon=ft.Icons.DOWNLOAD,
                            on_click=install_update,
                            style=ft.ButtonStyle(
                                bgcolor=ft.Colors.GREEN_600,
                                color=ft.Colors.WHITE,
                                elevation=2,
                                padding=ft.padding.symmetric(horizontal=20, vertical=10),
                                shape=ft.RoundedRectangleBorder(radius=8)
                            ),
                            height=40
                        ),
                        ft.ElevatedButton(
                            "הזכר מאוחר יותר",
                            icon=ft.Icons.SCHEDULE,
                            on_click=remind_later,
                            style=ft.ButtonStyle(
                                bgcolor=ft.Colors.ORANGE_600,
                                color=ft.Colors.WHITE,
                                elevation=2,
                                padding=ft.padding.symmetric(horizontal=20, vertical=10),
                                shape=ft.RoundedRectangleBorder(radius=8)
                            ),
                            height=40
                        ),
                        ft.ElevatedButton(
                            "סגור",
                            icon=ft.Icons.CLOSE,
                            on_click=close_dialog,
                            style=ft.ButtonStyle(
                                bgcolor=ft.Colors.GREY_600,
                                color=ft.Colors.WHITE,
                                elevation=2,
                                padding=ft.padding.symmetric(horizontal=20, vertical=10),
                                shape=ft.RoundedRectangleBorder(radius=8)
                            ),
                            height=40
                        )
                    ], alignment=ft.MainAxisAlignment.SPACE_EVENLY),
                    padding=ft.padding.all(10)
                )
            ],
            actions_alignment=ft.MainAxisAlignment.CENTER,
            content_padding=ft.padding.all(20),
            title_padding=ft.padding.all(20),
        )
        
        self.page.overlay.append(self.update_dialog)
        self.update_dialog.open = True
        self.page.update()
    
    def install_update(self, update_info):
        """Install the available update."""
        def install_worker():
            try:
                self.show_status("מתחיל התקנת עדכון...", "info")
                
                def restart_app():
                    """Callback for when restart is needed."""
                    self.show_status("העדכון הושלם! מאתחל את האפליקציה...", "success")
                    # Give user time to see the message
                    threading.Timer(3.0, lambda: self.update_manager._restart_application()).start()
                
                success = self.update_manager.download_and_install_update(
                    update_info, 
                    restart_callback=restart_app
                )
                
                if not success:
                    self.show_status("התקנת העדכון נכשלה", "error")
            
            except Exception as e:
                logger.error(f"Error installing update: {e}")
                self.show_status(f"שגיאה בהתקנת עדכון: {e}", "error")
        
        threading.Thread(target=install_worker, daemon=True).start()
    
    def create_license_button(self):
        """Create license button for header."""
        # Get current license status for button styling
        try:
            status = license_manager.get_license_status()
            license_type = status.get("type", license_manager.LICENSE_FREE)
            is_valid = status.get("status") == license_manager.STATUS_VALID
            
            if is_valid and license_type != license_manager.LICENSE_FREE:
                # Valid paid license
                # Translate license type to Hebrew
                license_type_map = {
                    "professional": "מקצועי",
                    "enterprise": "ארגוני",
                    "free": "חינמי"
                }
                license_type_hebrew = license_type_map.get(license_type, license_type)
                
                icon = ft.Icons.VPN_KEY
                color = ft.Colors.GREEN_600
                tooltip = f"רישיון {license_type_hebrew} פעיל"
            else:
                # Free tier or expired
                icon = ft.Icons.VPN_KEY_OFF
                color = ft.Colors.ORANGE_600
                tooltip = "מצב חינמי - לחץ לשדרוג"
        except:
            icon = ft.Icons.VPN_KEY_OFF
            color = ft.Colors.GREY_600
            tooltip = "ניהול רישיון"
        
        def license_button_clicked(e):
            logger.info("=" * 80)
            logger.info("=== LICENSE BUTTON CLICKED FROM MAIN UI ===")
            logger.info(f"Event: {e}")
            logger.info(f"Page: {self.page}")
            logger.info(f"Page controls count: {len(self.page.controls) if self.page and self.page.controls else 0}")
            logger.info(f"Page overlay count: {len(self.page.overlay) if self.page and self.page.overlay else 0}")
            logger.info(f"Button: {e.control if hasattr(e, 'control') else 'No control'}")
            logger.info("=" * 80)
            
            # Show immediate feedback
            self.show_status("פותח חלון ניהול רישיונות...", "info")
            
            try:
                # Show the license dialog
                logger.info("Calling show_license_dialog from main UI...")
                self.show_license_dialog()
                logger.info("show_license_dialog from main UI completed")
                self.show_status("חלון רישיונות נפתח", "success")
                self.show_snackbar("חלון ניהול רישיונות נפתח")
            except Exception as ex:
                logger.error(f"Error opening license dialog: {ex}")
                import traceback
                logger.error(traceback.format_exc())
                self.show_status(f"שגיאה בפתיחת חלון רישיונות: {ex}", "error")
                self.show_snackbar(f"שגיאה בפתיחת חלון רישיונות")
        
        button = ft.IconButton(
            icon=icon,
            icon_color=color,
            tooltip=tooltip,
            on_click=license_button_clicked
        )
        logger.info(f"License button created: {button}")
        return button

    def create_update_menu_button(self):
        """Create update menu button for header."""
        def show_update_menu(e):
            logger.info("Update button clicked - attempting to show menu")
            
            # Show immediate feedback
            self.show_status("פותח תפריט עדכונים...", "info")
            
            try:
                if not self.page:
                    logger.error("Page is None - cannot show update menu")
                    self.show_status("שגיאה: לא ניתן לפתוח תפריט עדכונים", "error")
                    return
                
                # Create popup menu for update options
                def check_updates(e):
                    logger.info("Check updates clicked")
                    self.show_status("מתחיל בדיקת עדכונים...", "info")
                    
                    # Close the menu dialog first
                    menu_dialog.open = False
                    self.page.update()
                    
                    self.check_for_updates_manual()
                
                def toggle_auto_updates(e):
                    settings = self.update_manager.get_update_settings()
                    settings["auto_check"] = not settings["auto_check"]
                    self.update_manager.update_settings(settings)
                    status = "מופעל" if settings["auto_check"] else "מבוטל"
                    self.show_status(f"בדיקת עדכונים אוטומטית {status}")
                
                def configure_github(e):
                    self.show_github_config_dialog()
                
                # Show simple dialog with update options
                def close_menu(e):
                    menu_dialog.open = False
                    self.page.update()
                
                settings = self.update_manager.get_update_settings()
                auto_check_text = "בטל בדיקה אוטומטית" if settings["auto_check"] else "הפעל בדיקה אוטומטית"
                
                menu_dialog = ft.AlertDialog(
                    modal=True,
                    title=ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.SETTINGS, size=28, color=ft.Colors.BLUE_600),
                            ft.Text("הגדרות עדכונים", size=22, weight=ft.FontWeight.BOLD, rtl=True, text_align=ft.TextAlign.RIGHT),
                        ], spacing=10, alignment=ft.MainAxisAlignment.CENTER),
                        padding=ft.padding.only(bottom=15)
                    ),
                    content=ft.Container(
                        content=ft.Card(
                            content=ft.Container(
                                content=ft.Column([
                                    ft.Container(
                                        content=ft.ElevatedButton(
                                            "בדוק עדכונים עכשיו",
                                            icon=ft.Icons.REFRESH,
                                            on_click=lambda e: (check_updates(e), close_menu(e)),
                                            style=ft.ButtonStyle(
                                                bgcolor=ft.Colors.BLUE_600,
                                                color=ft.Colors.WHITE,
                                                elevation=2,
                                                padding=ft.padding.symmetric(horizontal=20, vertical=12),
                                                shape=ft.RoundedRectangleBorder(radius=8)
                                            ),
                                            height=45
                                        ),
                                        width=220,
                                        alignment=ft.alignment.center
                                    ),
                                    ft.Container(
                                        content=ft.ElevatedButton(
                                            auto_check_text,
                                            icon=ft.Icons.AUTORENEW if settings["auto_check"] else ft.Icons.PAUSE_CIRCLE,
                                            on_click=lambda e: (toggle_auto_updates(e), close_menu(e)),
                                            style=ft.ButtonStyle(
                                                bgcolor=ft.Colors.GREEN_600 if settings["auto_check"] else ft.Colors.ORANGE_600,
                                                color=ft.Colors.WHITE,
                                                elevation=2,
                                                padding=ft.padding.symmetric(horizontal=20, vertical=12),
                                                shape=ft.RoundedRectangleBorder(radius=8)
                                            ),
                                            height=45
                                        ),
                                        width=220,
                                        alignment=ft.alignment.center
                                    ),
                                    ft.Container(
                                        content=ft.Text(
                                            f"גרסה נוכחית: {self.current_version}", 
                                            text_align=ft.TextAlign.CENTER,
                                            size=13,
                                            color=ft.Colors.GREY_700,
                                            weight=ft.FontWeight.W_500
                                        ),
                                        padding=ft.padding.all(10),
                                        bgcolor=ft.Colors.GREY_50,
                                        border_radius=8,
                                        margin=ft.margin.only(top=10)
                                    )
                                ], spacing=15, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                                padding=20,
                                border_radius=12
                            ),
                            elevation=3,
                            surface_tint_color=ft.Colors.BLUE_50
                        ),
                        width=280,
                        height=200
                    ),
                    actions=[
                        ft.Container(
                            content=ft.ElevatedButton(
                                "סגור",
                                icon=ft.Icons.CLOSE,
                                on_click=close_menu,
                                style=ft.ButtonStyle(
                                    bgcolor=ft.Colors.GREY_600,
                                    color=ft.Colors.WHITE,
                                    elevation=2,
                                    padding=ft.padding.symmetric(horizontal=20, vertical=10),
                                    shape=ft.RoundedRectangleBorder(radius=8)
                                ),
                                height=40
                            ),
                            padding=ft.padding.all(10)
                        )
                    ],
                    actions_alignment=ft.MainAxisAlignment.CENTER,
                    content_padding=ft.padding.all(20),
                    title_padding=ft.padding.all(20),
                )
                
                # Close any existing dialog first using overlay
                for control in self.page.overlay[:]:
                    if isinstance(control, ft.AlertDialog):
                        control.open = False
                        self.page.overlay.remove(control)
                
                # Add dialog to overlay
                self.page.overlay.append(menu_dialog)
                menu_dialog.open = True
                self.page.update()
                logger.info("Update menu dialog should now be visible")
                self.show_status("תפריט עדכונים נפתח", "success")
                self.show_snackbar("תפריט עדכונים נפתח")
            
            except Exception as e:
                logger.error(f"Error showing update menu: {e}")
                import traceback
                logger.error(traceback.format_exc())
                if hasattr(self, 'show_status'):
                    self.show_status(f"שגיאה בהצגת תפריט עדכונים: {e}")
        
        def update_button_clicked(e):
            logger.info(f"=== UPDATE BUTTON CLICKED ===")
            logger.info(f"Event: {e}")
            logger.info(f"Page: {self.page}")
            show_update_menu(e)
        
        button = ft.IconButton(
            icon=ft.Icons.SYSTEM_UPDATE,
            tooltip="הגדרות עדכונים",
            on_click=update_button_clicked,
            icon_color=ft.Colors.PRIMARY
        )
        logger.info(f"Update button created: {button}")
        return button
    
    def _close_test_dialog(self):
        """Close test dialog."""
        if self.page:
            # Close any AlertDialog in overlay
            for control in self.page.overlay[:]:
                if isinstance(control, ft.AlertDialog):
                    control.open = False
                    self.page.overlay.remove(control)
            self.page.update()
            logger.info("Test dialog closed")
    
    def show_github_config_dialog(self):
        """Show GitHub token configuration dialog."""
        if not self.page:
            return
        
        # Get current token status (but don't show the actual token)
        current_token = self.update_manager._get_github_token()
        has_token = bool(current_token)
        
        token_field = ft.TextField(
            label="GitHub Personal Access Token",
            password=True,
            hint_text="ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
            expand=True,
            border_radius=8
        )
        
        def save_token(e):
            token = token_field.value.strip()
            if token:
                self.update_manager.set_github_token(token)
                self.show_status("GitHub token saved successfully", "success")
            else:
                self.show_status("Please enter a valid token", "warning")
            config_dialog.open = False
            self.page.update()
        
        def remove_token(e):
            self.update_manager.set_github_token(None)
            self.show_status("GitHub token removed", "info")
            config_dialog.open = False
            self.page.update()
        
        def close_config(e):
            config_dialog.open = False
            self.page.update()
        
        def open_github_help(e):
            import webbrowser
            webbrowser.open("https://github.com/settings/tokens/new")
        
        config_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("הגדר GitHub Token לגישה לרפוזיטורי פרטי", text_align=ft.TextAlign.RIGHT, rtl=True),
            content=ft.Container(
                content=ft.Column([
                    ft.Text(
                        f"סטטוס נוכחי: {'מוגדר' if has_token else 'לא מוגדר'}",
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.GREEN if has_token else ft.Colors.RED,
                        text_align=ft.TextAlign.RIGHT,
                        rtl=True
                    ),
                    ft.Divider(),
                    ft.Text(
                        "כדי לגשת לרפוזיטורי פרטי, יש צורך ב-GitHub Personal Access Token:",
                        text_align=ft.TextAlign.RIGHT,
                        rtl=True,
                        size=12
                    ),
                    ft.Text(
                        "1. לך ל-GitHub Settings > Developer settings > Personal access tokens",
                        text_align=ft.TextAlign.RIGHT,
                        rtl=True,
                        size=11
                    ),
                    ft.Text(
                        "2. צור Token חדש עם הרשאת 'repo' (לרפוזיטורי פרטי)",
                        text_align=ft.TextAlign.RIGHT,
                        rtl=True,
                        size=11
                    ),
                    ft.Text(
                        "3. העתק את ה-Token והכנס אותו כאן:",
                        text_align=ft.TextAlign.RIGHT,
                        rtl=True,
                        size=11
                    ),
                    token_field,
                    ft.Row([
                        ft.TextButton(
                            "פתח GitHub Settings",
                            icon=ft.Icons.OPEN_IN_NEW,
                            on_click=open_github_help
                        )
                    ], alignment=ft.MainAxisAlignment.CENTER)
                ], spacing=10, tight=True),
                width=500,
                height=350
            ),
            actions=[
                ft.Row([
                    ft.ElevatedButton("שמור Token", on_click=save_token, icon=ft.Icons.SAVE),
                    ft.TextButton("הסר Token", on_click=remove_token, style=ft.ButtonStyle(color=ft.Colors.RED)) if has_token else None,
                    ft.TextButton("סגור", on_click=close_config)
                ], alignment=ft.MainAxisAlignment.END, rtl=True)
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )
        
        # Filter out None values from actions
        config_dialog.actions[0].controls = [btn for btn in config_dialog.actions[0].controls if btn is not None]
        
        self.page.overlay.append(config_dialog)
        config_dialog.open = True
        self.page.update()

def main(page: ft.Page):
    logger.info("=== MAIN FUNCTION STARTED ===")
    logger.info(f"Page object: {page}")
    
    app = ModernIDFProcessorGUI()
    logger.info("ModernIDFProcessorGUI instance created")
    
    def on_license_checked():
        """Called after license check is complete."""
        logger.info("on_license_checked callback called - building UI")
        app.build_ui(page)
    
    # Load UI directly - license check will be handled by UI elements
    logger.info("Loading UI directly - license check handled by UI")
    on_license_checked()

if __name__ == "__main__":
    import sys
    import tempfile
    
    # Windows-only program check
    if sys.platform != "win32":
        print("This program is designed for Windows only.")
        sys.exit(1)
    
    # Single instance protection for Windows
    lock_file = os.path.join(tempfile.gettempdir(), "idf_reader.lock")
    
    try:
        # Try to acquire lock
        lock = open(lock_file, 'w')
        import msvcrt
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except IOError:
            print("Another instance is already running")
            sys.exit(1)
        
        # Start the app
        ft.app(target=main, view=ft.AppView.FLET_APP_HIDDEN, assets_dir="data")
        
    except Exception as e:
        logger.error(f"Failed to start app: {e}")
        # Simple fallback without single instance check
        ft.app(target=main, assets_dir="data")
    finally:
        try:
            lock.close()
            os.unlink(lock_file)
        except:
            pass