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

first_hip_gp_event = (
    hip_gp_events
    .sort_by(clinical_events.date)
    .first_for_patient()
)

first_hip_admission = (
    candidate_hip_admissions
    .sort_by(apcs.admission_date)
    .first_for_patient()
)

index_date_for_qa = first_hip_admission.admission_date

prior_hip_admissions_6m = hip_admissions.where(
    apcs.admission_date.is_on_or_after(
        index_date_for_qa - months(6)
    )
    & apcs.admission_date.is_before(index_date_for_qa)
)

prior_hip_gp_events_6m = hip_gp_events.where(
    clinical_events.date.is_on_or_after(
        index_date_for_qa - months(6)
    )
    & clinical_events.date.is_before(index_date_for_qa)
)

last_prior_hip_admission_6m = (
    prior_hip_admissions_6m
    .sort_by(apcs.admission_date)
    .last_for_patient()
)

last_prior_hip_gp_event_6m = (
    prior_hip_gp_events_6m
    .sort_by(clinical_events.date)
    .last_for_patient()
)


second_hip_admission = (
    candidate_hip_admissions
    .where(
        apcs.admission_date.is_after(
            first_hip_admission.admission_date
        )
    )
    .sort_by(apcs.admission_date)
    .first_for_patient()
)

second_index_date_for_qa = second_hip_admission.admission_date

prior_hip_admissions_6m_before_second = hip_admissions.where(
    apcs.admission_date.is_on_or_after(
        second_index_date_for_qa - months(6)
    )
    & apcs.admission_date.is_before(second_index_date_for_qa)
)

prior_hip_gp_events_6m_before_second = hip_gp_events.where(
    clinical_events.date.is_on_or_after(
        second_index_date_for_qa - months(6)
    )
    & clinical_events.date.is_before(second_index_date_for_qa)
)

dataset.define_population(candidate_hip_admissions.exists_for_patient())
dataset.first_hip_admission_date = first_hip_admission.admission_date
dataset.number_of_candidate_hip_admissions = candidate_hip_admissions.count_for_patient()

dataset.first_hip_gp_event_date = first_hip_gp_event.date
dataset.number_of_hip_gp_events = hip_gp_events.count_for_patient()

dataset.number_of_prior_hip_admissions_6m = (
    prior_hip_admissions_6m.count_for_patient()
)

dataset.number_of_prior_hip_gp_events_6m = (
    prior_hip_gp_events_6m.count_for_patient()
)

dataset.last_prior_hip_admission_date_6m = (
    last_prior_hip_admission_6m.admission_date
)

dataset.last_prior_hip_gp_event_date_6m = (
    last_prior_hip_gp_event_6m.date
)

dataset.has_prior_hip_fracture_6m = (
    prior_hip_admissions_6m.exists_for_patient()
    | prior_hip_gp_events_6m.exists_for_patient()
)

dataset.second_hip_admission_date = (
    second_hip_admission.admission_date
)

dataset.number_of_prior_hip_admissions_6m_before_second = (
    prior_hip_admissions_6m_before_second.count_for_patient()
)

dataset.number_of_prior_hip_gp_events_6m_before_second = (
    prior_hip_gp_events_6m_before_second.count_for_patient()
)

dataset.has_prior_hip_fracture_6m_before_second = (
    prior_hip_admissions_6m_before_second.exists_for_patient()
    | prior_hip_gp_events_6m_before_second.exists_for_patient()
)