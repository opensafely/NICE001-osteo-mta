from pathlib import Path

import pandas as pd


INPUT_FILE = Path(
    "output/matched_matches_hip_2024.arrow"
)
OUTPUT_FILE = Path(
    "output/hip_matched_controls_for_ehrql_2024.csv.gz"
)


matched_controls = pd.read_feather(INPUT_FILE)

required_columns = [
    "patient_id",
    "index_date",
    "set_id",
]

missing_columns = set(required_columns) - set(
    matched_controls.columns
)

if missing_columns:
    raise ValueError(
        "Matched-control file is missing columns: "
        + ", ".join(sorted(missing_columns))
    )

matched_controls["index_date"] = pd.to_datetime(
    matched_controls["index_date"],
    errors="coerce",
)

if matched_controls["index_date"].isna().any():
    raise ValueError(
        "Matched controls contain a missing or invalid index date"
    )

if matched_controls["patient_id"].duplicated().any():
    raise ValueError(
        "A control patient appears in more than one matched set"
    )

matched_controls["index_date"] = matched_controls[
    "index_date"
].dt.strftime("%Y-%m-%d")

matched_controls[required_columns].to_csv(
    OUTPUT_FILE,
    index=False,
    compression="gzip",
)
