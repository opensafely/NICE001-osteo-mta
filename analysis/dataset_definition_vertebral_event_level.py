# Experimental vertebral-fracture event-level extraction for development and QA.

from ehrql import claim_permissions, codelist_from_csv, create_dataset
from ehrql.tables.tpp import (
    apcs,
    clinical_events,
    patients,
    practice_registrations,
)


dataset = create_dataset()

claim_permissions("event_level_data")


# Vertebral-fracture codelists
vertebral_fracture_icd_codes = codelist_from_csv(
    "local_codelists/vertebral-fracture-incident-icd10-xi.csv",
    column="code",
)

vertebral_fracture_snomed_codes = codelist_from_csv(
    "local_codelists/vertebral-fracture-incident-snomed-pm.csv",
    column="code",
)


# Complete vertebral-fracture histories
vertebral_admissions = apcs.where(
    apcs.all_diagnoses.contains_any_of(vertebral_fracture_icd_codes)
)

vertebral_gp_events = clinical_events.where(
    clinical_events.snomedct_code.is_in(vertebral_fracture_snomed_codes)
)


# Potential hospital index events within the permitted study-entry periods
candidate_vertebral_admissions = vertebral_admissions.where(
    apcs.admission_date.is_on_or_between("2019-03-01", "2026-01-31")
    & ~apcs.admission_date.is_on_or_between("2020-03-23", "2020-05-30")
    & ~apcs.admission_date.is_on_or_between("2020-09-07", "2021-04-24")
    & ~apcs.admission_date.is_on_or_between("2021-05-28", "2021-12-14")
)


# Potential GP index events within the permitted study-entry periods
candidate_vertebral_gp_events = vertebral_gp_events.where(
    clinical_events.date.is_on_or_between("2019-03-01", "2026-01-31")
    & ~clinical_events.date.is_on_or_between("2020-03-23", "2020-05-30")
    & ~clinical_events.date.is_on_or_between("2020-09-07", "2021-04-24")
    & ~clinical_events.date.is_on_or_between("2021-05-28", "2021-12-14")
)


# Include patients with at least one hospital or GP vertebral-fracture candidate
dataset.define_population(
    candidate_vertebral_admissions.exists_for_patient()
    | candidate_vertebral_gp_events.exists_for_patient()
)


# Patient-level information needed for event eligibility
dataset.date_of_birth_for_event_qa = patients.date_of_birth


# Candidate hospital records
dataset.add_event_table(
    "candidate_vertebral_admissions",
    admission_date=candidate_vertebral_admissions.admission_date,
    apcs_ident=candidate_vertebral_admissions.apcs_ident,
)


# Candidate GP records
dataset.add_event_table(
    "candidate_vertebral_gp_events",
    event_date=candidate_vertebral_gp_events.date,
    snomedct_code=candidate_vertebral_gp_events.snomedct_code,
)


# Complete hospital history for the six-month lookback
dataset.add_event_table(
    "vertebral_admissions_history",
    admission_date=vertebral_admissions.admission_date,
    apcs_ident=vertebral_admissions.apcs_ident,
)


# Complete GP history for the six-month lookback
dataset.add_event_table(
    "vertebral_gp_events_history",
    event_date=vertebral_gp_events.date,
    snomedct_code=vertebral_gp_events.snomedct_code,
)


# Registration periods used to assess three months' registration
dataset.add_event_table(
    "practice_registrations",
    start_date=practice_registrations.start_date,
    end_date=practice_registrations.end_date,
)