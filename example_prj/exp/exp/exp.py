import reflex as rx
from typing import List



import pandas as pd

class State(rx.State):
    stbd=pd.DataFrame([ {'k1': 'v1', 'k2': 'v2', 'k3': 'v3'},
                        {'k1': 'v1', 'k2': 'v2', 'k3': 'v3'},
                        {'k1': 'v1', 'k2': 'v2', 'k3': 'v3'}])
def index():
        return rx.data_table(
        data=State.stbd,
        columns=["k3", "k2"],
        pagination=True,
        search=True,
    )
app = rx.App()
app.add_page(index,)
app.compile()


app = rx.App()
app.add_page(index)
app.compile()
