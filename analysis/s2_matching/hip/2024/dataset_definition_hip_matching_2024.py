# Extract data for potential controls for hip fracture cases in 2024

# Current matching action does not allow time-varying matching variables
# It matches on columns before copying the index date to the control
# So can't get registration date and age for potential matches at the case's index date
# Therefore current trial solution is getting all cases with index date in 2024
# Getting potential matches and using 1st Jan 2024 as date to get their practice ID and age
# Matching criteria in SAP includes no same fracture in 6 months prior to index date
# So using 6 months before 1st Jan 2024 is 1st July 2023

from ehrql import case, codelist_from_csv, create_dataset, when
from ehrql.tables.tpp import (
    addresses,
    apcs,
    clinical_events,
    patients,
    practice_registrations,
)

# Set parameters --------------------------

# Date to get patient info for potential controls - start of 2024
ANCHOR_DATE = "2024-01-01"

# 
FRACTURE_WINDOW_START = "2023-07-01"

dataset = create_dataset()

# Load fracture ICD-10 and SNOMED codelists ------------------------------
hip_fracture_icd_codes = codelist_from_csv(
    "local_codelists/hip-fracture-incident-icd10-md.csv",
    column="code",
)

hip_fracture_snomed_codes = codelist_from_csv(
    "local_codelists/hip-fracture-incident-snomed-pm.csv",
    column="code",
)

# Get practice registration at anchor date
registration_at_anchor = practice_registrations.for_patient_on(
    ANCHOR_DATE
)

# Get address at anchor date
address_at_anchor = addresses.for_patient_on(ANCHOR_DATE)

# Check patient has registration spanning at least 6 months before anchor date
has_6m_registration_at_anchor = (
    practice_registrations
    .spanning(FRACTURE_WINDOW_START, ANCHOR_DATE)
    .exists_for_patient()
)

# Get hip fracture admissions in 6 months prior to anchor date
hip_admissions_in_anchor_window = apcs.where(
    apcs.all_diagnoses.contains_any_of(hip_fracture_icd_codes)
    & apcs.admission_date.is_on_or_between(
        FRACTURE_WINDOW_START,
        ANCHOR_DATE,
    )
)

# Get hip fracture GP records in 6 months prior to anchor date
hip_gp_events_in_anchor_window = clinical_events.where(
    clinical_events.snomedct_code.is_in(
        hip_fracture_snomed_codes
    )
    & clinical_events.date.is_on_or_between(
        FRACTURE_WINDOW_START,
        ANCHOR_DATE,
    )
)

# Create boolean indicator for whether patient as a hip fracture admission or GP record 
# in 6 months prior to anchor date
has_hip_fracture_in_anchor_window = (
    hip_admissions_in_anchor_window.exists_for_patient()
    | hip_gp_events_in_anchor_window.exists_for_patient()
)

# Get age at anchor date
age_at_anchor = patients.age_on(ANCHOR_DATE)

# Create indicator for if address at anchor date is matched to a care home (TPP algorithm) 
care_home_status_at_anchor = case(
    when(
        address_at_anchor.care_home_is_potential_match
    ).then("care_home"),
    otherwise="not_care_home",
)

# Define potential control population ------------------------------------------
# Include if:
# - Age at anchor date is 17 or more
# - Sex is not null
# - Registered on anchor date
# - Address found on anchor date

# Not yet excluding if:
# - Has hip fracture in 6 months prior to anchor date
# - Registered for less than 6 months at anchor date
dataset.define_population(
    patients.exists_for_patient()
    # Include patients who may turn 18 during 2024. Exact age is checked
    # later using the inherited case index date.
    & (age_at_anchor >= 17)
    & patients.sex.is_not_null()
    & registration_at_anchor.exists_for_patient()
    & address_at_anchor.exists_for_patient()
)

# Specify columns to include in output
dataset.age = age_at_anchor
dataset.sex = patients.sex
dataset.practice = registration_at_anchor.practice_pseudo_id
dataset.care_home = care_home_status_at_anchor
dataset.has_6m_registration_at_anchor = (
    has_6m_registration_at_anchor
)
dataset.no_hip_fracture_6m_anchor = (
    ~has_hip_fracture_in_anchor_window
)
