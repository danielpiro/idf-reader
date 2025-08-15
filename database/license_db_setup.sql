-- License Database Schema for IDF Reader
-- SQLite/PostgreSQL compatible schema

-- License types lookup table
CREATE TABLE license_types (
    id INTEGER PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    max_daily_files INTEGER,
    features TEXT, -- JSON string of features
    price_monthly DECIMAL(10,2),
    price_yearly DECIMAL(10,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Customers table
CREATE TABLE customers (
    id INTEGER PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    company VARCHAR(255),
    phone VARCHAR(50),
    country VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

-- License keys table
CREATE TABLE licenses (
    id INTEGER PRIMARY KEY,
    serial_key VARCHAR(19) UNIQUE NOT NULL, -- XXXX-XXXX-XXXX-XXXX
    customer_id INTEGER REFERENCES customers(id),
    license_type_id INTEGER REFERENCES license_types(id),
    status VARCHAR(20) DEFAULT 'active', -- active, expired, revoked, suspended
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    max_activations INTEGER DEFAULT 1,
    current_activations INTEGER DEFAULT 0,
    notes TEXT,
    created_by VARCHAR(100), -- Admin who created it
    
    -- Billing information
    order_id VARCHAR(100),
    payment_status VARCHAR(20), -- paid, pending, failed, refunded
    amount_paid DECIMAL(10,2),
    currency VARCHAR(3) DEFAULT 'ILS',
    
    CONSTRAINT check_status CHECK (status IN ('active', 'expired', 'revoked', 'suspended')),
    CONSTRAINT check_payment_status CHECK (payment_status IN ('paid', 'pending', 'failed', 'refunded'))
);

-- Machine activations table
CREATE TABLE activations (
    id INTEGER PRIMARY KEY,
    license_id INTEGER REFERENCES licenses(id),
    machine_id VARCHAR(64) NOT NULL,
    machine_name VARCHAR(255),
    platform VARCHAR(50),
    first_activated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    activation_count INTEGER DEFAULT 1,
    status VARCHAR(20) DEFAULT 'active', -- active, deactivated
    ip_address VARCHAR(45),
    user_agent TEXT,
    version VARCHAR(20),
    
    UNIQUE(license_id, machine_id),
    CONSTRAINT check_activation_status CHECK (status IN ('active', 'deactivated'))
);

-- Usage tracking table
CREATE TABLE usage_logs (
    id INTEGER PRIMARY KEY,
    license_id INTEGER REFERENCES licenses(id),
    machine_id VARCHAR(64),
    action VARCHAR(50), -- file_processed, report_generated, login, etc.
    details TEXT, -- JSON with additional info
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    file_count INTEGER DEFAULT 1
);

-- Admin users table (for license management)
CREATE TABLE admin_users (
    id INTEGER PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL, -- bcrypt hash
    role VARCHAR(20) DEFAULT 'admin', -- admin, super_admin, readonly
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- Audit log for license changes
CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY,
    table_name VARCHAR(50) NOT NULL,
    record_id INTEGER NOT NULL,
    action VARCHAR(20) NOT NULL, -- insert, update, delete
    old_values TEXT, -- JSON
    new_values TEXT, -- JSON
    changed_by VARCHAR(100),
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ip_address VARCHAR(45),
    user_agent TEXT
);

-- Insert default license types
INSERT INTO license_types (name, display_name, max_daily_files, features, price_monthly, price_yearly) VALUES
('free', 'חינמי', 3, '{"basic_reports": true, "limited_files": true, "israeli_weather": true}', 0.00, 0.00),
('professional', 'מקצועי', -1, '{"unlimited_files": true, "all_reports": true, "export_excel": true, "energy_rating": true, "advanced_analysis": true, "priority_support": true}', 199.00, 1990.00),
('enterprise', 'ארגוני', -1, '{"unlimited_files": true, "all_reports": true, "export_excel": true, "energy_rating": true, "advanced_analysis": true, "priority_support": true, "multi_user": true, "api_access": true, "custom_branding": true, "24_7_support": true}', 499.00, 4990.00);

-- Create indexes for better performance
CREATE INDEX idx_licenses_serial_key ON licenses(serial_key);
CREATE INDEX idx_licenses_customer_id ON licenses(customer_id);
CREATE INDEX idx_licenses_status ON licenses(status);
CREATE INDEX idx_licenses_expires_at ON licenses(expires_at);
CREATE INDEX idx_activations_license_id ON activations(license_id);
CREATE INDEX idx_activations_machine_id ON activations(machine_id);
CREATE INDEX idx_usage_logs_license_id ON usage_logs(license_id);
CREATE INDEX idx_usage_logs_created_at ON usage_logs(created_at);
CREATE INDEX idx_customers_email ON customers(email);

-- Create views for common queries
CREATE VIEW active_licenses AS
SELECT 
    l.*,
    c.email as customer_email,
    c.name as customer_name,
    c.company as customer_company,
    lt.display_name as license_type_name,
    lt.features as license_features
FROM licenses l
JOIN customers c ON l.customer_id = c.id
JOIN license_types lt ON l.license_type_id = lt.id
WHERE l.status = 'active' 
AND (l.expires_at IS NULL OR l.expires_at > CURRENT_TIMESTAMP);

CREATE VIEW license_usage_summary AS
SELECT 
    l.serial_key,
    c.email as customer_email,
    lt.display_name as license_type,
    l.current_activations,
    l.max_activations,
    COUNT(ul.id) as total_usage,
    COUNT(CASE WHEN DATE(ul.created_at) = DATE('now') THEN 1 END) as today_usage,
    MAX(ul.created_at) as last_used_at
FROM licenses l
JOIN customers c ON l.customer_id = c.id
JOIN license_types lt ON l.license_type_id = lt.id
LEFT JOIN usage_logs ul ON l.id = ul.license_id
WHERE l.status = 'active'
GROUP BY l.id, l.serial_key, c.email, lt.display_name;

-- Sample data for testing (remove in production)
INSERT INTO customers (email, name, company) VALUES
('demo@example.com', 'Demo User', 'Demo Company'),
('test@idf-reader.com', 'Test User', 'IDF Reader'),
('enterprise@company.com', 'Enterprise Admin', 'Large Corporation');

-- Sample licenses (remove in production)
INSERT INTO licenses (serial_key, customer_id, license_type_id, expires_at, order_id, payment_status, amount_paid) VALUES
('DEMO-1234-5678-9ABC', 1, 2, datetime('now', '+365 days'), 'ORDER-001', 'paid', 1990.00),
('TEST-ABCD-EFGH-IJKL', 2, 2, datetime('now', '+30 days'), 'ORDER-002', 'paid', 199.00),
('CORP-WXYZ-1234-5678', 3, 3, datetime('now', '+730 days'), 'ORDER-003', 'paid', 4990.00);