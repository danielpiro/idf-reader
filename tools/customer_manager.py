#!/usr/bin/env python3
"""
Customer Management Tool for IDF Reader
Manage customers, view their licenses, and handle customer operations.
"""

import sys
import os
import argparse
from datetime import datetime
import json

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.mongo_license_db import get_license_db

def main():
    parser = argparse.ArgumentParser(description='Customer Management Tool')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Add customer command
    add_parser = subparsers.add_parser('add', help='Add a new customer')
    add_parser.add_argument('--email', required=True, help='Customer email')
    add_parser.add_argument('--name', help='Customer name')
    add_parser.add_argument('--company', help='Company name')
    add_parser.add_argument('--phone', help='Phone number')
    add_parser.add_argument('--country', default='Israel', help='Country')
    add_parser.add_argument('--notes', help='Additional notes')
    
    # List customers command
    list_parser = subparsers.add_parser('list', help='List customers')
    list_parser.add_argument('--limit', type=int, default=50, help='Number of customers to show')
    list_parser.add_argument('--format', choices=['table', 'json'], default='table', help='Output format')
    
    # View customer command
    view_parser = subparsers.add_parser('view', help='View customer details')
    view_parser.add_argument('email', help='Customer email')
    view_parser.add_argument('--licenses', action='store_true', help='Show customer licenses')
    
    # Update customer command
    update_parser = subparsers.add_parser('update', help='Update customer information')
    update_parser.add_argument('email', help='Customer email')
    update_parser.add_argument('--name', help='Update name')
    update_parser.add_argument('--company', help='Update company')
    update_parser.add_argument('--phone', help='Update phone')
    update_parser.add_argument('--country', help='Update country')
    update_parser.add_argument('--notes', help='Update notes')
    
    # Search customers command
    search_parser = subparsers.add_parser('search', help='Search customers')
    search_parser.add_argument('query', help='Search query (email, name, or company)')
    search_parser.add_argument('--field', choices=['email', 'name', 'company'], help='Search specific field')
    
    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Customer statistics')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    try:
        # Initialize database
        db = get_license_db()
        
        if args.command == 'add':
            add_customer(db, args)
        elif args.command == 'list':
            list_customers(db, args)
        elif args.command == 'view':
            view_customer(db, args)
        elif args.command == 'update':
            update_customer(db, args)
        elif args.command == 'search':
            search_customers(db, args)
        elif args.command == 'stats':
            show_stats(db, args)
            
    except Exception as e:
        print(f" Error: {e}")
        sys.exit(1)

def add_customer(db, args):
    """Add a new customer."""
    try:
        # Check if customer already exists
        existing = db.get_customer_by_email(args.email)
        if existing:
            print(f" Customer with email {args.email} already exists")
            return
        
        # Create customer
        customer_id = db.create_customer(
            email=args.email,
            name=args.name or '',
            company=args.company or '',
            phone=args.phone or '',
            country=args.country or 'Israel',
            notes=args.notes or ''
        )
        
        print(f" Customer created successfully!")
        print(f"   Email: {args.email}")
        print(f"   ID: {customer_id}")
        
        if args.name:
            print(f"   Name: {args.name}")
        if args.company:
            print(f"   Company: {args.company}")
        if args.phone:
            print(f"   Phone: {args.phone}")
            
    except Exception as e:
        print(f" Failed to create customer: {e}")

def list_customers(db, args):
    """List customers."""
    try:
        customers = list(db.db.customers.find().sort("created_at", -1).limit(args.limit))
        
        if not customers:
            print(" No customers found")
            return
        
        if args.format == 'json':
            # Convert ObjectId to string for JSON serialization
            for customer in customers:
                customer['_id'] = str(customer['_id'])
                customer['created_at'] = customer['created_at'].isoformat()
                customer['updated_at'] = customer['updated_at'].isoformat()
            
            print(json.dumps(customers, indent=2, ensure_ascii=False))
            
        else:
            # Table format
            print(f"\nCustomers ({len(customers)} found):")
            print("=" * 100)
            print(f"{'Email':<30} {'Name':<20} {'Company':<20} {'Created':<12}")
            print("-" * 100)
            
            for customer in customers:
                name = customer.get('name', '')[:19]
                company = customer.get('company', '')[:19]
                created = customer['created_at'].strftime('%d/%m/%Y')
                
                print(f"{customer['email']:<30} {name:<20} {company:<20} {created:<12}")
            
            print("-" * 100)
            print(f"Total: {len(customers)} customers")
            
    except Exception as e:
        print(f" Failed to list customers: {e}")

def view_customer(db, args):
    """View customer details."""
    try:
        customer = db.get_customer_by_email(args.email)
        if not customer:
            print(f" Customer not found: {args.email}")
            return
        
        print(f"\nCustomer Details:")
        print("=" * 60)
        print(f"Email:    {customer['email']}")
        print(f"Name:     {customer.get('name', 'Not provided')}")
        print(f"Company:  {customer.get('company', 'Not provided')}")
        print(f"Phone:    {customer.get('phone', 'Not provided')}")
        print(f"Country:  {customer.get('country', 'Not provided')}")
        print(f"Created:  {customer['created_at'].strftime('%d/%m/%Y %H:%M:%S')}")
        print(f"Updated:  {customer['updated_at'].strftime('%d/%m/%Y %H:%M:%S')}")
        
        if customer.get('notes'):
            print(f"Notes:    {customer['notes']}")
        
        if args.licenses:
            # Show customer licenses
            licenses = list(db.db.licenses.find({"customer_id": customer["_id"]}))
            
            print(f"\nLicenses ({len(licenses)} found):")
            print("-" * 60)
            
            if licenses:
                for license_doc in licenses:
                    status_icon = "[ACTIVE]" if license_doc["status"] == "active" else "[INACTIVE]"
                    expires = license_doc["expires_at"].strftime('%d/%m/%Y') if license_doc["expires_at"] else "Never"
                    
                    print(f"{status_icon} {license_doc['serial_key']} ({license_doc['license_type']}) - Expires: {expires}")
            else:
                print("   No licenses found")
        
        print("=" * 60)
        
    except Exception as e:
        print(f" Failed to view customer: {e}")

def update_customer(db, args):
    """Update customer information."""
    try:
        customer = db.get_customer_by_email(args.email)
        if not customer:
            print(f" Customer not found: {args.email}")
            return
        
        # Prepare update data
        update_data = {'updated_at': datetime.utcnow()}
        
        if args.name is not None:
            update_data['name'] = args.name
        if args.company is not None:
            update_data['company'] = args.company
        if args.phone is not None:
            update_data['phone'] = args.phone
        if args.country is not None:
            update_data['country'] = args.country
        if args.notes is not None:
            update_data['notes'] = args.notes
        
        if len(update_data) == 1:  # Only updated_at
            print(" No fields to update provided")
            return
        
        # Update customer
        result = db.db.customers.update_one(
            {"_id": customer["_id"]},
            {"$set": update_data}
        )
        
        if result.modified_count > 0:
            print(f" Customer updated successfully!")
            print(f"   Email: {args.email}")
            
            for field, value in update_data.items():
                if field != 'updated_at':
                    print(f"   {field.title()}: {value}")
        else:
            print("  No changes made")
            
    except Exception as e:
        print(f" Failed to update customer: {e}")

def search_customers(db, args):
    """Search customers."""
    try:
        # Build search query
        query = {}
        
        if args.field:
            # Search specific field
            query[args.field] = {"$regex": args.query, "$options": "i"}
        else:
            # Search multiple fields
            query = {
                "$or": [
                    {"email": {"$regex": args.query, "$options": "i"}},
                    {"name": {"$regex": args.query, "$options": "i"}},
                    {"company": {"$regex": args.query, "$options": "i"}}
                ]
            }
        
        customers = list(db.db.customers.find(query).sort("created_at", -1))
        
        if not customers:
            print(f" No customers found matching: {args.query}")
            return
        
        print(f"\nSearch Results for '{args.query}' ({len(customers)} found):")
        print("=" * 100)
        print(f"{'Email':<30} {'Name':<20} {'Company':<20} {'Created':<12}")
        print("-" * 100)
        
        for customer in customers:
            name = customer.get('name', '')[:19]
            company = customer.get('company', '')[:19]
            created = customer['created_at'].strftime('%d/%m/%Y')
            
            print(f"{customer['email']:<30} {name:<20} {company:<20} {created:<12}")
        
        print("-" * 100)
        print(f"Total: {len(customers)} customers found")
        
    except Exception as e:
        print(f" Search failed: {e}")

def show_stats(db, args):
    """Show customer statistics."""
    try:
        # Basic stats
        total_customers = db.db.customers.count_documents({})
        
        # Customers with licenses
        customers_with_licenses = db.db.customers.count_documents({
            "_id": {"$in": [license["customer_id"] for license in db.db.licenses.find({}, {"customer_id": 1})]}
        })
        
        # Recent customers (last 30 days)
        from datetime import timedelta
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_customers = db.db.customers.count_documents({
            "created_at": {"$gte": thirty_days_ago}
        })
        
        # Top companies by customer count
        pipeline = [
            {"$match": {"company": {"$ne": ""}}},
            {"$group": {"_id": "$company", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 5}
        ]
        top_companies = list(db.db.customers.aggregate(pipeline))
        
        # Countries distribution
        countries_pipeline = [
            {"$group": {"_id": "$country", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]
        countries = list(db.db.customers.aggregate(countries_pipeline))
        
        print(f"\nCustomer Statistics:")
        print("=" * 50)
        print(f"Total Customers:        {total_customers}")
        print(f"With Licenses:          {customers_with_licenses}")
        print(f"New (Last 30 days):     {recent_customers}")
        print(f"Without Licenses:       {total_customers - customers_with_licenses}")
        
        if top_companies:
            print(f"\nTop Companies:")
            print("-" * 30)
            for company in top_companies:
                print(f"  {company['_id']}: {company['count']} customers")
        
        if countries:
            print(f"\nCountries:")
            print("-" * 30)
            for country in countries:
                country_name = country['_id'] or 'Not specified'
                print(f"  {country_name}: {country['count']} customers")
        
        print("=" * 50)
        
    except Exception as e:
        print(f" Failed to get stats: {e}")

if __name__ == "__main__":
    main()