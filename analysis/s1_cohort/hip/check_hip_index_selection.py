from hashlib import sha256
from pathlib import Path

import pandas as pd

# Repeats code in select_hip_index_event.py -------------------------------------------
CANDIDATE_FILE = Path("output/dataset.csv.gz")
SELECTED_FILE = Path("output/selected_hip_index_cases.csv")
REPORT_FILE = Path("output/hip_index_selection_check.txt")

MAX_CANDIDATE_DATES = 15
RANDOM_SEED = "hip-index-selection-v1"

def as_boolean(series):
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)

    return (
        series.astype("string")
        .str.upper()
        .isin(["T", "TRUE", "1"])
    )


patients = pd.read_csv(CANDIDATE_FILE)

# Read in output file from select_hip_index_event.py - selected hip fracture patients
actual = pd.read_csv(
    SELECTED_FILE,
    parse_dates=["index_date"],
)

# Rerun selection steps in select_hip_index_event.py to check that hash is reproducible ----------
candidate_frames = []

for candidate_number in range(1, MAX_CANDIDATE_DATES + 1):
    date_column = f"candidate_hip_date_{candidate_number}"
    eligibility_column = (
        f"candidate_hip_is_eligible_index_{candidate_number}"
    )
    age_column = f"candidate_hip_age_{candidate_number}"
    practice_column = (
        f"candidate_hip_practice_{candidate_number}"
    )
    care_home_column = (
        f"candidate_hip_care_home_{candidate_number}"
    )

    candidate = patients[
        [
            "patient_id",
            "sex",
            date_column,
            eligibility_column,
            age_column,
            practice_column,
            care_home_column,
        ]
    ].copy()

    candidate = candidate.rename(
        columns={
            date_column: "index_date",
            eligibility_column: "is_eligible_index",
            age_column: "age_at_index",
            practice_column: "practice_at_index",
            care_home_column: "care_home_at_index",
        }
    )

    candidate["candidate_number"] = candidate_number
    candidate["index_date"] = pd.to_datetime(
        candidate["index_date"],
        errors="coerce",
    )
    candidate["is_eligible_index"] = as_boolean(
        candidate["is_eligible_index"]
    )

    candidate = candidate.loc[
        candidate["index_date"].notna()
        & candidate["is_eligible_index"]
    ]

    candidate_frames.append(candidate)


eligible_candidates = pd.concat(
    candidate_frames,
    ignore_index=True,
)

overflow = patients[
    [
        "patient_id",
        "has_more_than_15_candidate_hip_dates",
    ]
].copy()

overflow["has_candidate_overflow"] = as_boolean(
    overflow["has_more_than_15_candidate_hip_dates"]
)

eligible_candidates = eligible_candidates.merge(
    overflow[
        [
            "patient_id",
            "has_candidate_overflow",
        ]
    ],
    on="patient_id",
    how="left",
)

selection_pool = eligible_candidates.loc[
    ~eligible_candidates["has_candidate_overflow"]
].copy()


def selection_score(row):
    key = "|".join(
        [
            RANDOM_SEED,
            str(row["patient_id"]),
            row["index_date"].date().isoformat(),
            str(row["candidate_number"]),
        ]
    )

    return sha256(key.encode("utf-8")).hexdigest()


selection_pool["selection_score"] = selection_pool.apply(
    selection_score,
    axis=1,
)

eligible_counts = (
    selection_pool
    .groupby("patient_id")
    .size()
    .rename("number_of_eligible_hip_index_events")
    .reset_index()
)

# Store selected patients (same method as select_hip_index_event.py) as QA table ------------------
expected = (
    selection_pool
    .sort_values(
        [
            "patient_id",
            "selection_score",
            "candidate_number",
        ]
    )
    .drop_duplicates("patient_id")
    .merge(
        eligible_counts,
        on="patient_id",
        how="left",
    )
)

expected["fracture_type"] = "hip"
expected["index_source"] = "hospital"

comparison_columns = [
    "patient_id",
    "index_date",
    "fracture_type",
    "index_source",
    "candidate_number",
    "number_of_eligible_hip_index_events",
    "age_at_index",
    "sex",
    "practice_at_index",
    "care_home_at_index",
]

# Checks ----------------------------------------------------------------------------------------
# If condition is True, program continues running

# Check patient ID is unique in selected patients
assert actual["patient_id"].is_unique

# Check that no missing index date for selected patients
assert not actual["index_date"].isna().any()

# Check that fracture type assigned is "hip" for all selected patients
assert (actual["fracture_type"] == "hip").all()

# Check that index source is "hospital" for all selected patients
assert (actual["index_source"] == "hospital").all()

# Convert age at index in the selection output table (holds selected patients) and QA table to integer
actual["age_at_index"] = pd.to_numeric(
    actual["age_at_index"],
    errors="coerce",
).astype("Int64")

expected["age_at_index"] = pd.to_numeric(
    expected["age_at_index"],
    errors="coerce",
).astype("Int64")

# Convert practice ID in the selection output and QA table to integer
actual["practice_at_index"] = pd.to_numeric(
    actual["practice_at_index"],
    errors="coerce",
).astype("Int64")

expected["practice_at_index"] = pd.to_numeric(
    expected["practice_at_index"],
    errors="coerce",
).astype("Int64")

# Reorder columns in selection output table 
actual = (
    actual[comparison_columns]
    .sort_values("patient_id")
    .reset_index(drop=True)
)

# Reorder columns in QA table to same order as selection output table
expected = (
    expected[comparison_columns]
    .sort_values("patient_id")
    .reset_index(drop=True)
)

# Check that the selection output table and QA table are the same
# Ignore datatype difference
# Raises error if tables are not the same and script stops running
pd.testing.assert_frame_equal(
    actual,
    expected,
    check_dtype=False,
)

# Report QA results
# Only get here if the checks above are passed
report = (
    "Hip index selection checks: All OK!\n"
    f"Eligible non-overflow patients checked: {len(expected)}\n"
    f"Selected index events checked: {len(actual)}\n"
    "Each patient contributed exactly one selected hip index event.\n"
    "Reproducible random selection was confirmed.\n"
    "Patients with candidate overflow were excluded.\n"
)

# Write QA check results to txt file
REPORT_FILE.write_text(report, encoding="utf-8")

# Print QA check results
print(report, end="")
