import csv

import pandas as pd

input_filename = "/Users/eli/Documents/input.csv"
output_filename = "/Users/eli/Documents/output100.csv"


def extract_fields(input_file: str, output_file: str):
    """Extract specific columns from a CSV file containing data rows and save them to another CSV file.

    Args:
        input_file: The path to the input CSV file.
        output_file: The path to the output CSV file.

    Example:
        extract_fields("input.csv", "output.csv")
    """
    columns_to_keep = [
        "Monitored Facility",
        "Length",
        "kVs",
        "TrLim",
        "Dfax",
        "Rate Base",
        "DC %Loading (No Transfer)",
    ]
    rows_to_keep = []
    columns = None

    # row containing "sending system" should be the column.
    search_value = "sending system"
    with open(input_file, "r", newline="") as infile:
        reader = csv.reader(infile)
        found_search_value = False

        for row in reader:
            if found_search_value:
                rows_to_keep.append(row)
            elif search_value in ",".join(row).lower():
                found_search_value = True
                columns = [r.strip() for r in row]
    # convert resulting rows and columns into a pandas dataframe
    df = pd.DataFrame(rows_to_keep, columns=columns)
    # save dataframe with extracted columns as csv file.
    df[columns_to_keep].to_csv(output_file, index=False)


if __name__ == "__main__":
    extract_fields(input_filename, output_filename)
