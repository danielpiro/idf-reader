#!/usr/bin/env python3
"""
Test script to verify CSV zone area parsing functionality.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from parsers.eplustbl_reader import read_zone_areas_from_csv
import logging

# Set up logging to see all debug messages
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s - %(name)s - %(message)s')

def test_csv_parsing():
    """Test the CSV zone area parsing with the reference file."""
    
    # Test with the reference CSV file
    csv_path = r"tests\eplustbl copy.csv"
    
    print(f"Testing CSV parsing with: {csv_path}")
    print(f"File exists: {os.path.exists(csv_path)}")
    
    # Test manual parsing to see what's happening
    try:
        import csv
        with open(csv_path, 'r', encoding='utf-8', errors='ignore') as csvfile:
            reader = csv.reader(csvfile)
            
            row_count = 0
            zone_summary_found = False
            
            for row in reader:
                row_count += 1
                if row_count <= 10:
                    print(f"Row {row_count}: {row}")
                
                if row and 'Zone Summary' in str(row[0]):
                    print(f"Found Zone Summary at row {row_count}")
                    zone_summary_found = True
                    
                    # Print next few rows to see structure
                    for next_row_num in range(5):
                        try:
                            next_row = next(reader)
                            row_count += 1
                            print(f"Row {row_count} after Zone Summary: {next_row}")
                        except StopIteration:
                            break
                
                if row_count > 250:  # Don't read the whole file
                    break
            
            print(f"Zone Summary found: {zone_summary_found}")
            
    except Exception as e:
        print(f"Error reading CSV manually: {e}")
    
    # Call the parsing function
    result = read_zone_areas_from_csv(csv_path)
    
    print(f"\nResults:")
    print(f"Number of zones found: {len(result)}")
    
    if result:
        print(f"\nFirst 5 zones:")
        for i, (zone_name, zone_data) in enumerate(result.items()):
            if i >= 5:
                break
            area = zone_data.get('area', 0)
            multiplier = zone_data.get('multiplier', 1)
            print(f"  {zone_name}: Area = {area} m², Multiplier = {multiplier}")
    else:
        print("No zones found - parsing failed!")
    
    return result

if __name__ == "__main__":
    test_csv_parsing()