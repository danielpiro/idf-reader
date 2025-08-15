# 🗄️ MongoDB License Database Setup Guide

Complete guide to set up and manage the MongoDB-based license system for IDF Reader.

## 🚀 Quick Start

### 1. **Install MongoDB**

#### Windows:
```bash
# Download MongoDB Community Server from https://www.mongodb.com/try/download/community
# Or using Chocolatey:
choco install mongodb

# Start MongoDB service
net start MongoDB
```

#### macOS:
```bash
# Using Homebrew
brew tap mongodb/brew
brew install mongodb-community
brew services start mongodb/brew/mongodb-community
```

#### Linux (Ubuntu):
```bash
# Import public key
wget -qO - https://www.mongodb.org/static/pgp/server-6.0.asc | sudo apt-key add -

# Add repository
echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu focal/mongodb-org/6.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-6.0.list

# Install MongoDB
sudo apt-get update
sudo apt-get install -y mongodb-org

# Start service
sudo systemctl start mongod
sudo systemctl enable mongod
```

### 2. **Install Python Dependencies**
```bash
pip install pymongo flask flask-cors
```

### 3. **Test Database Connection**
```bash
python -c "from database.mongo_license_db import get_license_db; db = get_license_db(); print('✅ Database connected!')"
```

## 📊 Database Collections

The system creates these MongoDB collections automatically:

```
idf_reader_licenses/
├── customers          # Customer information
├── licenses          # License keys and details
├── activations       # Machine activations
├── usage_logs        # Usage tracking
├── admin_users       # Admin accounts
├── audit_log         # Change tracking
└── config            # License type configurations
```

## 🔧 Environment Configuration

### **Environment Variables**
```bash
# MongoDB connection
export MONGODB_CONNECTION_STRING="mongodb://localhost:27017/"
export LICENSE_DB_NAME="idf_reader_licenses"

# License server security
export LICENSE_API_KEY="your-secure-api-key-here"
export ADMIN_SECRET_KEY="your-admin-secret-key-here"

# Optional: MongoDB Atlas (cloud)
export MONGODB_CONNECTION_STRING="mongodb+srv://username:password@cluster.mongodb.net/"
```

### **Windows (.env file)**
```bash
MONGODB_CONNECTION_STRING=mongodb://localhost:27017/
LICENSE_DB_NAME=idf_reader_licenses
LICENSE_API_KEY=your-secure-api-key-here
ADMIN_SECRET_KEY=your-admin-secret-key-here
```

## 🛠️ Management Tools

### **1. Generate License Keys**
```bash
# Generate professional license
python tools/generate_and_store_license.py \
  --email customer@example.com \
  --type professional \
  --days 365 \
  --name "John Doe" \
  --company "Tech Corp" \
  --amount 1990

# Bulk generation
python tools/generate_and_store_license.py \
  --email admin@company.com \
  --type professional \
  --quantity 10 \
  --days 365
```

### **2. Customer Management**
```bash
# Add customer
python tools/customer_manager.py add \
  --email customer@example.com \
  --name "John Doe" \
  --company "Tech Corp" \
  --phone "+972-50-123-4567"

# View customer with licenses
python tools/customer_manager.py view customer@example.com --licenses

# Search customers
python tools/customer_manager.py search "Tech"

# Customer statistics
python tools/customer_manager.py stats
```

### **3. Admin Web Interface**
```bash
# Start admin panel
cd admin/
python license_admin.py

# Access at: http://localhost:5000
# Default login: admin / admin123
```

### **4. License Server**
```bash
# Production server
python license_server_production.py --port 8080

# Test validation
curl -X POST http://localhost:8080/api/license/validate \
  -H "Content-Type: application/json" \
  -d '{"serial_key": "YOUR-SERIAL-KEY-HERE", "machine_id": "test-machine"}'
```

## 📋 Common Operations

### **Customer Workflow**
```bash
# 1. Customer contacts you for purchase
# 2. Process payment
# 3. Generate license
python tools/generate_and_store_license.py \
  --email customer@example.com \
  --type professional \
  --days 365 \
  --amount 1990 \
  --order "ORDER-123"

# 4. Send license key to customer
# 5. Customer activates in IDF Reader app
```

### **License Management**
```bash
# View license details
python -c "
from database.mongo_license_db import get_license_db
db = get_license_db()
license = db.get_license_by_key('XXXX-XXXX-XXXX-XXXX')
print(license)
"

# Revoke license
python -c "
from database.mongo_license_db import get_license_db
db = get_license_db()
db.revoke_license('XXXX-XXXX-XXXX-XXXX', 'Customer requested refund')
"
```

### **Usage Analytics**
```python
from database.mongo_license_db import get_license_db
from datetime import datetime, timedelta

db = get_license_db()

# Today's usage
today_usage = db.db.usage_logs.count_documents({
    "created_at": {"$gte": datetime.now().replace(hour=0, minute=0, second=0)},
    "action": "file_processed"
})

# Top customers this month
pipeline = [
    {"$match": {"created_at": {"$gte": datetime.now() - timedelta(days=30)}}},
    {"$group": {"_id": "$license_id", "total_files": {"$sum": "$file_count"}}},
    {"$sort": {"total_files": -1}},
    {"$limit": 10}
]
top_usage = list(db.db.usage_logs.aggregate(pipeline))
```

## 🔒 Security Configuration

### **1. Database Security**
```javascript
// In MongoDB shell
use idf_reader_licenses

// Create admin user
db.createUser({
  user: "idf_admin",
  pwd: "secure_password_here",
  roles: [
    { role: "readWrite", db: "idf_reader_licenses" },
    { role: "dbAdmin", db: "idf_reader_licenses" }
  ]
})

// Enable authentication in /etc/mongod.conf
security:
  authorization: enabled
```

### **2. Production Security Checklist**
- [ ] Change default admin credentials
- [ ] Set strong API keys in environment variables
- [ ] Enable MongoDB authentication
- [ ] Use SSL/TLS for MongoDB connections
- [ ] Configure firewall to restrict MongoDB access
- [ ] Set up regular database backups
- [ ] Monitor logs for suspicious activity
- [ ] Use environment variables for secrets
- [ ] Enable audit logging

## 📈 Monitoring & Maintenance

### **Database Backups**
```bash
# Create backup
mongodump --db idf_reader_licenses --out /path/to/backup/

# Restore backup
mongorestore --db idf_reader_licenses /path/to/backup/idf_reader_licenses/

# Automated daily backup script
#!/bin/bash
DATE=$(date +%Y%m%d)
mongodump --db idf_reader_licenses --out /backups/idf_licenses_$DATE/
```

### **Performance Monitoring**
```javascript
// Check collection stats
db.licenses.stats()
db.usage_logs.stats()

// Index usage
db.licenses.getIndexes()

// Slow queries
db.setProfilingLevel(2, { slowms: 100 })
db.system.profile.find().sort({ ts: -1 }).limit(5)
```

### **Data Cleanup**
```python
# Clean old usage logs (keep 90 days)
from datetime import datetime, timedelta
from database.mongo_license_db import get_license_db

db = get_license_db()
cutoff_date = datetime.utcnow() - timedelta(days=90)

result = db.db.usage_logs.delete_many({
    "created_at": {"$lt": cutoff_date}
})
print(f"Deleted {result.deleted_count} old usage logs")
```

## 🌐 Production Deployment

### **1. MongoDB Atlas (Cloud)**
```bash
# 1. Create cluster at https://cloud.mongodb.com/
# 2. Get connection string
# 3. Update environment variable
export MONGODB_CONNECTION_STRING="mongodb+srv://username:password@cluster.mongodb.net/"
```

### **2. Docker Deployment**
```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8080

CMD ["python", "license_server_production.py", "--host", "0.0.0.0", "--port", "8080"]
```

```yaml
# docker-compose.yml
version: '3.8'
services:
  mongodb:
    image: mongo:6.0
    environment:
      MONGO_INITDB_ROOT_USERNAME: admin
      MONGO_INITDB_ROOT_PASSWORD: password
    volumes:
      - mongodb_data:/data/db
    ports:
      - "27017:27017"

  license-server:
    build: .
    environment:
      MONGODB_CONNECTION_STRING: mongodb://admin:password@mongodb:27017/
      LICENSE_API_KEY: your-secure-api-key
    ports:
      - "8080:8080"
    depends_on:
      - mongodb

volumes:
  mongodb_data:
```

### **3. Systemd Service (Linux)**
```ini
# /etc/systemd/system/idf-license-server.service
[Unit]
Description=IDF Reader License Server
After=network.target mongod.service

[Service]
Type=simple
User=idf-license
WorkingDirectory=/opt/idf-reader
ExecStart=/opt/idf-reader/venv/bin/python license_server_production.py
Restart=always
Environment=MONGODB_CONNECTION_STRING=mongodb://localhost:27017/
Environment=LICENSE_API_KEY=your-secure-api-key

[Install]
WantedBy=multi-user.target
```

## 🔍 Troubleshooting

### **Common Issues**

1. **Connection Failed**
```bash
# Check MongoDB status
sudo systemctl status mongod

# Check connection
mongo --eval "db.adminCommand('ping')"
```

2. **Authentication Error**
```bash
# Connect with authentication
mongo -u idf_admin -p --authenticationDatabase idf_reader_licenses
```

3. **License Validation Fails**
```python
# Debug validation
from database.mongo_license_db import get_license_db
db = get_license_db()
license = db.get_license_by_key('YOUR-KEY-HERE')
print(license)
```

4. **Performance Issues**
```javascript
// Check slow queries
db.setProfilingLevel(2, { slowms: 100 })
db.system.profile.find().sort({ ts: -1 }).limit(5)

// Add missing indexes
db.usage_logs.createIndex({ "created_at": -1 })
db.licenses.createIndex({ "expires_at": 1 })
```

## 📞 Support

For database issues:
1. Check MongoDB logs: `/var/log/mongodb/mongod.log`
2. Verify environment variables
3. Test database connection
4. Check firewall settings
5. Review application logs

---

**🎉 Your MongoDB license database is now ready for production use!**