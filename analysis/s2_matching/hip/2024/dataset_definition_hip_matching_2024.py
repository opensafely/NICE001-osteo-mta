from ehrql import case, codelist_from_csv, create_dataset, when
from ehrql.tables.tpp import (
    addresses,
    apcs,
    clinical_events,
    patients,
    practice_registrations,
)


ANCHOR_DATE = "2024-01-01"
FRACTURE_WINDOW_START = "2023-07-01"

dataset = create_dataset()

hip_fracture_icd_codes = codelist_from_csv(
    "local_codelists/hip-fracture-incident-icd10-md.csv",
    column="code",
)

hip_fracture_snomed_codes = codelist_from_csv(
    "local_codelists/hip-fracture-incident-snomed-pm.csv",
    column="code",
)

registration_at_anchor = practice_registrations.for_patient_on(
    ANCHOR_DATE
)

address_at_anchor = addresses.for_patient_on(ANCHOR_DATE)

has_6m_registration_at_anchor = (
    practice_registrations
    .spanning(FRACTURE_WINDOW_START, ANCHOR_DATE)
    .exists_for_patient()
)

hip_admissions_in_anchor_window = apcs.where(
    apcs.all_diagnoses.contains_any_of(hip_fracture_icd_codes)
    & apcs.admission_date.is_on_or_between(
        FRACTURE_WINDOW_START,
        ANCHOR_DATE,
    )
)

hip_gp_events_in_anchor_window = clinical_events.where(
    clinical_events.snomedct_code.is_in(
        hip_fracture_snomed_codes
    )
    & clinical_events.date.is_on_or_between(
        FRACTURE_WINDOW_START,
        ANCHOR_DATE,
    )
)

has_hip_fracture_in_anchor_window = (
    hip_admissions_in_anchor_window.exists_for_patient()
    | hip_gp_events_in_anchor_window.exists_for_patient()
)

age_at_anchor = patients.age_on(ANCHOR_DATE)

care_home_status_at_anchor = case(
    when(
        address_at_anchor.care_home_is_potential_match
    ).then("care_home"),
    otherwise="not_care_home",
)

dataset.define_population(
    patients.exists_for_patient()
    # Include patients who may turn 18 during 2024. Exact age is checked
    # later using the inherited case index date.
    & (age_at_anchor >= 17)
    & patients.sex.is_not_null()
    & registration_at_anchor.exists_for_patient()
    & address_at_anchor.exists_for_patient()
)

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
