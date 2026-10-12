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
            "number_of_candidate_hip_admission_records": 1,
            "number_of_hip_gp_events": 1,
            "candidate_hip_date_1": date(2024, 6, 1),
            "candidate_hip_prior_hospital_count_6m_1": 0,
            "candidate_hip_prior_gp_count_6m_1": 1,
            "candidate_hip_has_prior_fracture_6m_1": True,
            "candidate_hip_passes_6m_rule_1": False,
            "candidate_hip_date_2": None,
            "candidate_hip_passes_6m_rule_2": False,
            "has_more_than_10_candidate_hip_dates": False,
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
            "number_of_candidate_hip_admission_records": 1,
            "number_of_hip_gp_events": 2,
            "candidate_hip_date_1": date(2024, 6, 1),
            "candidate_hip_prior_hospital_count_6m_1": 0,
            "candidate_hip_prior_gp_count_6m_1": 0,
            "candidate_hip_has_prior_fracture_6m_1": False,
            "candidate_hip_passes_6m_rule_1": True,
            "candidate_hip_date_2": None,
            "candidate_hip_passes_6m_rule_2": False,
            "has_more_than_10_candidate_hip_dates": False,
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
            "number_of_candidate_hip_admission_records": 1,
            "number_of_hip_gp_events": 0,
            "candidate_hip_date_1": date(2022, 1, 15),
            "candidate_hip_prior_hospital_count_6m_1": 1,
            "candidate_hip_prior_gp_count_6m_1": 0,
            "candidate_hip_has_prior_fracture_6m_1": True,
            "candidate_hip_passes_6m_rule_1": False,
            "candidate_hip_date_2": None,
            "candidate_hip_passes_6m_rule_2": False,
            "has_more_than_10_candidate_hip_dates": False,
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
            "number_of_candidate_hip_admission_records": 2,
            "number_of_hip_gp_events": 1,
            "candidate_hip_date_1": date(2023, 12, 1),
            "candidate_hip_prior_hospital_count_6m_1": 0,
            "candidate_hip_prior_gp_count_6m_1": 1,
            "candidate_hip_has_prior_fracture_6m_1": True,
            "candidate_hip_passes_6m_rule_1": False,
            "candidate_hip_date_2": date(2024, 8, 15),
            "candidate_hip_prior_hospital_count_6m_2": 0,
            "candidate_hip_prior_gp_count_6m_2": 0,
            "candidate_hip_has_prior_fracture_6m_2": False,
            "candidate_hip_passes_6m_rule_2": True,
            "candidate_hip_date_3": None,
            "candidate_hip_passes_6m_rule_3": False,
            "has_more_than_10_candidate_hip_dates": False,
        },
    },

    # Multiple APCS records on the same admission date should produce one
    # candidate date. A hip code in a secondary diagnosis position should
    # also be identified.
    5: {
        "apcs": [
            {
                "apcs_ident": 7,
                "admission_date": date(2024, 6, 1),
                "all_diagnoses": "||K219,S720",
            },
            {
                "apcs_ident": 8,
                "admission_date": date(2024, 6, 1),
                "all_diagnoses": "||S720",
            },
            {
                "apcs_ident": 9,
                "admission_date": date(2025, 1, 1),
                "all_diagnoses": "||S721",
            },
        ],
        "clinical_events": [],
        "expected_in_population": True,
        "expected_columns": {
            "number_of_candidate_hip_admission_records": 3,
            "number_of_hip_gp_events": 0,
            "candidate_hip_date_1": date(2024, 6, 1),
            "candidate_hip_prior_hospital_count_6m_1": 0,
            "candidate_hip_prior_gp_count_6m_1": 0,
            "candidate_hip_has_prior_fracture_6m_1": False,
            "candidate_hip_passes_6m_rule_1": True,
            "candidate_hip_date_2": date(2025, 1, 1),
            "candidate_hip_prior_hospital_count_6m_2": 0,
            "candidate_hip_prior_gp_count_6m_2": 0,
            "candidate_hip_has_prior_fracture_6m_2": False,
            "candidate_hip_passes_6m_rule_2": True,
            "candidate_hip_date_3": None,
            "candidate_hip_passes_6m_rule_3": False,
            "has_more_than_10_candidate_hip_dates": False,
        },
    },

    # A hospital hip-fracture record exactly six months before the next
    # candidate is included in the lookback, so the later candidate fails.
    6: {
        "apcs": [
            {
                "apcs_ident": 10,
                "admission_date": date(2024, 1, 1),
                "all_diagnoses": "||S720",
            },
            {
                "apcs_ident": 11,
                "admission_date": date(2024, 7, 1),
                "all_diagnoses": "||S721",
            },
        ],
        "clinical_events": [],
        "expected_in_population": True,
        "expected_columns": {
            "number_of_candidate_hip_admission_records": 2,
            "number_of_hip_gp_events": 0,
            "candidate_hip_date_1": date(2024, 1, 1),
            "candidate_hip_prior_hospital_count_6m_1": 0,
            "candidate_hip_has_prior_fracture_6m_1": False,
            "candidate_hip_passes_6m_rule_1": True,
            "candidate_hip_date_2": date(2024, 7, 1),
            "candidate_hip_prior_hospital_count_6m_2": 1,
            "candidate_hip_prior_gp_count_6m_2": 0,
            "candidate_hip_has_prior_fracture_6m_2": True,
            "candidate_hip_passes_6m_rule_2": False,
            "candidate_hip_date_3": None,
            "candidate_hip_passes_6m_rule_3": False,
            "has_more_than_10_candidate_hip_dates": False,
        },
    },

    # Eleven distinct candidate dates should populate the first ten date
    # columns and set the overflow flag.
    7: {
        "apcs": [
            {
                "apcs_ident": 12,
                "admission_date": date(2022, 1, 1),
                "all_diagnoses": "||S720",
            },
            {
                "apcs_ident": 13,
                "admission_date": date(2022, 2, 1),
                "all_diagnoses": "||S720",
            },
            {
                "apcs_ident": 14,
                "admission_date": date(2022, 3, 1),
                "all_diagnoses": "||S720",
            },
            {
                "apcs_ident": 15,
                "admission_date": date(2022, 4, 1),
                "all_diagnoses": "||S720",
            },
            {
                "apcs_ident": 16,
                "admission_date": date(2022, 5, 1),
                "all_diagnoses": "||S720",
            },
            {
                "apcs_ident": 17,
                "admission_date": date(2022, 6, 1),
                "all_diagnoses": "||S720",
            },
            {
                "apcs_ident": 18,
                "admission_date": date(2022, 7, 1),
                "all_diagnoses": "||S720",
            },
            {
                "apcs_ident": 19,
                "admission_date": date(2022, 8, 1),
                "all_diagnoses": "||S720",
            },
            {
                "apcs_ident": 20,
                "admission_date": date(2022, 9, 1),
                "all_diagnoses": "||S720",
            },
            {
                "apcs_ident": 21,
                "admission_date": date(2022, 10, 1),
                "all_diagnoses": "||S720",
            },
            {
                "apcs_ident": 22,
                "admission_date": date(2022, 11, 1),
                "all_diagnoses": "||S720",
            },
        ],
        "clinical_events": [],
        "expected_in_population": True,
        "expected_columns": {
            "number_of_candidate_hip_admission_records": 11,
            "number_of_hip_gp_events": 0,
            "candidate_hip_date_1": date(2022, 1, 1),
            "candidate_hip_date_10": date(2022, 10, 1),
            "has_more_than_10_candidate_hip_dates": True,
        },
    },

}