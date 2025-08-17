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
    def __init__(self, status_callback=None, update_available_callback=None):
        """
        Initialize the update manager.
        
        Args:
            status_callback: Function to call for status updates
            update_available_callback: Function to call when update is available
        """
        self.status_callback = status_callback or self._default_status
        self.update_available_callback = update_available_callback
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
            logger.info("Update check already in progress, skipping")
            return
        
        if not force and not self.should_check_for_updates():
            logger.debug("Skipping update check - not time yet")
            return
        
        def check_worker():
            try:
                update_info = self.check_for_updates(force=force)
                if update_info:
                    logger.info(f"Update found in background check: {update_info.get('version')}")
                    # Trigger update notification in UI if callback is available
                    if hasattr(self, 'update_available_callback') and callable(self.update_available_callback):
                        self.update_available_callback(update_info)
            except Exception as e:
                logger.error(f"Error in background update check: {e}")
                # Don't show error status for background checks to avoid disturbing user
        
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
            self.status_callback("בודק GitHub לעדכונים...")
            update_info = self._check_github_releases()
            
            if not update_info:
                # Fallback to custom update server
                self.status_callback("בודק שרת עדכונים מותאם אישית...")
                update_info = self._check_custom_server()
            
            if update_info:
                new_version = update_info.get("version")
                if new_version and compare_versions(self.current_version, new_version) < 0:
                    self.status_callback(f"עדכון זמין: גרסה {new_version}")
                    logger.info(f"Update available: {self.current_version} -> {new_version}")
                    return update_info
                else:
                    self.status_callback("האפליקציה מעודכנת לגרסה האחרונה")
                    logger.info("Application is up to date")
            else:
                self.status_callback("לא נמצאו עדכונים זמינים או שגיאה בחיבור לשרת")
        
        except Exception as e:
            logger.error(f"Error checking for updates: {e}")
            self.status_callback(f"שגיאה בבדיקת עדכונים: {e}")
        
        return None
    
    def _check_github_releases(self):
        """Check GitHub releases for updates."""
        try:
            from urllib.request import Request
            
            # Create SSL context that works on Windows
            ssl_context = ssl.create_default_context()
            
            # Create request headers (no authentication needed for public repos)
            headers = {
                'User-Agent': 'IDF-Reader-Auto-Updater/1.0',
                'Accept': 'application/vnd.github.v3+json'
            }
            
            request = Request(GITHUB_RELEASES_URL, headers=headers)
            
            with urlopen(request, timeout=15, context=ssl_context) as response:
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
            logger.error(f"GitHub releases check failed: {e}")
            self.status_callback(f"שגיאה בבדיקת GitHub: {e}")
        
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
            last_reported_percent = -1  # Track last reported percentage
            
            def progress_hook(block_num, block_size, total_size):
                nonlocal last_reported_percent
                if total_size > 0:
                    percent = min(100, (block_num * block_size * 100) // total_size)
                    
                    # Only report progress every 10% to avoid spamming the UI
                    # Report 100% only once when reached for the first time
                    if percent >= last_reported_percent + 10 or (percent == 100 and last_reported_percent < 100):
                        last_reported_percent = percent
                        self.status_callback(f"מוריד... {percent}%")
            
            urlretrieve(url, destination, reporthook=progress_hook)
            self.status_callback("ההורדה הושלמה")
            
        except Exception as e:
            raise Exception(f"כשל בהורדת הקובץ: {e}")
    
    def _install_update(self, update_executable, restart_callback=None):
        """Install the downloaded update using a safe method."""
        try:
            self.status_callback("מתקין עדכון...")
            
            # Get current executable path
            if getattr(sys, 'frozen', False):
                # Running as compiled executable
                current_exe = Path(sys.executable)
                backup_exe = current_exe.with_suffix('.bak')
                
                # Use a safer update method that works with locked files
                return self._install_executable_update(current_exe, backup_exe, update_executable, restart_callback)
            
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
    
    def _install_executable_update(self, current_exe, backup_exe, update_executable, restart_callback):
        """Install executable update using batch script method to handle file locking."""
        try:
            # Create a batch script that will:
            # 1. Wait for current process to exit
            # 2. Backup current executable
            # 3. Replace with new executable  
            # 4. Start new executable
            # 5. Clean up batch script
            
            batch_script = current_exe.parent / "update_installer.bat"
            new_exe_temp = current_exe.parent / f"new_{current_exe.name}"
            
            # Copy new executable to temporary location
            shutil.copy2(update_executable, new_exe_temp)
            self.status_callback("הועתק קובץ עדכון זמני")
            
            # Create batch script content
            batch_content = f'''@echo off
title IDF Reader Update Installer
echo Installing IDF Reader update...

REM Wait for main process to exit (PID: {os.getpid()})
:wait_for_exit
tasklist /FI "PID eq {os.getpid()}" 2>NUL | find /I /N "{os.getpid()}" >NUL
if "%ERRORLEVEL%" == "0" (
    timeout /t 1 /nobreak >NUL
    goto wait_for_exit
)

echo Main process exited, proceeding with update...

REM Create backup of current executable
if exist "{current_exe}" (
    echo Creating backup...
    copy "{current_exe}" "{backup_exe}" >NUL
    if errorlevel 1 (
        echo ERROR: Failed to create backup
        pause
        exit /b 1
    )
    echo Backup created successfully
)

REM Replace executable with new version
echo Installing new version...
move "{new_exe_temp}" "{current_exe}" >NUL
if errorlevel 1 (
    echo ERROR: Failed to install new version
    echo Restoring backup...
    if exist "{backup_exe}" (
        copy "{backup_exe}" "{current_exe}" >NUL
    )
    pause
    exit /b 1
)

echo Update installed successfully!

REM Start new version
echo Starting updated application...
start "" "{current_exe}"

REM Clean up
timeout /t 2 /nobreak >NUL
if exist "{backup_exe}" del "{backup_exe}" >NUL

REM Self-destruct (delete this batch file)
(goto) 2>nul & del "%~f0"
'''
            
            # Write batch script
            with open(batch_script, 'w', encoding='utf-8') as f:
                f.write(batch_content)
            
            self.status_callback("נוצר מתקין עדכון")
            
            # Start batch script in background
            subprocess.Popen([str(batch_script)], 
                           cwd=str(current_exe.parent),
                           creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            
            self.status_callback("עדכון יותקן לאחר סגירת האפליקציה...")
            
            # Schedule application exit
            if restart_callback:
                restart_callback()
            else:
                # Exit after short delay to allow batch script to start
                def delayed_exit():
                    time.sleep(3)
                    os._exit(0)
                
                threading.Thread(target=delayed_exit, daemon=True).start()
            
            return True
            
        except Exception as e:
            logger.error(f"Error in executable update: {e}")
            self.status_callback(f"שגיאה בעדכון קובץ הפעלה: {e}")
            
            # Clean up temporary files on error
            try:
                if 'new_exe_temp' in locals() and Path(new_exe_temp).exists():
                    Path(new_exe_temp).unlink()
                if 'batch_script' in locals() and Path(batch_script).exists():
                    Path(batch_script).unlink()
            except:
                pass
            
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