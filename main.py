from utils.logging_config import get_logger

logger = get_logger(__name__)
import argparse
import sys
import os
import time
from colorama import Fore, init
from processing_manager import ProcessingManager
import flet as ft
from modern_gui import ModernIDFProcessorGUI

init(autoreset=True)

def ensure_directory_exists(file_path: str) -> None:
    """
    Ensure the directory for the given file path exists.
    Create it if it doesn't exist.

    Args:
        file_path: Path to the file.
    """
    directory = os.path.dirname(file_path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory)

def cli_status_update(message: str) -> None:
    """
    Prints status messages to the console with appropriate color coding.

    Args:
        message: The message string to print.
    """
    if "error" in message.lower() or "failed" in message.lower():
        print(Fore.RED + message)
    elif "success" in message.lower() or "completed" in message.lower():
        print(Fore.GREEN + message)
    elif "warning" in message.lower():
        print(Fore.YELLOW + message)
    else:
        print(Fore.WHITE + message)

def cli_progress_update(value: float) -> None:
    """
    Prints a simple progress bar to the console.

    Args:
        value: Progress value (0.0 to 1.0), where 1.0 is 100%.
    """
    bar_length = 40
    filled_length = int(round(bar_length * value))
    bar = '█' * filled_length + '-' * (bar_length - filled_length)

    if value >= 1.0:
        print(f"\r{bar} 100% Complete", end='\n')
    else:
        print(f"\r{bar} {value * 100:.2f}% Complete", end='')

def _parse_arguments() -> argparse.Namespace:
    """
    Parses command-line arguments for the IDF processor.

    Returns:
        An argparse.Namespace object containing the parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description="Parse an EnergyPlus IDF file and generate reports using ProcessingManager."
    )
    parser.add_argument(
        "idf_file",
        help="Path to the input IDF file."
    )
    parser.add_argument(
        "--idd",
        required=True,
        help="Path to the Energy+.idd file (required)."
    )
    parser.add_argument(
        "-o", "--output",
        default="output",
        help="Path to the output directory for reports (default: 'output')."
    )
    return parser.parse_args()

def _handle_cli_error(message: str, exit_code: int = 1) -> None:
    """
    Handles CLI error reporting and exits the program.

    Args:
        message: The error message to display.
        exit_code: The exit code for the program.
    """
    cli_status_update(message)
    sys.exit(exit_code)

def run_cli() -> None:
    """
    Runs the command-line interface for processing IDF files.
    """
    args = _parse_arguments()

    idf_file_path = args.idf_file
    idd_file_path = args.idd
    output_dir_path = args.output

    ensure_directory_exists(os.path.join(output_dir_path, "dummy.txt"))

    cli_status_update(f"Starting processing for IDF: {idf_file_path}")
    cli_status_update(f"Using IDD: {idd_file_path}")
    cli_status_update(f"Output directory: {output_dir_path}")

    start_time = time.time()

    try:
        processor = ProcessingManager(
            status_callback=cli_status_update,
            progress_callback=cli_progress_update
        )

        success = processor.process_idf(
            input_file=idf_file_path,
            idd_path=idd_file_path,
            output_dir=output_dir_path
        )

        total_time = time.time() - start_time

        if success:
            cli_status_update(f"Processing completed successfully in {total_time:.2f}s")
        else:
            cli_status_update(f"Processing failed or was cancelled after {total_time:.2f}s")

    except FileNotFoundError as e:
        _handle_cli_error(f"Error: File not found - {str(e)}")
    except ImportError as import_err:
        err_msg = str(import_err).lower()
        if 'reportlab' in err_msg:
            _handle_cli_error("Error: 'reportlab' library is required. Install with: pip install reportlab")
        elif 'eppy' in err_msg:
            _handle_cli_error("Error: 'eppy' library is required. Install with: pip install eppy")
        else:
            _handle_cli_error(f"An unexpected import error occurred: {import_err}")
    except Exception as e:
        logger.error(f"An unexpected error occurred in CLI mode: {e}", exc_info=True)
        _handle_cli_error(f"An unexpected error occurred: {e}")

def run_gui() -> None:
    """
    Initializes and runs the Modern IDF Processor GUI using Flet.
    """
    cli_status_update("No CLI arguments detected. Starting Modern GUI mode...")
    try:
        def main(page: ft.Page):
            # Import here to avoid circular imports
            from utils.license_dialog import show_startup_license_check
            
            logger.info("=== GUI MAIN FUNCTION STARTED ===")
            logger.info(f"Page object: {page}")
            
            app = ModernIDFProcessorGUI()
            logger.info("ModernIDFProcessorGUI instance created")
            
            def on_license_checked():
                """Called after license check is complete."""
                logger.info("=" * 70)
                logger.info("=== ON_LICENSE_CHECKED CALLBACK CALLED ===")
                logger.info("Building main UI...")
                logger.info(f"Page controls count before build_ui: {len(page.controls) if page.controls else 0}")
                logger.info(f"Page overlay count before build_ui: {len(page.overlay) if page.overlay else 0}")
                # Clear page completely before building UI
                logger.info("Clearing page controls and overlay...")
                page.controls.clear()
                page.overlay.clear()
                page.update()
                logger.info("Page cleared")
                
                logger.info("Calling app.build_ui(page)...")
                app.build_ui(page)
                logger.info("app.build_ui(page) completed")
                logger.info(f"Page controls count after build_ui: {len(page.controls) if page.controls else 0}")
                logger.info(f"Page overlay count after build_ui: {len(page.overlay) if page.overlay else 0}")
                
                # Log detailed information about page controls
                if page.controls:
                    logger.info("=== PAGE CONTROLS DETAILS ===")
                    for i, control in enumerate(page.controls):
                        logger.info(f"Control {i}: {type(control).__name__} - {getattr(control, 'visible', 'no visible attr')}")
                        if hasattr(control, 'controls') and control.controls:
                            logger.info(f"  -> Has {len(control.controls)} child controls")
                
                # Force page update to ensure visibility
                logger.info("Forcing page update...")
                page.update()
                logger.info("Page update completed")
                
                # Additional debugging - check if controls are actually visible
                logger.info("=== FINAL PAGE STATE CHECK ===")
                logger.info(f"Page.visible: {getattr(page, 'visible', 'no visible attr')}")
                for i, control in enumerate(page.controls):
                    logger.info(f"Control {i} visible: {getattr(control, 'visible', True)}")
                
                # Try to force a second update in case the first one didn't work
                logger.info("Forcing second page update...")
                page.update()
                logger.info("Second page update completed")
                
                logger.info("=== MAIN UI BUILDING COMPLETED ===")
                logger.info("=" * 70)
            
            # Build UI directly - license can be managed through the license button
            logger.info("Building main UI directly")
            on_license_checked()
            logger.info("Main UI build completed")
        
        # Start Flet app (window size is set in page configuration within build_ui)
        ft.app(target=main, view=ft.AppView.FLET_APP, assets_dir="data")
    except ImportError as import_err:
        err_msg = str(import_err).lower()
        if 'flet' in err_msg:
             _handle_cli_error("Error: Flet library is required for GUI mode. Install with: pip install flet")
        elif 'reportlab' in err_msg:
             _handle_cli_error("Error: 'reportlab' library is required. Install with: pip install reportlab")
        elif 'eppy' in err_msg:
             _handle_cli_error("Error: 'eppy' library is required. Install with: pip install eppy")
        else:
            _handle_cli_error(f"An unexpected import error occurred while starting GUI: {import_err}")
    except Exception as e:
        logger.error(f"An unexpected error occurred while starting GUI: {e}", exc_info=True)
        _handle_cli_error(f"An unexpected error occurred while starting GUI: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_cli()
    else:
        run_gui()
