"""
Auto-update manager for IDF Reader application.
Handles checking for updates, downloading, and installing new versions.
"""

import os
import sys
import json
import shutil
import tempfile
import zipfile
import subprocess
import threading
from pathlib import Path
from urllib.request import urlopen, urlretrieve
from urllib.error import URLError, HTTPError
import ssl
import time

from utils.logging_config import get_logger
from version import get_version, compare_versions, UPDATE_SERVER_URL, GITHUB_RELEASES_URL

logger = get_logger(__name__)

class UpdateManager:
    def __init__(self, status_callback=None):
        """
        Initialize the update manager.
        
        Args:
            status_callback: Function to call for status updates
        """
        self.status_callback = status_callback or self._default_status
        self.current_version = get_version()
        self.app_directory = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent.parent
        self.update_in_progress = False
        
        # Update settings
        self.settings_file = Path(self.app_directory) / "update_settings.json"
        self.settings = self._load_update_settings()
    
    def _default_status(self, message):
        """Default status callback that just logs."""
        logger.info(f"Update: {message}")
    
    def _load_update_settings(self):
        """Load update settings from file."""
        default_settings = {
            "auto_check": True,
            "check_interval_hours": 24,
            "last_check": 0,
            "update_channel": "stable",  # stable, beta, alpha
            "download_timeout": 300  # 5 minutes
        }
        
        try:
            if self.settings_file.exists():
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    loaded_settings = json.load(f)
                    default_settings.update(loaded_settings)
        except Exception as e:
            logger.warning(f"Could not load update settings: {e}")
        
        return default_settings
    
    def _save_update_settings(self):
        """Save update settings to file."""
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Could not save update settings: {e}")
    
    def should_check_for_updates(self):
        """Check if it's time to check for updates based on settings."""
        if not self.settings["auto_check"]:
            return False
        
        current_time = time.time()
        last_check = self.settings["last_check"]
        interval_seconds = self.settings["check_interval_hours"] * 3600
        
        return (current_time - last_check) >= interval_seconds
    
    def check_for_updates_async(self, force=False):
        """Check for updates in background thread."""
        if self.update_in_progress:
            self.status_callback("בדיקת עדכונים כבר בתהליך...")
            return
        
        if not force and not self.should_check_for_updates():
            logger.debug("Skipping update check - not time yet")
            return
        
        def check_worker():
            try:
                self.check_for_updates(force=force)
            except Exception as e:
                logger.error(f"Error in background update check: {e}")
                self.status_callback(f"שגיאה בבדיקת עדכונים: {e}")
        
        thread = threading.Thread(target=check_worker, daemon=True)
        thread.start()
    
    def check_for_updates(self, force=False):
        """
        Check for available updates.
        
        Args:
            force: Force check even if recently checked
            
        Returns:
            dict: Update info if available, None if no updates
        """
        if self.update_in_progress:
            self.status_callback("בדיקת עדכונים כבר בתהליך...")
            return None
        
        if not force and not self.should_check_for_updates():
            return None
        
        self.status_callback("בודק עדכונים זמינים...")
        
        try:
            # Update last check time
            self.settings["last_check"] = time.time()
            self._save_update_settings()
            
            # Try GitHub releases first (more reliable)
            update_info = self._check_github_releases()
            
            if not update_info:
                # Fallback to custom update server
                update_info = self._check_custom_server()
            
            if update_info:
                new_version = update_info.get("version")
                if compare_versions(self.current_version, new_version) < 0:
                    self.status_callback(f"עדכון זמין: גרסה {new_version}")
                    logger.info(f"Update available: {self.current_version} -> {new_version}")
                    return update_info
                else:
                    self.status_callback("האפליקציה מעודכנת לגרסה האחרונה")
                    logger.info("Application is up to date")
            else:
                self.status_callback("לא ניתן לבדוק עדכונים")
        
        except Exception as e:
            logger.error(f"Error checking for updates: {e}")
            self.status_callback(f"שגיאה בבדיקת עדכונים: {e}")
        
        return None
    
    def _check_github_releases(self):
        """Check GitHub releases for updates."""
        try:
            from urllib.request import Request
            
            # Create request with authentication for private repos
            headers = {
                'User-Agent': 'IDF-Reader-Auto-Updater/1.0',
                'Accept': 'application/vnd.github.v3+json'
            }
            
            # Add GitHub token for private repos if available
            github_token = self._get_github_token()
            if github_token:
                headers['Authorization'] = f'token {github_token}'
            
            request = Request(GITHUB_RELEASES_URL, headers=headers)
            
            with urlopen(request, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                
                if data.get("tag_name"):
                    version = data["tag_name"].lstrip('v')  # Remove 'v' prefix if present
                    
                    # Find appropriate asset (Windows executable)
                    download_url = None
                    for asset in data.get("assets", []):
                        if asset["name"].endswith((".exe", ".zip")) and "windows" in asset["name"].lower():
                            download_url = asset["browser_download_url"]
                            break
                    
                    if not download_url and data.get("assets"):
                        # Fallback to first asset
                        download_url = data["assets"][0]["browser_download_url"]
                    
                    return {
                        "version": version,
                        "download_url": download_url,
                        "release_notes": data.get("body", ""),
                        "published_at": data.get("published_at"),
                        "source": "github"
                    }
        
        except (URLError, HTTPError, json.JSONDecodeError, KeyError) as e:
            logger.debug(f"GitHub releases check failed: {e}")
        
        return None
    
    def _check_custom_server(self):
        """Check custom update server for updates."""
        try:
            url = f"{UPDATE_SERVER_URL}/check_update"
            data = {
                "current_version": self.current_version,
                "channel": self.settings["update_channel"],
                "platform": sys.platform
            }
            
            # For GET request, append parameters to URL
            params = "&".join([f"{k}={v}" for k, v in data.items()])
            full_url = f"{url}?{params}"
            
            with urlopen(full_url, timeout=10) as response:
                result = json.loads(response.read().decode('utf-8'))
                
                if result.get("update_available"):
                    return {
                        "version": result["version"],
                        "download_url": result["download_url"],
                        "release_notes": result.get("release_notes", ""),
                        "source": "custom"
                    }
        
        except (URLError, HTTPError, json.JSONDecodeError) as e:
            logger.debug(f"Custom server check failed: {e}")
        
        return None
    
    def download_and_install_update(self, update_info, restart_callback=None):
        """
        Download and install an update.
        
        Args:
            update_info: Update information from check_for_updates
            restart_callback: Function to call when restart is needed
        """
        if self.update_in_progress:
            self.status_callback("עדכון כבר בתהליך...")
            return False
        
        self.update_in_progress = True
        
        try:
            download_url = update_info["download_url"]
            new_version = update_info["version"]
            
            if not download_url:
                self.status_callback("לא נמצא קישור הורדה לעדכון")
                return False
            
            self.status_callback(f"מוריד עדכון לגרסה {new_version}...")
            
            # Create temporary directory for download
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Determine file extension from URL
                if download_url.endswith('.zip'):
                    download_file = temp_path / "update.zip"
                else:
                    download_file = temp_path / "update.exe"
                
                # Download the update
                self._download_file(download_url, download_file)
                
                if download_file.suffix == '.zip':
                    # Extract zip file
                    extract_dir = temp_path / "extracted"
                    extract_dir.mkdir()
                    
                    with zipfile.ZipFile(download_file, 'r') as zip_ref:
                        zip_ref.extractall(extract_dir)
                    
                    # Find the executable in extracted files
                    exe_files = list(extract_dir.rglob("*.exe"))
                    if exe_files:
                        update_executable = exe_files[0]
                    else:
                        self.status_callback("לא נמצא קובץ הפעלה בעדכון")
                        return False
                else:
                    update_executable = download_file
                
                # Install the update
                return self._install_update(update_executable, restart_callback)
        
        except Exception as e:
            logger.error(f"Error downloading/installing update: {e}")
            self.status_callback(f"שגיאה בהתקנת עדכון: {e}")
            return False
        
        finally:
            self.update_in_progress = False
    
    def _download_file(self, url, destination):
        """Download a file with progress tracking."""
        try:
            def progress_hook(block_num, block_size, total_size):
                if total_size > 0:
                    percent = min(100, (block_num * block_size * 100) // total_size)
                    self.status_callback(f"מוריד... {percent}%")
            
            urlretrieve(url, destination, reporthook=progress_hook)
            self.status_callback("ההורדה הושלמה")
            
        except Exception as e:
            raise Exception(f"כשל בהורדת הקובץ: {e}")
    
    def _install_update(self, update_executable, restart_callback=None):
        """Install the downloaded update."""
        try:
            self.status_callback("מתקין עדכון...")
            
            # Get current executable path
            if getattr(sys, 'frozen', False):
                # Running as compiled executable
                current_exe = Path(sys.executable)
                backup_exe = current_exe.with_suffix('.bak')
                
                # Create backup of current executable
                shutil.copy2(current_exe, backup_exe)
                self.status_callback("נוצר גיבוי של הגרסה הנוכחית")
                
                # Replace current executable
                shutil.copy2(update_executable, current_exe)
                self.status_callback("הקובץ החדש הותקן בהצלחה")
                
                # Schedule restart
                if restart_callback:
                    self.status_callback("העדכון הושלם. נדרש אתחול האפליקציה...")
                    restart_callback()
                else:
                    self._restart_application()
                
                return True
            
            else:
                # Running as Python script - update source files
                self.status_callback("מעדכן קבצי מקור...")
                
                # This would require extracting and replacing Python files
                # Implementation depends on your distribution method
                self.status_callback("עדכון קבצי מקור לא נתמך כרגע")
                return False
        
        except Exception as e:
            logger.error(f"Error installing update: {e}")
            self.status_callback(f"שגיאה בהתקנת עדכון: {e}")
            return False
    
    def _restart_application(self):
        """Restart the application after update."""
        try:
            self.status_callback("מאתחל את האפליקציה...")
            
            if getattr(sys, 'frozen', False):
                # Running as executable
                executable = sys.executable
                
                # Start new process and exit current one
                subprocess.Popen([executable], 
                               cwd=os.path.dirname(executable),
                               creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0)
                
                # Exit current process after a short delay
                def delayed_exit():
                    time.sleep(2)
                    os._exit(0)
                
                threading.Thread(target=delayed_exit, daemon=True).start()
            
            else:
                # Running as Python script
                python = sys.executable
                subprocess.Popen([python] + sys.argv)
                os._exit(0)
                
        except Exception as e:
            logger.error(f"Error restarting application: {e}")
            self.status_callback(f"שגיאה באתחול האפליקציה: {e}")
    
    def get_update_settings(self):
        """Get current update settings."""
        return self.settings.copy()
    
    def update_settings(self, new_settings):
        """Update settings."""
        self.settings.update(new_settings)
        self._save_update_settings()
    
    def _get_github_token(self):
        """Get GitHub token for private repo access."""
        # Method 1: From environment variable
        import os
        token = os.environ.get('GITHUB_TOKEN')
        if token:
            return token
        
        # Method 2: From settings file
        token = self.settings.get('github_token')
        if token:
            return token
        
        # Method 3: From separate token file (more secure)
        try:
            token_file = Path(self.app_directory) / ".github_token"
            if token_file.exists():
                with open(token_file, 'r') as f:
                    return f.read().strip()
        except Exception:
            pass
        
        return None
    
    def set_github_token(self, token):
        """Set GitHub token for private repo access."""
        if token:
            # Store in settings (encrypted in production)
            self.settings['github_token'] = token
            self._save_update_settings()
            self.status_callback("GitHub token configured successfully")
        else:
            # Remove token
            if 'github_token' in self.settings:
                del self.settings['github_token']
                self._save_update_settings()
            self.status_callback("GitHub token removed")