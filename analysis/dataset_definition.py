# Temporary QA dataset for reconstructing and testing hip-fracture
# candidate dates. This is not the final eligible analysis cohort.

from ehrql import create_dataset, codelist_from_csv, months
from ehrql.tables.tpp import apcs, clinical_events

dataset = create_dataset()

hip_fracture_icd_codes = codelist_from_csv(
    "codelists/hip-fracture-incident-icd10-md.csv",
    column="code",
)

hip_fracture_snomed_codes = codelist_from_csv(
    "codelists/hip-fracture-incident-snomed-pm.csv",
    column="code",
)

vertebral_fracture_icd_codes = codelist_from_csv(
    "codelists/vertebral-fracture-incident-icd10-xi.csv",
    column="code",
)

vertebral_fracture_snomed_codes = codelist_from_csv(
    "codelists/vertebral-fracture-incident-snomed-pm.csv",
    column="code",
)

wrist_fracture_icd_codes = codelist_from_csv(
    "codelists/wrist-fracture-incident-icd10-xi.csv",
    column="code",
)

wrist_fracture_snomed_codes = codelist_from_csv(
    "codelists/wrist-fracture-incident-snomed-xi.csv",
    column="code",
)

prox_humerus_fracture_icd_codes = codelist_from_csv(
    "codelists/prox-humerus-fracture-incident-icd10-xi.csv",
    column="code",
)

prox_humerus_fracture_snomed_codes = codelist_from_csv(
    "codelists/prox-humerus-fracture-incident-snomed-xi.csv",
    column="code",
)

hip_admissions = apcs.where(
    apcs.all_diagnoses.contains_any_of(hip_fracture_icd_codes)
)

candidate_hip_admissions = hip_admissions.where(
    apcs.admission_date.is_on_or_between("2019-03-01", "2026-01-31")
    & ~apcs.admission_date.is_on_or_between("2020-03-23", "2020-05-30")
    & ~apcs.admission_date.is_on_or_between("2020-09-07", "2021-04-24")
    & ~apcs.admission_date.is_on_or_between("2021-05-28", "2021-12-14")
)

hip_gp_events = clinical_events.where(
    clinical_events.snomedct_code.is_in(hip_fracture_snomed_codes)
)

dataset.define_population(candidate_hip_admissions.exists_for_patient())

MAX_CANDIDATE_DATES = 10

remaining_candidate_hip_admissions = candidate_hip_admissions

for candidate_number in range(1, MAX_CANDIDATE_DATES + 1):
    candidate_admission = (
        remaining_candidate_hip_admissions
        .sort_by(apcs.admission_date)
        .first_for_patient()
    )

    candidate_date = candidate_admission.admission_date
    
    prior_hip_admissions_6m_for_candidate = hip_admissions.where(
        apcs.admission_date.is_on_or_after(
            candidate_date - months(6)
        )
        & apcs.admission_date.is_before(candidate_date)
    )

    prior_hip_gp_events_6m_for_candidate = hip_gp_events.where(
        clinical_events.date.is_on_or_after(
            candidate_date - months(6)
        )
        & clinical_events.date.is_before(candidate_date)
    )

    has_prior_hip_fracture_6m_for_candidate = (
        prior_hip_admissions_6m_for_candidate.exists_for_patient()
        | prior_hip_gp_events_6m_for_candidate.exists_for_patient()
    )

    passes_6m_rule = (
        candidate_date.is_not_null()
        & ~has_prior_hip_fracture_6m_for_candidate
    )

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

    remaining_candidate_hip_admissions = (
        remaining_candidate_hip_admissions.where(
            apcs.admission_date.is_after(candidate_date)
        )
    )
    
dataset.add_column(
    f"has_more_than_{MAX_CANDIDATE_DATES}_candidate_hip_dates",
    remaining_candidate_hip_admissions.exists_for_patient(),
)

dataset.number_of_candidate_hip_admission_records = (
    candidate_hip_admissions.count_for_patient()
)

dataset.number_of_hip_gp_events = hip_gp_events.count_for_patient()




