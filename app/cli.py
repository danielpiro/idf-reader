"""
CLI interface for the IDF Reader application.
"""
import argparse
import sys
import os
import time
from colorama import Fore, init
from processing_manager import ProcessingManager
from utils.logging_config import get_logger

logger = get_logger(__name__)
init(autoreset=True)


class CliInterface:
    """Command line interface for IDF processing."""
    
    def __init__(self):
        """Initialize CLI interface."""
        self.processor = None
    
    def ensure_directory_exists(self, file_path: str) -> None:
        """
        Ensure the directory for the given file path exists.
        
        Args:
            file_path: Path to the file
        """
        directory = os.path.dirname(file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
    
    def status_update(self, message: str) -> None:
        """
        Print status messages with color coding.
        
        Args:
            message: Status message to print
        """
        try:
            if "error" in message.lower() or "failed" in message.lower():
                print(Fore.RED + message)
            elif "success" in message.lower() or "completed" in message.lower():
                print(Fore.GREEN + message)
            elif "warning" in message.lower():
                print(Fore.YELLOW + message)
            else:
                print(Fore.WHITE + message)
        except UnicodeEncodeError:
            print(f"[STATUS] {message.encode('ascii', 'replace').decode('ascii')}")
    
    def progress_update(self, value: float) -> None:
        """
        Print progress bar to console.
        
        Args:
            value: Progress value (0.0 to 1.0)
        """
        bar_length = 40
        filled_length = int(round(bar_length * value))
        
        try:
            bar = '█' * filled_length + '-' * (bar_length - filled_length)
        except UnicodeEncodeError:
            bar = '=' * filled_length + '-' * (bar_length - filled_length)
        
        try:
            if value >= 1.0:
                print(f"\r{bar} 100% Complete", end='\n')
            else:
                print(f"\r{bar} {value * 100:.2f}% Complete", end='')
        except UnicodeEncodeError:
            print(f"\r[{value * 100:.2f}%] Processing...", end='')
    
    def parse_arguments(self) -> argparse.Namespace:
        """
        Parse command line arguments.
        
        Returns:
            Parsed arguments namespace
        """
        parser = argparse.ArgumentParser(
            description="Parse an EnergyPlus IDF file and generate reports."
        )
        parser.add_argument(
            "idf_file",
            help="Path to the input IDF file"
        )
        parser.add_argument(
            "--idd",
            required=False,
            help="Path to the Energy+.idd file (optional for EPJSON files)"
        )
        parser.add_argument(
            "-o", "--output",
            default="output",
            help="Path to the output directory for reports (default: 'output')"
        )
        return parser.parse_args()
    
    def handle_error(self, message: str, exit_code: int = 1) -> None:
        """
        Handle CLI error reporting and exit.
        
        Args:
            message: Error message to display
            exit_code: Exit code for the program
        """
        self.status_update(message)
        sys.exit(exit_code)
    
    def run(self) -> None:
        """Run the command line interface."""
        args = self.parse_arguments()
        
        idf_file_path = args.idf_file
        idd_file_path = args.idd
        output_dir_path = args.output
        
        self.ensure_directory_exists(os.path.join(output_dir_path, "dummy.txt"))
        
        self.status_update(f"Starting processing for IDF: {idf_file_path}")
        self.status_update(f"Using IDD: {idd_file_path}")
        self.status_update(f"Output directory: {output_dir_path}")
        
        start_time = time.time()
        
        try:
            self.processor = ProcessingManager(
                status_callback=self.status_update,
                progress_callback=self.progress_update
            )
            
            success = self.processor.process_idf(
                input_file=idf_file_path,
                idd_path=idd_file_path,
                output_dir=output_dir_path
            )
            
            total_time = time.time() - start_time
            
            if success:
                self.status_update(f"Processing completed successfully in {total_time:.2f}s")
            else:
                self.status_update(f"Processing failed or was cancelled after {total_time:.2f}s")
                
        except FileNotFoundError as e:
            self.handle_error(f"Error: File not found - {str(e)}")
        except ImportError as import_err:
            err_msg = str(import_err).lower()
            if 'reportlab' in err_msg:
                self.handle_error("Error: 'reportlab' library is required. Install with: pip install reportlab")
            else:
                self.handle_error(f"An unexpected import error occurred: {import_err}")
        except Exception as e:
            logger.error(f"An unexpected error occurred in CLI mode: {e}", exc_info=True)
            self.handle_error(f"An unexpected error occurred: {e}")


def run_cli():
    """Entry point for CLI interface."""
    cli = CliInterface()
    cli.run()