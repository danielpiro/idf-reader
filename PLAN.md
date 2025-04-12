# IDF Parser Plan

## Phase 1: Settings Report (Completed)

- **Objective:** Parse an IDF file and generate `settings.pdf` with predefined settings.
- **Modules:** `main.py`, `idf_parser.py` (modified in Phase 2), `settings_parser.py`, `pdf_generator.py`.
- **Dependencies:** `reportlab`.
- **Status:** Implemented and verified.

## Phase 2: Schedule Table Report

- **Objective:** Extract specific `Schedule:Compact` objects, identify unique schedule definitions, and present these definitions in a table format in a separate PDF report.
- **Input:** Same as Phase 1 (IDF file path).
- **Output:** The original `settings.pdf` (unchanged from Phase 1) AND a new `schedules.pdf` containing tables for each unique schedule definition found.

### New/Modified Modules (Relative to Phase 1):

1.  **`idf_parser.py` (Modify)**

    - **Purpose:** Parse IDF file, handling comments and objects.
    - **Modifications:**
      - Accepts a `settings_keys` argument (set of known keys like 'Geometry convention template').
      - Differentiates comment types: If a comment line matches `! key: value` and `key` is in `settings_keys`, yields `('comment', key, value, zone_id)`. Otherwise, yields `('comment', text_after_!, None, zone_id)`.
      - Accumulates multi-line objects, removes inline comments, splits by comma, cleans each field (strip whitespace, trailing commas), and yields `('object', keyword, list_of_cleaned_fields, zone_id)`.
      - Correctly extracts `current_zone_id` from the first field of `Zone` objects.

2.  **`schedule_parser.py` (New Module)** (Index adjusted)

    - **Purpose:** Extract relevant `Schedule:Compact` objects based on comments or keywords and identify unique schedule definitions (raw rules).
    - **Class:** `ScheduleExtractor`.
    - **Extraction Logic:**
      - Identify target schedules based on preceding comments (`! Schedule: <Name>`, `! Modified schedule: <Name>`) or keywords in the schedule name ("Heating Availability", "Cooling Availability").
      - Store unique raw schedule data fields (using a set of tuples).
    - **Parsing Logic:** (Simplified) No longer needs complex rule parsing for plotting. Stores raw rules associated with the unique definition.
    - **Modifications:** Updated `process_element` to accept the 4-tuple yield with cleaned fields. Extracts name, type, and rules based on field index.
    - **Output:** Method `get_parsed_unique_schedules()` returning a list of dictionaries, each containing the schedule name, type, and its list of cleaned rule fields: `[{'name': str, 'type': str, 'raw_rules': list_of_strings}]`.

3.  **`timeline_plotter.py` (Removed)** (Index adjusted)

    - This module is no longer needed as timeline plots are replaced by tables.

4.  **`pdf_generator.py` (Modify)** (Index adjusted)

    - **Purpose:** Generate PDF reports.
    - **Modifications:**
      - Split the combined generation function into two:
        - `generate_settings_pdf`: (Essentially unchanged from Phase 1) Takes settings data, outputs `settings.pdf`.
        - `generate_schedules_pdf` (New/Modified): Takes unique schedule data (name, type, cleaned rule fields), formats each schedule's cleaned rule fields into a `reportlab.platypus.Table`, and writes these tables to `schedules.pdf`.

5.  **`main.py` (Modify)** (Index adjusted)
    - **Purpose:** Orchestrate the extended workflow.
    - **Modifications:**
      - Import and instantiate `ScheduleExtractor`.
      - Remove import related to `timeline_plotter`.
      - Update the main loop to pass IDF elements to both extractors.
      - Import `TARGET_COMMENT_KEYS` from `settings_parser`.
      - Pass `settings_keys=set(TARGET_COMMENT_KEYS)` to `parse_idf`.
      - Update parsing loop to handle 4-tuple `(type, id, data, zone_id)` where `data` is cleaned fields for objects (already done).
      - After the loop, get settings data and unique schedule data (with raw rules).
      - Call `generate_settings_pdf` with settings data.
      - Call `generate_schedules_pdf` with schedule data.
      - Remove the `--output` command-line argument.
      - Handle potential errors (ImportError for reportlab, file errors, etc.). Remove specific handling for matplotlib errors.

### Dependencies:

- `reportlab` (install via `pip install reportlab`)
- (`matplotlib` dependency removed)

### Conceptual Flow (Phase 1 + 2 - Table Output):

````mermaid
graph TD
    A[User runs: python main.py path/to/your.idf] --> B(main.py);
    B -- Gets Path --> C(Input IDF File);
    B -- Instantiates & Runs --> D(idf_parser.py);
    D -- Reads Line-by-Line --> C;
    D -- Yields Line/Object --> E(settings_parser.py);
    D -- Yields Line/Object --> I(schedule_parser.py);
    E -- Extracts Settings --> F[Extracted Settings Data (dict)];
    I -- Extracts & Parses Schedules --> J[Parsed Unique Schedule Data (list)];
    B -- Gets Data From --> E;
    B -- Gets Data From --> I;
    B -- Calls --> G_Settings(generate_settings_pdf);
    G_Settings -- Uses --> F;
    G_Settings -- Writes --> H_Settings(settings.pdf);
    B -- Calls --> G_Schedules(generate_schedules_pdf);
    G_Schedules -- Uses --> J; # Uses parsed schedule data (name, type, raw_rules)
    G_Schedules -- Writes --> H_Schedules(schedules.pdf); # Writes tables
    subgraph Phase 3: Load Analysis
        direction LR
        L1[load_parser.py] --> L2[Extract ZoneControl:Thermostat]
        L2 --> L3[Get Unique Zone IDs]
    end
    subgraph Phase 4: Zone Schedule Mapping
         direction LR
         ZS1[zone_schedule_parser.py] --> ZS2[Map Schedules to Zones]
    end
    subgraph Phase 5: Zone Load Data Report
         direction LR
         ZD1[zone_load_data_parser.py] --> ZD2[Extract Load Data per Zone]
         ZD2 --> ZD3[Link Setpoint Schedules]
         ZD3 --> ZD4[Generate Load Report PDF]
         LG1[loads_report_generator.py] --> ZD4
    end

    D -- Yields (type, id, data, zone_id) --> E; # idf_parser includes current zone context
    D -- Yields (type, id, data, zone_id) --> I;
    D -- Yields (type, id, data, zone_id) --> L1;
    D -- Yields (type, id, data, zone_id) --> ZS1;
    D -- Yields (type, id, data, zone_id) --> ZD1;
    B -- Gets Data From --> ZD1;
    B -- Calls --> LG1;
    B -- Gets Data From --> L1;
    B -- Gets Data From --> ZS1;

    subgraph Modules
        direction LR
        D[idf_parser.py]
        E[settings_parser.py]
        I[schedule_parser.py]
        L[load_parser.py]
        ZS[zone_schedule_parser.py]
        ZD[zone_load_data_parser.py]
        LG[loads_report_generator.py]
        D -- Accepts settings_keys --> B; # idf_parser configured by main
        # M[timeline_plotter.py] (Removed)
        G_Settings & G_Schedules (in pdf_generator.py)
    end
| ```

## Phase 3: Load Analysis (Completed)

- **Objective:** Extract unique zone IDs from the IDF file.
- **Modules:** `load_parser.py` added. `main.py`, `idf_parser.py` modified.
- **Status:** Implemented (Zone IDs extracted from `ZoneControl:Thermostat` field 1).

## Phase 4: Zone Schedule Mapping

- **Objective:** Identify all schedules associated with each unique zone.
- **Input:** Same IDF file.
- **Output:** A dictionary mapping each Zone ID to a set of schedule names used within objects belonging to that zone.

### Module Modifications:

1.  **`idf_parser.py` (Modify)**
    - **Purpose:** Add zone context to yielded elements.
    - **Modifications:**
      - Track the `current_zone_id`. When a `Zone` object is encountered, update `current_zone_id` from its first field.
      - Modify the `yield` statement to include `current_zone_id` and yield cleaned fields for objects: `yield (element_type, identifier, cleaned_fields, current_zone_id)`.

### New Module:

1.  **`zone_schedule_parser.py` (New Module)**
    - **Purpose:** Map schedule names to the zone they are used in.
    - **Class:** `ZoneScheduleParser`.
    - **Data Structure:** `schedules_by_zone = {}` (dict mapping zone_id -> set of schedule names).
    - **Extraction Logic:**
      - Receives `(element_type, identifier, data, current_zone_id)` from `idf_parser`, where `data` is a list of cleaned fields for objects.
      - If `element_type == 'object'` and `current_zone_id` is not `None`:
        - Initialize `schedules_by_zone[current_zone_id]` if it doesn't exist.
        - Iterate through the cleaned fields (`data`).
        - Identify potential schedule name fields (e.g., by checking if "schedule" is in the field value).
        - Add the cleaned schedule name (the field value itself) to `schedules_by_zone[current_zone_id]`.
    - **Output:** Method `get_schedules_by_zone()` returning the dictionary.

### Main Changes (`main.py`):
- Import and instantiate `ZoneScheduleParser`.
- Update the parsing loop to handle the new 4-tuple format yielded by `idf_parser`.
- Pass elements to the `zone_schedule_parser`.
- After parsing, retrieve the `schedules_by_zone` dictionary.
- Print or process the results (e.g., print schedules for each zone ID found in Phase 3).

## Phase 5: Zone Load Data Report

- **Objective:** Extract key load parameters for each zone and generate a summary PDF report resembling the user-provided image.
- **Input:** Same IDF file.
- **Output:** `loads_report.pdf` containing a table summarizing zone load data.

### New Modules:

1.  **`zone_load_data_parser.py` (New Module)**
    - **Purpose:** Extract specific load parameters associated with each zone.
    - **Class:** `ZoneLoadDataExtractor`.
    - **Data Structure:** `zone_data = {}` mapping `zone_id` to a dictionary of parameters (e.g., `occupancy_people_per_area`, `lighting_schedule_name`, `heating_setpoint_schedule_name`, `infiltration_ach`).
    - **Extraction Logic:**
      - Receives elements with zone context from `idf_parser` (where `data` is a list of cleaned fields for objects).
      - Identifies relevant objects (`Zone`, `People`, `Lights`, `OtherEquipment`, `ZoneControl:Thermostat`, `ThermostatSetpoint:DualSetpoint`, `ZoneInfiltration:DesignFlowRate`, `ZoneVentilation:DesignFlowRate`).
      - Extracts specific fields from the cleaned fields list based on expected index for each relevant object type.
      - Stores `ThermostatSetpoint:DualSetpoint` schedule names globally keyed by object name for later linking.
      - Assumes Heating/Cooling Availability schedule names based on zone ID convention (can be refined later).
      - Calculates ACH for infiltration/ventilation using zone volume.
    - **Output:** Method `get_zone_load_data()` returning the dictionary. Needs a post-processing step in `main.py` to link setpoint schedules.

2.  **`loads_report_generator.py` (New Module)**
    - **Purpose:** Generate the PDF report table.
    - **Function:** `generate_loads_report_pdf`.
    - **Input:** `zone_load_data` dictionary, list of `zone_ids`.
    - **Functionality:** Uses `reportlab.platypus.Table` to create `loads_report.pdf` matching the image structure (headers, merged cells).

### Main Changes (`main.py`):
- Import and instantiate `ZoneLoadDataExtractor`.
- Import `generate_loads_report_pdf`.
- Pass elements to the `zone_load_data_extractor`.
- After parsing, retrieve `zone_load_data`.
- Perform post-processing to link setpoint schedule names from globally stored data into the `zone_load_data`.
- Call `generate_loads_report_pdf`.
````
