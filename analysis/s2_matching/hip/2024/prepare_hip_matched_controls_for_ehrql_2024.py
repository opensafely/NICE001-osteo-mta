# QA checks for matched controls after matching action 
# so matching variables can be extracted for them in next script with ehrql on their inherited index date
# to check if they still fit the matching criteria
# (Matching variables for them currently taken on fixed date)

# - Check required columns are present (patient ID, index date and set ID [patient ID of the case they are matched to])
# - Check all matches have an index date
# - Check none of the matches are matched to more than one case

from pathlib import Path

import pandas as pd

# Specify paths for files
INPUT_FILE = Path(
    "output/matched_matches_hip_2024.arrow"
)
OUTPUT_FILE = Path(
    "output/hip_matched_controls_for_ehrql_2024.csv.gz"
)

# Read in arrow output file from matching action containing matched controls
# as a pandas.DataFrame
matched_controls = pd.read_feather(INPUT_FILE)

# Check if patient ID, index date and set ID are missing ----------

# Specify required columns
required_columns = [
    "patient_id",
    "index_date",
    "set_id",
]

# Return patient_id, index_date and/or set_id if any are missing in the matched controls file
missing_columns = set(required_columns) - set(
    matched_controls.columns
)

# If any of the required columns are missing, raise error
if missing_columns:
    raise ValueError(
        "Matched-control file is missing columns: "
        + ", ".join(sorted(missing_columns))
    )

# Convert index date to datetime
matched_controls["index_date"] = pd.to_datetime(
    matched_controls["index_date"],
    errors="coerce",
)

# If any matched controls have a missing index date, raise error
if matched_controls["index_date"].isna().any():
    raise ValueError(
        "Matched controls contain a missing or invalid index date"
    )

# If the same patient has been selected as a control for more than one case, raise error
if matched_controls["patient_id"].duplicated().any():
    raise ValueError(
        "A control patient appears in more than one matched set"
    )

# Convert index date to string
matched_controls["index_date"] = matched_controls[
    "index_date"
].dt.strftime("%Y-%m-%d")

# Save table with matched controls - just patient ID, index date (inherited from the case) 
# and the set ID 
matched_controls[required_columns].to_csv(
    OUTPUT_FILE,
    index=False,
    compression="gzip",
)
