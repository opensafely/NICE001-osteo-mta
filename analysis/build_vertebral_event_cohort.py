from pathlib import Path

import pandas as pd


INPUT_DIR = Path("output/vertebral_event_level_qa")
OUTPUT_FILE = Path("output/vertebral_candidate_events_long.csv")


# Load candidate records from both sources
hospital_candidates = pd.read_csv(
    INPUT_DIR / "candidate_vertebral_admissions.csv",
    parse_dates=["admission_date"],
)

gp_candidates = pd.read_csv(
    INPUT_DIR / "candidate_vertebral_gp_events.csv",
    parse_dates=["event_date"],
)

hospital_history = pd.read_csv(
    INPUT_DIR / "vertebral_admissions_history.csv",
    parse_dates=["admission_date"],
)

gp_history = pd.read_csv(
    INPUT_DIR / "vertebral_gp_events_history.csv",
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

# Count hospital records for each patient and date
hospital_candidate_counts = (
    hospital_candidates
    .groupby(["patient_id", "admission_date"])
    .size()
    .rename("candidate_hospital_record_count")
    .reset_index()
    .rename(columns={"admission_date": "index_date"})
)


# Count GP records for each patient and date
gp_candidate_counts = (
    gp_candidates
    .groupby(["patient_id", "event_date"])
    .size()
    .rename("candidate_gp_record_count")
    .reset_index()
    .rename(columns={"event_date": "index_date"})
)


# Combine hospital and GP records occurring on the same date
events = hospital_candidate_counts.merge(
    gp_candidate_counts,
    on=["patient_id", "index_date"],
    how="outer",
)

count_columns = [
    "candidate_hospital_record_count",
    "candidate_gp_record_count",
]

events[count_columns] = (
    events[count_columns]
    .fillna(0)
    .astype("int64")
)


# Identify whether each combined event came from hospital, GP or both
events["index_source"] = "both"

events.loc[
    events["candidate_hospital_record_count"].gt(0)
    & events["candidate_gp_record_count"].eq(0),
    "index_source",
] = "hospital"

events.loc[
    events["candidate_hospital_record_count"].eq(0)
    & events["candidate_gp_record_count"].gt(0),
    "index_source",
] = "gp"


# Sort the candidate events and assign a temporary event identifier
events = (
    events
    .sort_values(["patient_id", "index_date"])
    .reset_index(drop=True)
)

events["candidate_event_id"] = events.index + 1
events["fracture_type"] = "vertebral"

# Define the preceding six-month period for each candidate event
events["lookback_start_6m"] = (
    events["index_date"] - pd.DateOffset(months=6)
)


# Identify prior hospital vertebral-fracture records
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


# Identify prior GP vertebral-fracture records
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
    .agg(
        prior_gp_record_count_6m=("snomedct_code", "size"),
        prior_gp_date_count_6m=("event_date", "nunique"),
    )
    .reset_index()
)

events = events.merge(
    prior_gp_counts,
    on="candidate_event_id",
    how="left",
)


# Replace missing lookback counts with zero
lookback_count_columns = [
    "prior_hospital_record_count_6m",
    "prior_hospital_date_count_6m",
    "prior_gp_record_count_6m",
    "prior_gp_date_count_6m",
]

events[lookback_count_columns] = (
    events[lookback_count_columns]
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

events["age_eligible"] = (
    events["age_at_index"].ge(18).fillna(False)
)


# Check that one registration spans the complete three-month period
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


# Combine all candidate-specific eligibility conditions
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
    "candidate_gp_record_count",
    "prior_hospital_record_count_6m",
    "prior_hospital_date_count_6m",
    "prior_gp_record_count_6m",
    "prior_gp_date_count_6m",
    "has_prior_same_type_fracture_6m",
    "passes_6m_rule",
    "age_at_index",
    "age_eligible",
    "has_3m_registration",
    "is_eligible_index",
]

events[output_columns].to_csv(OUTPUT_FILE, index=False)

print(f"Created {len(events)} candidate vertebral-fracture event rows")
print(events["index_source"].value_counts().sort_index())
print(f"Saved to: {OUTPUT_FILE}")