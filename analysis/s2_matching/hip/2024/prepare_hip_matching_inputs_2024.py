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

cases = cases_2024.rename(
    columns={
        "age_at_index": "age",
        "practice_at_index": "practice",
        "care_home_at_index": "care_home",
    }
)[
    [
        "patient_id",
        "index_date",
        "fracture_type",
        "age",
        "sex",
        "practice",
        "care_home",
    ]
].copy()

cases["age"] = pd.to_numeric(
    cases["age"],
    errors="coerce",
).astype("Int64")
cases["practice"] = pd.to_numeric(
    cases["practice"],
    errors="coerce",
).astype("Int64")

complete_case_attributes = cases[
    ["age", "sex", "practice", "care_home"]
].notna().all(axis=1)

cases = cases.loc[complete_case_attributes].copy()

# Keep the January pool broad. Registration and fracture eligibility are
# checked after controls inherit their matched case's exact index date.
controls = attributes.copy()

controls["age"] = pd.to_numeric(
    controls["age"],
    errors="coerce",
).astype("Int64")
controls["practice"] = pd.to_numeric(
    controls["practice"],
    errors="coerce",
).astype("Int64")

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
            "cases_with_complete_index_attributes",
            "cases_missing_index_attributes",
            "potential_controls_at_january_anchor",
            "potential_controls_with_6m_registration_at_anchor",
            "potential_controls_without_hip_fracture_6m_anchor",
        ],
        "value": [
            len(cases_2024),
            len(cases),
            len(cases_2024) - len(cases),
            len(controls),
            as_boolean(
                controls["has_6m_registration_at_anchor"]
            ).sum(),
            as_boolean(
                controls["no_hip_fracture_6m_anchor"]
            ).sum(),
        ],
    }
)

qa.to_csv(QA_OUTPUT_FILE, index=False)
