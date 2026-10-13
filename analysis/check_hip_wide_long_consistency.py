from pathlib import Path

import pandas as pd
from pandas.testing import assert_frame_equal


INPUT_DIR = Path("output/hip_event_level_pipeline")
WIDE_FILE = INPUT_DIR / "dataset.csv"
LONG_FILE = Path("output/hip_candidate_events_long.csv")
CHECK_OUTPUT_FILE = Path(
    "output/hip_wide_long_consistency.txt"
)

MAX_CANDIDATE_DATES = 10


def as_boolean(series):
    """Convert ehrQL/Pandas boolean representations to nullable booleans."""
    values = {
        True: True,
        False: False,
        "T": True,
        "F": False,
        "True": True,
        "False": False,
        1: True,
        0: False,
    }
    return series.map(values).astype("boolean")


candidate_date_columns = [
    f"candidate_hip_date_{number}"
    for number in range(1, MAX_CANDIDATE_DATES + 1)
]

wide = pd.read_csv(
    WIDE_FILE,
    parse_dates=candidate_date_columns,
)

long = pd.read_csv(
    LONG_FILE,
    parse_dates=["index_date"],
)


# The long table should contain one row per patient and candidate date.
duplicate_long_events = long.duplicated(
    ["patient_id", "index_date"],
    keep=False,
)

if duplicate_long_events.any():
    raise AssertionError(
        "Duplicate patient-index-date rows found in the long table:\n"
        f"{long.loc[duplicate_long_events, ['patient_id', 'index_date']]}"
    )


# Number the long events chronologically within each patient.
long = long.sort_values(
    ["patient_id", "index_date"]
).reset_index(drop=True)

long["candidate_number"] = (
    long.groupby("patient_id").cumcount() + 1
)


# Reconstruct a long table from the numbered wide QA columns.
wide_event_parts = []

for candidate_number in range(1, MAX_CANDIDATE_DATES + 1):
    part = wide[
        [
            "patient_id",
            f"candidate_hip_date_{candidate_number}",
            (
                "candidate_hip_prior_hospital_count_6m_"
                f"{candidate_number}"
            ),
            f"candidate_hip_prior_gp_count_6m_{candidate_number}",
            (
                "candidate_hip_has_prior_fracture_6m_"
                f"{candidate_number}"
            ),
            f"candidate_hip_passes_6m_rule_{candidate_number}",
            f"candidate_hip_age_{candidate_number}",
            f"candidate_hip_age_eligible_{candidate_number}",
            (
                "candidate_hip_has_3m_registration_"
                f"{candidate_number}"
            ),
            f"candidate_hip_is_eligible_index_{candidate_number}",
        ]
    ].copy()

    part.columns = [
        "patient_id",
        "index_date",
        "prior_hospital_record_count_6m",
        "prior_gp_record_count_6m",
        "has_prior_same_type_fracture_6m",
        "passes_6m_rule",
        "age_at_index",
        "age_eligible",
        "has_3m_registration",
        "is_eligible_index",
    ]

    part["candidate_number"] = candidate_number
    part = part.loc[part["index_date"].notna()]
    wide_event_parts.append(part)

wide_events = pd.concat(
    wide_event_parts,
    ignore_index=True,
)


comparison_columns = [
    "patient_id",
    "candidate_number",
    "index_date",
    "prior_hospital_record_count_6m",
    "prior_gp_record_count_6m",
    "has_prior_same_type_fracture_6m",
    "passes_6m_rule",
    "age_at_index",
    "age_eligible",
    "has_3m_registration",
    "is_eligible_index",
]

long_events = long.loc[
    long["candidate_number"].le(MAX_CANDIDATE_DATES),
    comparison_columns,
].copy()

wide_events = wide_events[comparison_columns].copy()


count_columns = [
    "prior_hospital_record_count_6m",
    "prior_gp_record_count_6m",
]

boolean_columns = [
    "has_prior_same_type_fracture_6m",
    "passes_6m_rule",
    "age_eligible",
    "has_3m_registration",
    "is_eligible_index",
]

for table in [wide_events, long_events]:
    for column in count_columns:
        table[column] = pd.to_numeric(
            table[column]
        ).astype("int64")

    table["age_at_index"] = pd.to_numeric(
        table["age_at_index"]
    ).astype("Int64")

    for column in boolean_columns:
        table[column] = as_boolean(table[column])

    table.sort_values(
        ["patient_id", "candidate_number"],
        inplace=True,
    )
    table.reset_index(drop=True, inplace=True)


assert_frame_equal(
    wide_events,
    long_events,
    check_dtype=False,
)


# Check that the overflow flag agrees with the complete long table.
long_event_counts = long.groupby("patient_id").size()

overflow_column = (
    f"has_more_than_{MAX_CANDIDATE_DATES}_candidate_hip_dates"
)

reported_overflow = as_boolean(
    wide[overflow_column]
).fillna(False)

expected_overflow = (
    wide["patient_id"]
    .map(long_event_counts)
    .fillna(0)
    .gt(MAX_CANDIDATE_DATES)
)

if not reported_overflow.astype(bool).equals(expected_overflow):
    raise AssertionError(
        "The wide overflow flag does not agree with the long table."
    )


# Hospital records on the same date are collapsed into one long event,
# so their counts should sum to the total wide admission-record count.
long_record_counts = (
    long.groupby("patient_id")["candidate_hospital_record_count"]
    .sum()
)

expected_record_counts = (
    wide["patient_id"]
    .map(long_record_counts)
    .fillna(0)
    .astype("int64")
)

reported_record_counts = (
    wide["number_of_candidate_hip_admission_records"]
    .astype("int64")
)

if not reported_record_counts.equals(expected_record_counts):
    raise AssertionError(
        "Candidate hospital-record totals differ between outputs."
    )


# Hip index events must currently come from hospital admissions.
if not long["fracture_type"].eq("hip").all():
    raise AssertionError("Unexpected fracture type in the long table.")

if not long["index_source"].eq("hospital").all():
    raise AssertionError("Unexpected hip index source in the long table.")


summary = (
    "Wide-to-long consistency checks: All OK!\n"
    f"Patients checked: {long['patient_id'].nunique()}\n"
    f"Candidate events checked: {len(long)}\n"
    f"Eligible index events: {long['is_eligible_index'].sum()}\n"
)

CHECK_OUTPUT_FILE.write_text(
    summary,
    encoding="utf-8",
)

print(summary, end="")