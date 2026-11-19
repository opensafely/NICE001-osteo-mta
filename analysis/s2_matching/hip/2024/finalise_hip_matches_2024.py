# Finalise cases and controls

# - Keep only matches that meet all the matching and eligibility criteria on their index date
#   as controls
# - Drop cases that don't have any matches that meet all the criteria

# Criteria for controls:
# - Same sex as case
# AND on the index date: 
# - Aged 18 or over and age +/- 3 years from case
# - Same practice ID as case
# - Same care home status as case
# - Has a practice registration that covers at least the 6 months prior
# - No hip fracture in GP records or hospital admissions
# - No hip fracture in GP records or hospital admissions in the 6 months prior


from pathlib import Path

import pandas as pd

# Specify paths for input files
MATCHED_CASES_FILE = Path(
    "output/matched_cases_hip_2024.arrow"
)
MATCHED_CONTROLS_FILE = Path(
    "output/matched_matches_hip_2024.arrow"
)
EXACT_ATTRIBUTES_FILE = Path(
    "output/hip_matched_control_attributes_2024.csv.gz"
)

# Specify paths for output files
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

# Create function to ensure boolean columns defined properly
def as_boolean(series):
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)

    return (
        series.astype("string")
        .str.upper()
        .isin(["T", "TRUE", "1"])
    )

# Create function to convert to integer
def as_integer(series):
    return pd.to_numeric(
        series,
        errors="coerce",
    ).astype("Int64")

# Create function to convert to string, remove leading and trailing characters
# and convert to lower case
def as_text(series):
    return (
        series.astype("string")
        .str.strip() 
        .str.lower()
    )

# Read in cases and preliminary controls output from matching action
cases = pd.read_feather(MATCHED_CASES_FILE)
controls = pd.read_feather(MATCHED_CONTROLS_FILE)

# Read table with preliminary controls with their variables on their index date
exact = pd.read_csv(EXACT_ATTRIBUTES_FILE)

# Convert patient ID and set ID in all three tables to integer
for frame in (cases, controls, exact):
    frame["patient_id"] = as_integer(frame["patient_id"])
    frame["set_id"] = as_integer(frame["set_id"])

# Convert index date in all three tables to datetime
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

# Rename index date in exact table
exact = exact.rename(
    columns={"index_date": "exact_index_date"}
)

# Join matching action output controls table with table with controls and their updated variables
controls = controls.merge(
    exact,
    on=["patient_id", "set_id"],
    how="left",
    validate="one_to_one",
)

# Get cases, with their matching variables
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

# Join cases to controls
controls = controls.merge(
    case_attributes,
    on="set_id",
    how="left",
    validate="many_to_one",
)

# Set age and practice ID to integer for both cases and controls
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

# Check that index date for control from matching output is equal to index date after 
# getting variables for controls on their index date with ehrql
# AND that the index date of controls is equal to the index date of cases
# If missing, make false
# (Not strictly necessary IMO)
controls["passes_index_date_check"] = (
    controls["index_date"].eq(
        controls["exact_index_date"]
    )
    & controls["index_date"].eq(
        controls["case_index_date"]
    )
).fillna(False)

# Check that controls are aged 18 or over on their index date
# AND that the age of the control on their index date is +- 3 from the age of the case 
controls["passes_age_check"] = (
    (controls["age_at_index"] >= 18)
    & (
        controls["age_at_index"]
        - controls["case_age"]
    ).abs().le(3)
).fillna(False)

# Check that the sex of the controls match their case
controls["passes_sex_check"] = as_text(
    controls["sex_at_index"]
).eq(
    as_text(controls["case_sex"])
).fillna(False)

# Check that the cases and controls have the same practice ID on their shared index date
controls["passes_practice_check"] = controls[
    "practice_at_index"
].eq(
    controls["case_practice"]
).fillna(False)

# Check that the cases and controls have the same care home status on their shared index date
controls["passes_care_home_check"] = as_text(
    controls["care_home_at_index"]
).eq(
    as_text(controls["case_care_home"])
).fillna(False)

# Make sure 6 month registration for controls at the index date is a boolean
controls["passes_registration_check"] = as_boolean(
    controls["has_6m_registration_at_index"]
)

# Make sure the indicator for not having a hip fracture on the index date and
# in the 6 months prior is a boolean
controls["passes_fracture_history_check"] = as_boolean(
    controls["no_hip_fracture_6m_index"]
)

# Specify the check columns that the controls have to pass all the criteria for
check_columns = [
    "passes_index_date_check",
    "passes_age_check",
    "passes_sex_check",
    "passes_practice_check",
    "passes_care_home_check",
    "passes_registration_check",
    "passes_fracture_history_check",
]

# Create boolean indicator for whether the control matches all the criteria
controls["passes_all_exact_date_checks"] = controls[
    check_columns
].all(axis=1)

# Keep only controls who match all the criteria for controls
eligible_controls = controls.loc[
    controls["passes_all_exact_date_checks"]
].copy()

# Count the number of controls matched to each case
final_match_counts = (
    eligible_controls
    .groupby("set_id")
    .size()
    .astype("Int64")
)

# Keep only the cases who have an eligible control
final_cases = cases.loc[
    cases["set_id"].isin(final_match_counts.index)
].copy()

# Add number of matches per case to final cases table
final_cases["match_counts"] = as_integer(
    final_cases["set_id"].map(final_match_counts)
)

# Rename columns for controls with info from the anchor date to specify anchor date
eligible_controls["anchor_age"] = eligible_controls["age"]
eligible_controls["anchor_practice"] = eligible_controls[
    "practice"
]
eligible_controls["anchor_care_home"] = eligible_controls[
    "care_home"
]

# Rename columns for controls with info on their inherited index date to be the actual
# age, sex, practice ID and care home status columns
eligible_controls["age"] = eligible_controls["age_at_index"]
eligible_controls["sex"] = eligible_controls["sex_at_index"]
eligible_controls["practice"] = eligible_controls[
    "practice_at_index"
]
eligible_controls["care_home"] = eligible_controls[
    "care_home_at_index"
]

# Specify fracture type for controls
eligible_controls["fracture_type"] = "hip"

# Add number of matches per case to final controls table
eligible_controls["match_counts"] = as_integer(
    eligible_controls["set_id"].map(final_match_counts)
)

# Create final controls table (with some circular logic)
final_controls = eligible_controls.loc[
    eligible_controls["set_id"].isin(final_cases["set_id"])
].copy()

# Specify final columns to keep for cases and controls
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

# Keep only specified columns for final cases and controls
final_cases = final_cases[final_output_columns].copy()
final_controls = final_controls[final_output_columns].copy()

# Combine final cases and controls to one table
final_combined = pd.concat(
    [final_cases, final_controls],
    ignore_index=True,
    sort=False,
)

# Sort combined table
final_combined = final_combined.sort_values(
    ["set_id", "case", "patient_id"],
    ascending=[True, False, True],
).reset_index(drop=True)

# Write final cases, final controls and combined table as arrow files
final_cases.reset_index(drop=True).to_feather(
    FINAL_CASES_FILE
)
final_controls.reset_index(drop=True).to_feather(
    FINAL_CONTROLS_FILE
)
final_combined.to_feather(FINAL_COMBINED_FILE)

# Create QA dictionary
# - Number of provisional cases from matching action
# - Number of provisional controls from matching action
# - Number of controls passing all criteria 
# - Number of controls failing each check - index date, age, sex, practice ID, care home status, 
#   at least 6 months registration, no hip fracture on index date and in prior 6 months
# - Number of final cases
# - Number of final controls
# - Number of cases dropped as they had no controls passing all criteria
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

# More QA checks
# - Number of cases with 1 to 5 number of controls
for number_of_controls in range(1, 5):
    qa_metrics[
        f"cases_with_{number_of_controls}_final_controls"
    ] = (final_match_counts == number_of_controls).sum()

# Make QA dictionary into table
qa = pd.DataFrame(
    {
        "metric": qa_metrics.keys(),
        "value": qa_metrics.values(),
    }
)

# Write
qa.to_csv(QA_FILE, index=False)
