# Select one wrist fracture admission or GP record date as the index date for wrist fracture per patient

# In detail:
# - Reshape hip fracture table from dataset_definition.py from one row per patient 
#   (with columns for max n number of distinct candidate admission dates)
#   to one row per admission date that meets the additional eligibility criteria 
#   (at admission date, patient aged 18 or above, has no hip fracture in prior 6 months
#   and has at least 6 months GP practice registration),
# - Exclude patients with more than max n candidate admission dates (no eligibility criteria applied)
# - Randomly select one eligible hip fracture admission date per patient to be the hip fracture index date for the patient

# See detailed comments in analysis/s1_cohort/hip/select_hip_index_event.py

from hashlib import sha256
from pathlib import Path

import pandas as pd

# Specify paths for files
INPUT_FILE = Path("output/wrist_candidates.csv.gz")
OUTPUT_FILE = Path("output/selected_wrist_index_cases.csv")
QA_FILE = Path("output/selected_wrist_index_cases_qa.csv")

# Set parameters
MAX_CANDIDATE_DATES_PER_SOURCE = 15
RANDOM_SEED = "wrist-index-selection-v1"

# Create function to ensure boolean columns defined properly
def as_boolean(series):
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)

    return (
        series.astype("string")
        .str.upper()
        .isin(["T", "TRUE", "1"])
    )

# Function that labels data sources a candidate date features when hospital admissions and GP records are combined
def combine_sources(values):

    sources = set(values)

    if sources == {"hospital", "gp"}:
        return "both"

    if "hospital" in sources:
        return "hospital"

    return "gp"

# Read in output from dataset_definition_wrist.py as dataframe
patients = pd.read_csv(INPUT_FILE)

# For admissions then GP records, drop rows where patient had no nth candidate date ------------------------------
# Pivot data from wide to long for 1st to MAX_CANDIDATE_DATES_PER_SOURCE (nth) candidate date
# So each patient has x number of rows for x number of candidate dates in the selected period (up to max n)
# Unlike hip fracture script, not filtering for only eligible candidate dates here yet

# Create empty list for appending loop outputs
candidate_frames = []

# Do for both data sources - admission columns then GP record columns
for source_name in ["hospital", "gp"]:

    # Loop through 1 to max n candidate number
    for candidate_number in range(
        1,
        MAX_CANDIDATE_DATES_PER_SOURCE + 1,
    ):
        # Make column names (to get relevant cols for nth candidate_number for data source from the output table)
        column_prefix = (
            f"candidate_wrist_{source_name}_"
            f"{candidate_number}"
        )

        date_column = f"{column_prefix}_date"
        eligibility_column = (
            f"{column_prefix}_is_eligible_index"
        )
        age_column = f"{column_prefix}_age"

        # Separate out columns for nth candidate_number for data source into df
        candidate = patients[
            [
                "patient_id",
                date_column,
                eligibility_column,
                age_column,
            ]
        ].copy()

        # Rename columns (allows row binding later)
        candidate = candidate.rename(
            columns={
                date_column: "index_date",
                eligibility_column: "is_eligible_index",
                age_column: "age_at_index",
            }
        )

        # Create column with data source
        candidate["candidate_source"] = source_name

        # Create column with candidate number
        candidate["source_candidate_number"] = candidate_number

        # Convert index date from string to datetime
        candidate["index_date"] = pd.to_datetime(
            candidate["index_date"],
            errors="coerce",
        )

        # Use custom function to make eligibility marker boolean
        candidate["is_eligible_index"] = as_boolean(
            candidate["is_eligible_index"]
        )

        # Keep only patients whose candidate date is not missing 
        # for their nth candidate admission
        # i.e. they had nth number of distinct admission/GP record dates
        # No eligibility filter applied yet
        candidate = candidate.loc[
            candidate["index_date"].notna()
        ]

        # Add dataframe with patients with admission/GP record for nth candidate number to list
        candidate_frames.append(candidate)

# Bind all dataframes with candidate admissions and GP records together by row - create new row index
source_candidates = pd.concat(
    candidate_frames,
    ignore_index=True,
)

# Count number of unique eligibility flags per patient and index date combo
# Eligibility must agree when the same patient and date appear
# in both hospital and GP data.
eligibility_counts = (
    source_candidates
    .groupby(["patient_id", "index_date"])
    ["is_eligible_index"]
    .nunique()
)

# Check that the number of unique eligibility flags per patient per index date is less than or equal to 1
# Ensures that eligibility is the same for a candidate date that appears in both hospital admissions and GP records
# Raises error and stops running if not
assert eligibility_counts.le(1).all()

# Collapse data from both sources so only one record per patient per candidate date remains ------------------------------------
# (Still a many rows per patient table as one patient can have multiple candidate dates, 
# pulling dates from both sources)

# For each patient ID and candidate date
# - Get the eligibility flag (check above ensures flag is the same for dates in both sources)
# - Get patient age at that date (chooses the first - because of sequence, age in admissions preferred)
# - Label data source the date was derived from
combined_candidates = (
    source_candidates
    .groupby(
        [
            "patient_id",
            "index_date",
        ],
        as_index=False,
    )
    .agg(
        is_eligible_index=(
            "is_eligible_index",
            "first",
        ),
        age_at_index=(
            "age_at_index",
            "first",
        ),
        index_source=(
            "candidate_source",
            combine_sources,
        ),
    )
)

# Separate out flag columns for whether patient has more than MAX_CANDIDATE_DATES_PER_SOURCE (n) candidate dates (irrespective of eligibility) -----------
# in each source from original output table (one row per patient)
# Note that these flag are comparing the count of all candidate dates in the data source for a patient to the threshold, 
# not the count of eligible candidate dates only

# Get patient ID and more than max candidate dates indicator columns for admissions and GP records
overflow = patients[
    [
        "patient_id",
        "has_more_than_15_candidate_wrist_hospital_dates",
        "has_more_than_15_candidate_wrist_gp_dates",
    ]
].copy()

# Convert more than max candidate dates indicators to boolean using custom function - as new col
# For both data sources
overflow["has_hospital_candidate_overflow"] = as_boolean(
    overflow[
        "has_more_than_15_candidate_wrist_hospital_dates"
    ]
)

overflow["has_gp_candidate_overflow"] = as_boolean(
    overflow[
        "has_more_than_15_candidate_wrist_gp_dates"
    ]
)

# Create boolean indicator for if patient has more than max candidate dates in either data source
overflow["has_any_candidate_overflow"] = (
    overflow["has_hospital_candidate_overflow"]
    | overflow["has_gp_candidate_overflow"]
)

# Keep patient ID, modified indicators and new indicator in table
overflow = overflow[
    [
        "patient_id",
        "has_hospital_candidate_overflow",
        "has_gp_candidate_overflow",
        "has_any_candidate_overflow",
    ]
]

# Join overflow flag to table with one row per patient per candidate date
combined_candidates = combined_candidates.merge(
    overflow,
    on="patient_id",
    how="left",
)

# Keep only candidate dates that meet eligibility criteria ---------------------------------------------------------
# (at date: aged 18 or over, no hip fracture in prior 6 months, at least 6 months registration)
# (still a many rows per patient table as one patient can have multiple eligible candidate dates)
eligible_candidates = combined_candidates.loc[
    combined_candidates["is_eligible_index"]
].copy()

# Drop patients with more than max candidate dates in either data source -------------------------------------
selection_pool = eligible_candidates.loc[
    ~eligible_candidates["has_any_candidate_overflow"]
].copy()

# Create function that takes one eligible candidate row and creates a hash using a string made up of the following bits:
# - Prefix defined above (RANDOM_SEED)
# - Patient ID
# - Index date for candidate date meeting eligibility criteria
def selection_score(row):
    key = "|".join(
        [
            RANDOM_SEED,
            str(row["patient_id"]),
            row["index_date"].date().isoformat(),
        ]
    )

    return sha256(key.encode("utf-8")).hexdigest()

# Generate a hash for each row using the function
selection_pool["selection_score"] = selection_pool.apply(
    selection_score,
    axis=1,
)

# Count the number of eligible candidate dates across both data sources per patient (with no overflow)
eligible_counts = (
    selection_pool
    .groupby("patient_id")
    .size()
    .rename("number_of_eligible_wrist_index_events")
    .reset_index()
)

# Select one eligible candidate admission or GP record as the index date per patient -----------------------------

# Sorts the candidate rows per patient by the hash and date and selects the first one,
# so the final table for wrist fracture patients contains one eligible candidate admission/GP record 
# as the index date per patient with no more than max n admissions/GP records for wrist fracture in that period
# Join count of eligible candidate admission dates for patient
selected_cases = (
    selection_pool
    .sort_values(
        [
            "patient_id",
            "selection_score",
            "index_date",
        ]
    )
    .drop_duplicates("patient_id")
    .merge(
        eligible_counts,
        on="patient_id",
        how="left",
    )
)

# Convert age to integer for final table 
selected_cases["age_at_index"] = pd.to_numeric(
    selected_cases["age_at_index"],
    errors="coerce",
).astype("Int64")

# Label fracture type
selected_cases["fracture_type"] = "wrist"

# Specify output table column order
output_columns = [
    "patient_id",
    "index_date",
    "fracture_type",
    "index_source",
    "number_of_eligible_wrist_index_events",
    "age_at_index",
]

# Write the final table with wrist fracture patients and their selected index date
selected_cases[output_columns].to_csv(
    OUTPUT_FILE,
    index=False,
    date_format="%Y-%m-%d",
)

# Create QA table to check selection ----------------------------------------------------------------------
# - patients_in_candidate_dataset: Initial number of patients from dataset_definition_wrist.py
# - patients_with_eligible_candidate: Number of patients with eligible candidate admissions/GP records
# - patients_with_hospital_candidate_overflow: Number of patients with more than max n candidate admissions (dropped)
# - patients_with_gp_candidate_overflow: Number of patients with more than max n candidate GP records (dropped)
# - patients_with_any_candidate_overflow: Number of patients with more than max n candidate admissions or GP records (dropped)
# - selected_wrist_index_cases: Final number of patients selected

# The overflow numbers are not limited to those with eligible candidates
# So the selected n patients is not patients with eligible candidates minus patients with overflow
qa = pd.DataFrame(
    {
        "metric": [
            "patients_in_candidate_dataset",
            "patients_with_eligible_candidate",
            "patients_with_hospital_candidate_overflow",
            "patients_with_gp_candidate_overflow",
            "patients_with_any_candidate_overflow",
            "selected_wrist_index_cases",
        ],
        "value": [
            patients["patient_id"].nunique(),
            eligible_candidates["patient_id"].nunique(),
            overflow.loc[
                overflow["has_hospital_candidate_overflow"],
                "patient_id",
            ].nunique(),
            overflow.loc[
                overflow["has_gp_candidate_overflow"],
                "patient_id",
            ].nunique(),
            overflow.loc[
                overflow["has_any_candidate_overflow"],
                "patient_id",
            ].nunique(),
            selected_cases["patient_id"].nunique(),
        ],
    }
)

# Write QA file
qa.to_csv(QA_FILE, index=False)