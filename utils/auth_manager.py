"""
Authentication and license management for IDF Reader application.
Supports freemium model with online license validation.
"""

import os
import json
import time
import hashlib
import requests
from datetime import datetime, timedelta
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
import uuid

from utils.logging_config import get_logger

logger = get_logger(__name__)

class AuthManager:
    """Manages user authentication and license validation."""
    
    def __init__(self, status_callback=None):
        self.status_callback = status_callback or self._default_status
        self.auth_file = Path("auth_data.json")
        self.usage_file = Path("usage_data.json")
        
        # License server configuration
        self.license_server = "https://your-license-server.com/api"  # Replace with your server
        
        # Load stored authentication data
        self.auth_data = self._load_auth_data()
        self.usage_data = self._load_usage_data()
        
        # Generate unique device ID
        self.device_id = self._get_device_id()
    
    def _default_status(self, message):
        logger.info(f"Auth: {message}")
    
    def _load_auth_data(self):
        """Load stored authentication data."""
        default_auth = {
            "user_id": None,
            "email": None,
            "license_key": None,
            "license_type": "free",  # free, pro, enterprise
            "license_expires": None,
            "last_validation": 0,
            "validation_token": None,
            "offline_days_remaining": 0
        }
        
        try:
            if self.auth_file.exists():
                with open(self.auth_file, 'r', encoding='utf-8') as f:
                    loaded_auth = json.load(f)
                    default_auth.update(loaded_auth)
        except Exception as e:
            logger.warning(f"Could not load auth data: {e}")
        
        return default_auth
    
    def _load_usage_data(self):
        """Load usage tracking data."""
        default_usage = {
            "daily_idf_count": 0,
            "last_reset_date": datetime.now().date().isoformat(),
            "total_files_processed": 0,
            "features_used": []
        }
        
        try:
            if self.usage_file.exists():
                with open(self.usage_file, 'r', encoding='utf-8') as f:
                    loaded_usage = json.load(f)
                    default_usage.update(loaded_usage)
        except Exception as e:
            logger.warning(f"Could not load usage data: {e}")
        
        return default_usage
    
    def _save_auth_data(self):
        """Save authentication data to file."""
        try:
            with open(self.auth_file, 'w', encoding='utf-8') as f:
                json.dump(self.auth_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Could not save auth data: {e}")
    
    def _save_usage_data(self):
        """Save usage data to file."""
        try:
            with open(self.usage_file, 'w', encoding='utf-8') as f:
                json.dump(self.usage_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Could not save usage data: {e}")
    
    def _get_device_id(self):
        """Get unique device identifier."""
        try:
            # Use MAC address and computer name for device ID
            import uuid
            mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff) 
                           for elements in range(0,2*6,2)][::-1])
            computer_name = os.environ.get('COMPUTERNAME', 'unknown')
            device_string = f"{mac}-{computer_name}"
            return hashlib.sha256(device_string.encode()).hexdigest()[:16]
        except Exception:
            # Fallback to random ID
            return hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()[:16]
    
    def is_authenticated(self):
        """Check if user is authenticated with valid license."""
        return self.auth_data.get("license_type") != "free" and self._is_license_valid()
    
    def get_license_type(self):
        """Get current license type."""
        return self.auth_data.get("license_type", "free")
    
    def get_user_info(self):
        """Get current user information."""
        return {
            "email": self.auth_data.get("email"),
            "license_type": self.auth_data.get("license_type", "free"),
            "expires": self.auth_data.get("license_expires"),
            "offline_days": self.auth_data.get("offline_days_remaining", 0)
        }
    
    def _is_license_valid(self):
        """Check if current license is valid."""
        license_type = self.auth_data.get("license_type", "free")
        
        if license_type == "free":
            return True  # Free is always "valid" but limited
        
        # Check expiration
        expires = self.auth_data.get("license_expires")
        if expires:
            expiry_date = datetime.fromisoformat(expires)
            if datetime.now() > expiry_date:
                self.status_callback("הרישיון פג תוקף")
                return False
        
        # Check if we need online validation
        last_validation = self.auth_data.get("last_validation", 0)
        days_since_validation = (time.time() - last_validation) / (24 * 3600)
        
        if days_since_validation > 7:  # Validate every 7 days
            return self._validate_license_online()
        
        return True
    
    def _validate_license_online(self):
        """Validate license with online server."""
        try:
            license_key = self.auth_data.get("license_key")
            if not license_key:
                return False
            
            # Prepare validation request
            validation_data = {
                "license_key": license_key,
                "device_id": self.device_id,
                "app_version": "1.0.3"  # Current version
            }
            
            # Make request to license server
            response = self._make_license_request("/validate", validation_data)
            
            if response and response.get("valid"):
                # Update auth data with server response
                self.auth_data["last_validation"] = time.time()
                self.auth_data["license_type"] = response.get("license_type", "free")
                self.auth_data["license_expires"] = response.get("expires")
                self.auth_data["offline_days_remaining"] = response.get("offline_days", 30)
                self._save_auth_data()
                
                self.status_callback("הרישיון אומת בהצלחה")
                return True
            else:
                self.status_callback("אימות הרישיון נכשל")
                return False
                
        except Exception as e:
            logger.warning(f"Online validation failed: {e}")
            # Allow offline usage for limited time
            offline_days = self.auth_data.get("offline_days_remaining", 0)
            if offline_days > 0:
                self.auth_data["offline_days_remaining"] = offline_days - 1
                self._save_auth_data()
                self.status_callback(f"מצב לא מקוון - {offline_days-1} ימים נותרו")
                return True
            else:
                self.status_callback("נדרש חיבור לאינטרנט לאימות הרישיון")
                return False
    
    def _make_license_request(self, endpoint, data):
        """Make HTTP request to license server."""
        try:
            url = f"{self.license_server}{endpoint}"
            
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'IDF-Reader/1.0.3'
            }
            
            json_data = json.dumps(data).encode('utf-8')
            request = Request(url, data=json_data, headers=headers)
            
            with urlopen(request, timeout=10) as response:
                return json.loads(response.read().decode('utf-8'))
                
        except (URLError, HTTPError, json.JSONDecodeError) as e:
            logger.debug(f"License server request failed: {e}")
            return None
    
    def login_with_license_key(self, license_key, email=None):
        """Login with license key."""
        try:
            self.status_callback("מאמת רישיון...")
            
            # Validate license key format
            if not license_key or len(license_key) < 20:
                self.status_callback("מפתח רישיון לא תקין")
                return False
            
            # Try to validate with server
            validation_data = {
                "license_key": license_key,
                "device_id": self.device_id,
                "email": email
            }
            
            response = self._make_license_request("/activate", validation_data)
            
            if response and response.get("valid"):
                # Save license information
                self.auth_data.update({
                    "license_key": license_key,
                    "email": email or response.get("email"),
                    "user_id": response.get("user_id"),
                    "license_type": response.get("license_type", "pro"),
                    "license_expires": response.get("expires"),
                    "last_validation": time.time(),
                    "validation_token": response.get("token"),
                    "offline_days_remaining": response.get("offline_days", 30)
                })
                
                self._save_auth_data()
                self.status_callback(f"התחברת בהצלחה! רישיון: {self.auth_data['license_type']}")
                return True
            else:
                error_msg = response.get("error", "רישיון לא תקין") if response else "שגיאה בחיבור לשרת"
                self.status_callback(f"כישלון באימות: {error_msg}")
                return False
                
        except Exception as e:
            logger.error(f"Login failed: {e}")
            self.status_callback(f"שגיאה בהתחברות: {e}")
            return False
    
    def logout(self):
        """Logout and reset to free tier."""
        try:
            # Notify server about logout
            if self.auth_data.get("license_key"):
                logout_data = {
                    "license_key": self.auth_data["license_key"],
                    "device_id": self.device_id
                }
                self._make_license_request("/deactivate", logout_data)
            
            # Reset auth data
            self.auth_data = {
                "user_id": None,
                "email": None,
                "license_key": None,
                "license_type": "free",
                "license_expires": None,
                "last_validation": 0,
                "validation_token": None,
                "offline_days_remaining": 0
            }
            
            self._save_auth_data()
            self.status_callback("התנתקת בהצלחה")
            return True
            
        except Exception as e:
            logger.error(f"Logout error: {e}")
            return False
    
    def check_usage_limits(self, feature_name="idf_processing"):
        """Check if user can use a feature based on their license and usage."""
        license_type = self.get_license_type()
        
        # Reset daily counter if needed
        self._reset_daily_usage_if_needed()
        
        if license_type in ["pro", "enterprise"]:
            return True  # Unlimited usage
        
        # Free tier limitations
        if feature_name == "idf_processing":
            daily_limit = 3
            current_count = self.usage_data.get("daily_idf_count", 0)
            
            if current_count >= daily_limit:
                self.status_callback(f"הגעת למגבלה היומית ({daily_limit} קבצי IDF ביום). שדרג לחבילת Pro לשימוש ללא הגבלה.")
                return False
            
            return True
        
        elif feature_name == "energy_rating":
            self.status_callback("דיווח דירוג אנרגיה זמין רק בחבילת Pro")
            return False
        
        elif feature_name == "advanced_reports":
            self.status_callback("דוחות מתקדמים זמינים רק בחבילת Pro")
            return False
        
        return True
    
    def record_usage(self, feature_name="idf_processing"):
        """Record feature usage."""
        self._reset_daily_usage_if_needed()
        
        if feature_name == "idf_processing":
            self.usage_data["daily_idf_count"] += 1
            self.usage_data["total_files_processed"] += 1
        
        # Track features used
        features_used = self.usage_data.get("features_used", [])
        if feature_name not in features_used:
            features_used.append(feature_name)
            self.usage_data["features_used"] = features_used
        
        self._save_usage_data()
    
    def _reset_daily_usage_if_needed(self):
        """Reset daily usage counters if it's a new day."""
        today = datetime.now().date().isoformat()
        last_reset = self.usage_data.get("last_reset_date")
        
        if last_reset != today:
            self.usage_data["daily_idf_count"] = 0
            self.usage_data["last_reset_date"] = today
            self._save_usage_data()
    
    def get_usage_stats(self):
        """Get current usage statistics."""
        self._reset_daily_usage_if_needed()
        
        license_type = self.get_license_type()
        daily_limit = "ללא הגבלה" if license_type in ["pro", "enterprise"] else "3"
        daily_used = self.usage_data.get("daily_idf_count", 0)
        
        return {
            "license_type": license_type,
            "daily_used": daily_used,
            "daily_limit": daily_limit,
            "total_processed": self.usage_data.get("total_files_processed", 0),
            "features_used": self.usage_data.get("features_used", [])
        }
    
    def get_upgrade_url(self):
        """Get URL for license upgrade."""
        return "https://your-website.com/upgrade"  # Replace with your payment page