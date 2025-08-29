"""
Main application entry point for the IDF Reader.
"""
import sys
import flet as ft
from utils.sentry_config import initialize_sentry, capture_exception_with_context, add_breadcrumb
from utils.logging_config import get_logger
from app.cli import run_cli
from modern_gui import ModernIDFProcessorGUI

logger = get_logger(__name__)


class GuiApplication:
    """GUI application wrapper."""
    
    def __init__(self):
        """Initialize GUI application."""
        pass
    
    def run(self) -> None:
        """Run the GUI application."""
        logger.info("Starting GUI mode...")
        
        try:
            def main(page: ft.Page):
                from utils.license_dialog import show_startup_license_check
                
                app = ModernIDFProcessorGUI()
                
                def on_license_checked():
                    """Called after license check is complete."""
                    page.controls.clear()
                    page.overlay.clear()
                    page.update()
                    
                    app.build_ui(page)
                    page.update()
                
                # Build UI directly - license managed through license button
                on_license_checked()
            
            ft.app(
                target=main, 
                view=ft.AppView.FLET_APP, 
                assets_dir="data",
                web_renderer=ft.WebRenderer.HTML
            )
            
        except ImportError as import_err:
            err_msg = str(import_err).lower()
            if 'flet' in err_msg:
                logger.error("Flet library is required for GUI mode")
                print("Error: Flet library is required for GUI mode. Install with: pip install flet")
                sys.exit(1)
            elif 'reportlab' in err_msg:
                logger.error("ReportLab library is required")
                print("Error: 'reportlab' library is required. Install with: pip install reportlab")
                sys.exit(1)
            else:
                logger.error(f"Import error in GUI: {import_err}")
                print(f"An unexpected import error occurred while starting GUI: {import_err}")
                sys.exit(1)
        except Exception as e:
            logger.error(f"Error starting GUI: {e}", exc_info=True)
            print(f"An unexpected error occurred while starting GUI: {e}")
            sys.exit(1)


def main():
    """Main entry point for the application."""
    # Initialize Sentry for error monitoring
    sentry_initialized = initialize_sentry()
    if sentry_initialized:
        add_breadcrumb("Application started", category="app", level="info")
    
    try:
        if len(sys.argv) > 1:
            add_breadcrumb("Starting CLI mode", category="app", level="info")
            run_cli()
        else:
            add_breadcrumb("Starting GUI mode", category="app", level="info")
            gui_app = GuiApplication()
            gui_app.run()
            
    except Exception as e:
        logger.error(f"Unhandled exception in main: {e}", exc_info=True)
        if sentry_initialized:
            capture_exception_with_context(e, mode="main_app", args=str(sys.argv))
        raise


if __name__ == "__main__":
    main()