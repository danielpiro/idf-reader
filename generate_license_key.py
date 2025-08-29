#!/usr/bin/env python3
"""
License Key Generator for IDF Reader
Run this script to generate license keys for customers.
"""

import argparse
from datetime import datetime, timedelta
from utils.license_manager import LicenseManager

def main():
    parser = argparse.ArgumentParser(description='Generate license keys for IDF Reader')
    parser.add_argument('--type', choices=['professional', 'enterprise'], 
                       default='professional', help='License type')
    parser.add_argument('--days', type=int, default=365, 
                       help='Number of days the license is valid')
    parser.add_argument('--email', type=str, default='', 
                       help='Customer email address')
    parser.add_argument('--activations', type=int, default=1, 
                       help='Maximum number of machine activations')
    
    args = parser.parse_args()
    
    # Create license manager instance
    license_manager = LicenseManager()
    
    # Generate the key
    serial_key = license_manager.generate_serial_key(
        license_type=args.type,
        days_valid=args.days,
        user_email=args.email,
        max_activations=args.activations
    )
    
    # Calculate expiration date
    expiration_date = datetime.now() + timedelta(days=args.days)
    
    print("\n" + "="*60)
    print("IDF Reader License Key Generated")
    print("="*60)
    print(f"Serial Key:     {serial_key}")
    print(f"License Type:   {args.type}")
    print(f"Valid For:      {args.days} days")
    print(f"Expires:        {expiration_date.strftime('%d/%m/%Y')}")
    print(f"Customer Email: {args.email or 'Not specified'}")
    print(f"Max Activations: {args.activations}")
    print("="*60)
    
    # Show instructions
    print("\nCustomer Instructions:")
    print("1. Download and install IDF Reader")
    print("2. Launch the application")
    print("3. Click the license key icon in the header")
    print("4. Enter the serial key above")
    print("5. Click 'Activate License'")
    print("\nThe customer will need to provide their Machine ID")
    print("   for activation if you implement machine binding.")
    
if __name__ == "__main__":
    main()