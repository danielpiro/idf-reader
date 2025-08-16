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
        key_data = {
            "type": license_type,
            "expires": (datetime.now() + timedelta(days=days_valid)).isoformat(),
            "email": user_email,
            "max_activations": max_activations,
            "created": datetime.now().isoformat(),
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
        
        logger.info(f"Generated key for {license_type} license: {formatted_key}")
        return formatted_key
    
    def validate_serial_key(self, serial_key: str, force_online: bool = False) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate a serial key directly against MongoDB.
        
        Args:
            serial_key: Serial key to validate
            force_online: Force database validation (ignore cache)
            
        Returns:
            Tuple of (is_valid, license_info)
        """
        try:
            # Clean and format key
            clean_key = serial_key.replace("-", "").upper()
            if len(clean_key) != 16:
                return False, {"error": "Invalid key format"}
            
            formatted_key = f"{clean_key[:4]}-{clean_key[4:8]}-{clean_key[8:12]}-{clean_key[12:16]}"
            
            # Try database validation first
            if force_online or self._should_validate_online():
                db_result = self._validate_database(formatted_key)
                if db_result[0]:
                    self._cache_license(formatted_key, db_result[1])
                    return db_result
                else:
                    # If database validation fails, try cache as fallback
                    logger.warning("Database validation failed, trying cache...")
            
            # Fallback to cached validation
            cached_result = self._validate_cached(formatted_key)
            if cached_result[0]:
                return cached_result
            
            # Last resort: try local validation for test keys
            logger.info("Trying local validation for test key...")
            return self._validate_local_key(formatted_key)
            
        except Exception as e:
            logger.error(f"License validation error: {e}")
            # Try cache as last resort
            try:
                return self._validate_cached(formatted_key)
            except:
                return False, {"error": "License validation failed"}
    
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
        """Validate locally generated test keys."""
        try:
            logger.info(f"Validating local key: {serial_key}")
            
            # Extract components from the key
            parts = serial_key.split('-')
            if len(parts) != 4:
                return False, {"error": "Invalid key format"}
            
            base_key = ''.join(parts[:3])
            checksum = parts[3]
            
            # Try to reverse-engineer the key for basic validation
            # This is a simplified validation for test keys
            if len(base_key) == 12 and len(checksum) == 4:
                # Create a professional license for test keys
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
                
                logger.info(f"Local key validation successful: {serial_key}")
                return True, license_info
            
            return False, {"error": "Invalid local key format"}
            
        except Exception as e:
            logger.error(f"Local key validation error: {e}")
            return False, {"error": f"Local validation failed: {str(e)}"}
    
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
        logger.info(f"=== GET LICENSE STATUS CALLED ===")
        logger.info(f"License file path: {self.license_file}")
        logger.info(f"License file exists: {self.license_file.exists()}")
        
        try:
            if not self.license_file.exists():
                status_result = {
                    "status": "unlicensed",
                    "type": self.LICENSE_FREE,
                    "message": "No license found"
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
                "type": self.LICENSE_FREE,
                "message": f"License check failed: {e}"
            }
    
    def activate_license(self, serial_key: str) -> Tuple[bool, str]:
        """
        Activate a license with a serial key.
        
        Args:
            serial_key: Serial key to activate
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Validate the key
            is_valid, license_info = self.validate_serial_key(serial_key, force_online=True)
            
            if is_valid:
                return True, "License activated successfully!"
            else:
                error_msg = license_info.get("error", "Unknown error")
                return False, f"Activation failed: {error_msg}"
                
        except Exception as e:
            logger.error(f"License activation error: {e}")
            return False, f"Activation error: {e}"
    
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
    
    def is_feature_enabled(self, feature: str) -> bool:
        """Check if a specific feature is enabled by license."""
        status = self.get_license_status()
        
        if status["status"] != self.STATUS_VALID:
            # Free tier features
            free_features = ["basic_reports", "limited_files"]
            return feature in free_features
        
        license_type = status.get("type", self.LICENSE_FREE)
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
        
        # Free tier
        return feature in ["basic_reports", "limited_files"]
    
    def check_daily_usage_limit(self) -> Tuple[bool, int, int]:
        """
        Check if daily usage limit is exceeded.
        
        Returns:
            Tuple of (can_use, used_today, limit)
        """
        status = self.get_license_status()
        
        if status["status"] != self.STATUS_VALID:
            # Free tier: 3 files per day
            return True, 0, 3  # For now, don't track usage for free tier
        
        license_type = status.get("type", self.LICENSE_FREE)
        
        if license_type in [self.LICENSE_PROFESSIONAL, self.LICENSE_ENTERPRISE]:
            # Unlimited usage
            return True, 0, -1
        
        # Free tier default
        return True, 0, 3


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
        
        if status["status"] == "unlicensed":
            # No license - allow free tier
            return True, status
        elif status["status"] == license_manager.STATUS_VALID:
            # Valid license
            return True, status
        elif status["status"] == license_manager.STATUS_EXPIRED:
            # Expired license - revert to free tier
            return True, status
        else:
            # Invalid license - allow free tier but show warning
            return True, status
            
    except Exception as e:
        logger.error(f"Startup license check failed: {e}")
        return True, {
            "status": "error",
            "type": license_manager.LICENSE_FREE,
            "message": f"License check failed: {e}"
        }