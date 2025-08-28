"""
Application configuration and settings management.
"""
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from utils.logger import get_module_logger

logger = get_module_logger(__name__)


class AppSettings:
    """Application settings manager with persistent storage."""
    
    def __init__(self, settings_file: str = "settings.json"):
        """
        Initialize settings manager.
        
        Args:
            settings_file: Path to settings JSON file
        """
        self.settings_file = settings_file
        self._settings = self._load_default_settings()
        self.load()
    
    def _load_default_settings(self) -> Dict[str, Any]:
        """
        Load default application settings.
        
        Returns:
            Dictionary with default settings
        """
        return {
            "last_idf_file": "",
            "last_idd_file": "",
            "last_output_directory": "output",
            "city_name": "תל אביב",
            "area_name": "א",
            "iso_type": "ISO_TYPE_2017_A",
            "window_width": 1200,
            "window_height": 800,
            "theme_mode": "light",
            "language": "he",
            "auto_save_settings": True,
            "debug_mode": False,
            "max_recent_files": 10,
            "recent_files": [],
            "recent_directories": []
        }
    
    def load(self) -> bool:
        """
        Load settings from file.
        
        Returns:
            True if loaded successfully, False if using defaults
        """
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    file_settings = json.load(f)
                    self._settings.update(file_settings)
                logger.info(f"Settings loaded from {self.settings_file}")
                return True
            else:
                logger.info("Settings file not found, using defaults")
                return False
        except Exception as e:
            logger.error(f"Error loading settings: {e}")
            return False
    
    def save(self) -> bool:
        """
        Save settings to file.
        
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self._settings, f, indent=2, ensure_ascii=False)
            logger.info(f"Settings saved to {self.settings_file}")
            return True
        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get setting value.
        
        Args:
            key: Setting key
            default: Default value if key not found
            
        Returns:
            Setting value or default
        """
        return self._settings.get(key, default)
    
    def set(self, key: str, value: Any, auto_save: bool = None) -> None:
        """
        Set setting value.
        
        Args:
            key: Setting key
            value: Setting value
            auto_save: Whether to auto-save (uses setting if None)
        """
        self._settings[key] = value
        
        if auto_save is None:
            auto_save = self.get("auto_save_settings", True)
        
        if auto_save:
            self.save()
    
    def update(self, settings: Dict[str, Any], auto_save: bool = None) -> None:
        """
        Update multiple settings.
        
        Args:
            settings: Dictionary of settings to update
            auto_save: Whether to auto-save (uses setting if None)
        """
        self._settings.update(settings)
        
        if auto_save is None:
            auto_save = self.get("auto_save_settings", True)
        
        if auto_save:
            self.save()
    
    def add_recent_file(self, file_path: str) -> None:
        """
        Add file to recent files list.
        
        Args:
            file_path: Path to recently used file
        """
        recent_files = self.get("recent_files", [])
        max_recent = self.get("max_recent_files", 10)
        
        # Remove if already exists
        if file_path in recent_files:
            recent_files.remove(file_path)
        
        # Add to beginning
        recent_files.insert(0, file_path)
        
        # Limit list size
        recent_files = recent_files[:max_recent]
        
        self.set("recent_files", recent_files)
    
    def add_recent_directory(self, dir_path: str) -> None:
        """
        Add directory to recent directories list.
        
        Args:
            dir_path: Path to recently used directory
        """
        recent_dirs = self.get("recent_directories", [])
        max_recent = self.get("max_recent_files", 10)  # Reuse same limit
        
        # Remove if already exists
        if dir_path in recent_dirs:
            recent_dirs.remove(dir_path)
        
        # Add to beginning
        recent_dirs.insert(0, dir_path)
        
        # Limit list size
        recent_dirs = recent_dirs[:max_recent]
        
        self.set("recent_directories", recent_dirs)
    
    def get_all(self) -> Dict[str, Any]:
        """
        Get all settings.
        
        Returns:
            Complete settings dictionary
        """
        return self._settings.copy()
    
    def reset_to_defaults(self) -> None:
        """Reset all settings to defaults."""
        self._settings = self._load_default_settings()
        self.save()
        logger.info("Settings reset to defaults")


class ConfigManager:
    """Global configuration manager."""
    
    _instance: Optional['ConfigManager'] = None
    _settings: Optional[AppSettings] = None
    
    def __new__(cls) -> 'ConfigManager':
        """Singleton pattern implementation."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize configuration manager."""
        if self._settings is None:
            self._settings = AppSettings()
    
    @property
    def settings(self) -> AppSettings:
        """Get settings instance."""
        return self._settings
    
    @classmethod
    def get_instance(cls) -> 'ConfigManager':
        """Get singleton instance."""
        return cls()


# Global configuration instance
config = ConfigManager()