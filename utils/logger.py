"""
Shared logging utilities to eliminate duplicate imports across modules.
"""
from utils.logging_config import get_logger


def create_module_logger(module_name):
    """
    Create a logger for a specific module.
    
    Args:
        module_name (str): Name of the module (__name__)
        
    Returns:
        Logger: Configured logger instance
    """
    return get_logger(module_name)


# Convenience function for common use case
def get_module_logger(module_name):
    """
    Get logger for module. Alias for create_module_logger for backwards compatibility.
    
    Args:
        module_name (str): Module name (__name__)
        
    Returns:
        Logger: Configured logger instance
    """
    return create_module_logger(module_name)