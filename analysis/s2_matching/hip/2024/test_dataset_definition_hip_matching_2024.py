from datetime import date

from dataset_definition_hip_matching_2024 import dataset


def matching_patient(
    patient_id,
    date_of_birth,
    sex,
    practice=100,
    care_home=False,
    registration_start=date(2020, 1, 1),
    hip_fracture_date=None,
    expected_in_population=True,
):
    record = {
        "patients": {
            "date_of_birth": date_of_birth,
            "sex": sex,
        },
        "practice_registrations": [
            {
                "start_date": registration_start,
                "end_date": None,
                "practice_pseudo_id": practice,
            },
        ],
        "addresses": [
            {
                "address_id": patient_id,
                "start_date": date(2020, 1, 1),
                "end_date": None,
                "care_home_is_potential_match": care_home,
            },
        ],
        "apcs": [],
        "clinical_events": [],
        "expected_in_population": expected_in_population,
    }

    if hip_fracture_date is not None:
        record["apcs"] = [
            {
                "apcs_ident": patient_id,
                "admission_date": hip_fracture_date,
                "all_diagnoses": "||S720",
            },
        ]

    if expected_in_population:
        record["expected_columns"] = {
            "age": (
                date(2024, 1, 1).year
                - date_of_birth.year
                - (
                    (1, 1)
                    < (date_of_birth.month, date_of_birth.day)
                )
            ),
            "sex": sex,
            "practice": practice,
            "care_home": (
                "care_home" if care_home else "not_care_home"
            ),
            "has_6m_registration_at_anchor": (
                registration_start <= date(2023, 7, 1)
            ),
            "no_hip_fracture_6m_anchor": (
                hip_fracture_date is None
                or not date(2023, 7, 1)
                <= hip_fracture_date
                <= date(2024, 1, 1)
            ),
        }

    return record


test_data = {
    # Selected 2024 hip case. It is absent from the 1 January snapshot
    # because registration begins in March 2024.
    11: matching_patient(
        patient_id=11,
        date_of_birth=date(1980, 1, 1),
        sex="female",
        registration_start=date(2024, 3, 1),
        hip_fracture_date=date(2024, 5, 1),
        expected_in_population=False,
    ),

    # Selected 2024 hip case. It is 17 at the annual anchor but 18 at
    # its exact June index date, so the broad snapshot must include it.
    12: matching_patient(
        patient_id=12,
        date_of_birth=date(2006, 6, 1),
        sex="male",
        registration_start=date(2023, 12, 1),
        hip_fracture_date=date(2024, 6, 1),
    ),

    # Four clean matches for patient 12: male, same practice,
    # same care-home status and within three years of age.
    201: matching_patient(
        201, date(2006, 1, 1), "male"
    ),
    202: matching_patient(
        202, date(2005, 1, 1), "male"
    ),
    203: matching_patient(
        203, date(2004, 1, 1), "male"
    ),
    204: matching_patient(
        204, date(2003, 1, 1), "male"
    ),

    # Too old to match within +/-3 years.
    205: matching_patient(
        205, date(2002, 1, 1), "male"
    ),

    # Wrong sex.
    206: matching_patient(
        206, date(2006, 1, 1), "female"
    ),

    # Wrong practice.
    207: matching_patient(
        207,
        date(2006, 1, 1),
        "male",
        practice=200,
    ),

    # Wrong care-home status.
    208: matching_patient(
        208,
        date(2006, 1, 1),
        "male",
        care_home=True,
    ),

    # Otherwise suitable at the January snapshot, but has a hip fracture
    # before a June case date. The post-match exact-date check will remove it.
    209: matching_patient(
        209,
        date(2006, 1, 1),
        "male",
        hip_fracture_date=date(2024, 4, 1),
    ),
}
