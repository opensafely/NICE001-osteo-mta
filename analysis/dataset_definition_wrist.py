# Patient-level wrist-fracture candidate extraction for production use.

from ehrql import create_dataset, codelist_from_csv, months

from ehrql.tables.tpp import (
    apcs,
    clinical_events,
    patients,
    practice_registrations,
)


dataset = create_dataset()

MAX_CANDIDATE_DATES_PER_SOURCE = 15


wrist_fracture_icd_codes = codelist_from_csv(
    "local_codelists/wrist-fracture-incident-icd10-xi.csv",
    column="code",
)

wrist_fracture_snomed_codes = codelist_from_csv(
    "local_codelists/wrist-fracture-incident-snomed-xi.csv",
    column="code",
)


wrist_admissions = apcs.where(
    apcs.all_diagnoses.contains_any_of(wrist_fracture_icd_codes)
)

wrist_gp_events = clinical_events.where(
    clinical_events.snomedct_code.is_in(wrist_fracture_snomed_codes)
)


candidate_wrist_admissions = wrist_admissions.where(
    apcs.admission_date.is_on_or_between("2019-03-01", "2026-01-31")
    & ~apcs.admission_date.is_on_or_between("2020-03-23", "2020-05-30")
    & ~apcs.admission_date.is_on_or_between("2020-09-07", "2021-04-24")
    & ~apcs.admission_date.is_on_or_between("2021-05-28", "2021-12-14")
)

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


dataset.define_population(
    candidate_wrist_admissions.exists_for_patient()
    | candidate_wrist_gp_events.exists_for_patient()
)


def add_candidate_source_columns(
    source_name,
    candidate_events,
    event_date_column,
    event_date_name,
):
    remaining_candidate_events = candidate_events

    for candidate_number in range(
        1,
        MAX_CANDIDATE_DATES_PER_SOURCE + 1,
    ):
        candidate_event = (
            remaining_candidate_events
            .sort_by(event_date_column)
            .first_for_patient()
        )

        candidate_date = getattr(
            candidate_event,
            event_date_name,
        )

        prior_wrist_admissions_6m = wrist_admissions.where(
            apcs.admission_date.is_on_or_after(
                candidate_date - months(6)
            )
            & apcs.admission_date.is_before(candidate_date)
        )

        prior_wrist_gp_events_6m = wrist_gp_events.where(
            clinical_events.date.is_on_or_after(
                candidate_date - months(6)
            )
            & clinical_events.date.is_before(candidate_date)
        )

        has_prior_wrist_fracture_6m = (
            prior_wrist_admissions_6m.exists_for_patient()
            | prior_wrist_gp_events_6m.exists_for_patient()
        )

        passes_6m_rule = (
            candidate_date.is_not_null()
            & ~has_prior_wrist_fracture_6m
        )

        age_at_candidate_date = patients.age_on(candidate_date)

        age_eligible = (
            candidate_date.is_not_null()
            & (age_at_candidate_date >= 18)
        )

        has_6m_registration = (
            candidate_date.is_not_null()
            & practice_registrations
            .spanning(
                candidate_date - months(6),
                candidate_date,
            )
            .exists_for_patient()
        )

        is_eligible_index = (
            passes_6m_rule
            & age_eligible
            & has_6m_registration
        )

        column_prefix = (
            f"candidate_wrist_{source_name}_"
            f"{candidate_number}"
        )

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

        remaining_candidate_events = (
            remaining_candidate_events.where(
                event_date_column.is_after(candidate_date)
            )
        )

    return remaining_candidate_events


remaining_candidate_wrist_admissions = add_candidate_source_columns(
    source_name="hospital",
    candidate_events=candidate_wrist_admissions,
    event_date_column=apcs.admission_date,
    event_date_name="admission_date",
)

remaining_candidate_wrist_gp_events = add_candidate_source_columns(
    source_name="gp",
    candidate_events=candidate_wrist_gp_events,
    event_date_column=clinical_events.date,
    event_date_name="date",
)


dataset.add_column(
    "has_more_than_15_candidate_wrist_hospital_dates",
    remaining_candidate_wrist_admissions.exists_for_patient(),
)

dataset.add_column(
    "has_more_than_15_candidate_wrist_gp_dates",
    remaining_candidate_wrist_gp_events.exists_for_patient(),
)

dataset.number_of_candidate_wrist_admission_records = (
    candidate_wrist_admissions.count_for_patient()
)

dataset.number_of_candidate_wrist_gp_records = (
    candidate_wrist_gp_events.count_for_patient()
)