"""
MongoDB License Database Manager for IDF Reader
Handles all license-related database operations using MongoDB.
"""

import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import pymongo
from pymongo import MongoClient
from bson import ObjectId
import hashlib
import secrets
import json
import logging

logger = logging.getLogger(__name__)

class LicenseDatabase:
    """MongoDB-based license database manager."""
    
    def __init__(self, connection_string: str = None):
        """Initialize database connection."""
        # Use MongoDB Atlas connection string (URL encode password if needed)
        self.connection_string = connection_string or os.getenv(
            'MONGODB_CONNECTION_STRING', 
            'mongodb+srv://danielpiro:G3fh9l8q@cluster0.igf4v.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0'
        )
        
        self.db_name = os.getenv('LICENSE_DB_NAME', 'idf_reader_licenses')
        self.client = None
        self.db = None
        
        self.connect()
        self.setup_collections()
    
    def connect(self):
        """Connect to MongoDB."""
        try:
            self.client = MongoClient(self.connection_string)
            self.db = self.client[self.db_name]
            
            # Test connection
            self.client.admin.command('ping')
            logger.info(f"Connected to MongoDB: {self.db_name}")
            
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise
    
    def setup_collections(self):
        """Set up collections and indexes."""
        try:
            # Create collections
            collections = [
                'customers', 'licenses', 'activations', 
                'usage_logs', 'admin_users', 'audit_log'
            ]
            
            for collection_name in collections:
                if collection_name not in self.db.list_collection_names():
                    self.db.create_collection(collection_name)
            
            # Create indexes
            self.create_indexes()
            
            # Insert default license types if not exist
            self.setup_default_data()
            
            logger.info("Database collections and indexes set up successfully")
            
        except Exception as e:
            logger.error(f"Failed to setup collections: {e}")
            raise
    
    def create_indexes(self):
        """Create database indexes for optimal performance."""
        # Customers indexes
        self.db.customers.create_index("email", unique=True)
        self.db.customers.create_index("created_at")
        
        # Licenses indexes
        self.db.licenses.create_index("serial_key", unique=True)
        self.db.licenses.create_index("customer_id")
        self.db.licenses.create_index("status")
        self.db.licenses.create_index("expires_at")
        self.db.licenses.create_index("license_type")
        
        # Activations indexes
        self.db.activations.create_index([("license_id", 1), ("machine_id", 1)], unique=True)
        self.db.activations.create_index("machine_id")
        self.db.activations.create_index("last_seen_at")
        
        # Usage logs indexes
        self.db.usage_logs.create_index("license_id")
        self.db.usage_logs.create_index("created_at")
        self.db.usage_logs.create_index([("license_id", 1), ("created_at", -1)])
        
        # Admin users indexes
        self.db.admin_users.create_index("username", unique=True)
        self.db.admin_users.create_index("email", unique=True)
    
    def setup_default_data(self):
        """Set up default license types and sample data."""
        # License types (stored as a configuration document)
        license_types = {
            "_id": "license_types_config",
            "types": {
                "free": {
                    "display_name": "חינמי",
                    "max_daily_files": 3,
                    "features": {
                        "basic_reports": True,
                        "limited_files": True,
                        "israeli_weather": True
                    },
                    "price_monthly": 0.0,
                    "price_yearly": 0.0
                },
                "professional": {
                    "display_name": "מקצועי",
                    "max_daily_files": -1,  # unlimited
                    "features": {
                        "unlimited_files": True,
                        "all_reports": True,
                        "export_excel": True,
                        "energy_rating": True,
                        "advanced_analysis": True,
                        "priority_support": True
                    },
                    "price_monthly": 199.0,
                    "price_yearly": 1990.0
                },
                "enterprise": {
                    "display_name": "ארגוני",
                    "max_daily_files": -1,  # unlimited
                    "features": {
                        "unlimited_files": True,
                        "all_reports": True,
                        "export_excel": True,
                        "energy_rating": True,
                        "advanced_analysis": True,
                        "priority_support": True,
                        "multi_user": True,
                        "api_access": True,
                        "custom_branding": True,
                        "support_24_7": True
                    },
                    "price_monthly": 499.0,
                    "price_yearly": 4990.0
                }
            },
            "updated_at": datetime.utcnow()
        }
        
        # Insert or update license types config
        self.db.config.replace_one(
            {"_id": "license_types_config"},
            license_types,
            upsert=True
        )
    
    # Customer management
    def create_customer(self, email: str, name: str = "", company: str = "", 
                       phone: str = "", country: str = "", notes: str = "") -> str:
        """Create a new customer."""
        customer = {
            "email": email.lower().strip(),
            "name": name.strip(),
            "company": company.strip(),
            "phone": phone.strip(),
            "country": country.strip(),
            "notes": notes.strip(),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        result = self.db.customers.insert_one(customer)
        logger.info(f"Created customer: {email}")
        return str(result.inserted_id)
    
    def get_customer_by_email(self, email: str) -> Optional[Dict]:
        """Get customer by email."""
        return self.db.customers.find_one({"email": email.lower().strip()})
    
    def get_customer_by_id(self, customer_id: str) -> Optional[Dict]:
        """Get customer by ID."""
        return self.db.customers.find_one({"_id": ObjectId(customer_id)})
    
    # License management
    def create_license(self, serial_key: str, customer_email: str, license_type: str,
                      expires_days: int = 365, max_activations: int = 3,
                      order_id: str = "", amount_paid: float = 0.0,
                      created_by: str = "system") -> str:
        """Create a new license."""
        # Get or create customer
        customer = self.get_customer_by_email(customer_email)
        if not customer:
            customer_id = self.create_customer(customer_email)
        else:
            customer_id = str(customer["_id"])
        
        # Calculate expiration
        expires_at = datetime.utcnow() + timedelta(days=expires_days) if expires_days > 0 else None
        
        license_doc = {
            "serial_key": serial_key.upper(),
            "customer_id": ObjectId(customer_id),
            "customer_email": customer_email.lower(),
            "license_type": license_type,
            "status": "active",
            "created_at": datetime.utcnow(),
            "expires_at": expires_at,
            "max_activations": max_activations,
            "current_activations": 0,
            "created_by": created_by,
            "order_id": order_id,
            "payment_status": "paid" if amount_paid > 0 else "pending",
            "amount_paid": amount_paid,
            "currency": "ILS",
            "notes": ""
        }
        
        result = self.db.licenses.insert_one(license_doc)
        logger.info(f"Created license: {serial_key} for {customer_email}")
        return str(result.inserted_id)
    
    def get_license_by_key(self, serial_key: str) -> Optional[Dict]:
        """Get license by serial key."""
        return self.db.licenses.find_one({"serial_key": serial_key.upper()})
    
    def validate_license(self, serial_key: str, machine_id: str, 
                        platform: str = "", version: str = "", 
                        ip_address: str = "") -> Tuple[bool, Dict]:
        """Validate a license key and return license info."""
        try:
            license_doc = self.get_license_by_key(serial_key)
            if not license_doc:
                return False, {"error": "Invalid license key"}
            
            # Check if license is active
            if license_doc["status"] != "active":
                return False, {"error": f"License is {license_doc['status']}"}
            
            # Check expiration
            if license_doc["expires_at"] and datetime.utcnow() > license_doc["expires_at"]:
                # Mark as expired
                self.db.licenses.update_one(
                    {"_id": license_doc["_id"]},
                    {"$set": {"status": "expired"}}
                )
                return False, {"error": "License expired"}
            
            # Check activation limits
            activation = self.get_activation(license_doc["_id"], machine_id)
            if not activation:
                # New machine - check if we can add more activations
                if license_doc["current_activations"] >= license_doc["max_activations"]:
                    return False, {"error": "Maximum activations exceeded"}
                
                # Create new activation
                self.create_activation(license_doc["_id"], machine_id, platform, version, ip_address)
                
                # Update activation count
                self.db.licenses.update_one(
                    {"_id": license_doc["_id"]},
                    {"$inc": {"current_activations": 1}}
                )
            else:
                # Update existing activation
                self.update_activation(license_doc["_id"], machine_id, ip_address)
            
            # Get license type info
            license_type_info = self.get_license_type_info(license_doc["license_type"])
            
            # Log usage
            self.log_usage(license_doc["_id"], machine_id, "license_validation")
            
            return True, {
                "license_type": license_doc["license_type"],
                "expires": license_doc["expires_at"].isoformat() if license_doc["expires_at"] else None,
                "features": license_type_info.get("features", {}),
                "customer_email": license_doc["customer_email"],
                "max_activations": license_doc["max_activations"],
                "current_activations": license_doc["current_activations"]
            }
            
        except Exception as e:
            logger.error(f"License validation error: {e}")
            return False, {"error": f"Validation failed: {str(e)}"}
    
    def get_license_type_info(self, license_type: str) -> Dict:
        """Get license type configuration."""
        config = self.db.config.find_one({"_id": "license_types_config"})
        if config and license_type in config["types"]:
            return config["types"][license_type]
        return {}
    
    # Activation management
    def create_activation(self, license_id: ObjectId, machine_id: str, 
                         platform: str = "", version: str = "", ip_address: str = "") -> str:
        """Create a new machine activation."""
        activation = {
            "license_id": license_id,
            "machine_id": machine_id,
            "platform": platform,
            "version": version,
            "first_activated_at": datetime.utcnow(),
            "last_seen_at": datetime.utcnow(),
            "activation_count": 1,
            "status": "active",
            "ip_address": ip_address
        }
        
        result = self.db.activations.insert_one(activation)
        logger.info(f"Created activation for machine {machine_id}")
        return str(result.inserted_id)
    
    def get_activation(self, license_id: ObjectId, machine_id: str) -> Optional[Dict]:
        """Get activation record."""
        return self.db.activations.find_one({
            "license_id": license_id,
            "machine_id": machine_id
        })
    
    def update_activation(self, license_id: ObjectId, machine_id: str, ip_address: str = ""):
        """Update activation last seen time."""
        self.db.activations.update_one(
            {"license_id": license_id, "machine_id": machine_id},
            {
                "$set": {"last_seen_at": datetime.utcnow(), "ip_address": ip_address},
                "$inc": {"activation_count": 1}
            }
        )
    
    def deactivate_machine(self, license_id: ObjectId, machine_id: str) -> bool:
        """Deactivate a machine."""
        result = self.db.activations.update_one(
            {"license_id": license_id, "machine_id": machine_id},
            {"$set": {"status": "deactivated"}}
        )
        
        if result.modified_count > 0:
            # Decrease activation count
            self.db.licenses.update_one(
                {"_id": license_id},
                {"$inc": {"current_activations": -1}}
            )
            logger.info(f"Deactivated machine {machine_id}")
            return True
        return False
    
    # Usage logging
    def log_usage(self, license_id: ObjectId, machine_id: str, action: str, 
                  details: Dict = None, file_count: int = 1):
        """Log usage activity."""
        usage_log = {
            "license_id": license_id,
            "machine_id": machine_id,
            "action": action,
            "details": details or {},
            "file_count": file_count,
            "created_at": datetime.utcnow()
        }
        
        self.db.usage_logs.insert_one(usage_log)
    
    def get_daily_usage(self, license_id: ObjectId, date: datetime = None) -> int:
        """Get daily usage count for a license."""
        if date is None:
            date = datetime.utcnow()
        
        start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)
        
        pipeline = [
            {
                "$match": {
                    "license_id": license_id,
                    "created_at": {"$gte": start_of_day, "$lt": end_of_day},
                    "action": "file_processed"
                }
            },
            {
                "$group": {
                    "_id": None,
                    "total_files": {"$sum": "$file_count"}
                }
            }
        ]
        
        result = list(self.db.usage_logs.aggregate(pipeline))
        return result[0]["total_files"] if result else 0
    
    # Admin functions
    def get_all_licenses(self, status: str = None, limit: int = 100, offset: int = 0) -> List[Dict]:
        """Get all licenses with optional filtering."""
        query = {}
        if status:
            query["status"] = status
        
        cursor = self.db.licenses.find(query).skip(offset).limit(limit).sort("created_at", -1)
        licenses = list(cursor)
        
        # Enrich with customer info
        for license_doc in licenses:
            customer = self.get_customer_by_id(str(license_doc["customer_id"]))
            if customer:
                license_doc["customer_name"] = customer.get("name", "")
                license_doc["customer_company"] = customer.get("company", "")
        
        return licenses
    
    def get_license_stats(self) -> Dict:
        """Get license statistics."""
        total_licenses = self.db.licenses.count_documents({})
        active_licenses = self.db.licenses.count_documents({"status": "active"})
        expired_licenses = self.db.licenses.count_documents({"status": "expired"})
        
        # Revenue calculation
        revenue_pipeline = [
            {"$match": {"payment_status": "paid"}},
            {"$group": {"_id": None, "total_revenue": {"$sum": "$amount_paid"}}}
        ]
        revenue_result = list(self.db.licenses.aggregate(revenue_pipeline))
        total_revenue = revenue_result[0]["total_revenue"] if revenue_result else 0
        
        # Today's usage
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_usage = self.db.usage_logs.count_documents({
            "created_at": {"$gte": today_start},
            "action": "file_processed"
        })
        
        return {
            "total_licenses": total_licenses,
            "active_licenses": active_licenses,
            "expired_licenses": expired_licenses,
            "total_revenue": total_revenue,
            "today_usage": today_usage,
            "total_customers": self.db.customers.count_documents({})
        }
    
    def revoke_license(self, serial_key: str, reason: str = "") -> bool:
        """Revoke a license."""
        result = self.db.licenses.update_one(
            {"serial_key": serial_key.upper()},
            {
                "$set": {
                    "status": "revoked",
                    "revoked_at": datetime.utcnow(),
                    "revoke_reason": reason
                }
            }
        )
        
        if result.modified_count > 0:
            logger.info(f"Revoked license: {serial_key}")
            return True
        return False
    
    def close(self):
        """Close database connection."""
        if self.client:
            self.client.close()
            logger.info("Database connection closed")


# Global database instance
license_db = None

def get_license_db() -> LicenseDatabase:
    """Get or create license database instance."""
    global license_db
    if license_db is None:
        license_db = LicenseDatabase()
    return license_db