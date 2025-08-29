"""
Utility functions for validating report data before generation.
Used to determine if a report should be created based on data availability.
"""
from typing import Any, Dict, List, Union
from utils.logging_config import get_logger

logger = get_logger(__name__)


def has_valid_data(data: Any, report_type: str = "Unknown") -> bool:
    """
    Validates if data contains meaningful content for report generation.
    
    Args:
        data: The data to validate (can be list, dict, or other types)
        report_type: Name of the report type for logging purposes
    
    Returns:
        bool: True if data is valid and should generate a report, False otherwise
    """
    if data is None:
        logger.info(f"Skipping {report_type} report - data is None")
        return False
    
    # Handle list data (most common case)
    if isinstance(data, list):
        if not data:
            logger.info(f"Skipping {report_type} report - empty list")
            return False
        
        # Check if list contains meaningful data (not all None/empty items)
        valid_items = [item for item in data if item is not None and item != {}]
        if not valid_items:
            logger.info(f"Skipping {report_type} report - list contains only None/empty items")
            return False
            
        return True
    
    # Handle dict data
    if isinstance(data, dict):
        if not data:
            logger.info(f"Skipping {report_type} report - empty dict")
            return False
            
        # Check if dict has meaningful values
        has_meaningful_data = any(
            value is not None and value != [] and value != {} and value != ""
            for value in data.values()
        )
        
        if not has_meaningful_data:
            logger.info(f"Skipping {report_type} report - dict contains no meaningful data")
            return False
            
        return True
    
    # Handle string data
    if isinstance(data, str):
        if not data.strip():
            logger.info(f"Skipping {report_type} report - empty string")
            return False
        return True
    
    # Handle numeric data
    if isinstance(data, (int, float)):
        return True
    
    # For other types, assume valid if not None
    return data is not None


def validate_lighting_data(lighting_data: Dict[str, List]) -> bool:
    """
    Validates lighting data structure for report generation.
    
    Args:
        lighting_data: Dict with keys like 'controls', 'exterior_lights', 'task_lights'
    
    Returns:
        bool: True if any section has valid data
    """
    if not isinstance(lighting_data, dict):
        logger.info("Skipping Lighting report - data is not a dict")
        return False
    
    # Check each section for valid data
    sections_with_data = []
    for section_name, section_data in lighting_data.items():
        if has_valid_data(section_data, f"Lighting-{section_name}"):
            sections_with_data.append(section_name)
    
    if not sections_with_data:
        logger.info("Skipping Lighting report - no valid data in any section")
        return False
    
    logger.info(f"Lighting report will be generated - found data in sections: {sections_with_data}")
    return True


def validate_schedule_data(schedule_data: List[Dict]) -> bool:
    """
    Validates schedule data for report generation.
    
    Args:
        schedule_data: List of schedule dictionaries
        
    Returns:
        bool: True if there are valid schedules with rule blocks
    """
    if not has_valid_data(schedule_data, "Schedule"):
        return False
    
    # Check if any schedule has meaningful rule blocks
    valid_schedules = 0
    for schedule in schedule_data:
        if isinstance(schedule, dict):
            rule_blocks = schedule.get('rule_blocks', [])
            if isinstance(rule_blocks, list) and rule_blocks:
                # Check if rule blocks have actual data
                for block in rule_blocks:
                    if isinstance(block, dict) and block.get('hourly_values'):
                        valid_schedules += 1
                        break
    
    if valid_schedules == 0:
        logger.info("Skipping Schedule report - no schedules with valid rule blocks found")
        return False
    
    logger.info(f"Schedule report will be generated - found {valid_schedules} valid schedules")
    return True


def validate_materials_data(materials_data: Dict) -> bool:
    """
    Validates materials data for report generation.
    
    Args:
        materials_data: Dict containing materials information
        
    Returns:
        bool: True if there are materials to report
    """
    if not isinstance(materials_data, dict):
        logger.info("Skipping Materials report - data is not a dict")
        return False
    
    # Check for common materials sections
    sections_to_check = ['materials', 'constructions', 'elements']
    for section in sections_to_check:
        if section in materials_data and has_valid_data(materials_data[section], f"Materials-{section}"):
            logger.info(f"Materials report will be generated - found data in {section}")
            return True
    
    # Fallback: check if any value in the dict is valid
    if has_valid_data(materials_data, "Materials"):
        return True
    
    logger.info("Skipping Materials report - no valid materials data found")
    return False


def validate_glazing_data(glazing_data: Any) -> bool:
    """
    Validates glazing data for report generation.
    
    Args:
        glazing_data: Glazing data structure
        
    Returns:
        bool: True if there is glazing data to report
    """
    return has_valid_data(glazing_data, "Glazing")


def validate_loads_data(loads_data: Any) -> bool:
    """
    Validates loads data for report generation.
    
    Args:
        loads_data: Loads data structure
        
    Returns:
        bool: True if there is loads data to report
    """
    return has_valid_data(loads_data, "Loads")


def validate_settings_data(settings_data: Any) -> bool:
    """
    Validates settings data for report generation.
    
    Args:
        settings_data: Settings data structure
        
    Returns:
        bool: True if there is settings data to report
    """
    return has_valid_data(settings_data, "Settings")


def validate_natural_ventilation_data(ventilation_data: Any) -> bool:
    """
    Validates natural ventilation data for report generation.
    
    Args:
        ventilation_data: Natural ventilation data structure
        
    Returns:
        bool: True if there is ventilation data to report
    """
    return has_valid_data(ventilation_data, "Natural Ventilation")


def validate_automatic_error_detection_data(error_data: Any) -> bool:
    """
    Validates automatic error detection data for report generation.
    
    Args:
        error_data: Error detection data structure
        
    Returns:
        bool: True if there is error data to report
    """
    return has_valid_data(error_data, "Automatic Error Detection")