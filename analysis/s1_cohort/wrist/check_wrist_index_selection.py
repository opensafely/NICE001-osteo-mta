from hashlib import sha256
from pathlib import Path

import pandas as pd


CANDIDATE_FILE = Path("output/wrist_candidates.csv.gz")
SELECTED_FILE = Path("output/selected_wrist_index_cases.csv")
QA_FILE = Path("output/selected_wrist_index_cases_qa.csv")
REPORT_FILE = Path("output/wrist_index_selection_check.txt")

MAX_CANDIDATE_DATES_PER_SOURCE = 15
RANDOM_SEED = "wrist-index-selection-v1"


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


def selection_score(row):
    key = "|".join(
        [
            RANDOM_SEED,
            str(row["patient_id"]),
            row["index_date"].date().isoformat(),
        ]
    )

    return sha256(key.encode("utf-8")).hexdigest()


patients = pd.read_csv(CANDIDATE_FILE)

actual = pd.read_csv(
    SELECTED_FILE,
    parse_dates=["index_date"],
)

actual_qa = pd.read_csv(QA_FILE)

candidate_frames = []

for source_name in ["hospital", "gp"]:
    for candidate_number in range(
        1,
        MAX_CANDIDATE_DATES_PER_SOURCE + 1,
    ):
        column_prefix = (
            f"candidate_wrist_{source_name}_"
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
        "has_more_than_15_candidate_wrist_hospital_dates",
        "has_more_than_15_candidate_wrist_gp_dates",
    ]
].copy()

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

overflow["has_any_candidate_overflow"] = (
    overflow["has_hospital_candidate_overflow"]
    | overflow["has_gp_candidate_overflow"]
)

combined_candidates = combined_candidates.merge(
    overflow[
        [
            "patient_id",
            "has_hospital_candidate_overflow",
            "has_gp_candidate_overflow",
            "has_any_candidate_overflow",
        ]
    ],
    on="patient_id",
    how="left",
)

eligible_candidates = combined_candidates.loc[
    combined_candidates["is_eligible_index"]
].copy()

selection_pool = eligible_candidates.loc[
    ~eligible_candidates["has_any_candidate_overflow"]
].copy()

selection_pool["selection_score"] = selection_pool.apply(
    selection_score,
    axis=1,
)

eligible_counts = (
    selection_pool
    .groupby("patient_id")
    .size()
    .rename("number_of_eligible_wrist_index_events")
    .reset_index()
)

expected = (
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

expected["fracture_type"] = "wrist"

comparison_columns = [
    "patient_id",
    "index_date",
    "fracture_type",
    "index_source",
    "number_of_eligible_wrist_index_events",
    "age_at_index",
]

assert actual["patient_id"].is_unique
assert not actual["index_date"].isna().any()
assert (actual["fracture_type"] == "wrist").all()
assert actual["index_source"].isin(
    ["hospital", "gp", "both"]
).all()

for frame in [actual, expected]:
    frame["age_at_index"] = pd.to_numeric(
        frame["age_at_index"],
        errors="coerce",
    ).astype("Int64")

    frame["number_of_eligible_wrist_index_events"] = (
        pd.to_numeric(
            frame["number_of_eligible_wrist_index_events"],
            errors="raise",
        ).astype("Int64")
    )

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


expected_qa = pd.DataFrame(
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
            expected["patient_id"].nunique(),
        ],
    }
)

pd.testing.assert_frame_equal(
    actual_qa,
    expected_qa,
    check_dtype=False,
)

report = (
    "Wrist index selection checks: All OK!\n"
    f"Eligible non-overflow patients checked: {len(expected)}\n"
    f"Selected index events checked: {len(actual)}\n"
    "Same-day hospital and GP candidates were combined correctly.\n"
    "Each patient contributed exactly one selected wrist index event.\n"
    "Reproducible random selection was confirmed.\n"
    "Patients with candidate overflow were excluded.\n"
)

REPORT_FILE.write_text(report, encoding="utf-8")

print(report, end="")