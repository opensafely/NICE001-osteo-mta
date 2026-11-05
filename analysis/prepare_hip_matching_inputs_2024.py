from pathlib import Path

import pandas as pd


SELECTED_CASES_FILE = Path(
    "output/selected_hip_index_cases.csv"
)
ATTRIBUTES_FILE = Path(
    "output/hip_matching_attributes_2024.csv.gz"
)

CASES_OUTPUT_FILE = Path(
    "output/hip_cases_2024_matching.csv.gz"
)
CONTROLS_OUTPUT_FILE = Path(
    "output/hip_potential_controls_2024_matching.csv.gz"
)
QA_OUTPUT_FILE = Path(
    "output/hip_matching_inputs_2024_qa.csv"
)


def as_boolean(series):
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)

    return (
        series.astype("string")
        .str.upper()
        .isin(["T", "TRUE", "1"])
    )


selected_cases = pd.read_csv(SELECTED_CASES_FILE)
attributes = pd.read_csv(ATTRIBUTES_FILE)

selected_cases["index_date"] = pd.to_datetime(
    selected_cases["index_date"],
    errors="coerce",
)

cases_2024 = selected_cases.loc[
    selected_cases["index_date"].between(
        "2024-01-01",
        "2024-12-31",
    )
].copy()

cases_2024_patient_ids = set(cases_2024["patient_id"])

cases = cases_2024.merge(
    attributes[
        [
            "patient_id",
            "age",
            "sex",
            "practice",
            "care_home",
        ]
    ],
    on="patient_id",
    how="inner",
    validate="one_to_one",
)

controls = attributes.loc[
    as_boolean(attributes["no_hip_fracture_6m_anchor"])
].copy()

controls = controls.loc[
    ~controls["patient_id"].isin(cases_2024_patient_ids)
]

cases["index_date"] = cases["index_date"].dt.strftime(
    "%Y-%m-%d"
)

matching_columns = [
    "patient_id",
    "age",
    "sex",
    "practice",
    "care_home",
]

cases[
    ["patient_id", "index_date", "fracture_type"]
    + matching_columns[1:]
].to_csv(
    CASES_OUTPUT_FILE,
    index=False,
    compression="gzip",
)

controls[matching_columns].to_csv(
    CONTROLS_OUTPUT_FILE,
    index=False,
    compression="gzip",
)

qa = pd.DataFrame(
    {
        "metric": [
            "selected_hip_cases_in_2024",
            "cases_with_complete_anchor_attributes",
            "cases_missing_anchor_attributes",
            "potential_controls_at_anchor",
        ],
        "value": [
            len(cases_2024),
            len(cases),
            len(cases_2024) - len(cases),
            len(controls),
        ],
    }
)

qa.to_csv(QA_OUTPUT_FILE, index=False)