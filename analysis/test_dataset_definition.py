from datetime import date

from dataset_definition import dataset


test_data = {
    # A GP hip-fracture event occurs two months before the candidate admission.
    1: {
        "apcs": [
            {
                "apcs_ident": 1,
                "admission_date": date(2024, 6, 1),
                "all_diagnoses": "||S720",
            },
        ],
        "clinical_events": [
            {
                "date": date(2024, 4, 1),
                "snomedct_code": "5913000",
            },
        ],
        "expected_in_population": True,
        "expected_columns": {
            "first_hip_admission_date": date(2024, 6, 1),
            "number_of_candidate_hip_admissions": 1,
            "first_hip_gp_event_date": date(2024, 4, 1),
            "number_of_hip_gp_events": 1,
            "number_of_prior_hip_admissions_6m": 0,
            "number_of_prior_hip_gp_events_6m": 1,
            "last_prior_hip_admission_date_6m": None,
            "last_prior_hip_gp_event_date_6m": date(2024, 4, 1),
            "has_prior_hip_fracture_6m": True,
        },
    },

    # One GP event is too old and the other occurs after the admission.
    2: {
        "apcs": [
            {
                "apcs_ident": 2,
                "admission_date": date(2024, 6, 1),
                "all_diagnoses": "||S720",
            },
        ],
        "clinical_events": [
            {
                "date": date(2023, 10, 1),
                "snomedct_code": "5913000",
            },
            {
                "date": date(2024, 7, 1),
                "snomedct_code": "5913000",
            },
        ],
        "expected_in_population": True,
        "expected_columns": {
            "first_hip_admission_date": date(2024, 6, 1),
            "number_of_candidate_hip_admissions": 1,
            "first_hip_gp_event_date": date(2023, 10, 1),
            "number_of_hip_gp_events": 2,
            "number_of_prior_hip_admissions_6m": 0,
            "number_of_prior_hip_gp_events_6m": 0,
            "last_prior_hip_admission_date_6m": None,
            "last_prior_hip_gp_event_date_6m": None,
            "has_prior_hip_fracture_6m": False,
        },
    },

    # The earlier hospital admission occurred during an excluded wave,
    # but it should still count in the six-month lookback.
    3: {
        "apcs": [
            {
                "apcs_ident": 3,
                "admission_date": date(2021, 10, 15),
                "all_diagnoses": "||S720",
            },
            {
                "apcs_ident": 4,
                "admission_date": date(2022, 1, 15),
                "all_diagnoses": "||S720",
            },
        ],
        "clinical_events": [],
        "expected_in_population": True,
        "expected_columns": {
            "first_hip_admission_date": date(2022, 1, 15),
            "number_of_candidate_hip_admissions": 1,
            "first_hip_gp_event_date": None,
            "number_of_hip_gp_events": 0,
            "number_of_prior_hip_admissions_6m": 1,
            "number_of_prior_hip_gp_events_6m": 0,
            "last_prior_hip_admission_date_6m": date(2021, 10, 15),
            "last_prior_hip_gp_event_date_6m": None,
            "has_prior_hip_fracture_6m": True,
        },
    },

    # The first candidate fails because of a recent GP event.
    # The second candidate occurs after a six-month fracture-free interval.
    4: {
        "apcs": [
            {
                "apcs_ident": 5,
                "admission_date": date(2023, 12, 1),
                "all_diagnoses": "||S720",
            },
            {
                "apcs_ident": 6,
                "admission_date": date(2024, 8, 15),
                "all_diagnoses": "||S720",
            },
        ],
        "clinical_events": [
            {
                "date": date(2023, 10, 1),
                "snomedct_code": "5913000",
            },
        ],
        "expected_in_population": True,
        "expected_columns": {
            "first_hip_admission_date": date(2023, 12, 1),
            "number_of_candidate_hip_admissions": 2,
            "first_hip_gp_event_date": date(2023, 10, 1),
            "number_of_hip_gp_events": 1,
            "number_of_prior_hip_admissions_6m": 0,
            "number_of_prior_hip_gp_events_6m": 1,
            "last_prior_hip_admission_date_6m": None,
            "last_prior_hip_gp_event_date_6m": date(2023, 10, 1),
            "has_prior_hip_fracture_6m": True,
            "second_hip_admission_date": date(2024, 8, 15),
            "number_of_prior_hip_admissions_6m_before_second": 0,
            "number_of_prior_hip_gp_events_6m_before_second": 0,
            "has_prior_hip_fracture_6m_before_second": False,
        },
    },
}