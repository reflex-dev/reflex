import reflex as rx
import random

class State(rx.State):
    data = [
  {
    "name": "A",
    "uv": 4000,
    "pv": 2400,
    "amt": 2400
  },
  {
    "name": "B",
    "uv": 3000,
    "pv": 1398,
    "amt": 2210
  },
  {
    "name": "C",
    "uv": 2000,
    "pv": 9800,
    "amt": 2290
  },
  {
    "name": "D",
    "uv": 2780,
    "pv": 3908,
    "amt": 2000
  },
  {
    "name": "E",
    "uv": 1890,
    "pv": 4800,
    "amt": 2181
  },
  {
    "name": "F",
    "uv": 2390,
    "pv": 3800,
    "amt": 2500
  },
  {
    "name": "G",
    "uv": 3490,
    "pv": 4300,
    "amt": 2100
  }]

    def randomize_data(self):
        for i in range(len(self.data)):
            self.data[i]["uv"] = random.randint(0, 10000)
            self.data[i]["pv"] = random.randint(0, 10000)
            self.data[i]["amt"] = random.randint(0, 10000)

    def click_print(self):
        print("Clicked!")

    def click_print_1(self):
        print("Clicked 1!")

    def click_print_2(self):
        print("Clicked 2!")

    def mouse_enter(self):
        print("Mouse entered!")
    
    def mouse_leave(self):
        print("Mouse left!")
    
    def mouse_move(self):
        print("Mouse moved!")


def bar_example():
    return rx.recharts.bar_chart(
            rx.recharts.graphing_tooltip(),
            rx.recharts.bar(
                data_key="uv",
                fill="#8884d8",
            ),
            rx.recharts.bar(
                data_key="pv",
                fill="#82ca9d",
            ),
            rx.recharts.x_axis(
                data_key="name",
            ),
            rx.recharts.y_axis(),
            
            data=State.data,
            height=400,
            width="100%",
    )

 
def index():  
    return rx.vstack(
        bar_example(),
    )


app = rx.App()
app.add_page(index)
app.compile()