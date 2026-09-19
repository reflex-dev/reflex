# Data App

This app is used to showcase and edit tabular data live in an app. 

## Use the app

There are 4 custom database Models defined here `Customer`, `Cereals`, `Covid` and `Countries`. Three of these come with datasets that load data automatically into the table when the app is loaded and the last is an empty table, where the user can add data from scratch. For all of these tables the user can add, edit or delete data and this will update the data in the database itself. The data file types currently supported are `csv`, `xlsx` and `json`, but it is very easy to extend this to any data type by just writing your own `loading_data` function inside of the `data_loading.py` file. There is also in-built sorting based on any column heading. 


To use the app, set the `MODEL` parameter to the table of your choice defined in the `models.py` file. If you wish to load data set the `data_file_path` parameter.


## Add your own data file


You can add your own data by creating an `rx.Model` class in the `models.py` file. It is critical that the names of the `keys` in the model match up EXACTLY to the names of the columns in your data source. Here are some examples:

* Heading: `Name`, key must be `Name` and not `name`
* Heading: `State/UT`, this name must be changed to something that can be written in python such as `state`.
* Heading: `people count`, heading must be changed to be `people_count`

You can load other data types by defining your own `loading_data` function inside of the `data_loading.py` file.