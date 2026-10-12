# Experimental event-level output for data-development QA only.

from ehrql import claim_permissions
from ehrql.tables.tpp import patients, practice_registrations

from dataset_definition import (
    candidate_hip_admissions,
    dataset,
    hip_admissions,
    hip_gp_events,
)

claim_permissions("event_level_data")

# Patient-level information required for downstream eligibility.
dataset.date_of_birth_for_event_qa = patients.date_of_birth

# Potential hip index admissions within the permitted study-entry periods.
dataset.add_event_table(
    "candidate_hip_admissions",
    admission_date=candidate_hip_admissions.admission_date,
    apcs_ident=candidate_hip_admissions.apcs_ident,
)

# All hip admissions, including admissions outside the permitted entry periods,
# so they can be used for the six-month lookback.
dataset.add_event_table(
    "hip_admissions_history",
    admission_date=hip_admissions.admission_date,
    apcs_ident=hip_admissions.apcs_ident,
)

# GP hip-fracture evidence used in the six-month lookback.
dataset.add_event_table(
    "hip_gp_events_history",
    event_date=hip_gp_events.date,
    snomedct_code=hip_gp_events.snomedct_code,
)

# Registration periods needed to assess three months' continuous registration
# at each candidate date.
dataset.add_event_table(
    "practice_registrations",
    start_date=practice_registrations.start_date,
    end_date=practice_registrations.end_date,
)