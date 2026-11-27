# Currently for hip fracture cases with index date in 2024 and their controls only
# Change input file path when ready

import datetime

from ehrql import (
    case,
    codelist_from_csv,
    create_dataset,
    months,
    years,
    days,
    table_from_file,
    when,
)
from ehrql.tables.tpp import (
    addresses,
    apcs,
    clinical_events,
    patients,
    practice_registrations,
    ethnicity_from_sus,
    medications
)

# Specify paths for files
# File with final cases and controls
CASES_AND_CONTROLS_FILE = (
    "output/matched_combined_hip_2024.arrow"
)

# Read in codelists --------------------------------------------------------------------------------
ethnicity_codes = codelist_from_csv(
    "local_codelists/user-xixiong-ethnicity-with-class.csv",
    column = "code",
    category_column = "class")

bmi_codes = codelist_from_csv(
    "codelists/nhsd-primary-care-domain-refsets-bmival_cod.csv",
    column = "code")

oral_corticosteroid_codes = codelist_from_csv(
    "local_codelists/user-xixiong-oral-systemic-corticosteroids.csv",
    column = "code")

rheumatoid_arthritis_codes = codelist_from_csv(
    "codelists/nhsd-primary-care-domain-refsets-rarth_cod.csv",
    column = "code")

sle_codes = codelist_from_csv(
    "codelists/nhsd-primary-care-domain-refsets-slupus_cod.csv",
    column = "code")

hip_fracture_icd_codes = codelist_from_csv(
    "local_codelists/hip-fracture-incident-icd10-md.csv",
    column="code"
)

hip_fracture_snomed_codes = codelist_from_csv(
    "local_codelists/hip-fracture-incident-snomed-pm.csv",
    column="code"
)

# Read in patient ID for cases and controls and their index date
cohort = table_from_file(
    CASES_AND_CONTROLS_FILE,
    columns={
        "index_date": datetime.date,
    },
)

# Include all patients in cohort in dataset
dataset = create_dataset()
dataset.define_population(
    cohort.exists_for_patient()
)

# Ethnicity ------------------------------------------------------------------------------------
# Get latest ethnicity record on or before index date
# (chooses arbitrarily if there are ties)
latest_ethnicity_gp = (
    clinical_events.where(clinical_events.snomedct_code.is_in(ethnicity_codes))
    .where(clinical_events.date.is_on_or_before(cohort.index_date))
    .sort_by(clinical_events.date)
    .last_for_patient()
)

# Add ethnicity group and date from latest ethnicity record to dataset
dataset.ethnicity_group_gp = latest_ethnicity_gp.snomedct_code.to_category(ethnicity_codes)
dataset.ethnicity_date_gp = latest_ethnicity_gp.date

# Add most frequent ethnicity code from SUS to dataset
dataset.ethnicity_sus = ethnicity_from_sus.code

# BMI value -------------------------------------------------------------------------------------
# Get latest non-missing BMI value above 0 on or before the index date
latest_bmi = (
    clinical_events.where(clinical_events.snomedct_code.is_in(bmi_codes))
    .where(clinical_events.date.is_on_or_before(cohort.index_date))
    .where(clinical_events.numeric_value.is_not_null())
    .where(clinical_events.numeric_value > 0.0)
    .sort_by(clinical_events.date)
    .last_for_patient()
)

# Add BMI value and date from latest BMI record to dataset
dataset.baseline_bmi = latest_bmi.numeric_value
dataset.baseline_bmi_date = latest_bmi.date

# Recent oral systemic corticosteroid use --------------------------------------------------------
# Count the number of oral corticosteroid records in the 6 months before the index date
count_6m_corticosteroid_use = (
    medications.where(medications.dmd_code.is_in(oral_corticosteroid_codes))
    .where(medications.date.is_on_or_between(cohort.index_date - months(6), cohort.index_date - days(1)))
    .count_for_patient()
)

# Add indicator for whether patient had two records of oral corticosteroids in the 6 months
# before the index date
dataset.had_2_corticosteroids_6m_prior = (count_6m_corticosteroid_use >= 2)

# History of rheumatoid arthritis --------------------------------------------------------------
# Add indicator for whether patient had any GP record of rheumatoid arthritis before the index date  
dataset.has_rheumatoid_arthritis = (
    clinical_events.where(clinical_events.snomedct_code.is_in(rheumatoid_arthritis_codes))
    .where(clinical_events.date.is_before(cohort.index_date))
    .exists_for_patient()
)

# History of systemic lupus erythematosus (SLE) -------------------------------------------------------
# Add indicator for whether patient had any GP record of SLE before the index date 
dataset.has_sle = (
    clinical_events.where(clinical_events.snomedct_code.is_in(sle_codes))
    .where(clinical_events.date.is_before(cohort.index_date))
    .exists_for_patient()
)
# Family history of osteoporosis ----------------------------------------------------------------
# Alcohol intake --------------------------------------------------------------------------------
# EFI -------------------------------------------------------------------------------------------

# Hospital admissions in previous 5 years -----------------------------------------------------
# Add count of number of ordinary admissions in the 5 years before the index date
dataset.n_admissions_5y_prior = (
    apcs.where(apcs.admission_date.is_on_or_between(cohort.index_date - years(5), cohort.index_date - days(1)))
    .where(apcs.patient_classification == "1")
    .count_for_patient()
)

# History of hip fracture -----------------------------------------------------------------------
# Whether patient has hip fracture admission before the index date
has_prior_hip_fracture_admission = (
    apcs.where(apcs.all_diagnoses.contains_any_of(hip_fracture_icd_codes))
    .where(apcs.admission_date.is_before(cohort.index_date))
    .exists_for_patient()
)

# Whether patient has hip fracture GP record before the index date
has_prior_hip_fracture_gp_record = (
    clinical_events.where(clinical_events.snomedct_code.is_in(hip_fracture_snomed_codes))
    .where(clinical_events.date.is_before(cohort.index_date))
    .exists_for_patient()
)

# Add indicator for whether a patient had a hip fracture admission or GP record before the index date
dataset.had_hip_fracture = (has_prior_hip_fracture_admission | has_prior_hip_fracture_gp_record)