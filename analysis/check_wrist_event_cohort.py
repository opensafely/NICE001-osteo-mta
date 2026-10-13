from pathlib import Path

import pandas as pd


INPUT_FILE = Path("output/wrist_candidate_events_long.csv")
REPORT_FILE = Path("output/wrist_event_cohort_check.txt")


events = pd.read_csv(
    INPUT_FILE,
    parse_dates=["index_date"],
)


# There should be one row per patient, fracture type and index date
assert len(events) == 5

assert not events.duplicated(
    ["patient_id", "fracture_type", "index_date"]
).any()

assert set(events["patient_id"]) == {1, 2, 3, 4}


expected = pd.DataFrame(
    [
        {
            "patient_id": 1,
            "index_date": pd.Timestamp("2024-06-01"),
            "index_source": "hospital",
            "candidate_hospital_record_count": 1,
            "candidate_gp_record_count": 0,
            "prior_hospital_record_count_6m": 0,
            "prior_gp_record_count_6m": 0,
            "has_prior_same_type_fracture_6m": False,
            "passes_6m_rule": True,
            "age_at_index": 44,
            "age_eligible": True,
            "has_3m_registration": True,
            "is_eligible_index": True,
        },
        {
            "patient_id": 2,
            "index_date": pd.Timestamp("2024-07-01"),
            "index_source": "gp",
            "candidate_hospital_record_count": 0,
            "candidate_gp_record_count": 1,
            "prior_hospital_record_count_6m": 0,
            "prior_gp_record_count_6m": 0,
            "has_prior_same_type_fracture_6m": False,
            "passes_6m_rule": True,
            "age_at_index": 49,
            "age_eligible": True,
            "has_3m_registration": True,
            "is_eligible_index": True,
        },
        {
            "patient_id": 3,
            "index_date": pd.Timestamp("2024-08-15"),
            "index_source": "both",
            "candidate_hospital_record_count": 2,
            "candidate_gp_record_count": 2,
            "prior_hospital_record_count_6m": 0,
            "prior_gp_record_count_6m": 0,
            "has_prior_same_type_fracture_6m": False,
            "passes_6m_rule": True,
            "age_at_index": 64,
            "age_eligible": True,
            "has_3m_registration": True,
            "is_eligible_index": True,
        },
        {
            "patient_id": 4,
            "index_date": pd.Timestamp("2024-01-01"),
            "index_source": "gp",
            "candidate_hospital_record_count": 0,
            "candidate_gp_record_count": 1,
            "prior_hospital_record_count_6m": 0,
            "prior_gp_record_count_6m": 0,
            "has_prior_same_type_fracture_6m": False,
            "passes_6m_rule": True,
            "age_at_index": 34,
            "age_eligible": True,
            "has_3m_registration": True,
            "is_eligible_index": True,
        },
        {
            "patient_id": 4,
            "index_date": pd.Timestamp("2024-04-01"),
            "index_source": "hospital",
            "candidate_hospital_record_count": 1,
            "candidate_gp_record_count": 0,
            "prior_hospital_record_count_6m": 0,
            "prior_gp_record_count_6m": 1,
            "has_prior_same_type_fracture_6m": True,
            "passes_6m_rule": False,
            "age_at_index": 34,
            "age_eligible": True,
            "has_3m_registration": True,
            "is_eligible_index": False,
        },
    ]
)

comparison_columns = list(expected.columns)

actual = (
    events[comparison_columns]
    .sort_values(["patient_id", "index_date"])
    .reset_index(drop=True)
)

expected = (
    expected
    .sort_values(["patient_id", "index_date"])
    .reset_index(drop=True)
)

pd.testing.assert_frame_equal(
    actual,
    expected,
    check_dtype=False,
)


report = (
    "Wrist event cohort checks: All OK!\n"
    f"Candidate events checked: {len(events)}\n"
    f"Eligible index events: {events['is_eligible_index'].sum()}\n"
    "Same-day hospital and GP records were combined correctly.\n"
)

REPORT_FILE.write_text(report, encoding="utf-8")

print(report, end="")