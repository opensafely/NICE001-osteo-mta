from pathlib import Path

import pandas as pd


INPUT_DIR = Path("output/hip_event_level_pipeline")
OUTPUT_FILE = Path("output/hip_candidate_events_long.csv")


# Load the raw event-level outputs
candidate_records = pd.read_csv(
    INPUT_DIR / "candidate_hip_admissions.csv",
    parse_dates=["admission_date"],
)

hospital_history = pd.read_csv(
    INPUT_DIR / "hip_admissions_history.csv",
    parse_dates=["admission_date"],
)

gp_history = pd.read_csv(
    INPUT_DIR / "hip_gp_events_history.csv",
    parse_dates=["event_date"],
)

registrations = pd.read_csv(
    INPUT_DIR / "practice_registrations.csv",
    parse_dates=["start_date", "end_date"],
)

patients = pd.read_csv(
    INPUT_DIR / "dataset.csv",
    usecols=["patient_id", "date_of_birth_for_event_qa"],
    parse_dates=["date_of_birth_for_event_qa"],
)


# Collapse multiple APCS records on the same date into one candidate event
candidate_record_counts = (
    candidate_records
    .groupby(["patient_id", "admission_date"])
    .size()
    .rename("candidate_hospital_record_count")
    .reset_index()
)

events = (
    candidate_record_counts
    .rename(columns={"admission_date": "index_date"})
    .sort_values(["patient_id", "index_date"])
    .reset_index(drop=True)
)

events["candidate_event_id"] = events.index + 1
events["fracture_type"] = "hip"
events["index_source"] = "hospital"

events["lookback_start_6m"] = (
    events["index_date"] - pd.DateOffset(months=6)
)


# Hospital fracture history during the preceding six months
hospital_pairs = events[
    [
        "candidate_event_id",
        "patient_id",
        "index_date",
        "lookback_start_6m",
    ]
].merge(
    hospital_history,
    on="patient_id",
    how="left",
)

prior_hospital = hospital_pairs.loc[
    hospital_pairs["admission_date"].ge(
        hospital_pairs["lookback_start_6m"]
    )
    & hospital_pairs["admission_date"].lt(
        hospital_pairs["index_date"]
    )
]

prior_hospital_counts = (
    prior_hospital
    .groupby("candidate_event_id")
    .agg(
        prior_hospital_record_count_6m=("apcs_ident", "size"),
        prior_hospital_date_count_6m=("admission_date", "nunique"),
    )
    .reset_index()
)

events = events.merge(
    prior_hospital_counts,
    on="candidate_event_id",
    how="left",
)


# GP fracture history during the preceding six months
gp_pairs = events[
    [
        "candidate_event_id",
        "patient_id",
        "index_date",
        "lookback_start_6m",
    ]
].merge(
    gp_history,
    on="patient_id",
    how="left",
)

prior_gp = gp_pairs.loc[
    gp_pairs["event_date"].ge(gp_pairs["lookback_start_6m"])
    & gp_pairs["event_date"].lt(gp_pairs["index_date"])
]

prior_gp_counts = (
    prior_gp
    .groupby("candidate_event_id")
    .size()
    .rename("prior_gp_record_count_6m")
    .reset_index()
)

events = events.merge(
    prior_gp_counts,
    on="candidate_event_id",
    how="left",
)

count_columns = [
    "prior_hospital_record_count_6m",
    "prior_hospital_date_count_6m",
    "prior_gp_record_count_6m",
]

events[count_columns] = (
    events[count_columns]
    .fillna(0)
    .astype("int64")
)

events["has_prior_same_type_fracture_6m"] = (
    events["prior_hospital_record_count_6m"].gt(0)
    | events["prior_gp_record_count_6m"].gt(0)
)

events["passes_6m_rule"] = (
    ~events["has_prior_same_type_fracture_6m"]
)


# Calculate age at each candidate event
events = events.merge(
    patients,
    on="patient_id",
    how="left",
)

date_of_birth = events["date_of_birth_for_event_qa"]
index_date = events["index_date"]

birthday_not_reached = (
    (index_date.dt.month < date_of_birth.dt.month)
    | (
        (index_date.dt.month == date_of_birth.dt.month)
        & (index_date.dt.day < date_of_birth.dt.day)
    )
)

events["age_at_index"] = (
    index_date.dt.year
    - date_of_birth.dt.year
    - birthday_not_reached.astype("int64")
)

events["age_at_index"] = events["age_at_index"].astype("Int64")
events["age_eligible"] = events["age_at_index"].ge(18).fillna(False)


# Check whether one registration spans the complete three-month period
events["registration_lookback_start"] = (
    events["index_date"] - pd.DateOffset(months=3)
)

registration_pairs = events[
    [
        "candidate_event_id",
        "patient_id",
        "index_date",
        "registration_lookback_start",
    ]
].merge(
    registrations,
    on="patient_id",
    how="left",
)

registration_spans_period = (
    registration_pairs["start_date"].le(
        registration_pairs["registration_lookback_start"]
    )
    & (
        registration_pairs["end_date"].isna()
        | registration_pairs["end_date"].ge(
            registration_pairs["index_date"]
        )
    )
)

eligible_registration_event_ids = registration_pairs.loc[
    registration_spans_period,
    "candidate_event_id",
].unique()

events["has_3m_registration"] = events[
    "candidate_event_id"
].isin(eligible_registration_event_ids)


# Combine the candidate-specific eligibility conditions
events["is_eligible_index"] = (
    events["passes_6m_rule"]
    & events["age_eligible"]
    & events["has_3m_registration"]
)


output_columns = [
    "patient_id",
    "candidate_event_id",
    "index_date",
    "fracture_type",
    "index_source",
    "candidate_hospital_record_count",
    "prior_hospital_record_count_6m",
    "prior_hospital_date_count_6m",
    "prior_gp_record_count_6m",
    "has_prior_same_type_fracture_6m",
    "passes_6m_rule",
    "age_at_index",
    "age_eligible",
    "has_3m_registration",
    "is_eligible_index",
]

events[output_columns].to_csv(OUTPUT_FILE, index=False)

print(f"Created {len(events)} candidate hip-fracture event rows")
print(f"Eligible index events: {events['is_eligible_index'].sum()}")
print(f"Saved to: {OUTPUT_FILE}")