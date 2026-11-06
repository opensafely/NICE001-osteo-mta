from pathlib import Path

import pandas as pd


MATCHED_CASES_FILE = Path(
    "output/matched_cases_hip_2024.arrow"
)
MATCHED_CONTROLS_FILE = Path(
    "output/matched_matches_hip_2024.arrow"
)
EXACT_ATTRIBUTES_FILE = Path(
    "output/hip_matched_control_attributes_2024.csv.gz"
)

FINAL_CASES_FILE = Path(
    "output/final_matched_cases_hip_2024.arrow"
)
FINAL_CONTROLS_FILE = Path(
    "output/final_matched_controls_hip_2024.arrow"
)
FINAL_COMBINED_FILE = Path(
    "output/final_matched_combined_hip_2024.arrow"
)
QA_FILE = Path(
    "output/final_hip_matching_2024_qa.csv"
)


def as_boolean(series):
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)

    return (
        series.astype("string")
        .str.upper()
        .isin(["T", "TRUE", "1"])
    )


def as_integer(series):
    return pd.to_numeric(
        series,
        errors="coerce",
    ).astype("Int64")


def as_text(series):
    return (
        series.astype("string")
        .str.strip()
        .str.lower()
    )


cases = pd.read_feather(MATCHED_CASES_FILE)
controls = pd.read_feather(MATCHED_CONTROLS_FILE)
exact = pd.read_csv(EXACT_ATTRIBUTES_FILE)

for frame in (cases, controls, exact):
    frame["patient_id"] = as_integer(frame["patient_id"])
    frame["set_id"] = as_integer(frame["set_id"])

cases["index_date"] = pd.to_datetime(
    cases["index_date"],
    errors="coerce",
)
controls["index_date"] = pd.to_datetime(
    controls["index_date"],
    errors="coerce",
)
exact["index_date"] = pd.to_datetime(
    exact["index_date"],
    errors="coerce",
)

exact = exact.rename(
    columns={"index_date": "exact_index_date"}
)

controls = controls.merge(
    exact,
    on=["patient_id", "set_id"],
    how="left",
    validate="one_to_one",
)

case_attributes = cases[
    [
        "set_id",
        "index_date",
        "age",
        "sex",
        "practice",
        "care_home",
    ]
].rename(
    columns={
        "index_date": "case_index_date",
        "age": "case_age",
        "sex": "case_sex",
        "practice": "case_practice",
        "care_home": "case_care_home",
    }
)

controls = controls.merge(
    case_attributes,
    on="set_id",
    how="left",
    validate="many_to_one",
)

controls["age_at_index"] = as_integer(
    controls["age_at_index"]
)
controls["case_age"] = as_integer(controls["case_age"])
controls["practice_at_index"] = as_integer(
    controls["practice_at_index"]
)
controls["case_practice"] = as_integer(
    controls["case_practice"]
)

controls["passes_index_date_check"] = (
    controls["index_date"].eq(
        controls["exact_index_date"]
    )
    & controls["index_date"].eq(
        controls["case_index_date"]
    )
).fillna(False)

controls["passes_age_check"] = (
    (controls["age_at_index"] >= 18)
    & (
        controls["age_at_index"]
        - controls["case_age"]
    ).abs().le(3)
).fillna(False)

controls["passes_sex_check"] = as_text(
    controls["sex_at_index"]
).eq(
    as_text(controls["case_sex"])
).fillna(False)

controls["passes_practice_check"] = controls[
    "practice_at_index"
].eq(
    controls["case_practice"]
).fillna(False)

controls["passes_care_home_check"] = as_text(
    controls["care_home_at_index"]
).eq(
    as_text(controls["case_care_home"])
).fillna(False)

controls["passes_registration_check"] = as_boolean(
    controls["has_6m_registration_at_index"]
)

controls["passes_fracture_history_check"] = as_boolean(
    controls["no_hip_fracture_6m_index"]
)

check_columns = [
    "passes_index_date_check",
    "passes_age_check",
    "passes_sex_check",
    "passes_practice_check",
    "passes_care_home_check",
    "passes_registration_check",
    "passes_fracture_history_check",
]

controls["passes_all_exact_date_checks"] = controls[
    check_columns
].all(axis=1)

eligible_controls = controls.loc[
    controls["passes_all_exact_date_checks"]
].copy()

final_match_counts = (
    eligible_controls
    .groupby("set_id")
    .size()
    .astype("Int64")
)

final_cases = cases.loc[
    cases["set_id"].isin(final_match_counts.index)
].copy()

final_cases["match_counts"] = as_integer(
    final_cases["set_id"].map(final_match_counts)
)

eligible_controls["anchor_age"] = eligible_controls["age"]
eligible_controls["anchor_practice"] = eligible_controls[
    "practice"
]
eligible_controls["anchor_care_home"] = eligible_controls[
    "care_home"
]

eligible_controls["age"] = eligible_controls["age_at_index"]
eligible_controls["sex"] = eligible_controls["sex_at_index"]
eligible_controls["practice"] = eligible_controls[
    "practice_at_index"
]
eligible_controls["care_home"] = eligible_controls[
    "care_home_at_index"
]
eligible_controls["fracture_type"] = "hip"
eligible_controls["match_counts"] = as_integer(
    eligible_controls["set_id"].map(final_match_counts)
)

final_controls = eligible_controls.loc[
    eligible_controls["set_id"].isin(final_cases["set_id"])
].copy()

final_output_columns = [
    "patient_id",
    "index_date",
    "fracture_type",
    "age",
    "sex",
    "practice",
    "care_home",
    "set_id",
    "case",
    "match_counts",
]

final_cases = final_cases[final_output_columns].copy()
final_controls = final_controls[final_output_columns].copy()

final_combined = pd.concat(
    [final_cases, final_controls],
    ignore_index=True,
    sort=False,
)

final_combined = final_combined.sort_values(
    ["set_id", "case", "patient_id"],
    ascending=[True, False, True],
).reset_index(drop=True)

final_cases.reset_index(drop=True).to_feather(
    FINAL_CASES_FILE
)
final_controls.reset_index(drop=True).to_feather(
    FINAL_CONTROLS_FILE
)
final_combined.to_feather(FINAL_COMBINED_FILE)

qa_metrics = {
    "provisional_matched_cases": len(cases),
    "provisional_matched_controls": len(controls),
    "controls_passing_all_exact_date_checks": len(
        eligible_controls
    ),
    "controls_failing_index_date_check": (
        ~controls["passes_index_date_check"]
    ).sum(),
    "controls_failing_age_check": (
        ~controls["passes_age_check"]
    ).sum(),
    "controls_failing_sex_check": (
        ~controls["passes_sex_check"]
    ).sum(),
    "controls_failing_practice_check": (
        ~controls["passes_practice_check"]
    ).sum(),
    "controls_failing_care_home_check": (
        ~controls["passes_care_home_check"]
    ).sum(),
    "controls_failing_registration_check": (
        ~controls["passes_registration_check"]
    ).sum(),
    "controls_failing_fracture_history_check": (
        ~controls["passes_fracture_history_check"]
    ).sum(),
    "final_matched_cases": len(final_cases),
    "final_matched_controls": len(final_controls),
    "cases_losing_all_controls": len(cases) - len(final_cases),
}

for number_of_controls in range(1, 5):
    qa_metrics[
        f"cases_with_{number_of_controls}_final_controls"
    ] = (final_match_counts == number_of_controls).sum()

qa = pd.DataFrame(
    {
        "metric": qa_metrics.keys(),
        "value": qa_metrics.values(),
    }
)

qa.to_csv(QA_FILE, index=False)
