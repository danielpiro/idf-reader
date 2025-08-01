"""
Centralized logging configuration for the IDF Reader application.
All modules should import and use this configuration to ensure consistent file-based logging.
"""
import logging
import os
from datetime import datetime

def setup_file_logging():
    """
    Sets up file-based logging configuration.
    Creates logs directory and configures all loggers to write to timestamped log files.
    """
    # Create logs directory if it doesn't exist
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Create log filename with timestamp
    log_filename = os.path.join(log_dir, f"debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

    # Configure root logger to write to file only (no console output)
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename, encoding='utf-8'),
        ],
        force=True  # Override any existing configuration
    )

    return log_filename

def get_logger(name):
    """
    Get a logger instance with the specified name.
    The logger will automatically use the file-based configuration.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)

# Initialize file logging on module import
_log_file = setup_file_logging()