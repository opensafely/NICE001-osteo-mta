import argparse
from pathlib import Path

import pandas as pd


VALID_FRACTURE_TYPES = [
    "hip",
    "wrist",
    "vertebral",
    "prox_humerus",
]


parser = argparse.ArgumentParser()
parser.add_argument(
    "fracture_type",
    choices=VALID_FRACTURE_TYPES,
)
args = parser.parse_args()

fracture_type = args.fracture_type

input_file = Path(
    f"output/selected_{fracture_type}_index_cases_qa.csv"
)
output_file = Path(
    f"output/selected_{fracture_type}_index_cases_qa_sdc.csv"
)


def disclosure_control(value):
    value = int(value)

    if value == 0:
        return "0"

    if value <= 7:
        return "[REDACTED]"

    return str(5 * ((value + 2) // 5))


qa = pd.read_csv(input_file)

qa["value"] = qa["value"].apply(disclosure_control)
qa["disclosure_control"] = (
    "Counts <=7 redacted; remaining counts rounded to nearest 5"
)

qa.to_csv(output_file, index=False)