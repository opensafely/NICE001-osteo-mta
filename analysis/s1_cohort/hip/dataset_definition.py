# Temporary QA dataset for reconstructing and testing hip-fracture
# candidate dates. This is not the final eligible analysis cohort.

from ehrql import case, create_dataset, codelist_from_csv, months, when, show

from ehrql.tables.tpp import (
    addresses,
    apcs,
    clinical_events,
    patients,
    practice_registrations,
)

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

# Hospital admission spells for hip fractures (APCS [Admitted Patient Care Spells]) ---

# Get apcs (admission spells) records where hip fracture ICD-10 codes 
# is in any diagnosis (all primary and secondary diagnoses)
hip_admissions = apcs.where(
    apcs.all_diagnoses.contains_any_of(hip_fracture_icd_codes)
)
# (These and subsequent things are not new dataframes, 
# rather an ehrQL expression representing a filter on the apcs table.
# The underlying records are still apcs records)

# Further subset to spells where admission date is between March 2019 and January 2026,
# excluding spells where admission date is in COVID-19 pandemic periods
candidate_hip_admissions = hip_admissions.where(
    apcs.admission_date.is_on_or_between("2019-03-01", "2026-01-31")
    & ~apcs.admission_date.is_on_or_between("2020-03-23", "2020-05-30")
    & ~apcs.admission_date.is_on_or_between("2020-09-07", "2021-04-24")
    & ~apcs.admission_date.is_on_or_between("2021-05-28", "2021-12-14")
)
# (hip_admissions.where() specifies which records we are filtering.
# apcs.admission_date inside .where() as hip_admissions is still apcs records, 
# so specifying which property of apcs record subset we are filtering on)

# GP clinical/consultation events for hip fractures --------------------------

# Get clinical_events (GP records) with hip fracture SNOMED codes
# From any time period
hip_gp_events = clinical_events.where(
    clinical_events.snomedct_code.is_in(hip_fracture_snomed_codes)
)

# Define initial study population ---------------------------------------------------
# Include only patients with a hip fracture admission in the selected time period
dataset.define_population(candidate_hip_admissions.exists_for_patient())

# Get patient's sex
dataset.sex = patients.sex

# Loop through eligible hip fracture admissions per patient from earliest to latest date ---------
# and find all eligible index dates (max 15) -----------------------------------------------------
# Get patient info at admission date and assess if admission spell meets criteria
# - No hip fracture in 6 months prior (in GP records or hospital admissions) to admission date
# - At least 6 months prior GP practice registration at admission date
# - Aged 18 or over at admission date

# Set maximum candidate dates per patient 
MAX_CANDIDATE_DATES = 15

# For first loop run, start with all candidate hip fracture admissions
remaining_candidate_hip_admissions = candidate_hip_admissions

# Loop through 15 times
for candidate_number in range(1, MAX_CANDIDATE_DATES + 1):

    # Get earliest hip fracture admission per patient
    # from remaining candidate hip fracture admissions
    candidate_admission = (
        remaining_candidate_hip_admissions
        .sort_by(apcs.admission_date)
        .first_for_patient()
    )

    # Get admission date for that admission, per patient - "candidate date"
    candidate_date = candidate_admission.admission_date

    # Get single best practice registration info at that candidate date, per patient
    registration_at_candidate_date = (
        practice_registrations.for_patient_on(candidate_date)
    )

    # Get single best address info at that candidate date, per patient
    address_at_candidate_date = addresses.for_patient_on(
        candidate_date
    )

    # Get care home status from address info at that candidate date, per patient
    # - If address exists and address is matched to a care home (TPP algorithm) - "care_home"
    # - If address exists and address is not matched to a care home - "not_care_home"
    # - If no address exists - NULL
    care_home_status_at_candidate_date = case(
        when(
            address_at_candidate_date.exists_for_patient()
            & address_at_candidate_date.care_home_is_potential_match
        ).then("care_home"),
        when(
            address_at_candidate_date.exists_for_patient()
        ).then("not_care_home"),
    )

    # Get hip fracture admissions in the 6 months before that candidate date, per patient
    prior_hip_admissions_6m_for_candidate = hip_admissions.where(
        apcs.admission_date.is_on_or_after(
            candidate_date - months(6)
        )
        & apcs.admission_date.is_before(candidate_date)
    )

    # Get hip fracture GP records in the 6 months before that candidate date, per patient
    prior_hip_gp_events_6m_for_candidate = hip_gp_events.where(
        clinical_events.date.is_on_or_after(
            candidate_date - months(6)
        )
        & clinical_events.date.is_before(candidate_date)
    )

    # Create boolean indicator for if patient had hip fracture
    # (admission or GP record) in 6 months before the candidate date
    has_prior_hip_fracture_6m_for_candidate = (
        prior_hip_admissions_6m_for_candidate.exists_for_patient()
        | prior_hip_gp_events_6m_for_candidate.exists_for_patient()
    )

    # Create boolean indicator for if patient has a candidate date
    # (for hip fracture in the selected period at loop number) and 
    # does not have a hip fracture in the 6 months prior
    passes_6m_rule = (
        candidate_date.is_not_null()
        & ~has_prior_hip_fracture_6m_for_candidate
    )     

    # Get age on candidate date, per patient
    age_at_candidate_date = patients.age_on(candidate_date)

    # Create boolean indicator for if patient has a candidate date
    # and is aged 18 or above at that date
    age_eligible = (
        candidate_date.is_not_null()
        & (age_at_candidate_date >= 18)
    )

    # Create boolean indicator for if patient has a candidate date
    # and has at least one practice registration record which covers the 6 months 
    # prior to the candidate date
    has_6m_registration = (
        candidate_date.is_not_null()
        & practice_registrations
        .spanning(
            candidate_date - months(6),
            candidate_date,
        )
        .exists_for_patient()
    )

    # Create boolean indicator for if on the candidate date, the patient
    # - Does not have hip fracture in prior 6 months
    # - Is aged 18 or over
    # - Has prior 6 months registration
    is_eligible_index = (
        passes_6m_rule
        & age_eligible
        & has_6m_registration
    )

    # Add columns
    dataset.add_column(
        f"candidate_hip_date_{candidate_number}",
        candidate_date,
    )

    dataset.add_column(
        f"candidate_hip_prior_hospital_count_6m_{candidate_number}",
        prior_hip_admissions_6m_for_candidate.count_for_patient(),
    )

    dataset.add_column(
        f"candidate_hip_prior_gp_count_6m_{candidate_number}",
        prior_hip_gp_events_6m_for_candidate.count_for_patient(),
    )

    dataset.add_column(
        f"candidate_hip_has_prior_fracture_6m_{candidate_number}",
        has_prior_hip_fracture_6m_for_candidate,
    )

    dataset.add_column(
        f"candidate_hip_passes_6m_rule_{candidate_number}",
        passes_6m_rule,
    )

    dataset.add_column(
        f"candidate_hip_age_{candidate_number}",
        age_at_candidate_date,
    )

    dataset.add_column(
        f"candidate_hip_practice_{candidate_number}",
        registration_at_candidate_date.practice_pseudo_id,
    )

    dataset.add_column(
        f"candidate_hip_care_home_{candidate_number}",
        care_home_status_at_candidate_date,
    )

    dataset.add_column(
        f"candidate_hip_age_eligible_{candidate_number}",
        age_eligible,
    )

    dataset.add_column(
        f"candidate_hip_has_6m_registration_{candidate_number}",
        has_6m_registration,
    )

    dataset.add_column(
        f"candidate_hip_is_eligible_index_{candidate_number}",
        is_eligible_index,
    )

    # Examine next hip fracture admissions
    # (Keep only hip fracture admissions after the candidate date, per patient)
    remaining_candidate_hip_admissions = (
        remaining_candidate_hip_admissions.where(
            apcs.admission_date.is_after(candidate_date)
        )
    )

# After looping through first 15 eligible hip fracture admission dates per patient ----------------

# Create boolean indicator for if patient has more than max distinct candidate admission dates    
dataset.add_column(
    f"has_more_than_{MAX_CANDIDATE_DATES}_candidate_hip_dates",
    remaining_candidate_hip_admissions.exists_for_patient(),
)

# Count number of hip fracture admission spell records in selected period, per patient
# irrespective of whether the admissions meet the additional criteria
# (no hip fracture in prior 6 months, prior 6 month registration, aged 18 or over)
# Counting records, not distinct admission dates
dataset.number_of_candidate_hip_admission_records = (
    candidate_hip_admissions.count_for_patient()
)

# Count number of hip fracture GP records in all time, per patient
dataset.number_of_hip_gp_events = hip_gp_events.count_for_patient()




