from pathlib import Path

import pandas as pd


OUTPUT = Path("output")
JULY_START = pd.Timestamp("2024-07-01")


def read_cases(period):
    cases = pd.read_csv(
        OUTPUT / f"hip_cases_{period}_matching.csv.gz",
        usecols=["patient_id", "index_date"],
        parse_dates=["index_date"],
    )
    if cases["patient_id"].duplicated().any():
        raise ValueError("A patient appears more than once in a case input")
    return cases.set_index("patient_id")["index_date"].sort_index()


def read_controls(period):
    controls = pd.read_feather(
        OUTPUT / f"final_matched_controls_hip_{period}.arrow",
        columns=["patient_id", "set_id"],
    )
    if controls["patient_id"].duplicated().any():
        raise ValueError("A patient was used as a control more than once")
    if controls["patient_id"].eq(controls["set_id"]).any():
        raise ValueError("Self-match found in final controls")
    return controls


def summarise_controls(controls, eligible_cases, comparison_cases):
    if not controls["set_id"].isin(eligible_cases.index).all():
        raise ValueError("A final control belongs to an unexpected case")

    counts = controls.groupby("set_id").size()
    if counts.gt(4).any():
        raise ValueError("A case has more than four final controls")

    counts = counts.reindex(comparison_cases.index, fill_value=0)
    return [
        int(counts.eq(0).sum()),
        int(counts.between(1, 3).sum()),
        int(counts.eq(4).sum()),
    ]


annual_cases = read_cases("2024")
first_cases = read_cases("first_half_2024")
july_cases = read_cases("july_2024")

expected_first = annual_cases.loc[annual_cases.lt(JULY_START)]
expected_july = annual_cases.loc[annual_cases.ge(JULY_START)]

if not first_cases.equals(expected_first) or not july_cases.equals(expected_july):
    raise ValueError("Annual and six-monthly case inputs differ")

annual_controls = read_controls("2024")
first_controls = read_controls("first_half_2024")
july_controls = read_controls("july_2024")

if july_controls["patient_id"].isin(first_controls["patient_id"]).any():
    raise ValueError("A final control was reused across halves")

summarise_controls(first_controls, first_cases, first_cases)

summary = pd.DataFrame(
    {
        "final_controls_per_case": ["0", "1-3", "4"],
        "annual_january_anchor": summarise_controls(
            annual_controls, annual_cases, july_cases
        ),
        "six_monthly_january_july_anchors": summarise_controls(
            july_controls, july_cases, july_cases
        ),
    }
)

for column in summary.columns[1:]:
    counts = summary[column]
    # Suppress the whole column if any category is small, to limit differencing.
    if counts.le(7).any():
        summary[column] = "[REDACTED]"
    else:
        summary[column] = (counts / 5).round().astype(int) * 5

summary.to_csv(OUTPUT / "hip_matching_anchor_comparison_2024_sdc.csv", index=False)