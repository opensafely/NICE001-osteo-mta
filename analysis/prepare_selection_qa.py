from pathlib import Path

import pandas as pd


INPUT_FILE = Path("output/selected_hip_index_cases_qa.csv")
OUTPUT_FILE = Path("output/selected_hip_index_cases_qa_sdc.csv")


def disclosure_control(value):
    value = int(value)

    if value == 0:
        return "0"

    if value <= 7:
        return "[REDACTED]"

    # Round counts above 7 to the nearest 5.
    return str(5 * ((value + 2) // 5))


qa = pd.read_csv(INPUT_FILE)

qa["value"] = qa["value"].apply(disclosure_control)
qa["disclosure_control"] = (
    "Counts <=7 redacted; remaining counts rounded to nearest 5"
)

qa.to_csv(OUTPUT_FILE, index=False)