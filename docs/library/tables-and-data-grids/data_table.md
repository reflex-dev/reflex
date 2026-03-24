---
components:
    - rx.data_table
---

```python exec
import reflex as rx
from pcweb.pages.docs import library
```

# Data Table

The data table component is a great way to display static data in a table format.
You can pass in a pandas dataframe to the data prop to create the table.

In this example we will read data from a csv file, convert it to a pandas dataframe and display it in a data_table.

We will also add a search, pagination, sorting to the data_table to make it more accessible.

If you want to [add, edit or remove data]({library.tables_and_data_grids.table.path}) in your app or deal with anything but static data then the [`rx.table`]({library.tables_and_data_grids.table.path}) might be a better fit for your use case.


```python demo box
rx.data_table(
    data=[
        ["Avery Bradley", "6-2", 25.0],
        ["Jae Crowder", "6-6", 25.0],
        ["John Holland", "6-5", 27.0],
        ["R.J. Hunter", "6-5", 22.0],
        ["Jonas Jerebko", "6-10", 29.0],
        ["Amir Johnson", "6-9", 29.0],
        ["Jordan Mickey", "6-8", 21.0],
        ["Kelly Olynyk", "7-0", 25.0],
        ["Terry Rozier", "6-2", 22.0],
        ["Marcus Smart", "6-4", 22.0],
    ],
    columns=["Name", "Height", "Age"],
    pagination=True,
    search=True,
    sort=True,
)
```

```python
import pandas as pd
nba_data = pd.read_csv("data/nba.csv")
...
rx.data_table(
    data = nba_data[["Name", "Height", "Age"]],
    pagination= True,
    search= True,
    sort= True,
)  
```

📊 **Dataset source:** [nba.csv](https://media.geeksforgeeks.org/wp-content/uploads/nba.csv)

The example below shows how to create a data table from from a list.

```python
class State(rx.State):
    data: List = [
        ["Lionel", "Messi", "PSG"],
        ["Christiano", "Ronaldo", "Al-Nasir"]
     ]
    columns: List[str] = ["First Name", "Last Name"]
    
def index():  
    return rx.data_table(
        data=State.data,
        columns=State.columns,
    )   
```
