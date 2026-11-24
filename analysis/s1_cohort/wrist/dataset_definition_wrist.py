# Patient-level wrist-fracture candidate extraction for production use.

from ehrql import create_dataset, codelist_from_csv, months

from ehrql.tables.tpp import (
    apcs,
    clinical_events,
    patients,
    practice_registrations,
)

dataset = create_dataset()

# Set maximum candidate dates per patient per source
MAX_CANDIDATE_DATES_PER_SOURCE = 15

# Load fracture ICD-10 and SNOMED codelists ------------------------------
wrist_fracture_icd_codes = codelist_from_csv(
    "local_codelists/wrist-fracture-incident-icd10-xi.csv",
    column="code",
)

wrist_fracture_snomed_codes = codelist_from_csv(
    "local_codelists/wrist-fracture-incident-snomed-xi.csv",
    column="code",
)

# Hospital admission spells and GP records for wrist fractures ---

# Get apcs (admission spells) records where wrist fracture ICD-10 codes 
# is in any diagnosis (all primary and secondary diagnoses)
# from any time period
wrist_admissions = apcs.where(
    apcs.all_diagnoses.contains_any_of(wrist_fracture_icd_codes)
)

# Get clinical_events (GP records) with wrist fracture SNOMED codes
# From any time period
wrist_gp_events = clinical_events.where(
    clinical_events.snomedct_code.is_in(wrist_fracture_snomed_codes)
)

# Subset admissions to where admission date is between March 2019 and January 2026,
# excluding spells where admission date is in COVID-19 pandemic periods
candidate_wrist_admissions = wrist_admissions.where(
    apcs.admission_date.is_on_or_between("2019-03-01", "2026-01-31")
    & ~apcs.admission_date.is_on_or_between("2020-03-23", "2020-05-30")
    & ~apcs.admission_date.is_on_or_between("2020-09-07", "2021-04-24")
    & ~apcs.admission_date.is_on_or_between("2021-05-28", "2021-12-14")
)

# Subset GP records with same time restrictions
candidate_wrist_gp_events = wrist_gp_events.where(
    clinical_events.date.is_on_or_between("2019-03-01", "2026-01-31")
    & ~clinical_events.date.is_on_or_between(
        "2020-03-23",
        "2020-05-30",
    )
    & ~clinical_events.date.is_on_or_between(
        "2020-09-07",
        "2021-04-24",
    )
    & ~clinical_events.date.is_on_or_between(
        "2021-05-28",
        "2021-12-14",
    )
)

# Define initial study population ---------------------------------------------------
# Include only patients with a wrist fracture admission or GP record in the selected time period
dataset.define_population(
    candidate_wrist_admissions.exists_for_patient()
    | candidate_wrist_gp_events.exists_for_patient()
)

# Function to find wrist fracture events per patient per source (hospital admission spells [apcs] or GP record [clinical_events]) -----------
# from earliest to latest date, up to max admission dates per source set (MAX_CANDIDATE_DATES_PER_SOURCE)
def add_candidate_source_columns(
    source_name,
    candidate_events,
    event_date_column,
    event_date_name,
):
    # For first loop run, start with all candidate admissions (hospital) or records (GP)
    remaining_candidate_events = candidate_events

    # Loop through MAX_CANDIDATE_DATES_PER_SOURCE times
    for candidate_number in range(
        1,
        MAX_CANDIDATE_DATES_PER_SOURCE + 1,
    ):

        # Get earliest admission/GP record per patient
        # from remaining admissions/GP records
        candidate_event = (
            remaining_candidate_events
            .sort_by(event_date_column)
            .first_for_patient()
        )

        # Get date for that admission/GP record, per patient - "candidate date"
        candidate_date = getattr(
            candidate_event,
            event_date_name,
        )

        # Get wrist fracture admissions in the 6 months before that candidate date, per patient
        prior_wrist_admissions_6m = wrist_admissions.where(
            apcs.admission_date.is_on_or_after(
                candidate_date - months(6)
            )
            & apcs.admission_date.is_before(candidate_date)
        )

        # Get wrist fracture GP records in the 6 months before that candidate date, per patient
        prior_wrist_gp_events_6m = wrist_gp_events.where(
            clinical_events.date.is_on_or_after(
                candidate_date - months(6)
            )
            & clinical_events.date.is_before(candidate_date)
        )

        # Create boolean indicator for if patient had wrist fracture
        # (admission or GP record) in 6 months before the candidate date
        has_prior_wrist_fracture_6m = (
            prior_wrist_admissions_6m.exists_for_patient()
            | prior_wrist_gp_events_6m.exists_for_patient()
        )

        # Create boolean indicator for if patient has a candidate date
        # (for wrist fracture in the selected period at loop number) in the selected data source
        # and does not have a wrist fracture in the 6 months prior
        passes_6m_rule = (
            candidate_date.is_not_null()
            & ~has_prior_wrist_fracture_6m
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

        # Create boolean indicator for if the admission/GP record is an eligible index date for the patient
        # i.e. on the candidate wrist fracture admission/GP record, the patient
        # - Has no admission or GP record of wrist fracture in prior 6 months
        # - Is aged 18 or over
        # - Has prior 6 months registration
        is_eligible_index = (
            passes_6m_rule
            & age_eligible
            & has_6m_registration
        )

        # Make prefix for columns to be added with fracture type, data source and candidate number
        column_prefix = (
            f"candidate_wrist_{source_name}_"
            f"{candidate_number}"
        )

        # Add columns
        dataset.add_column(
            f"{column_prefix}_date",
            candidate_date,
        )

        dataset.add_column(
            f"{column_prefix}_prior_hospital_count_6m",
            prior_wrist_admissions_6m.count_for_patient(),
        )

        dataset.add_column(
            f"{column_prefix}_prior_gp_count_6m",
            prior_wrist_gp_events_6m.count_for_patient(),
        )

        dataset.add_column(
            f"{column_prefix}_has_prior_fracture_6m",
            has_prior_wrist_fracture_6m,
        )

        dataset.add_column(
            f"{column_prefix}_passes_6m_rule",
            passes_6m_rule,
        )

        dataset.add_column(
            f"{column_prefix}_age",
            age_at_candidate_date,
        )

        dataset.add_column(
            f"{column_prefix}_age_eligible",
            age_eligible,
        )

        dataset.add_column(
            f"{column_prefix}_has_6m_registration",
            has_6m_registration,
        )

        dataset.add_column(
            f"{column_prefix}_is_eligible_index",
            is_eligible_index,
        )

        # Examine next wrist fracture date in admissions (hospital) or records (GP)
        # Keep only wrist fracture admissions/GP records after the candidate date examined in this loop, per patient
        # Drops admission/GP records with same date as candidate date
        remaining_candidate_events = (
            remaining_candidate_events.where(
                event_date_column.is_after(candidate_date)
            )
        )

    # Return table after adding the columns for the max n candidate events
    return remaining_candidate_events

# Apply function - Get up to max n candidate events per patient in source and --------------------
# evaluate each event's eligibility to be the index date for the patient for that fracture

# Run for wrist fracture hospital admissions
remaining_candidate_wrist_admissions = add_candidate_source_columns(
    source_name="hospital",
    candidate_events=candidate_wrist_admissions,
    event_date_column=apcs.admission_date,
    event_date_name="admission_date",
)

# Run for wrist fracture GP records
remaining_candidate_wrist_gp_events = add_candidate_source_columns(
    source_name="gp",
    candidate_events=candidate_wrist_gp_events,
    event_date_column=clinical_events.date,
    event_date_name="date",
)

# After looping through first MAX_CANDIDATE_DATES (nth) candidate wrist fracture admission dates per patient ----------------

# Create boolean indicator for if patient has more than max distinct candidate admission dates    
dataset.add_column(
    "has_more_than_15_candidate_wrist_hospital_dates",
    remaining_candidate_wrist_admissions.exists_for_patient(),
)

# Create boolean indicator for if patient has more than max distinct candidate GP records    
dataset.add_column(
    "has_more_than_15_candidate_wrist_gp_dates",
    remaining_candidate_wrist_gp_events.exists_for_patient(),
)

# Count number of wrist fracture admission spells in selected period, per patient
# irrespective of whether the admissions meet the additional eligibility criteria to be the index date
# Counting records, not distinct admission dates (whereas the loop separates out up to max n distinct dates)
dataset.number_of_candidate_wrist_admission_records = (
    candidate_wrist_admissions.count_for_patient()
)

# Count number of wrist fracture GP records in selected period, per patient
# irrespective of whether the GP records meet the additional eligibility criteria to be the index date
# Counting records, not distinct GP record dates (whereas the loop separates out up to max n distinct dates)
dataset.number_of_candidate_wrist_gp_records = (
    candidate_wrist_gp_events.count_for_patient()
)