import argparse
import sys
import os
import time
from colorama import Fore, Style, init
from gui import IDFProcessorGUI, ProcessingManager # Import GUI and ProcessingManager

# Initialize colorama
init(autoreset=True)

def ensure_directory_exists(file_path: str) -> None:
    """
    Ensure the directory for the given file path exists.
    Create it if it doesn't exist.
    
    Args:
        file_path: Path to the file
    """
    directory = os.path.dirname(file_path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory)

# --- CLI Callback Functions ---
def cli_status_update(message: str):
    """Prints status messages to the console with color."""
    if "error" in message.lower():
        print(f"{Fore.RED}{message}{Style.RESET_ALL}")
    elif "success" in message.lower():
        print(f"{Fore.GREEN}{message}{Style.RESET_ALL}")
    else:
        print(f"{Fore.CYAN}{message}{Style.RESET_ALL}")

def cli_progress_update(value: float):
    """Prints a simple progress indicator to the console."""
    # Simple text update, could be enhanced with a progress bar library if needed
    print(f"Progress: {value*100:.0f}%")

# --- Main CLI Function ---
def main():
    """
    Command-line interface for processing IDF files using ProcessingManager.
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
        default="output", # Default output directory
        help="Path to the output directory for reports (default: 'output')."
    )

    args = parser.parse_args()

    idf_file_path = args.idf_file
    idd_file_path = args.idd
    output_dir_path = args.output

    # Ensure output directory exists (ProcessingManager also does this, but good practice)
    ensure_directory_exists(os.path.join(output_dir_path, "dummy.txt"))

    cli_status_update(f"Starting processing for IDF: {idf_file_path}")
    cli_status_update(f"Using IDD: {idd_file_path}")
    cli_status_update(f"Output directory: {output_dir_path}")

    start_time = time.time()

    try:
        # Instantiate ProcessingManager with CLI callbacks
        processor = ProcessingManager(
            status_callback=cli_status_update,
            progress_callback=cli_progress_update
        )

        # Run the centralized processing logic
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
        cli_status_update(f"Error: File not found - {str(e)}")
        sys.exit(1)
    except ImportError as import_err:
        if 'reportlab' in str(import_err).lower():
             cli_status_update("Error: 'reportlab' library required - install with: pip install reportlab")
        elif 'eppy' in str(import_err).lower():
             cli_status_update("Error: 'eppy' library required - install with: pip install eppy")
        else:
             cli_status_update(f"An unexpected import error occurred: {import_err}")
        sys.exit(1)
    except Exception as e:
        cli_status_update(f"An unexpected error occurred: {e}")
        # Consider adding traceback here for debugging
        # import traceback
        # traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    # Check if any arguments were passed (besides the script name)
    if len(sys.argv) > 1:
        # If arguments are provided, run the CLI main function
        main()
    else:
        # If no arguments, run the GUI
        print("No command-line arguments detected, launching GUI...")
        app = IDFProcessorGUI()
        app.run()