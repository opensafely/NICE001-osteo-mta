# After matching, get values for matching variables and additional eligibility 
# criteria for matches on their index date that they have inherited from the case

# Allows checking if still a valid match using data for the matched patients on the correct date
# (They were matched using info from a proxy anchor date)

import datetime

from ehrql import (
    case,
    codelist_from_csv,
    create_dataset,
    months,
    table_from_file,
    when,
)
from ehrql.tables.tpp import (
    addresses,
    apcs,
    clinical_events,
    patients,
    practice_registrations,
)

# Specify paths for files
MATCHED_CONTROLS_FILE = (
    "output/hip_matched_controls_for_ehrql_2024.csv.gz"
)

# Read in QA-ed matched controls table
matched_controls = table_from_file(
    MATCHED_CONTROLS_FILE,
    columns={
        "index_date": datetime.date,
        "set_id": int,
    },
)

# Read in codelists
hip_fracture_icd_codes = codelist_from_csv(
    "local_codelists/hip-fracture-incident-icd10-md.csv",
    column="code",
)

hip_fracture_snomed_codes = codelist_from_csv(
    "local_codelists/hip-fracture-incident-snomed-pm.csv",
    column="code",
)

# Separate index date
index_date = matched_controls.index_date

# Get registration at index date
registration_at_index = practice_registrations.for_patient_on(
    index_date
)

# Get address at index date
address_at_index = addresses.for_patient_on(index_date)

# Create indicator for if address at index date is matched to a care home 
care_home_status_at_index = case(
    when(
        address_at_index.exists_for_patient()
        & address_at_index.care_home_is_potential_match
    ).then("care_home"),
    when(
        address_at_index.exists_for_patient()
    ).then("not_care_home"),
)

# Check patient has registration spanning at least 6 months before index date
has_6m_registration_at_index = (
    practice_registrations
    .spanning(index_date - months(6), index_date)
    .exists_for_patient()
)

# Get hip fracture admissions in 6 months prior to index date
hip_admissions_in_6m_window = apcs.where(
    apcs.all_diagnoses.contains_any_of(hip_fracture_icd_codes)
    & apcs.admission_date.is_on_or_between(
        index_date - months(6),
        index_date,
    )
)

# Get hip fracture GP records in 6 months prior to index date
hip_gp_events_in_6m_window = clinical_events.where(
    clinical_events.snomedct_code.is_in(
        hip_fracture_snomed_codes
    )
    & clinical_events.date.is_on_or_between(
        index_date - months(6),
        index_date,
    )
)

# Create boolean indicator for whether patient as a hip fracture admission or GP record 
# in 6 months prior to index date
has_hip_fracture_in_6m_window = (
    hip_admissions_in_6m_window.exists_for_patient()
    | hip_gp_events_in_6m_window.exists_for_patient()
)

# Create dataset
dataset = create_dataset()

# Include all patients from matched controls in dataset
dataset.define_population(
    matched_controls.exists_for_patient()
)

# Specify columns to include in output dataset
dataset.set_id = matched_controls.set_id
dataset.index_date = index_date
dataset.age_at_index = patients.age_on(index_date)
dataset.sex_at_index = patients.sex
dataset.practice_at_index = (
    registration_at_index.practice_pseudo_id
)
dataset.care_home_at_index = care_home_status_at_index
dataset.has_6m_registration_at_index = (
    has_6m_registration_at_index
)
dataset.no_hip_fracture_6m_index = (
    ~has_hip_fracture_in_6m_window
)
