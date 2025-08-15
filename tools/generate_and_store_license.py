#!/usr/bin/env python3
"""
Generate and Store License Keys in Database
Creates license keys and stores them directly in MongoDB with customer information.
"""

import sys
import os
import argparse
from datetime import datetime, timedelta

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.mongo_license_db import get_license_db
from utils.license_manager import LicenseManager

def main():
    parser = argparse.ArgumentParser(
        description='Generate license keys and store in database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate professional license for 1 year
  python generate_and_store_license.py --email customer@example.com --type professional --days 365

  # Generate enterprise license with custom details
  python generate_and_store_license.py --email corp@company.com --type enterprise --days 730 \\
    --name "John Doe" --company "Big Corp" --activations 5 --amount 4990 --order ORDER-123

  # Generate multiple licenses for a company
  python generate_and_store_license.py --email admin@company.com --type professional \\
    --quantity 10 --days 365 --company "Tech Company"
        """
    )
    
    # Required arguments
    parser.add_argument('--email', required=True, 
                       help='Customer email address')
    parser.add_argument('--type', choices=['professional', 'enterprise'], 
                       default='professional', help='License type')
    
    # License configuration
    parser.add_argument('--days', type=int, default=365, 
                       help='Number of days the license is valid (default: 365)')
    parser.add_argument('--activations', type=int, default=3, 
                       help='Maximum number of machine activations (default: 3)')
    
    # Customer information
    parser.add_argument('--name', type=str, default='', 
                       help='Customer full name')
    parser.add_argument('--company', type=str, default='', 
                       help='Customer company name')
    parser.add_argument('--phone', type=str, default='', 
                       help='Customer phone number')
    parser.add_argument('--country', type=str, default='Israel', 
                       help='Customer country (default: Israel)')
    
    # Business information
    parser.add_argument('--amount', type=float, default=0, 
                       help='Amount paid for the license')
    parser.add_argument('--currency', type=str, default='ILS', 
                       help='Currency (default: ILS)')
    parser.add_argument('--order', type=str, default='', 
                       help='Order ID or reference')
    parser.add_argument('--notes', type=str, default='', 
                       help='Additional notes about the license')
    
    # Bulk generation
    parser.add_argument('--quantity', type=int, default=1, 
                       help='Number of licenses to generate (default: 1)')
    
    # Output options
    parser.add_argument('--format', choices=['text', 'json', 'csv'], 
                       default='text', help='Output format')
    parser.add_argument('--output', type=str, 
                       help='Output file (default: print to console)')
    parser.add_argument('--send-email', action='store_true',
                       help='Send license key via email (requires email config)')
    
    args = parser.parse_args()
    
    try:
        # Initialize database and license manager
        print("Connecting to database...")
        db = get_license_db()
        license_manager = LicenseManager()
        
        print(f"Connected to database: {db.db_name}")
        
        # Generate and store licenses
        generated_licenses = []
        
        for i in range(args.quantity):
            print(f"\nGenerating license {i+1}/{args.quantity}...")
            
            # Generate serial key
            serial_key = license_manager.generate_serial_key(
                license_type=args.type,
                days_valid=args.days,
                user_email=args.email,
                max_activations=args.activations
            )
            
            # Create unique order ID if not provided
            order_id = args.order
            if not order_id and args.quantity > 1:
                order_id = f"BULK-{datetime.now().strftime('%Y%m%d%H%M%S')}-{i+1:03d}"
            elif not order_id:
                order_id = f"GEN-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            # Store in database
            license_id = db.create_license(
                serial_key=serial_key,
                customer_email=args.email,
                license_type=args.type,
                expires_days=args.days,
                max_activations=args.activations,
                order_id=order_id,
                amount_paid=args.amount,
                created_by="license_generator"
            )
            
            # Update customer information if provided
            if any([args.name, args.company, args.phone, args.country]):
                customer = db.get_customer_by_email(args.email)
                if customer:
                    update_data = {}
                    if args.name: update_data['name'] = args.name
                    if args.company: update_data['company'] = args.company
                    if args.phone: update_data['phone'] = args.phone
                    if args.country: update_data['country'] = args.country
                    if args.notes: update_data['notes'] = args.notes
                    
                    if update_data:
                        update_data['updated_at'] = datetime.utcnow()
                        db.db.customers.update_one(
                            {"_id": customer["_id"]},
                            {"$set": update_data}
                        )
            
            # Calculate expiration date
            expiration_date = datetime.utcnow() + timedelta(days=args.days)
            
            license_info = {
                'serial_key': serial_key,
                'license_id': str(license_id),
                'customer_email': args.email,
                'license_type': args.type,
                'expires_days': args.days,
                'expiration_date': expiration_date.strftime('%d/%m/%Y'),
                'max_activations': args.activations,
                'amount_paid': args.amount,
                'currency': args.currency,
                'order_id': order_id,
                'created_at': datetime.utcnow().strftime('%d/%m/%Y %H:%M:%S')
            }
            
            generated_licenses.append(license_info)
            print(f"Created license: {serial_key}")
        
        # Output results
        output_licenses(generated_licenses, args)
        
        # Send email if requested
        if args.send_email:
            send_license_email(generated_licenses, args)
        
        print(f"\nSuccessfully generated and stored {len(generated_licenses)} license(s)!")
        print(f"Customer: {args.email}")
        print(f"License Type: {args.type}")
        print(f"Valid for: {args.days} days")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

def output_licenses(licenses, args):
    """Output licenses in the specified format."""
    
    if args.format == 'text':
        output_text_format(licenses, args)
    elif args.format == 'json':
        output_json_format(licenses, args)
    elif args.format == 'csv':
        output_csv_format(licenses, args)

def output_text_format(licenses, args):
    """Output in human-readable text format."""
    output_lines = []
    
    output_lines.append("=" * 80)
    output_lines.append("IDF Reader License Keys Generated")
    output_lines.append("=" * 80)
    
    for i, license in enumerate(licenses):
        output_lines.append(f"\nLicense #{i+1}:")
        output_lines.append(f"  Serial Key:     {license['serial_key']}")
        output_lines.append(f"  Customer:       {license['customer_email']}")
        output_lines.append(f"  Type:           {license['license_type']}")
        output_lines.append(f"  Valid Until:    {license['expiration_date']}")
        output_lines.append(f"  Max Activations: {license['max_activations']}")
        output_lines.append(f"  Amount Paid:    {license['currency']} {license['amount_paid']}")
        output_lines.append(f"  Order ID:       {license['order_id']}")
        output_lines.append(f"  Created:        {license['created_at']}")
    
    output_lines.append("\n" + "=" * 80)
    output_lines.append("Customer Instructions:")
    output_lines.append("1. Download and install IDF Reader")
    output_lines.append("2. Launch the application")
    output_lines.append("3. Click the license key button in the header")
    output_lines.append("4. Enter the serial key above")
    output_lines.append("5. Click 'Activate License'")
    output_lines.append("=" * 80)
    
    output_text = "\n".join(output_lines)
    
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_text)
        print(f"Output saved to: {args.output}")
    else:
        print(output_text)

def output_json_format(licenses, args):
    """Output in JSON format."""
    import json
    
    output_data = {
        "generated_at": datetime.utcnow().isoformat(),
        "license_count": len(licenses),
        "licenses": licenses
    }
    
    json_output = json.dumps(output_data, indent=2, ensure_ascii=False)
    
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(json_output)
        print(f"JSON output saved to: {args.output}")
    else:
        print(json_output)

def output_csv_format(licenses, args):
    """Output in CSV format."""
    import csv
    import io
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        'Serial Key', 'Customer Email', 'License Type', 'Expiration Date',
        'Max Activations', 'Amount Paid', 'Currency', 'Order ID', 'Created At'
    ])
    
    # Write data
    for license in licenses:
        writer.writerow([
            license['serial_key'],
            license['customer_email'],
            license['license_type'],
            license['expiration_date'],
            license['max_activations'],
            license['amount_paid'],
            license['currency'],
            license['order_id'],
            license['created_at']
        ])
    
    csv_output = output.getvalue()
    
    if args.output:
        with open(args.output, 'w', encoding='utf-8', newline='') as f:
            f.write(csv_output)
        print(f"CSV output saved to: {args.output}")
    else:
        print(csv_output)

def send_license_email(licenses, args):
    """Send license keys via email (placeholder - implement with your email service)."""
    print("\nEmail sending feature:")
    print("Email sending is not implemented yet.")
    print("   You can integrate with:")
    print("   - SendGrid")
    print("   - AWS SES")
    print("   - SMTP server")
    print("   - Other email service")
    
    print(f"\nEmail Template Data:")
    print(f"   To: {args.email}")
    print(f"   Subject: Your IDF Reader License Key")
    print(f"   License Keys: {[l['serial_key'] for l in licenses]}")

if __name__ == "__main__":
    main()