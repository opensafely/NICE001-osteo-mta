# Select one hip fracture admission date as the index date per patient

# In detail:
# - Reshape hip fracture table from dataset_definition.py from one row per patient 
#   (with columns for max n number of distinct candidate admission dates)
#   to one row per admission date that meets the additional eligibility criteria 
#   (at admission date, patient aged 18 or above, has no hip fracture in prior 6 months
#   and has at least 6 months GP practice registration),
# - Exclude patients with more than max n candidate admission dates (no eligibility criteria applied)
# - Randomly select one eligible hip fracture admission date per patient to be the hip fracture index date for the patient

from hashlib import sha256
from pathlib import Path

import pandas as pd

# Specify paths for files
INPUT_FILE = Path("output/dataset.csv.gz")
OUTPUT_FILE = Path("output/selected_hip_index_cases.csv")
QA_FILE = Path("output/selected_hip_index_cases_qa.csv")

# Set parameters
MAX_CANDIDATE_DATES = 15

# Prefix for string used to generate hash
# If changed, hash will change for even if patient ID, admission date and candidate number remain the same
RANDOM_SEED = "hip-index-selection-v1" 

# Create function to ensure boolean columns defined properly
# If already read in as boolean, change missing values to False
# If not, convert series to string, capitalise, then make into boolean 
# T, TRUE and "1" become True, everything else becomes False
def as_boolean(series):
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)

    return (
        series.astype("string")
        .str.upper()
        .isin(["T", "TRUE", "1"])
    )

# Read in output from dataset_definition.py as dataframe
patients = pd.read_csv(INPUT_FILE)

# Keep eligible index dates only ---------------------------------------------------------
# Pivot data from wide to long for 1st to MAX_CANDIDATE_DATES (nth) candidate admission date ------------------

# Create empty list for appending loop outputs
candidate_frames = []

# Loop through 1 to max n candidate number
for candidate_number in range(1, MAX_CANDIDATE_DATES + 1):

    # Make column names (to get relevant cols for nth candidate_number from the output table)
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

    # Separate out columns for nth candidate_number into df
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

    # Rename columns (allows row binding later)
    candidate = candidate.rename(
        columns={
            date_column: "index_date",
            eligibility_column: "is_eligible_index",
            age_column: "age_at_index",
            practice_column: "practice_at_index",
            care_home_column: "care_home_at_index",
        }
    )

    # Create column with candidate number
    candidate["candidate_number"] = candidate_number

    # Convert index date from string to datetime
    candidate["index_date"] = pd.to_datetime(
        candidate["index_date"],
        errors="coerce",
    )

    # Use custom function to make eligibility marker boolean
    candidate["is_eligible_index"] = as_boolean(
        candidate["is_eligible_index"]
    )

    # Keep only patients whose index date is not missing and the admission is eligible
    # for their nth candidate admission
    candidate = candidate.loc[
        candidate["index_date"].notna()
        & candidate["is_eligible_index"]
    ]

    # Add dataframe with patients with eligible admission for nth candidate number to list
    candidate_frames.append(candidate)

# Bind all dataframes with eligible admissions together by row - create new row index
eligible_candidates = pd.concat(
    candidate_frames,
    ignore_index=True,
)

# Separate out flag column for whether patient has more than MAX_CANDIDATE_DATES (n) candidate dates (irrespective of eligibility) -----------
# from original output table

# Get patient ID and more than max candidate dates indicator column
overflow = patients[
    [
        "patient_id",
        "has_more_than_15_candidate_hip_dates",
    ]
].copy()

# Convert more than max candidate dates indicator to boolean using custom function - as new col
overflow["has_candidate_overflow"] = as_boolean(
    overflow["has_more_than_15_candidate_hip_dates"]
)

# Keep only patient ID and new column 
# (note that this is one row per patient already as the output table is one row per patient)
overflow = overflow[
    [
        "patient_id",
        "has_candidate_overflow",
    ]
]

# Drop patients with more than max candidate admission dates -------------------------------------
# (not eligible index dates, this is all candidate admission dates, regardless of how many meet 
# the additional three eligibility criteria)

# Patients with overflow are not selected because their full set of
# candidate dates is unavailable. Selecting one from only their first max n admissions could be biased

# Join eligible index date table with overflow table
eligible_candidates = eligible_candidates.merge(
    overflow,
    on="patient_id",
    how="left",
)

# Keep only patients with no overflow (1 to max n candidate admissions) for selection
selection_pool = eligible_candidates.loc[
    ~eligible_candidates["has_candidate_overflow"]
].copy()

# Create function that takes one candidate row and creates a hash using a string made up of the following bits:
# - Prefix defined above (RANDOM_SEED)
# - Patient ID
# - Index date for candidate admission meeting eligibility criteria
# - Candidate number
# Essentially gives a pseudo-random unique key for a given input so a random eligible candidate admission can be selected per patient
# The same input always give the same hash so this is reproducible (it is deterministic) 
# and the input here is made up of the specified bits above
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

# Generate a hash for each row using the function
selection_pool["selection_score"] = selection_pool.apply(
    selection_score,
    axis=1,
)

# Count the number of eligible candidate admission dates per patient (with no overflow)
eligible_counts = (
    selection_pool
    .groupby("patient_id")
    .size()
    .rename("number_of_eligible_hip_index_events")
    .reset_index()
)

# Select one eligible candidate admission as the index date per patient -----------------------------

# Sorts the candidate rows per patient by the hash and the candidate number and selects the first one,
# so the final table for hip fracture patients contains one eligible candidate admission as the index date
# per patient with no more than max n candidate admissions for hip fracture in that period
# Join count of eligible candidate admission dates for patient
selected_cases = (
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

# Convert age to integer for final table 
selected_cases["age_at_index"] = pd.to_numeric(
    selected_cases["age_at_index"],
    errors="coerce",
).astype("Int64")

# Convert practice ID to integer for final table
selected_cases["practice_at_index"] = pd.to_numeric(
    selected_cases["practice_at_index"],
    errors="coerce",
).astype("Int64")

# Label fracture type
selected_cases["fracture_type"] = "hip"

# Label source used to get candidate dates for cohort selection
selected_cases["index_source"] = "hospital"

# Specify output table column order
output_columns = [
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

# Write the final table with hip fracture patients and their selected index date
selected_cases[output_columns].to_csv(
    OUTPUT_FILE,
    index=False,
    date_format="%Y-%m-%d",
)

# Create QA table to check selection ----------------------------------------------------------------------
# - patients_in_candidate_dataset: Initial number of patients from dataset_definition.py
# - patients_with_eligible_candidate: Number of patients with eligible candidate admissions
# - patients_with_candidate_overflow: Number of patients with more than max n candidate admissions (dropped)
# - selected_hip_index_cases: Final number of patients selected
qa = pd.DataFrame(
    {
        "metric": [
            "patients_in_candidate_dataset",
            "patients_with_eligible_candidate",
            "patients_with_candidate_overflow",
            "selected_hip_index_cases",
        ],
        "value": [
            patients["patient_id"].nunique(),
            eligible_candidates["patient_id"].nunique(),
            overflow.loc[
                overflow["has_candidate_overflow"],
                "patient_id",
            ].nunique(),
            selected_cases["patient_id"].nunique(),
        ],
    }
)

# Write QA file
qa.to_csv(QA_FILE, index=False)
