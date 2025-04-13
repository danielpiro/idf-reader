import os
import tempfile
import datetime

try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import numpy as np
except ImportError:
    print("Error: matplotlib library not found.")
    print("Please install it using: pip install matplotlib")
    plt = None # Flag that plotting is unavailable

# Helper function to convert month/day to day of year
def get_day_of_year(month_day_str):
    """Converts 'DD Month' string to day of year (1-366)."""
    try:
        # Assuming non-leap year for simplicity in matching month days
        # Using a fixed year like 2001 (non-leap) for parsing
        dt = datetime.datetime.strptime(f"2001 {month_day_str}", '%Y %d %B')
        return dt.timetuple().tm_yday
    except ValueError:
        # Handle potential parsing errors or different formats if needed
        print(f"Warning: Could not parse date '{month_day_str}'")
        return None

def parse_schedule_rules(raw_rules):
    """
    Parses raw Schedule:Compact rules into a list of (end_day, value) tuples.
    This is a simplified parser assuming 'Through', 'For: AllDays', 'Until'.
    """
    parsed_periods = []
    current_day = 0
    last_value = None

    # Process rules in chunks (assuming Through, For, Until pattern)
    # This needs to be robust to variations. A simple chunking might work for the example.
    i = 0
    while i < len(raw_rules):
        period_data = {}
        # Look for Through, For, Until in the next few lines
        chunk = raw_rules[i:i+3] # Look ahead

        through_str = chunk[0] if len(chunk)>0 else None
        for_str = chunk[1] if len(chunk)>1 else None
        until_str = chunk[2] if len(chunk)>2 else None

        end_day = None
        value = None

        if through_str and through_str.lower().startswith("through:"):
            date_part = through_str.split(":", 1)[1].strip()
            # Remove trailing comma if present before parsing
            if date_part.endswith(','):
                date_part = date_part[:-1].strip()
            end_day = get_day_of_year(date_part)

        # Basic check for 'For: AllDays' - ignore other 'For' types for now
        is_all_days = for_str and "alldays" in for_str.lower()

        if until_str and until_str.lower().startswith("until:"):
            try:
                # Value is usually the last part after the comma
                value_str = until_str.split(',')[-1].strip()
                # Attempt to convert value to float, fallback to string
                if not value_str: # Check if the extracted value string is empty
                    value = np.nan # Use NaN for empty values
                    # print(f"DEBUG: Found empty value for Until: '{until_str}', using NaN.") # Debug
                else:
                    try:
                        value = float(value_str)
                    except ValueError:
                        # Keep as string if conversion to float fails and it wasn't empty
                        # This might be relevant for non-numeric schedule types, though the current
                        # plotting expects numbers. Consider how to handle non-numeric values if needed.
                        print(f"Warning: Could not convert value '{value_str}' to float. Treating as NaN for plotting.")
                        value = np.nan # Use NaN if it's non-empty but not a float
            except IndexError:
                print(f"Warning: Could not parse value from Until: '{until_str}'")
                value = None # Or some default error value

        # If we have the key components for this period
        if end_day is not None and is_all_days and value is not None:
            parsed_periods.append({'end_day': end_day, 'value': value})
            i += 3 # Move past this chunk
        else:
            # Could not parse this chunk as expected, skip to next line
            # This parsing is basic and might need significant improvement for complex schedules
            i += 1

    # Sort periods by end_day
    parsed_periods.sort(key=lambda p: p['end_day'])

    # Create day-by-day values (assuming 365 days)
    # This needs refinement for proper interpolation/step handling
    schedule_values = np.full(365, np.nan) # Initialize with NaN
    start_day = 0
    for period in parsed_periods:
        end_day = period['end_day']
        value = period['value']
        # Fill values from the start of this period up to the end day
        # Use min(end_day, 365) to avoid index errors
        schedule_values[start_day:min(end_day, 365)] = value
        start_day = min(end_day, 365) # Next period starts after this one ends

    # Handle any remaining days if the last period doesn't end on Dec 31
    if start_day < 365 and parsed_periods:
         # Use the value from the last defined period to fill the rest? Or NaN?
         # Let's fill with the last value for now.
         schedule_values[start_day:365] = parsed_periods[-1]['value']

    return schedule_values


def plot_schedule_timeline(schedule_data, output_dir=None):
    """
    Generates a timeline plot for a given schedule.

    Args:
        schedule_data (dict): Dict with 'name', 'type', 'raw_rules'.
        output_dir (str, optional): Directory to save the image. Defaults to temp dir.

    Returns:
        str: Path to the generated temporary image file, or None if plotting fails.
    """
    if plt is None:
        print("Plotting skipped because matplotlib is not installed.")
        return None

    schedule_name = schedule_data.get('name', 'Unnamed Schedule')
    raw_rules = schedule_data.get('raw_rules', [])

    # Parse rules into daily values
    daily_values = parse_schedule_rules(raw_rules)

    if daily_values is None or np.all(np.isnan(daily_values)):
         print(f"Warning: Could not parse or no data found for schedule '{schedule_name}'. Skipping plot.")
         return None

    # --- Plotting ---
    try:
        days = np.arange(1, 366) # Days 1 to 365

        fig, ax = plt.subplots(figsize=(10, 3)) # Adjust figure size as needed

        # Use step plot for schedule values
        ax.step(days, daily_values, where='post', linewidth=1.5)

        # Formatting the x-axis to show months
        # Create date objects for the axis formatter
        base_date = datetime.date(2001, 1, 1) # Use a non-leap year
        dates = [base_date + datetime.timedelta(days=int(d-1)) for d in days]

        ax.set_xlim(1, 365)
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b')) # Month abbreviation

        ax.set_xlabel("Month")
        ax.set_ylabel("Schedule Value")
        ax.set_title(f"Schedule: {schedule_name}", fontsize=10)
        ax.grid(True, axis='y', linestyle='--', linewidth=0.5)
        plt.tight_layout()

        # Save plot to a temporary file
        if output_dir is None:
            output_dir = tempfile.gettempdir()

        # Create a unique filename
        safe_name = "".join(c if c.isalnum() else "_" for c in schedule_name)
        output_image_path = os.path.join(output_dir, f"schedule_{safe_name}_{os.urandom(4).hex()}.png")

        plt.savefig(output_image_path)
        plt.close(fig) # Close the figure to free memory
        # print(f"DEBUG: Saved plot to {output_image_path}") # Debug
        return output_image_path

    except Exception as e:
        print(f"Error generating plot for schedule '{schedule_name}': {e}")
        # Ensure plot is closed if error occurs after figure creation
        if 'fig' in locals() and plt.fignum_exists(fig.number):
             plt.close(fig)
        return None