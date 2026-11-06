from pathlib import Path

import pandas as pd


INPUT_FILE = Path(
    "output/final_hip_matching_2024_qa.csv"
)
OUTPUT_FILE = Path(
    "output/final_hip_matching_2024_qa_sdc.csv"
)

DISCLOSURE_CONTROL = (
    "Counts <=7 redacted; remaining counts rounded to nearest 5"
)


def disclosure_control_count(value):
    if pd.isna(value):
        raise ValueError("QA count is missing")

    value = int(value)

    if value < 0:
        raise ValueError("QA count cannot be negative")

    if value == 0:
        return "0"

    if value <= 7:
        return "[REDACTED]"

    return str(int(5 * round(value / 5)))


qa = pd.read_csv(INPUT_FILE)

if list(qa.columns) != ["metric", "value"]:
    raise ValueError(
        "Expected QA columns: metric,value"
    )

qa["value"] = qa["value"].map(
    disclosure_control_count
)
qa["disclosure_control"] = DISCLOSURE_CONTROL

qa.to_csv(OUTPUT_FILE, index=False)
