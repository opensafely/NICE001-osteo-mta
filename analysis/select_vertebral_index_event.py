from hashlib import sha256
from pathlib import Path

import pandas as pd


INPUT_FILE = Path("output/vertebral_candidates.csv.gz")
OUTPUT_FILE = Path("output/selected_vertebral_index_cases.csv")
QA_FILE = Path("output/selected_vertebral_index_cases_qa.csv")

MAX_CANDIDATE_DATES_PER_SOURCE = 15
RANDOM_SEED = "vertebral-index-selection-v1"


def as_boolean(series):
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)

    return (
        series.astype("string")
        .str.upper()
        .isin(["T", "TRUE", "1"])
    )


def combine_sources(values):
    sources = set(values)

    if sources == {"hospital", "gp"}:
        return "both"

    if "hospital" in sources:
        return "hospital"

    return "gp"


patients = pd.read_csv(INPUT_FILE)

candidate_frames = []

for source_name in ["hospital", "gp"]:
    for candidate_number in range(
        1,
        MAX_CANDIDATE_DATES_PER_SOURCE + 1,
    ):
        column_prefix = (
            f"candidate_vertebral_{source_name}_"
            f"{candidate_number}"
        )

        date_column = f"{column_prefix}_date"
        eligibility_column = (
            f"{column_prefix}_is_eligible_index"
        )
        age_column = f"{column_prefix}_age"

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

        candidate["candidate_source"] = source_name
        candidate["source_candidate_number"] = candidate_number

        candidate["index_date"] = pd.to_datetime(
            candidate["index_date"],
            errors="coerce",
        )

        candidate["is_eligible_index"] = as_boolean(
            candidate["is_eligible_index"]
        )

        candidate = candidate.loc[
            candidate["index_date"].notna()
        ]

        candidate_frames.append(candidate)


source_candidates = pd.concat(
    candidate_frames,
    ignore_index=True,
)


# Eligibility and age must agree when the same patient and date appear
# in both hospital and GP data.
eligibility_counts = (
    source_candidates
    .groupby(["patient_id", "index_date"])
    ["is_eligible_index"]
    .nunique()
)

assert eligibility_counts.le(1).all()


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


overflow = patients[
    [
        "patient_id",
        "has_more_than_15_candidate_vertebral_hospital_dates",
        "has_more_than_15_candidate_vertebral_gp_dates",
    ]
].copy()

overflow["has_hospital_candidate_overflow"] = as_boolean(
    overflow[
        "has_more_than_15_candidate_vertebral_hospital_dates"
    ]
)

overflow["has_gp_candidate_overflow"] = as_boolean(
    overflow[
        "has_more_than_15_candidate_vertebral_gp_dates"
    ]
)

overflow["has_any_candidate_overflow"] = (
    overflow["has_hospital_candidate_overflow"]
    | overflow["has_gp_candidate_overflow"]
)

overflow = overflow[
    [
        "patient_id",
        "has_hospital_candidate_overflow",
        "has_gp_candidate_overflow",
        "has_any_candidate_overflow",
    ]
]


combined_candidates = combined_candidates.merge(
    overflow,
    on="patient_id",
    how="left",
)

eligible_candidates = combined_candidates.loc[
    combined_candidates["is_eligible_index"]
].copy()


# Patients with overflow are excluded because their complete candidate
# history was not available for random selection.
selection_pool = eligible_candidates.loc[
    ~eligible_candidates["has_any_candidate_overflow"]
].copy()


def selection_score(row):
    key = "|".join(
        [
            RANDOM_SEED,
            str(row["patient_id"]),
            row["index_date"].date().isoformat(),
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
    .rename("number_of_eligible_vertebral_index_events")
    .reset_index()
)

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

selected_cases["age_at_index"] = pd.to_numeric(
    selected_cases["age_at_index"],
    errors="coerce",
).astype("Int64")

selected_cases["fracture_type"] = "vertebral"

output_columns = [
    "patient_id",
    "index_date",
    "fracture_type",
    "index_source",
    "number_of_eligible_vertebral_index_events",
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
            "patients_with_hospital_candidate_overflow",
            "patients_with_gp_candidate_overflow",
            "patients_with_any_candidate_overflow",
            "selected_vertebral_index_cases",
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

qa.to_csv(QA_FILE, index=False)