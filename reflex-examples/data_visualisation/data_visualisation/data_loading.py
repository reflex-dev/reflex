import csv
import pandas as pd
import json

import reflex as rx


def add_csv_data_to_db(data_file_path: str, model: rx.Model):
    with open(data_file_path, mode="r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(
            file
        )  # This automatically uses the first row as header names

        with rx.session() as session:
            for row in reader:
                # Create an instance of Model using dictionary unpacking
                item = model(**row)
                session.add(item)
            session.commit()


def add_pandas_data_to_db(df: pd.DataFrame, model: rx.Model):
    with rx.session() as session:
        for index, row in df.iterrows():
            data_tuple = row.to_dict()
            # Create an instance of Model using dictionary unpacking
            item = model(**data_tuple)
            session.add(item)
        session.commit()


def loading_data(data_file_path: str, model: rx.Model):
    try:
        if data_file_path.endswith(".csv"):
            # Open your CSV file
            add_csv_data_to_db(data_file_path, model)

        if data_file_path.endswith(".xlsx"):
            # Open your excel file
            df = pd.read_excel(data_file_path)
            add_pandas_data_to_db(df, model)

        if data_file_path.endswith(".json"):
            # Open your json file
            with open(data_file_path, "r") as file:
                data = json.load(file)
                df = pd.DataFrame(data)
                add_pandas_data_to_db(df, model)

    except Exception as e:
        print(
            f"An error occurred! You might have the wrong datafile for your Model. Here is the error: {e}"
        )
