from datetime import date

from dataset_definition_prox_humerus import dataset


def patient(date_of_birth):
    return {
        "date_of_birth": date_of_birth,
    }


def registration(start_date):
    return [
        {
            "start_date": start_date,
            "end_date": None,
            "practice_pseudo_id": 100,
        },
    ]


test_data = {
    # Hospital-only eligible prox_humerus fracture.
    1: {
        "patients": patient(date(1980, 1, 1)),
        "practice_registrations": registration(date(2010, 1, 1)),
        "apcs": [
            {
                "apcs_ident": 101,
                "admission_date": date(2024, 6, 1),
                "all_diagnoses": "||S422",
            },
        ],
        "clinical_events": [],
        "expected_in_population": True,
        "expected_columns": {
            "number_of_candidate_prox_humerus_admission_records": 1,
            "number_of_candidate_prox_humerus_gp_records": 0,
            "candidate_prox_humerus_hospital_1_date": date(2024, 6, 1),
            "candidate_prox_humerus_hospital_1_is_eligible_index": True,
            "candidate_prox_humerus_gp_1_date": None,
            "candidate_prox_humerus_gp_1_is_eligible_index": False,
            "has_more_than_15_candidate_prox_humerus_hospital_dates": False,
            "has_more_than_15_candidate_prox_humerus_gp_dates": False,
        },
    },

    # GP-only eligible prox_humerus fracture.
    2: {
        "patients": patient(date(1975, 1, 1)),
        "practice_registrations": registration(date(2010, 1, 1)),
        "apcs": [],
        "clinical_events": [
            {
                "date": date(2024, 7, 1),
                "snomedct_code": "127286005",
            },
        ],
        "expected_in_population": True,
        "expected_columns": {
            "number_of_candidate_prox_humerus_admission_records": 0,
            "number_of_candidate_prox_humerus_gp_records": 1,
            "candidate_prox_humerus_gp_1_date": date(2024, 7, 1),
            "candidate_prox_humerus_gp_1_is_eligible_index": True,
            "has_more_than_15_candidate_prox_humerus_hospital_dates": False,
            "has_more_than_15_candidate_prox_humerus_gp_dates": False,
        },
    },

    # Multiple hospital and GP records on the same date represent one
    # candidate date from both sources.
    3: {
        "patients": patient(date(1960, 1, 1)),
        "practice_registrations": registration(date(2010, 1, 1)),
        "apcs": [
            {
                "apcs_ident": 301,
                "admission_date": date(2024, 8, 15),
                "all_diagnoses": "||S422",
            },
            {
                "apcs_ident": 302,
                "admission_date": date(2024, 8, 15),
                "all_diagnoses": "||S422",
            },
        ],
        "clinical_events": [
            {
                "date": date(2024, 8, 15),
                "snomedct_code": "127286005",
            },
            {
                "date": date(2024, 8, 15),
                "snomedct_code": "208239001",
            },
        ],
        "expected_in_population": True,
        "expected_columns": {
            "number_of_candidate_prox_humerus_admission_records": 2,
            "number_of_candidate_prox_humerus_gp_records": 2,
            "candidate_prox_humerus_hospital_1_date": date(2024, 8, 15),
            "candidate_prox_humerus_hospital_1_is_eligible_index": True,
            "candidate_prox_humerus_hospital_2_date": None,
            "candidate_prox_humerus_gp_1_date": date(2024, 8, 15),
            "candidate_prox_humerus_gp_1_is_eligible_index": True,
            "candidate_prox_humerus_gp_2_date": None,
        },
    },

    # The January GP fracture makes the April hospital candidate ineligible.
    4: {
        "patients": patient(date(1990, 1, 1)),
        "practice_registrations": registration(date(2010, 1, 1)),
        "apcs": [
            {
                "apcs_ident": 401,
                "admission_date": date(2024, 4, 1),
                "all_diagnoses": "||S422",
            },
        ],
        "clinical_events": [
            {
                "date": date(2024, 1, 1),
                "snomedct_code": "127286005",
            },
        ],
        "expected_in_population": True,
        "expected_columns": {
            "candidate_prox_humerus_gp_1_date": date(2024, 1, 1),
            "candidate_prox_humerus_gp_1_is_eligible_index": True,
            "candidate_prox_humerus_hospital_1_date": date(2024, 4, 1),
            "candidate_prox_humerus_hospital_1_prior_gp_count_6m": 1,
            "candidate_prox_humerus_hospital_1_has_prior_fracture_6m": True,
            "candidate_prox_humerus_hospital_1_passes_6m_rule": False,
            "candidate_prox_humerus_hospital_1_is_eligible_index": False,
        },
    },

    # Under 18 at the candidate date.
    5: {
        "patients": patient(date(2007, 1, 1)),
        "practice_registrations": registration(date(2010, 1, 1)),
        "apcs": [
            {
                "apcs_ident": 501,
                "admission_date": date(2024, 6, 1),
                "all_diagnoses": "||S422",
            },
        ],
        "clinical_events": [],
        "expected_in_population": True,
        "expected_columns": {
            "candidate_prox_humerus_hospital_1_age": 17,
            "candidate_prox_humerus_hospital_1_age_eligible": False,
            "candidate_prox_humerus_hospital_1_has_6m_registration": True,
            "candidate_prox_humerus_hospital_1_passes_6m_rule": True,
            "candidate_prox_humerus_hospital_1_is_eligible_index": False,
        },
    },

    # Less than six months of registration.
    6: {
        "patients": patient(date(1980, 1, 1)),
        "practice_registrations": registration(date(2024, 1, 1)),
        "apcs": [
            {
                "apcs_ident": 601,
                "admission_date": date(2024, 6, 1),
                "all_diagnoses": "||S422",
            },
        ],
        "clinical_events": [],
        "expected_in_population": True,
        "expected_columns": {
            "candidate_prox_humerus_hospital_1_age_eligible": True,
            "candidate_prox_humerus_hospital_1_has_6m_registration": False,
            "candidate_prox_humerus_hospital_1_passes_6m_rule": True,
            "candidate_prox_humerus_hospital_1_is_eligible_index": False,
        },
    },

    # Exactly 18 with exactly six months of registration.
    7: {
        "patients": patient(date(2006, 6, 1)),
        "practice_registrations": registration(date(2023, 12, 1)),
        "apcs": [],
        "clinical_events": [
            {
                "date": date(2024, 6, 1),
                "snomedct_code": "127286005",
            },
        ],
        "expected_in_population": True,
        "expected_columns": {
            "candidate_prox_humerus_gp_1_age": 18,
            "candidate_prox_humerus_gp_1_age_eligible": True,
            "candidate_prox_humerus_gp_1_has_6m_registration": True,
            "candidate_prox_humerus_gp_1_passes_6m_rule": True,
            "candidate_prox_humerus_gp_1_is_eligible_index": True,
        },
    },

    # Sixteen unique hospital candidate dates trigger hospital overflow.
    8: {
        "patients": patient(date(1980, 1, 1)),
        "practice_registrations": registration(date(2010, 1, 1)),
        "apcs": [
            {
                "apcs_ident": 800 + candidate_number,
                "admission_date": date(
                    2022 + candidate_number // 12,
                    candidate_number % 12 + 1,
                    1,
                ),
                "all_diagnoses": "||S422",
            }
            for candidate_number in range(16)
        ],
        "clinical_events": [],
        "expected_in_population": True,
        "expected_columns": {
            "number_of_candidate_prox_humerus_admission_records": 16,
            "candidate_prox_humerus_hospital_1_date": date(2022, 1, 1),
            "candidate_prox_humerus_hospital_15_date": date(2023, 3, 1),
            "has_more_than_15_candidate_prox_humerus_hospital_dates": True,
            "has_more_than_15_candidate_prox_humerus_gp_dates": False,
        },
    },

    # Sixteen unique GP candidate dates trigger GP overflow.
    9: {
        "patients": patient(date(1980, 1, 1)),
        "practice_registrations": registration(date(2010, 1, 1)),
        "apcs": [],
        "clinical_events": [
            {
                "date": date(
                    2022 + candidate_number // 12,
                    candidate_number % 12 + 1,
                    1,
                ),
                "snomedct_code": "127286005",
            }
            for candidate_number in range(16)
        ],
        "expected_in_population": True,
        "expected_columns": {
            "number_of_candidate_prox_humerus_gp_records": 16,
            "candidate_prox_humerus_gp_1_date": date(2022, 1, 1),
            "candidate_prox_humerus_gp_15_date": date(2023, 3, 1),
            "has_more_than_15_candidate_prox_humerus_hospital_dates": False,
            "has_more_than_15_candidate_prox_humerus_gp_dates": True,
        },
    },

    # Unrelated records do not place the patient in the prox_humerus population.
    10: {
        "patients": patient(date(1980, 1, 1)),
        "practice_registrations": registration(date(2010, 1, 1)),
        "apcs": [
            {
                "apcs_ident": 1001,
                "admission_date": date(2024, 6, 1),
                "all_diagnoses": "||K219",
            },
        ],
        "clinical_events": [
            {
                "date": date(2024, 6, 1),
                "snomedct_code": "5913000",
            },
        ],
        "expected_in_population": False,
    },
}