# idf_code_cleaner.py
import os
import re
import subprocess
import sys

# --- Configuration ---
TARGET_DIRECTORIES = ["generators", "parsers", "utils"]
TARGET_FILES_IN_ROOT = ["main.py", "gui.py", "package.py"]
AUTOFLAKE_ARGS = [
    "autoflake",
    "--in-place",
    "--remove-all-unused-imports",
    "--remove-unused-variables",
    "--remove-duplicate-keys",
    "--exclude", "**/__init__.py"
]
# Regex for print and logging.debug statements (match whole lines)
# Using re.MULTILINE means ^ and $ match start/end of lines.
# Adding \r?\n? to consume the newline if the line is removed.
PRINT_RE = re.compile(r"^\s*print\s*\(.*?\)\s*(#.*)?\s*$", re.MULTILINE)
LOGGING_DEBUG_RE = re.compile(r"^\s*logging\.debug\s*\(.*?\)\s*(#.*)?\s*$", re.MULTILINE)

PRESERVED_COMMENT_PATTERNS = [
    re.compile(r"^\s*# type:"),
    re.compile(r"^\s*# noqa"),
    re.compile(r"^\s*# pragma:"),
    re.compile(r"^\s*# pylint:"),
    re.compile(r"^\s*# TODO"),
    re.compile(r"^\s*# FIXME"),
    re.compile(r"^\s*#!"),  # Shebang
]

# --- Helper Functions ---
def get_files_to_process():
    files_to_process = []
    for target_dir in TARGET_DIRECTORIES:
        if os.path.isdir(target_dir):
            for root_dir, _, files_in_dir in os.walk(target_dir):
                for file_in_dir in files_in_dir:
                    if file_in_dir.endswith(".py"):
                        files_to_process.append(os.path.join(root_dir, file_in_dir))
        else:
            print(f"Warning: Directory '{target_dir}' not found. Skipping.")
    
    for target_file in TARGET_FILES_IN_ROOT:
        if os.path.isfile(target_file):
            files_to_process.append(target_file)
        else:
            print(f"Warning: File '{target_file}' not found. Skipping.")
            
    return sorted(list(set(files_to_process)))

def run_autoflake(filepath):
    try:
        command = AUTOFLAKE_ARGS + [filepath]
        result = subprocess.run(command, capture_output=True, text=True, check=False, encoding='utf-8')
        if result.returncode != 0:
            # Autoflake can have non-zero exit if it makes changes, so check stderr for actual errors
            if result.stderr and "Traceback" in result.stderr: # A more specific error check might be needed
                 print(f"Autoflake error on {filepath}: {result.stderr}")
    except Exception as e:
        print(f"Failed to run autoflake on {filepath}: {e}")

def is_comment_preserved(comment_text):
    for pattern in PRESERVED_COMMENT_PATTERNS:
        if pattern.match(comment_text):
            return True
    return False

def clean_file_content_custom(code_content):
    # 1. Remove print and logging.debug statements
    code_content = PRINT_RE.sub("", code_content)
    code_content = LOGGING_DEBUG_RE.sub("", code_content)

    # 2. Remove general comments line by line
    lines = code_content.splitlines()
    processed_lines = []
    for line in lines:
        stripped_line = line.lstrip()
        
        # Handle full-line comments
        if stripped_line.startswith("#"):
            if not is_comment_preserved(stripped_line):
                # If the line is only this comment (and whitespace), skip it
                if re.fullmatch(r"\s*#.*", line):
                    continue 
        
        # Handle inline comments
        # Find the position of '#' not inside a string (this is a simplified check)
        hash_pos = -1
        in_string_single_quote = False
        in_string_double_quote = False
        for i, char in enumerate(line):
            if char == "'" and (i == 0 or line[i-1] != '\\'):
                in_string_single_quote = not in_string_single_quote
            elif char == '"' and (i == 0 or line[i-1] != '\\'):
                in_string_double_quote = not in_string_double_quote
            elif char == '#' and not in_string_single_quote and not in_string_double_quote:
                hash_pos = i
                break
        
        if hash_pos != -1:
            comment_part = line[hash_pos:]
            # Check if the comment part itself (when stripped) is a preserved type
            if not is_comment_preserved(comment_part.lstrip()):
                line = line[:hash_pos].rstrip() # Remove inline comment

        processed_lines.append(line)
    
    code_content = "\n".join(processed_lines)
    
    # Normalize multiple blank lines to a maximum of one, but preserve single blank lines
    # This regex replaces 2 or more newlines (potentially with whitespace between them) with two newlines.
    code_content = re.sub(r"(\r?\n)\s*(\r?\n)+", r"\1\1", code_content)
    
    return code_content

# --- Main Logic ---
def main():
    print("Starting code cleanup script (idf_code_cleaner.py)...")
    print("IMPORTANT: This script will modify files in-place.")
    print("It's highly recommended to have your code under version control (e.g., Git).")
    
    # Check for autoflake
    try:
        subprocess.run(["autoflake", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Error: 'autoflake' command not found. Please install it (`pip install autoflake`) and ensure it's in your PATH.")
        sys.exit(1)

    all_py_files = get_files_to_process()
    if not all_py_files:
        print("No Python files found to process based on configuration.")
        return

    print(f"\nFound {len(all_py_files)} Python files to process.")

    # Step 1: Run autoflake on all files
    print("\nStep 1: Running autoflake for unused imports/variables...")
    for filepath in all_py_files:
        run_autoflake(filepath)
    print("Autoflake pass complete.")

    # Step 2: Clean comments and print statements
    print("\nStep 2: Cleaning comments and print statements...")
    custom_cleaned_files_count = 0
    for filepath in all_py_files:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                original_content = f.read()
            
            cleaned_content = clean_file_content_custom(original_content)
            
            # Ensure a single trailing newline if content is not empty
            if cleaned_content.strip(): # If there's any non-whitespace content
                cleaned_content = cleaned_content.strip() + "\n"
            else: # If content became empty, make it truly empty
                cleaned_content = ""

            if cleaned_content != original_content:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(cleaned_content)
                custom_cleaned_files_count +=1
        except Exception as e:
            print(f"Error processing {filepath} for comments/prints: {e}")
    print(f"Comment and print cleaning pass complete. {custom_cleaned_files_count} files affected in this stage.")

    print("\n--------------------------------------------------------------------")
    print("Code cleanup script finished.")
    print("Summary of actions performed by this script:")
    print("- Used 'autoflake' to remove unused imports and variables.")
    print("- Removed debug print() and logging.debug() statements.")
    print("- Removed general comments (preserving docstrings, type hints, shebangs, and common directives like # noqa).")
    print("\nLimitations acknowledged by this script:")
    print("- This script does NOT automatically remove unused functions or classes due to the risk and complexity involved.")
    print("  Identifying these safely requires more advanced static analysis (e.g., using Vulture) and manual review.")
    print("- Comment removal logic targets common cases; complex or unusual comment styles might require manual review.")
    print("\nPlease review the changes made by this script carefully.")
    print("--------------------------------------------------------------------")

if __name__ == "__main__":
    main()