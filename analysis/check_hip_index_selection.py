from hashlib import sha256
from pathlib import Path

import pandas as pd


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

actual = pd.read_csv(
    SELECTED_FILE,
    parse_dates=["index_date"],
)

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
]

assert actual["patient_id"].is_unique
assert not actual["index_date"].isna().any()
assert (actual["fracture_type"] == "hip").all()
assert (actual["index_source"] == "hospital").all()

actual["age_at_index"] = pd.to_numeric(
    actual["age_at_index"],
    errors="coerce",
).astype("Int64")

expected["age_at_index"] = pd.to_numeric(
    expected["age_at_index"],
    errors="coerce",
).astype("Int64")

actual = (
    actual[comparison_columns]
    .sort_values("patient_id")
    .reset_index(drop=True)
)

expected = (
    expected[comparison_columns]
    .sort_values("patient_id")
    .reset_index(drop=True)
)

pd.testing.assert_frame_equal(
    actual,
    expected,
    check_dtype=False,
)

report = (
    "Hip index selection checks: All OK!\n"
    f"Eligible non-overflow patients checked: {len(expected)}\n"
    f"Selected index events checked: {len(actual)}\n"
    "Each patient contributed exactly one selected hip index event.\n"
    "Reproducible random selection was confirmed.\n"
    "Patients with candidate overflow were excluded.\n"
)

REPORT_FILE.write_text(report, encoding="utf-8")

print(report, end="")