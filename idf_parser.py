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

def split_objects(fields):
    """Split fields that might contain multiple objects (separated by semicolons)"""
    result = []
    current_fields = []
    
    for field in fields:
        if ';' in field:
            # Split the field that contains semicolon
            parts = field.split(';')
            # Add the first part to current fields
            if parts[0].strip():
                current_fields.append(parts[0].strip())
            if current_fields:
                result.append(current_fields)
            current_fields = []
            # Start new object with remaining parts if they exist
            if len(parts) > 1 and parts[1].strip():
                current_fields.append(parts[1].strip())
        else:
            current_fields.append(field.strip())
            
    if current_fields:
        result.append(current_fields)
    return result

def parse_idf(file_path, settings_keys=None):
    """
    Parses an IDF file line by line, yielding comments and object definitions.
    """
    if settings_keys is None:
        settings_keys = set()
    current_object_keyword = None
    current_object_lines = []
    current_zone_id = None

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, original_line_full in enumerate(f, 1):
                original_line = original_line_full.strip()

                if not original_line: continue # Skip blank lines

                # Handle Comments
                if original_line.startswith('!'):
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
                                    value_part = strip_inline_comment(comment_text_full.split(':', 1)[1].strip())

                            if is_setting:
                                yield ('comment', key_part, value_part, current_zone_id)
                            else:
                                yield ('comment', comment_text_full, None, current_zone_id)
                    continue

                # Handle Objects
                if current_object_keyword: # Inside a multi-line object
                    current_object_lines.append(original_line)
                    if original_line.strip().endswith(';'):
                        # End of object - process accumulated lines
                        keyword = current_object_keyword
                        all_content_lines = []

                        for line in current_object_lines:
                            cleaned_line = strip_inline_comment(line.strip())
                            if not cleaned_line or cleaned_line.startswith('!'):
                                continue
                            if line == current_object_lines[0]:
                                cleaned_line = re.sub(r"^\s*" + re.escape(keyword) + r"\s*,?\s*", "", cleaned_line, count=1)
                            if line == current_object_lines[-1]:
                                cleaned_line = cleaned_line.rstrip(';')
                            all_content_lines.append(cleaned_line)

                        full_content = " ".join(all_content_lines)
                        fields = [f.strip() for f in full_content.split(',')]
                        cleaned_fields = [f for f in fields if f]

                        # Split into multiple objects if semicolons are present
                        object_fields_list = split_objects(cleaned_fields)
                        for fields in object_fields_list:
                            yield ('object', keyword, fields, current_zone_id)

                        current_object_keyword = None
                        current_object_lines = []

                else: # Potentially starting a new object
                    if not original_line.strip().startswith('!'):
                        match = re.match(r"^\s*([^!,;]+?)\s*,", original_line)
                        if match:
                            keyword = match.group(1).strip()
                            current_object_keyword = keyword
                            current_object_lines = [original_line]

                            # Update zone context if it's a Zone object
                            if keyword.lower() == 'zone':
                                zone_name_match = re.match(r"^\s*[^,]+,\s*(.*?)\s*(?:!|,|;|$)", original_line)
                                if zone_name_match:
                                    potential_zone_id = strip_inline_comment(zone_name_match.group(1).strip())
                                    if potential_zone_id:
                                        current_zone_id = potential_zone_id

                            # Handle single-line objects
                            if original_line.strip().endswith(';'):
                                cleaned_line = strip_inline_comment(original_line.strip())
                                cleaned_line = re.sub(r"^\s*" + re.escape(keyword) + r"\s*,?\s*", "", cleaned_line, count=1)
                                cleaned_line = cleaned_line.rstrip(';')
                                fields = [f.strip() for f in cleaned_line.split(',')]
                                cleaned_fields = [f for f in fields if f]

                                # Split into multiple objects if semicolons are present
                                object_fields_list = split_objects(cleaned_fields)
                                for fields in object_fields_list:
                                    yield ('object', keyword, fields, current_zone_id)

                                current_object_keyword = None
                                current_object_lines = []

    except FileNotFoundError:
        print(f"Error: IDF file not found at {file_path}")
        raise
    except Exception as e:
        print(f"An error occurred during IDF parsing on or near line {line_num}: {e}")
        raise

if __name__ == '__main__':
    test_file = 'in.idf'
    print(f"Testing parser with {test_file}")
    test_settings = {'Version Identifier'}
    try:
        for element_type, identifier, data, zone_id_context in parse_idf(test_file, test_settings):
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