"""
License Management System for IDF Reader
Direct MongoDB connection - no server required.
"""

import hashlib
import hmac
import json
import os
import platform
import socket
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Tuple, Any
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

from utils.logging_config import get_logger

logger = get_logger(__name__)

class LicenseManager:
    """Manages software licensing with direct MongoDB validation."""
    
    # License types
    LICENSE_FREE = "free"
    LICENSE_PROFESSIONAL = "professional"
    LICENSE_ENTERPRISE = "enterprise"
    
    # License status
    STATUS_VALID = "valid"
    STATUS_EXPIRED = "expired"
    STATUS_INVALID = "invalid"
    STATUS_TRIAL = "trial"
    STATUS_BLACKLISTED = "blacklisted"
    
    def __init__(self):
        self.app_data_dir = self._get_app_data_dir()
        self.license_file = self.app_data_dir / "license.dat"
        self.machine_id = self._generate_machine_id()
        
        # Secret key for encryption
        self.secret_key = b"IDF_READER_SECRET_KEY_CHANGE_IN_PRODUCTION"
        self.cipher = self._create_cipher()
        
        # Create app data directory
        self.app_data_dir.mkdir(parents=True, exist_ok=True)
        
        # Database connection will be lazy-loaded
        self._db = None
    
    def _get_database(self):
        """Get database connection (lazy loading)."""
        if self._db is None:
            try:
                from database.mongo_license_db import get_license_db
                self._db = get_license_db()
                logger.info("Connected to license database")
            except Exception as e:
                logger.error(f"Failed to connect to database: {e}")
                raise
        return self._db
    
    def _get_app_data_dir(self) -> Path:
        """Get application data directory."""
        if platform.system() == "Windows":
            app_data = os.getenv("APPDATA", os.path.expanduser("~"))
            return Path(app_data) / "IDF Reader"
        else:
            return Path.home() / ".idf-reader"
    
    def _create_cipher(self) -> Fernet:
        """Create encryption cipher for license data."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'idf_reader_salt',
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(self.secret_key))
        return Fernet(key)
    
    def _generate_machine_id(self) -> str:
        """Generate unique machine identifier."""
        try:
            # Get machine-specific info
            machine_info = [
                platform.machine(),
                platform.processor(),
                platform.system(),
                socket.gethostname(),
                str(uuid.getnode()),  # MAC address
            ]
            
            # Create hash
            machine_string = "|".join(machine_info)
            machine_hash = hashlib.sha256(machine_string.encode()).hexdigest()
            return machine_hash[:16].upper()
            
        except Exception as e:
            logger.warning(f"Could not generate machine ID: {e}")
            # Fallback to MAC address only
            return str(uuid.getnode())[:16].upper()
    
    def generate_serial_key(self, license_type: str, days_valid: int = 365, 
                           user_email: str = "", max_activations: int = 3) -> str:
        """
        Generate a new serial key.
        
        Args:
            license_type: Type of license (professional, enterprise)
            days_valid: Number of days the license is valid
            user_email: User's email address
            max_activations: Maximum number of machine activations
            
        Returns:
            Generated serial key in format XXXX-XXXX-XXXX-XXXX
        """
        # Key components
        created_time = datetime.now()
        key_data = {
            "type": license_type,
            "expires": (created_time + timedelta(days=days_valid)).isoformat(),
            "email": user_email,
            "max_activations": max_activations,
            "created": created_time.isoformat(),
            "version": "1.0"
        }
        
        # Create checksum
        key_string = json.dumps(key_data, sort_keys=True)
        checksum = hmac.new(
            self.secret_key,
            key_string.encode(),
            hashlib.sha256
        ).hexdigest()[:8].upper()
        
        # Generate base key
        base_key = hashlib.sha256(
            (key_string + checksum).encode()
        ).hexdigest()[:12].upper()
        
        # Format as XXXX-XXXX-XXXX-XXXX
        formatted_key = f"{base_key[:4]}-{base_key[4:8]}-{base_key[8:12]}-{checksum[:4]}"
        
        # Store generation parameters for validation (in memory cache for testing)
        if not hasattr(self, '_generated_keys'):
            self._generated_keys = {}
        self._generated_keys[formatted_key] = key_data
        
        logger.info(f"Generated key for {license_type} license: {formatted_key}")
        return formatted_key
    
    def validate_serial_key(self, serial_key: str, force_online: bool = False) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate a serial key with proper error handling and user feedback.
        
        Args:
            serial_key: Serial key to validate
            force_online: Force database validation (ignore cache)
            
        Returns:
            Tuple of (is_valid, license_info)
        """
        try:
            # Check for development keys first (before length validation)
            if self._is_development_key(serial_key):
                logger.info(f"Development key detected early: {serial_key}")
                license_info = {
                    "type": self.LICENSE_PROFESSIONAL,
                    "expires": (datetime.now() + timedelta(days=365)).isoformat(),
                    "status": self.STATUS_VALID,
                    "features": {
                        "unlimited_files": True,
                        "all_reports": True,
                        "export_excel": True,
                        "energy_rating": True,
                        "advanced_analysis": True,
                        "priority_support": True
                    },
                    "validated_online": False,
                    "last_check": datetime.now().isoformat(),
                    "max_activations": 3,
                    "current_activations": 1
                }
                return True, license_info
            
            # Clean and format key for normal validation
            clean_key = serial_key.replace("-", "").replace(" ", "").upper()
            if len(clean_key) != 16:
                logger.warning(f"Invalid key length: {len(clean_key)} (expected 16)")
                return False, {"error": "Invalid key format - must be 16 characters"}
            
            # Validate that key contains only alphanumeric characters
            if not clean_key.isalnum():
                logger.warning(f"Invalid key contains non-alphanumeric characters")
                return False, {"error": "Invalid key format - only letters and numbers allowed"}
            
            formatted_key = f"{clean_key[:4]}-{clean_key[4:8]}-{clean_key[8:12]}-{clean_key[12:16]}"
            logger.info(f"Validating formatted key: {formatted_key[:8]}...")
            
            # Try database validation first
            if force_online or self._should_validate_online():
                db_result = self._validate_database(formatted_key)
                if db_result[0]:
                    self._cache_license(formatted_key, db_result[1])
                    return db_result
                else:
                    logger.warning(f"Database validation failed: {db_result[1].get('error', 'Unknown error')}")
                    # Continue to try other validation methods
            
            # Try cached validation
            cached_result = self._validate_cached(formatted_key)
            if cached_result[0]:
                return cached_result
            else:
                logger.warning(f"Cached validation failed: {cached_result[1].get('error', 'No cache or invalid')}")
            
            # Last resort: try local validation for test keys
            local_result = self._validate_local_key(formatted_key)
            if local_result[0]:
                # Cache the local validation result too
                self._cache_license(formatted_key, local_result[1])
                return local_result
            else:
                logger.warning(f"Local validation failed: {local_result[1].get('error', 'Invalid key')}")
            
            # All validation methods failed
            logger.error(f"All validation methods failed for key: {formatted_key[:8]}...")
            return False, {"error": "Invalid license key - not found in database or cache"}
            
        except Exception as e:
            logger.error(f"License validation error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False, {"error": f"License validation failed: {str(e)}"}
    
    def _validate_database(self, serial_key: str) -> Tuple[bool, Dict[str, Any]]:
        """Validate key against MongoDB database."""
        try:
            db = self._get_database()
            
            # Validate license using database
            is_valid, license_data = db.validate_license(
                serial_key=serial_key,
                machine_id=self.machine_id,
                platform=platform.system(),
                version="1.0.0"
            )
            
            if is_valid:
                license_info = {
                    "type": license_data.get("license_type", self.LICENSE_PROFESSIONAL),
                    "expires": license_data.get("expires"),
                    "status": self.STATUS_VALID,
                    "features": license_data.get("features", {}),
                    "validated_online": True,
                    "last_check": datetime.now().isoformat(),
                    "max_activations": license_data.get("max_activations", 3),
                    "current_activations": license_data.get("current_activations", 0)
                }
                
                logger.info(f"License validated successfully: {serial_key}")
                return True, license_info
            else:
                error_msg = license_data.get("error", "Invalid license")
                logger.warning(f"License validation failed: {error_msg}")
                return False, {"error": error_msg}
                
        except Exception as e:
            logger.error(f"Database validation error: {e}")
            return False, {"error": f"Database validation failed: {str(e)}"}
    
    def _validate_cached(self, serial_key: str) -> Tuple[bool, Dict[str, Any]]:
        """Validate key using cached license data."""
        try:
            if not self.license_file.exists():
                return False, {"error": "No cached license found"}
            
            # Read and decrypt license data
            encrypted_data = self.license_file.read_bytes()
            decrypted_data = self.cipher.decrypt(encrypted_data)
            license_data = json.loads(decrypted_data.decode())
            
            # Check if this is the same key
            if license_data.get("serial_key") != serial_key:
                return False, {"error": "Key mismatch"}
            
            # Check machine ID
            if license_data.get("machine_id") != self.machine_id:
                return False, {"error": "Machine mismatch"}
            
            # Check expiration
            expires_str = license_data.get("expires")
            if expires_str:
                expires = datetime.fromisoformat(expires_str)
                if datetime.now() > expires:
                    return False, {"error": "License expired", "status": self.STATUS_EXPIRED}
            
            # Valid cached license
            license_info = {
                "type": license_data.get("type", self.LICENSE_PROFESSIONAL),
                "expires": expires_str,
                "status": self.STATUS_VALID,
                "features": license_data.get("features", {}),
                "validated_online": False,
                "last_check": license_data.get("last_check"),
                "max_activations": license_data.get("max_activations", 3),
                "current_activations": license_data.get("current_activations", 0)
            }
            
            logger.info("License validated from cache")
            return True, license_info
            
        except Exception as e:
            logger.error(f"Cached validation error: {e}")
            return False, {"error": "Cache validation failed"}
    
    def _validate_local_key(self, serial_key: str) -> Tuple[bool, Dict[str, Any]]:
        """Validate locally generated test keys with proper validation."""
        try:
            logger.info(f"Validating local key: {serial_key}")
            
            # Extract components from the key
            parts = serial_key.split('-')
            if len(parts) != 4:
                return False, {"error": "Invalid key format"}
            
            base_key = ''.join(parts[:3])
            provided_checksum = parts[3]
            
            # Validate key format
            if len(base_key) != 12 or len(provided_checksum) != 4:
                return False, {"error": "Invalid key format"}
            
            # First, check if this key was recently generated by us (for testing)
            if hasattr(self, '_generated_keys') and serial_key in self._generated_keys:
                key_data = self._generated_keys[serial_key]
                logger.info(f"Found key in generated keys cache: {serial_key}")
                
                license_info = {
                    "type": key_data["type"],
                    "expires": key_data["expires"],
                    "status": self.STATUS_VALID,
                    "features": {
                        "unlimited_files": True,
                        "all_reports": True,
                        "export_excel": True,
                        "energy_rating": True,
                        "advanced_analysis": True,
                        "priority_support": True
                    },
                    "validated_online": False,
                    "last_check": datetime.now().isoformat(),
                    "max_activations": key_data.get("max_activations", 3),
                    "current_activations": 1
                }
                
                return True, license_info
            
            # Try to reverse-validate the key by testing different combinations
            license_types = [self.LICENSE_PROFESSIONAL, self.LICENSE_ENTERPRISE]
            day_ranges = [30, 90, 365, 1095]  # Common license durations
            emails = ["test@example.com", "", "user@domain.com"]
            
            # Get current time and try different time windows (keys might be generated recently)
            base_time = datetime.now()
            time_windows = [
                base_time,
                base_time - timedelta(seconds=30),
                base_time - timedelta(minutes=1),
                base_time - timedelta(minutes=5),
                base_time - timedelta(hours=1)
            ]
            
            for license_type in license_types:
                for days in day_ranges:
                    for email in emails:
                        for created_time in time_windows:
                            # Test this combination
                            test_data = {
                                "type": license_type,
                                "expires": (created_time + timedelta(days=days)).isoformat(),
                                "email": email,
                                "max_activations": 3,
                                "created": created_time.isoformat(),
                                "version": "1.0"
                            }
                            
                            # Generate what the key should be for this data
                            key_string = json.dumps(test_data, sort_keys=True)
                            test_checksum = hmac.new(
                                self.secret_key,
                                key_string.encode(),
                                hashlib.sha256
                            ).hexdigest()[:8].upper()
                            
                            test_base_key = hashlib.sha256(
                                (key_string + test_checksum).encode()
                            ).hexdigest()[:12].upper()
                            
                            # Check if this matches our key
                            if base_key == test_base_key and provided_checksum == test_checksum[:4]:
                                license_info = {
                                    "type": license_type,
                                    "expires": test_data["expires"],
                                    "status": self.STATUS_VALID,
                                    "features": {
                                        "unlimited_files": True,
                                        "all_reports": True,
                                        "export_excel": True,
                                        "energy_rating": True,
                                        "advanced_analysis": True,
                                        "priority_support": True
                                    },
                                    "validated_online": False,
                                    "last_check": datetime.now().isoformat(),
                                    "max_activations": 3,
                                    "current_activations": 1
                                }
                                
                                return True, license_info
            
            # Check for development keys (only specific prefixes)
            if self._is_development_key(serial_key):
                logger.info(f"Development key detected: {serial_key}")
                license_info = {
                    "type": self.LICENSE_PROFESSIONAL,
                    "expires": (datetime.now() + timedelta(days=365)).isoformat(),
                    "status": self.STATUS_VALID,
                    "features": {
                        "unlimited_files": True,
                        "all_reports": True,
                        "export_excel": True,
                        "energy_rating": True,
                        "advanced_analysis": True,
                        "priority_support": True
                    },
                    "validated_online": False,
                    "last_check": datetime.now().isoformat(),
                    "max_activations": 3,
                    "current_activations": 1
                }
                return True, license_info
            
            # If no pattern matches, the key is invalid
            logger.warning(f"Local key validation failed - invalid key: {serial_key}")
            return False, {"error": "Invalid license key"}
            
        except Exception as e:
            logger.error(f"Local key validation error: {e}")
            return False, {"error": f"Local validation failed: {str(e)}"}
    
    def _is_development_key(self, serial_key: str) -> bool:
        """Check if this is a development/test key with strict validation."""
        try:
            # Development keys: check for specific patterns only
            dev_patterns = [
                "TEST-",
                "DEV-",
                "DEMO-"
            ]
            
            # Check if key starts with any development pattern
            for pattern in dev_patterns:
                if serial_key.upper().startswith(pattern):
                    return True
            
            # Do NOT accept arbitrary well-formed keys as development keys
            # This was the security vulnerability - any 16-char key was accepted
            # Only accept keys that start with specific development prefixes
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking development key: {e}")
            return False
    
    def _cache_license(self, serial_key: str, license_info: Dict[str, Any]) -> None:
        """Cache license information locally."""
        try:
            cache_data = {
                "serial_key": serial_key,
                "machine_id": self.machine_id,
                "type": license_info.get("type"),
                "expires": license_info.get("expires"),
                "features": license_info.get("features"),
                "max_activations": license_info.get("max_activations"),
                "current_activations": license_info.get("current_activations"),
                "last_check": datetime.now().isoformat(),
                "cached_at": datetime.now().isoformat()
            }
            
            # Encrypt and save
            json_data = json.dumps(cache_data)
            encrypted_data = self.cipher.encrypt(json_data.encode())
            self.license_file.write_bytes(encrypted_data)
            
            logger.info("License cached successfully")
            
        except Exception as e:
            logger.error(f"License caching error: {e}")
    
    def _should_validate_online(self) -> bool:
        """Check if database validation is needed."""
        try:
            if not self.license_file.exists():
                return True
            
            # Read last check time
            encrypted_data = self.license_file.read_bytes()
            decrypted_data = self.cipher.decrypt(encrypted_data)
            license_data = json.loads(decrypted_data.decode())
            
            last_check_str = license_data.get("last_check")
            if not last_check_str:
                return True
            
            last_check = datetime.fromisoformat(last_check_str)
            # Validate against database once per week
            return datetime.now() - last_check > timedelta(days=7)
            
        except Exception:
            return True
    
    def get_license_status(self) -> Dict[str, Any]:
        """Get current license status."""
        logger.info(f"License file path: {self.license_file}")
        logger.info(f"License file exists: {self.license_file.exists()}")
        
        try:
            if not self.license_file.exists():
                status_result = {
                    "status": "unlicensed",
                    "type": "unlicensed",
                    "message": "License required - please activate your license"
                }
                logger.info(f"No license file - returning: {status_result}")
                return status_result
            
            # Read license data
            encrypted_data = self.license_file.read_bytes()
            decrypted_data = self.cipher.decrypt(encrypted_data)
            license_data = json.loads(decrypted_data.decode())
            
            # Check expiration
            expires_str = license_data.get("expires")
            if expires_str:
                expires = datetime.fromisoformat(expires_str)
                if datetime.now() > expires:
                    return {
                        "status": self.STATUS_EXPIRED,
                        "type": license_data.get("type"),
                        "expires": expires_str,
                        "message": "License expired"
                    }
            
            return {
                "status": self.STATUS_VALID,
                "type": license_data.get("type", self.LICENSE_PROFESSIONAL),
                "expires": expires_str,
                "features": license_data.get("features", {}),
                "last_check": license_data.get("last_check"),
                "max_activations": license_data.get("max_activations", 3),
                "current_activations": license_data.get("current_activations", 0),
                "message": "License active"
            }
            
        except Exception as e:
            logger.error(f"License status error: {e}")
            return {
                "status": "error", 
                "type": "unlicensed",
                "message": f"License check failed: {e}"
            }
    
    def activate_license(self, serial_key: str) -> Tuple[bool, str]:
        """
        Activate a license with a serial key with detailed feedback.
        
        Args:
            serial_key: Serial key to activate
            
        Returns:
            Tuple of (success, message)
        """
        try:
            logger.info(f"Attempting to activate key: {serial_key[:8] if serial_key else 'None'}...")
            
            # Basic validation
            if not serial_key or not serial_key.strip():
                logger.warning("Empty serial key provided")
                return False, "Please enter a license key"
            
            # Validate the key
            is_valid, license_info = self.validate_serial_key(serial_key, force_online=True)
            
            if is_valid:
                license_type = license_info.get("type", "professional")
                expires = license_info.get("expires")
                
                if expires:
                    from datetime import datetime
                    try:
                        exp_date = datetime.fromisoformat(expires)
                        expires_text = exp_date.strftime("%d/%m/%Y")
                        success_msg = f"License activated successfully! Type: {license_type}, Valid until: {expires_text}"
                    except:
                        success_msg = f"License activated successfully! Type: {license_type}"
                else:
                    success_msg = f"License activated successfully! Type: {license_type}"
                
                logger.info(f"LICENSE ACTIVATION SUCCESSFUL: {success_msg}")
                return True, success_msg
            else:
                error_msg = license_info.get("error", "Unknown validation error")
                logger.error(f"LICENSE ACTIVATION FAILED: {error_msg}")
                
                # Provide more specific error messages
                if "Invalid key format" in error_msg:
                    return False, "Invalid license key format. Please check your key and try again."
                elif "not found" in error_msg.lower():
                    return False, "License key not found. Please verify your key is correct."
                elif "expired" in error_msg.lower():
                    return False, "This license key has expired. Please contact support for renewal."
                else:
                    return False, f"License activation failed: {error_msg}"
                
        except Exception as e:
            logger.error(f"License activation error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False, f"License activation error: {str(e)}"
    
    def deactivate_license(self) -> bool:
        """Deactivate current license."""
        try:
            if self.license_file.exists():
                self.license_file.unlink()
                logger.info("License deactivated")
                return True
        except Exception as e:
            logger.error(f"License deactivation error: {e}")
        return False
    
    def get_machine_id(self) -> str:
        """Get machine ID for licensing."""
        return self.machine_id
    
    def get_machine_info(self) -> Dict[str, str]:
        """Get detailed machine information for licensing."""
        try:
            machine_info = {
                "machine_id": self.machine_id,
                "machine": platform.machine(),
                "processor": platform.processor(),
                "system": platform.system(),
                "hostname": socket.gethostname(),
                "mac_address": str(uuid.getnode()),
                "full_string": f"{platform.machine()}|{platform.processor()}|{platform.system()}|{socket.gethostname()}|{uuid.getnode()}"
            }
            return machine_info
        except Exception as e:
            logger.error(f"Error getting machine info: {e}")
            return {"machine_id": self.machine_id, "error": str(e)}
    
    def is_feature_enabled(self, feature: str) -> bool:
        """Check if a specific feature is enabled by license."""
        status = self.get_license_status()
        
        if status["status"] != self.STATUS_VALID:
            # No license - no features enabled
            return False
        
        license_type = status.get("type", "")
        features = status.get("features", {})
        
        # Check specific feature enablement
        if feature in features:
            return features[feature]
        
        # Default feature sets by license type
        if license_type == self.LICENSE_PROFESSIONAL:
            return feature in [
                "unlimited_files", "all_reports", "export_excel", 
                "energy_rating", "advanced_analysis"
            ]
        elif license_type == self.LICENSE_ENTERPRISE:
            return True  # All features enabled
        
        # No valid license
        return False
    
    def check_daily_usage_limit(self) -> Tuple[bool, int, int]:
        """
        Check if daily usage limit is exceeded.
        
        Returns:
            Tuple of (can_use, used_today, limit)
        """
        status = self.get_license_status()
        
        if status["status"] != self.STATUS_VALID:
            # No license - cannot use
            return False, 0, 0
        
        license_type = status.get("type", "")
        
        if license_type in [self.LICENSE_PROFESSIONAL, self.LICENSE_ENTERPRISE]:
            # Unlimited usage for licensed users
            return True, 0, -1
        
        # No valid license
        return False, 0, 0


# Global license manager instance
license_manager = LicenseManager()


def check_license_on_startup() -> Tuple[bool, Dict[str, Any]]:
    """
    Check license status on application startup.
    
    Returns:
        Tuple of (can_continue, license_status)
    """
    try:
        status = license_manager.get_license_status()
        
        # Always allow UI to load - license check is handled by UI elements
        return True, status
            
    except Exception as e:
        logger.error(f"Startup license check failed: {e}")
        return True, {
            "status": "error",
            "type": "unlicensed", 
            "message": f"License check failed: {e}"
        }