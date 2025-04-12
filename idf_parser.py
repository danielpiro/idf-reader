import re

def strip_inline_comment(line):
    """Removes inline comments starting with '!' that are not at the beginning."""
    try:
        comment_start_index = line.index('!')
        # Remove comment if '!' is not the very first character
        if comment_start_index > 0:
            return line[:comment_start_index].strip()
        # If '!' is the first character or not found, return original line
        return line
    except ValueError:
        return line # Return original if '!' not found

def parse_idf(file_path, settings_keys=None):
    """
    Parses an IDF file line by line, yielding comments and object definitions.
    Objects are yielded with their keyword, a list of cleaned data fields,
    and the current zone context. Handles multi-line objects and comments.

    Note: Many common simulation settings (e.g., Version, RunPeriod,
    Site:Location, SimulationControl) are defined as standard IDF objects,
    not as comments. The code consuming this parser's output should check
    for yielded elements with element_type='object' and the corresponding
    keyword (identifier) to retrieve data for these settings. Settings comments
    (! Key : Value) are typically used for metadata or less common parameters.

    Args:
        file_path (str): The path to the IDF file.
        settings_keys (set, optional): Known keys for settings comments.

    Yields:
        tuple: (element_type, identifier, data, current_zone_id)
            - element_type (str): 'comment' or 'object'.
            - identifier (str): Settings key, other comment text, or object keyword.
            - data (list/str/None): Comment value, list of cleaned object fields, or None.
            - current_zone_id (str or None): ID of the current zone.
    """
    if settings_keys is None:
        settings_keys = set()
    current_object_keyword = None
    current_object_lines = [] # Accumulate raw lines for the current object block
    current_zone_id = None

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, original_line_full in enumerate(f, 1):
                original_line = original_line_full.strip()

                if not original_line: continue # Skip blank lines

                # Handle Comments
                if original_line.startswith('!'):
                    # If inside an object definition, store comment line as part of it
                    if current_object_keyword:
                         current_object_lines.append(original_line)
                    else: # Process top-level comments
                        comment_text_full = original_line[1:].strip()
                        if comment_text_full:
                            key_part, value_part, is_setting = None, None, False
                            if ':' in comment_text_full:
                                potential_key = comment_text_full.split(':', 1)[0].strip()
                                if potential_key in settings_keys:
                                    is_setting = True
                                    key_part = potential_key
                                    value_part = strip_inline_comment(comment_text_full.split(':', 1)[1].strip()) # Clean value only

                            if is_setting:
                                yield ('comment', key_part, value_part, current_zone_id)
                            else:
                                yield ('comment', comment_text_full, None, current_zone_id)
                    continue # Move to next line after processing comment

                # Handle Objects
                if current_object_keyword: # Inside a multi-line object
                    current_object_lines.append(original_line) # Append raw line
                    if original_line.strip().endswith(';'): # Check stripped line end
                        # End of object - process accumulated lines
                        keyword = current_object_keyword
                        all_content_lines = []
                        num_lines = len(current_object_lines)

                        for i, line in enumerate(current_object_lines):
                            # 1. Strip leading/trailing whitespace and remove comments
                            cleaned_line = strip_inline_comment(line.strip())

                            # 2. Skip empty lines or lines that were only comments
                            if not cleaned_line or cleaned_line.startswith('!'):
                                continue

                            # 3. Handle first line: remove keyword
                            if i == 0:
                                cleaned_line = re.sub(r"^\s*" + re.escape(keyword) + r"\s*,?\s*", "", cleaned_line, count=1)

                            # 4. Handle last relevant line: find the actual last line with content
                            #    Need to check if this *is* the last line with content before removing ';'
                            is_last_content_line = False
                            if i == num_lines - 1: # If it's the absolute last line
                                is_last_content_line = True
                            else:
                                # Check if subsequent lines are all comments/empty
                                all_following_are_comments = True
                                for j in range(i + 1, num_lines):
                                    following_line_cleaned = strip_inline_comment(current_object_lines[j].strip())
                                    if following_line_cleaned and not following_line_cleaned.startswith('!'):
                                        all_following_are_comments = False
                                        break
                                if all_following_are_comments:
                                    is_last_content_line = True

                            if is_last_content_line:
                                cleaned_line = cleaned_line.rstrip().rstrip(';')

                            # 5. Append the processed line content
                            all_content_lines.append(cleaned_line)

                        # 6. Join all processed lines and then split by comma
                        full_content = " ".join(all_content_lines) # Join with space
                        fields = [f.strip() for f in full_content.split(',')]
                        cleaned_fields = [f for f in fields if f] # Remove empty fields

                        yield ('object', keyword, cleaned_fields, current_zone_id)

                        # Reset state AFTER yielding
                        current_object_keyword = None
                        current_object_lines = []

                else: # Potentially starting a new object
                    if not original_line.strip().startswith('!'):
                        match = re.match(r"^\s*([^!,;]+?)\s*,", original_line)
                        if match:
                            keyword = match.group(1).strip()
                            current_object_keyword = keyword
                            current_object_lines = [original_line] # Start accumulating

                            # Update zone context if it's a Zone object
                            if keyword.lower() == 'zone':
                                 zone_name_match = re.match(r"^\s*[^,]+,\s*(.*?)\s*(?:!|,|;|$)", original_line)
                                 if zone_name_match:
                                     potential_zone_id = strip_inline_comment(zone_name_match.group(1).strip())
                                     if potential_zone_id:
                                         current_zone_id = potential_zone_id

                            # Handle single-line objects immediately
                            if original_line.strip().endswith(';'): # Check stripped line end
                                # Process the accumulated (single) line
                                keyword = current_object_keyword
                                cleaned_line = strip_inline_comment(original_line.strip()) # Clean comments

                                # Remove keyword and first comma
                                cleaned_line = re.sub(r"^\s*" + re.escape(keyword) + r"\s*,?\s*", "", cleaned_line, count=1)
                                # Remove trailing semicolon
                                cleaned_line = cleaned_line.rstrip().rstrip(';')
                                # Split and clean fields
                                fields = [f.strip() for f in cleaned_line.split(',')]
                                cleaned_fields = [f for f in fields if f]

                                yield ('object', keyword, cleaned_fields, current_zone_id)

                                # Reset state AFTER yielding
                                current_object_keyword = None
                                current_object_lines = []
                            # else: Multi-line object started, continue accumulating

    except FileNotFoundError:
        print(f"Error: IDF file not found at {file_path}")
        raise
    except Exception as e:
        print(f"An error occurred during IDF parsing on or near line {line_num}: {e}") # Added line number context
        raise

if __name__ == '__main__':
    test_file = 'in.idf'
    print(f"Testing parser with {test_file}")
    test_settings = {'Version Identifier'} # Example setting key
    try:
        # Test loop expects 4 args, data is list of cleaned fields
        for element_type, identifier, data, zone_id_context in parse_idf(test_file, settings_keys=test_settings):
            print(f"Type: {element_type}, ID/Keyword: {identifier}")
            if isinstance(data, list):
                print("  Cleaned Fields:")
                for i, item in enumerate(data):
                    print(f"    [{i}] - '{item}'")
            else:
                print(f"  Value: {data}")
            print(f"  Zone Context: {zone_id_context}")
            print("-" * 10)
    except FileNotFoundError:
        print(f"Test file '{test_file}' not found. Cannot run example.")
    except Exception as e:
        print(f"Error during test: {e}")