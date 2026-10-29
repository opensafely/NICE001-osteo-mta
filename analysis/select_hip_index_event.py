from hashlib import sha256
from pathlib import Path

import pandas as pd


INPUT_FILE = Path("output/dataset.csv.gz")
OUTPUT_FILE = Path("output/selected_hip_index_cases.csv")
QA_FILE = Path("output/selected_hip_index_cases_qa.csv")

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


patients = pd.read_csv(INPUT_FILE)

candidate_frames = []

for candidate_number in range(1, MAX_CANDIDATE_DATES + 1):
    date_column = f"candidate_hip_date_{candidate_number}"
    eligibility_column = (
        f"candidate_hip_is_eligible_index_{candidate_number}"
    )
    age_column = f"candidate_hip_age_{candidate_number}"

    candidate = patients[
        [
            "patient_id",
            date_column,
            eligibility_column,
            age_column,
        ]
    ].copy()

    candidate = candidate.rename(
        columns={
            date_column: "index_date",
            eligibility_column: "is_eligible_index",
            age_column: "age_at_index",
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

overflow = overflow[
    [
        "patient_id",
        "has_candidate_overflow",
    ]
]

eligible_candidates = eligible_candidates.merge(
    overflow,
    on="patient_id",
    how="left",
)

# Patients with overflow are not selected because their full set of
# candidate dates is unavailable.
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

selected_cases["age_at_index"] = pd.to_numeric(
    selected_cases["age_at_index"],
    errors="coerce",
).astype("Int64")

selected_cases["fracture_type"] = "hip"
selected_cases["index_source"] = "hospital"

output_columns = [
    "patient_id",
    "index_date",
    "fracture_type",
    "index_source",
    "candidate_number",
    "number_of_eligible_hip_index_events",
    "age_at_index",
]

selected_cases[output_columns].to_csv(
    OUTPUT_FILE,
    index=False,
    date_format="%Y-%m-%d",
)

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

qa.to_csv(QA_FILE, index=False)