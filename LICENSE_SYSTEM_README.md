# 🔐 IDF Reader License System

A comprehensive licensing system with serial keys, usage limits, and secure validation.

## 🎯 Features

### 📊 **License Tiers**
- **Free Tier**: 3 files/day, basic reports, Israeli weather data
- **Professional**: Unlimited files, all reports, Excel export, priority support
- **Enterprise**: All features + multi-user, API, custom branding, 24/7 support

### 🔑 **Key Features**
- ✅ Serial key format: `XXXX-XXXX-XXXX-XXXX`
- ✅ Machine binding (hardware fingerprinting)
- ✅ Online + offline validation
- ✅ Usage tracking and limits
- ✅ Encrypted local license cache
- ✅ Automatic license checking
- ✅ User-friendly license management UI

## 🚀 Quick Start

### 1. **Generate License Keys**
```bash
# Generate professional license (1 year)
python generate_license_key.py --type professional --days 365 --email customer@example.com

# Generate enterprise license (2 years)
python generate_license_key.py --type enterprise --days 730 --email enterprise@company.com --activations 10
```

### 2. **Test with Mock Server** (Development)
```bash
# Start mock license server
python license_server_mock.py --port 8080

# Demo key for testing: DEMO-1234-5678-9ABC
```

### 3. **Customer Activation**
1. Customer downloads and installs IDF Reader
2. Clicks license key icon (🔑) in header
3. Enters serial key
4. System validates online and caches locally

## 💼 Business Workflow

### **For New Customers:**
1. **Customer Contact** → Customer reaches out for purchase
2. **Payment Processing** → Handle payment through your preferred method
3. **Key Generation** → Use `generate_license_key.py` to create key
4. **Key Delivery** → Send serial key + activation instructions
5. **Customer Support** → Help with activation if needed

### **Key Information to Collect:**
- Customer email
- License type needed (Professional/Enterprise)
- Number of machines (for Enterprise)
- Duration preference

## 🛠 Technical Implementation

### **Files Added:**
```
utils/
├── license_manager.py      # Core license management
├── license_dialog.py       # GUI license dialogs
├── 
Tools/
├── generate_license_key.py # Key generation script
├── license_server_mock.py  # Development server
└── LICENSE_SYSTEM_README.md # This file
```

### **Integration Points:**
- **Startup Check**: `show_startup_license_check()` in main()
- **Usage Limits**: `check_license_and_usage()` before processing
- **UI Management**: License button in header, upgrade dialogs
- **Settings Storage**: Encrypted license cache in app data folder

## 🔒 Security Features

### **Key Validation:**
- HMAC-based key signatures
- Machine ID binding
- Encrypted local storage
- Periodic online validation

### **Anti-Piracy:**
- Hardware fingerprinting
- Usage tracking
- Server-side validation
- Blacklist capability

## 📱 User Experience

### **Free Tier Users:**
- Clear usage tracking: "2/3 files used today"
- Upgrade prompts when limits reached
- Feature comparison in license dialog

### **Paid Users:**
- Seamless unlimited access
- License status indicator in header
- Easy license management

## 🌐 Production Deployment

### **License Server Setup:**
1. **Replace Mock Server**: Implement proper web service
2. **Database Integration**: Store licenses in secure database
3. **API Authentication**: Add API keys for server security
4. **SSL/HTTPS**: Ensure encrypted communication
5. **Monitoring**: Log activation attempts and usage

### **Server Endpoints:**
```
POST /license/validate
- Validates serial keys
- Returns license information
- Tracks machine activations

GET /license/status/{key}
- Check license status
- View activation history

POST /license/deactivate
- Deactivate from machine
- Free up activation slot
```

### **Environment Variables:**
```bash
IDF_LICENSE_SERVER_URL=https://api.idf-reader.com
IDF_LICENSE_SECRET_KEY=your-production-secret-key
IDF_LICENSE_ENCRYPTION_SALT=unique-salt-for-encryption
```

## 💰 Revenue Model

### **Pricing Suggestions:**
- **Professional**: $19-29/month or $199-299/year
- **Enterprise**: $49-99/month or $499-999/year

### **Payment Integration:**
- Stripe for credit cards
- PayPal for international
- Bank transfer for enterprise
- Regional payment methods

## 📊 Analytics & Monitoring

### **Key Metrics to Track:**
- License activations per day/month
- Conversion from free to paid
- Feature usage patterns
- Support ticket categories
- Churn rate and renewal patterns

### **Customer Success:**
- Onboarding email sequences
- Feature education
- Usage analytics
- Proactive support

## 🐛 Troubleshooting

### **Common Issues:**
1. **"Invalid License Key"**
   - Check key format (includes dashes)
   - Verify key hasn't expired
   - Check internet connection for validation

2. **"Machine Mismatch"**
   - License tied to different hardware
   - Contact support for transfer
   - May need manual deactivation

3. **"Daily Limit Reached"**
   - Free tier limitation
   - Upgrade to Professional for unlimited
   - Limit resets at midnight

### **Support Commands:**
```bash
# Generate new key for customer
python generate_license_key.py --type professional --email customer@email.com

# Check license status (requires server access)
curl -X POST https://api.idf-reader.com/license/validate \
  -H "Content-Type: application/json" \
  -d '{"serial_key": "XXXX-XXXX-XXXX-XXXX"}'
```

## 🔄 Future Enhancements

### **Planned Features:**
- [ ] Team licenses with user management
- [ ] Volume discounts for bulk purchases
- [ ] Temporary trial extensions
- [ ] Feature-specific licensing
- [ ] Integration with accounting systems
- [ ] Automated renewal reminders
- [ ] Usage-based billing tiers

### **Advanced Security:**
- [ ] Hardware token support
- [ ] Multi-factor authentication
- [ ] Audit logging
- [ ] Geo-restrictions
- [ ] Time-based access controls

---

## 📞 Support

For licensing questions or technical support:
- **Email**: license-support@idf-reader.com
- **Documentation**: This README + inline code comments
- **Emergency**: Contact development team for critical issues

---

**🎉 Your licensing system is now ready! Start generating keys and processing payments to grow your IDF Reader business.**