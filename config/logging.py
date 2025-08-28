"""
Centralized logging configuration.
"""
import logging
import logging.handlers
import os
from pathlib import Path
from datetime import datetime
from typing import Optional


class LoggingConfig:
    """Centralized logging configuration manager."""
    
    @staticmethod
    def setup_logging(
        log_level: str = "INFO",
        log_dir: str = "logs",
        app_name: str = "idf_reader",
        max_file_size: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5
    ) -> logging.Logger:
        """
        Set up application logging with file and console handlers.
        
        Args:
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_dir: Directory for log files
            app_name: Application name for log files
            max_file_size: Maximum size of each log file in bytes
            backup_count: Number of backup files to keep
            
        Returns:
            Configured root logger
        """
        # Create logs directory if it doesn't exist
        Path(log_dir).mkdir(exist_ok=True)
        
        # Configure root logger
        logger = logging.getLogger()
        logger.setLevel(getattr(logging, log_level.upper()))
        
        # Clear existing handlers
        logger.handlers.clear()
        
        # Create formatters
        detailed_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        simple_formatter = logging.Formatter(
            '%(levelname)s - %(message)s'
        )
        
        # File handler with rotation
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(log_dir, f"debug_{timestamp}.log")
        
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_file_size,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(detailed_formatter)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, log_level.upper()))
        console_handler.setFormatter(simple_formatter)
        
        # Add handlers
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        logger.info(f"Logging configured - Level: {log_level}, File: {log_file}")
        return logger
    
    @staticmethod
    def get_logger(name: str) -> logging.Logger:
        """
        Get a logger instance for a module.
        
        Args:
            name: Logger name (typically __name__)
            
        Returns:
            Logger instance
        """
        return logging.getLogger(name)
    
    @staticmethod
    def set_log_level(level: str) -> None:
        """
        Set logging level for all loggers.
        
        Args:
            level: New logging level
        """
        numeric_level = getattr(logging, level.upper(), None)
        if isinstance(numeric_level, int):
            logging.getLogger().setLevel(numeric_level)
            # Update all handlers
            for handler in logging.getLogger().handlers:
                if isinstance(handler, logging.StreamHandler):
                    handler.setLevel(numeric_level)


# Legacy compatibility function
def get_logger(name: str) -> logging.Logger:
    """
    Legacy wrapper for getting logger.
    
    Args:
        name: Module name (__name__)
        
    Returns:
        Logger instance
    """
    return LoggingConfig.get_logger(name)