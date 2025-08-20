"""
EPJSON Handler for EnergyPlus files
Handles EPJSON file loading, conversion, and manipulation using native Python JSON.
Replaces the eppy-based approach with modern EPJSON format.
"""
import json
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from utils.logging_config import get_logger
from utils.idf_version_checker import IDFVersionChecker
from .path_utils import contains_non_ascii, create_safe_path_for_energyplus

logger = get_logger(__name__)

class EPJSONHandler:
    """Handles EPJSON files using native Python JSON operations."""
    
    def __init__(self, energyplus_path: Optional[str] = None):
        """
        Initialize the EPJSON Handler.
        
        Args:
            energyplus_path: Path to EnergyPlus installation directory
        """
        self.energyplus_path = energyplus_path
        self.version_checker = IDFVersionChecker(energyplus_path)
        
    def load_epjson(self, file_path: str) -> Dict[str, Any]:
        """
        Load EPJSON file into Python dictionary.
        
        Args:
            file_path: Path to the EPJSON file
            
        Returns:
            Dictionary containing the EPJSON data
            
        Raises:
            FileNotFoundError: If file not found
            json.JSONDecodeError: If file is not valid JSON
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"EPJSON file not found at '{file_path}'")
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            logger.info(f"Successfully loaded EPJSON file: {file_path}")
            logger.info(f"EPJSON data contains {len(data)} object types")
            
            return data
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in file '{file_path}': {e}")
            raise
        except Exception as e:
            logger.error(f"Error loading EPJSON file '{file_path}': {e}")
            raise
    
    def save_epjson(self, data: Dict[str, Any], file_path: str) -> None:
        """
        Save Python dictionary as EPJSON file.
        
        Args:
            data: Dictionary containing EPJSON data
            file_path: Path where to save the EPJSON file
        """
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
            logger.info(f"Successfully saved EPJSON file: {file_path}")
            
        except Exception as e:
            logger.error(f"Error saving EPJSON file '{file_path}': {e}")
            raise
    
    def convert_idf_to_epjson(self, idf_path: str, output_path: Optional[str] = None) -> str:
        """
        Convert IDF file to EPJSON using EnergyPlus converter.
        
        Args:
            idf_path: Path to the IDF file
            output_path: Path for the output EPJSON file (optional)
            
        Returns:
            Path to the converted EPJSON file
            
        Raises:
            FileNotFoundError: If IDF file or EnergyPlus not found
            RuntimeError: If conversion fails
        """
        if not os.path.exists(idf_path):
            raise FileNotFoundError(f"IDF file not found at '{idf_path}'")
        
        # Handle Unicode/Hebrew characters in file paths
        safe_idf_path = idf_path
        cleanup_func = None
        
        try:
            if contains_non_ascii(idf_path):
                logger.info(f"IDF file path contains Unicode/Hebrew characters: {idf_path}")
                safe_idf_path, cleanup_func = create_safe_path_for_energyplus(idf_path)
                logger.info(f"Using ASCII-safe path for conversion: {safe_idf_path}")
            
            # Get IDF version and handle version compatibility
            idf_version = self.version_checker.get_idf_version(safe_idf_path)
            if idf_version:
                logger.info(f"Detected IDF version: {idf_version}")
            
            # Use user-provided EnergyPlus path (user ensures correct version compatibility)
            energyplus_exe = self._find_energyplus_executable()
            if not energyplus_exe:
                raise RuntimeError("Could not find EnergyPlus executable. Please ensure the EnergyPlus installation path is correctly specified.")
            
            # Check if version update is needed
            final_idf_path = safe_idf_path
            version_cleanup_func = None
            
            # Support all versions 9.4+ - no version compatibility warnings needed
            if idf_version:
                logger.info(f"Processing IDF version {idf_version} - all versions 9.4+ are supported")
            
            final_idf_path = safe_idf_path
            
            # Determine output path
            if output_path is None:
                output_path = os.path.splitext(idf_path)[0] + '.epJSON'
            
            # Run EnergyPlus converter
            logger.info(f"Converting IDF to EPJSON: {final_idf_path} -> {output_path}")
            
            result = subprocess.run(
                [energyplus_exe, '--convert-only', final_idf_path],
                cwd=os.path.dirname(final_idf_path),
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode != 0:
                # Log detailed error information
                error_msg = f"EnergyPlus conversion failed: {result.stderr}"
                if result.stdout:
                    logger.error(f"EnergyPlus stdout: {result.stdout}")
                logger.error(error_msg)
                
                # Check if error file exists for more detailed error information
                error_file = os.path.join(os.path.dirname(safe_idf_path), "eplusout.err")
                if os.path.exists(error_file):
                    try:
                        with open(error_file, 'r', encoding='utf-8') as f:
                            error_content = f.read()
                            logger.error(f"EnergyPlus detailed errors from {error_file}:\n{error_content}")
                    except Exception as e:
                        logger.warning(f"Could not read error file {error_file}: {e}")
                
                raise RuntimeError(error_msg)
            
            # Find the generated EPJSON file
            generated_epjson = os.path.splitext(final_idf_path)[0] + '.epJSON'
            if os.path.exists(generated_epjson):
                # Move to desired output location if different
                if os.path.abspath(generated_epjson) != os.path.abspath(output_path):
                    import shutil
                    shutil.move(generated_epjson, output_path)
                    
                logger.info(f"Successfully converted IDF to EPJSON: {output_path}")
                return output_path
            else:
                raise RuntimeError(f"Expected EPJSON file not found: {generated_epjson}")
                
        except subprocess.TimeoutExpired:
            raise RuntimeError("EnergyPlus conversion timed out")
        finally:
            # Clean up temporary files if they were created
            if cleanup_func:
                cleanup_func()
                logger.debug("Cleaned up temporary IDF file after conversion")
            if version_cleanup_func:
                version_cleanup_func()
                logger.debug("Cleaned up version-updated IDF file after conversion")
    
    def convert_epjson_to_idf(self, epjson_path: str, output_path: Optional[str] = None) -> str:
        """
        Convert EPJSON file to IDF using EnergyPlus converter.
        
        Args:
            epjson_path: Path to the EPJSON file
            output_path: Path for the output IDF file (optional)
            
        Returns:
            Path to the converted IDF file
        """
        if not os.path.exists(epjson_path):
            raise FileNotFoundError(f"EPJSON file not found at '{epjson_path}'")
        
        # Find EnergyPlus executable
        energyplus_exe = self._find_energyplus_executable()
        if not energyplus_exe:
            raise RuntimeError("Could not find EnergyPlus executable")
        
        # Determine output path
        if output_path is None:
            output_path = os.path.splitext(epjson_path)[0] + '.idf'
        
        try:
            # Run EnergyPlus converter
            logger.info(f"Converting EPJSON to IDF: {epjson_path} -> {output_path}")
            
            result = subprocess.run(
                [energyplus_exe, '--convert-only', epjson_path],
                cwd=os.path.dirname(epjson_path),
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode != 0:
                error_msg = f"EnergyPlus conversion failed: {result.stderr}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            
            # Find the generated IDF file
            generated_idf = os.path.splitext(epjson_path)[0] + '.idf'
            if os.path.exists(generated_idf):
                # Move to desired output location if different
                if os.path.abspath(generated_idf) != os.path.abspath(output_path):
                    import shutil
                    shutil.move(generated_idf, output_path)
                    
                logger.info(f"Successfully converted EPJSON to IDF: {output_path}")
                return output_path
            else:
                raise RuntimeError(f"Expected IDF file not found: {generated_idf}")
                
        except subprocess.TimeoutExpired:
            raise RuntimeError("EnergyPlus conversion timed out")
    
    def _find_energyplus_executable(self) -> Optional[str]:
        """
        Find EnergyPlus executable using user-specified path or common locations.
        
        Returns:
            Path to EnergyPlus executable or None if not found
        """
        if self.energyplus_path:
            # Try the provided path
            exe_path = os.path.join(self.energyplus_path, "energyplus.exe")
            if os.path.exists(exe_path):
                return exe_path
        
        # Try to find EnergyPlus installation in common locations
        common_paths = [
            "C:\\EnergyPlusV24-1-0",
            "C:\\Program Files\\EnergyPlusV24-1-0",
            "C:\\Program Files (x86)\\EnergyPlusV24-1-0",
            "C:\\EnergyPlusV23-2-0",
            "C:\\Program Files\\EnergyPlusV23-2-0",
            "C:\\EnergyPlusV9-6-0",
            "C:\\Program Files\\EnergyPlusV9-6-0",
            "C:\\EnergyPlusV9-5-0",
            "C:\\Program Files\\EnergyPlusV9-5-0",
            "C:\\EnergyPlusV9-4-0",
            "C:\\Program Files\\EnergyPlusV9-4-0"
        ]
        
        for path in common_paths:
            if os.path.exists(path):
                exe_path = os.path.join(path, "energyplus.exe")
                if os.path.exists(exe_path):
                    logger.info(f"Found EnergyPlus installation at: {path}")
                    self.energyplus_path = path
                    return exe_path
        
        # Try to find energyplus in PATH
        try:
            result = subprocess.run(['where', 'energyplus'], 
                                  capture_output=True, text=True, shell=True)
            if result.returncode == 0 and result.stdout.strip():
                exe_path = result.stdout.strip().split('\n')[0]
                logger.info(f"Found EnergyPlus in PATH: {exe_path}")
                return exe_path
        except Exception:
            pass
        
        logger.error("Could not find EnergyPlus executable")
        return None
    
    def get_objects_by_type(self, epjson_data: Dict[str, Any], object_type: str) -> Dict[str, Dict[str, Any]]:
        """
        Get all objects of a specific type from EPJSON data.
        
        Args:
            epjson_data: The EPJSON data dictionary
            object_type: The type of objects to retrieve (e.g., 'Zone', 'BuildingSurface:Detailed')
            
        Returns:
            Dictionary of objects with their names as keys
        """
        objects = epjson_data.get(object_type, {})
        logger.info(f"Retrieved {len(objects)} objects of type '{object_type}'")
        return objects
    
    def get_schedule_objects(self, epjson_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """
        Get all Schedule:Compact objects from EPJSON data.
        
        Args:
            epjson_data: The EPJSON data dictionary
            
        Returns:
            Dictionary of Schedule:Compact objects
        """
        schedules = self.get_objects_by_type(epjson_data, "Schedule:Compact")
        logger.info(f"Retrieved {len(schedules)} Schedule:Compact objects")
        return schedules
    
    def add_output_variable(self, epjson_data: Dict[str, Any], key_value: str, 
                           variable_name: str, reporting_frequency: str) -> None:
        """
        Add an Output:Variable to the EPJSON data.
        
        Args:
            epjson_data: The EPJSON data dictionary to modify
            key_value: Key value for the output variable
            variable_name: Name of the variable to output
            reporting_frequency: Reporting frequency (e.g., 'RunPeriod')
        """
        if "Output:Variable" not in epjson_data:
            epjson_data["Output:Variable"] = {}
        
        # Create unique name for the output variable
        output_name = f"{variable_name}_{key_value}_{reporting_frequency}".replace("*", "All").replace(" ", "_")
        
        epjson_data["Output:Variable"][output_name] = {
            "key_value": key_value,
            "variable_name": variable_name,
            "reporting_frequency": reporting_frequency
        }
        
        logger.info(f"Added Output:Variable: {variable_name}")
    
    def ensure_output_variables(self, epjson_data: Dict[str, Any]) -> None:
        """
        Ensure required output variables exist in the EPJSON data.
        
        Args:
            epjson_data: The EPJSON data dictionary to modify
        """
        required_vars = [
            {
                'key_value': '*',
                'variable_name': 'Zone Ideal Loads Supply Air Total Cooling Energy',
                'reporting_frequency': 'RunPeriod'
            },
            {
                'key_value': '*',
                'variable_name': 'Zone Ideal Loads Supply Air Total Heating Energy',
                'reporting_frequency': 'RunPeriod'
            },
            {
                'key_value': '*',
                'variable_name': 'Lights Electricity Energy',
                'reporting_frequency': 'RunPeriod'
            }
        ]
        
        for var_data in required_vars:
            self.add_output_variable(
                epjson_data,
                var_data['key_value'],
                var_data['variable_name'],
                var_data['reporting_frequency']
            )
    
    def load_or_convert_file(self, file_path: str, prefer_epjson: bool = True) -> Tuple[Dict[str, Any], str]:
        """
        Load a file as EPJSON, converting from IDF if necessary.
        
        Args:
            file_path: Path to the file (can be .idf or .epJSON)
            prefer_epjson: Whether to prefer EPJSON format for output
            
        Returns:
            Tuple of (epjson_data, actual_file_path_used)
        """
        file_ext = os.path.splitext(file_path)[1].lower()
        
        if file_ext == '.epjson':
            # File is already EPJSON - no injection needed
            epjson_data = self.load_epjson(file_path)
            return epjson_data, file_path
            
        elif file_ext == '.idf':
            # Inject required output variables before conversion
            temp_idf_path = self._inject_required_output_variables(file_path)
            
            try:
                # Convert modified IDF to EPJSON with version handling
                epjson_path = self.convert_idf_to_epjson(temp_idf_path)
                epjson_data = self.load_epjson(epjson_path)
            finally:
                # Clean up temporary file
                if os.path.exists(temp_idf_path):
                    os.unlink(temp_idf_path)
                    logger.debug(f"Cleaned up temporary IDF file: {temp_idf_path}")
            
            if prefer_epjson:
                return epjson_data, epjson_path
            else:
                return epjson_data, file_path
        else:
            raise ValueError(f"Unsupported file format: {file_ext}. Expected .idf or .epJSON")
    
    def _inject_required_output_variables(self, idf_path: str) -> str:
        """
        Inject required Output:Variable entries into IDF file before conversion.
        Creates a temporary modified IDF file with the required output variables.
        
        Args:
            idf_path: Path to the original IDF file
            
        Returns:
            Path to the temporary modified IDF file
        """
        import tempfile
        import shutil
        
        # Create temporary file
        temp_dir = tempfile.gettempdir()
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.idf', delete=False, dir=temp_dir, encoding='utf-8')
        temp_path = temp_file.name
        
        try:
            # Copy original file content
            with open(idf_path, 'r', encoding='utf-8') as original:
                content = original.read()
            
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
            
            # Write to temporary file
            temp_file.write(content + additional_content)
            temp_file.close()
            
            logger.info(f"Injected 3 OUTPUT:VARIABLE entries into temporary IDF: {temp_path}")
            return temp_path
            
        except Exception as e:
            temp_file.close()
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise RuntimeError(f"Failed to inject output variables: {e}")
    
    def _update_idf_version(self, idf_path: str) -> str:
        """
        Update IDF file to current EnergyPlus version.
        
        Args:
            idf_path: Path to the IDF file to update
            
        Returns:
            Path to the version-updated IDF file
            
        Raises:
            RuntimeError: If version update fails
        """
        import tempfile
        
        # Create temporary file for updated IDF
        temp_dir = tempfile.gettempdir()
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.idf', delete=False, dir=temp_dir)
        temp_path = temp_file.name
        temp_file.close()
        
        # Find EnergyPlus executable
        energyplus_exe = self._find_energyplus_executable()
        if not energyplus_exe:
            raise RuntimeError("EnergyPlus executable not found for version update")
        
        try:
            # Use absolute path for version update
            abs_idf_path = os.path.abspath(idf_path)
            
            # Run EnergyPlus version update
            logger.info(f"Updating IDF version: {abs_idf_path} -> {temp_path}")
            
            result = subprocess.run(
                [energyplus_exe, '--version-only', abs_idf_path],
                cwd=os.path.dirname(abs_idf_path),
                capture_output=True,
                text=True,
                timeout=120  # 2 minute timeout for version update
            )
            
            if result.returncode != 0:
                error_msg = f"Version update failed with return code {result.returncode}"
                if result.stderr:
                    error_msg += f": {result.stderr}"
                if result.stdout:
                    logger.error(f"Version update stdout: {result.stdout}")
                raise RuntimeError(error_msg)
            
            # Find the version-updated file (EnergyPlus creates it in the same directory)
            updated_file = os.path.splitext(abs_idf_path)[0] + '.idf'
            
            # If that doesn't exist, look for common version update output patterns
            if not os.path.exists(updated_file):
                dir_name = os.path.dirname(abs_idf_path)
                base_name = os.path.splitext(os.path.basename(abs_idf_path))[0]
                
                # Check for various possible output file names
                possible_names = [
                    f"{base_name}.idf",
                    f"{base_name}_updated.idf",
                    f"{base_name}_V24-1-0.idf"
                ]
                
                for name in possible_names:
                    candidate = os.path.join(dir_name, name)
                    if os.path.exists(candidate) and candidate != abs_idf_path:
                        updated_file = candidate
                        break
            
            if not os.path.exists(updated_file) or updated_file == abs_idf_path:
                raise RuntimeError(f"Version-updated file not found or same as input: {updated_file}")
            
            # Move the updated file to our temporary location
            import shutil
            shutil.move(updated_file, temp_path)
            
            logger.info(f"IDF version update successful: {temp_path}")
            return temp_path
            
        except Exception as e:
            # Clean up temp file on error
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise RuntimeError(f"IDF version update failed: {e}")
    
    def validate_epjson(self, epjson_data: Dict[str, Any]) -> List[str]:
        """
        Perform basic validation of EPJSON data.
        
        Args:
            epjson_data: The EPJSON data to validate
            
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        # Check if data is a dictionary
        if not isinstance(epjson_data, dict):
            errors.append("EPJSON data must be a dictionary")
            return errors
        
        # Check for Version object
        if "Version" not in epjson_data:
            errors.append("EPJSON data missing required 'Version' object")
        
        # Check for basic required objects
        required_objects = ["SimulationControl", "Timestep"]
        for obj_type in required_objects:
            if obj_type not in epjson_data:
                errors.append(f"EPJSON data missing recommended '{obj_type}' object")
        
        # Validate object structure
        for obj_type, objects in epjson_data.items():
            if not isinstance(objects, dict):
                errors.append(f"Object type '{obj_type}' should contain a dictionary of objects")
                continue
                
            for obj_name, obj_data in objects.items():
                if not isinstance(obj_data, dict):
                    errors.append(f"Object '{obj_name}' in '{obj_type}' should be a dictionary")
        
        return errors