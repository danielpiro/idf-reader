# 🔑 Client-Only License System Setup

## Overview

Your IDF Reader now uses a **client-only licensing system** that connects directly to MongoDB Atlas. No separate server required!

## 🏗️ Architecture

```
IDF Reader App → MongoDB Atlas
```

**Benefits:**
- ✅ Simple setup - no server to maintain
- ✅ Direct database connection
- ✅ Built-in caching for offline use
- ✅ Secure when compiled to .exe

## 🚀 Quick Setup

### 1. **MongoDB Atlas Connection**
The connection string is already configured in `database/mongo_license_db.py`:
```python
mongodb+srv://danielpiro:G3fh9l8q@cluster0.igf4v.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0
```

### 2. **Generate License Keys**
```bash
python tools/generate_and_store_license.py \
  --email customer@example.com \
  --type professional \
  --days 365 \
  --activations 3 \
  --amount 1990
```

### 3. **Test License Validation**
```bash
python -c "
from utils.license_manager import license_manager
success, msg = license_manager.activate_license('YOUR-KEY-HERE')
print(f'Success: {success}, Message: {msg}')
"
```

## 📋 How It Works

### **User Workflow:**
1. User downloads `idf-reader.exe`
2. User runs the application
3. User clicks license key button (🔑)
4. User enters serial key
5. App validates directly against MongoDB
6. License is cached locally for offline use

### **Validation Process:**
1. **First time**: App connects to MongoDB to validate key
2. **Offline**: App uses encrypted local cache
3. **Weekly check**: App re-validates against MongoDB
4. **Machine binding**: Each activation is tied to specific machine

## 🔒 Security Features

### **In Development:**
- Connection string visible in source code
- Used for testing and development

### **After PyInstaller Build:**
- Connection string compiled into binary
- Users only see `idf-reader.exe`
- Non-technical users cannot access credentials
- Local license cache is encrypted

## 🛠️ Management Tools

### **Generate Licenses**
```bash
# Single professional license
python tools/generate_and_store_license.py \
  --email customer@example.com \
  --type professional \
  --days 365

# Multiple enterprise licenses
python tools/generate_and_store_license.py \
  --email corp@company.com \
  --type enterprise \
  --quantity 5 \
  --days 730 \
  --activations 3
```

### **Customer Management**
```bash
# Add customer
python tools/customer_manager.py add \
  --email customer@example.com \
  --name "John Doe" \
  --company "Tech Corp"

# View customer with licenses
python tools/customer_manager.py view customer@example.com --licenses

# Customer statistics
python tools/customer_manager.py stats
```

## 📊 License Features

### **Free Tier (No License)**
- 3 files per day
- Basic reports only
- Israeli weather data

### **Professional License**
- Unlimited files
- All report types
- Excel export
- Energy rating
- Advanced analysis
- Up to 3 machine activations

### **Enterprise License**
- All professional features
- Multi-user support
- API access
- Custom branding
- 24/7 support
- Up to 3 machine activations

## 🔍 Troubleshooting

### **License Activation Fails**
1. Check internet connection
2. Verify MongoDB Atlas is accessible
3. Check if license key is correct format: `XXXX-XXXX-XXXX-XXXX`
4. Ensure license hasn't expired
5. Check if machine activation limit exceeded

### **Database Connection Issues**
1. Verify MongoDB Atlas cluster is running
2. Check IP whitelist in MongoDB Atlas
3. Ensure database user has proper permissions
4. Test connection: `python -c "from database.mongo_license_db import get_license_db; db = get_license_db()"`

### **Offline Usage**
- App works offline using cached license
- Cache is valid for 7 days
- After 7 days, requires internet connection to re-validate

## 🏗️ Build Process

When building the final executable:

```bash
# Build with PyInstaller
pyinstaller --onefile --windowed modern_gui.py

# Result: dist/modern_gui.exe
# - Contains all dependencies
# - MongoDB connection string is compiled in
# - Users cannot see source code
# - Ready for distribution
```

## 💼 Business Workflow

### **Customer Purchase Process:**
1. Customer contacts you for license
2. Customer pays via your preferred method
3. You generate license key using the tool
4. You email license key to customer
5. Customer activates in IDF Reader
6. License is validated and cached

### **License Management:**
- All licenses stored in MongoDB Atlas
- Track activations and usage
- Monitor customer statistics
- Revoke licenses if needed

## 📈 Monitoring

### **License Statistics**
```bash
python tools/customer_manager.py stats
```

### **Database Queries**
```python
from database.mongo_license_db import get_license_db
db = get_license_db()

# Active licenses
active = db.get_all_licenses(status="active")

# Revenue calculation
stats = db.get_license_stats()
print(f"Total revenue: {stats['total_revenue']} ILS")

# Today's usage
print(f"Files processed today: {stats['today_usage']}")
```

---

**🎉 Your client-only license system is ready!**

No servers to maintain, direct MongoDB connection, secure when compiled, and easy for customers to use.