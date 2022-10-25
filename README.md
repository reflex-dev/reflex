<div align="center">

<img src="logo.png" alt="drawing" width = 450/>

**The easiest way to build and deploy web apps.**

[![PyPI version](https://badge.fury.io/py/pynecone-io.svg)](https://badge.fury.io/py/pynecone-io)
![versions](https://img.shields.io/pypi/pyversions/pynecone-io.svg)
[![License](https://img.shields.io/badge/License-Apache_2.0-yellowgreen.svg)](https://opensource.org/licenses/Apache-2.0)  


<div align="left">

## Getting Started

Pynecone is a full-stack python framework that makes it easy to build and deploy web apps in minutes.

All the information for getting started can be found in this README, however, a more detailed explanation of the following topics can be found on our website:

<div align="center">

### [Introduction](https://pyneconetest1261-pynetree.pynecone.app/docs/getting-started/introduction) | [Component Library](https://pyneconetest1261-pynetree.pynecone.app/docs/library) | [Examples](https://pyneconetest1261-pynetree.pynecone.app) | [Deployment](https://pyneconetest1261-pynetree.pynecone.app/docs/hosting/deploy) 

<div align="left">

## Installation
Pynecone requires to following to get started:
* Python 3.7+
* [NodeJS 12.22.0+](https://nodejs.org/en/)

```
$ pip install pynecone-io
```

## Create your first Pynecone app

Installing Pynecone also installs the pc command line tool. Test that the install was successful by creating a new project. 

Replace my_app_name with your project name:

```
$ mkdir my_app_name
$ cd my_app_name
$ pc init
```

This initializes a template app in your new directory.
You can run this app in development mode:
```
$ pc run
```


You should see your app running at http://localhost:3000.


Note that the port may be different if you have another app running on port 3000.


Now you can modify the source code in my_app_name/my_app_name.py. Pynecone has fast refreshes so you can see your changes instantly when you save your code.

## Example App

Let's go over a simple counter app to explore the basics of Pynecone.

<div align="center">
<img src="Counter.gif" alt="drawing" width="550"/>
<div align="left">

Here is the complete code to create this.

```python
import pynecone as pc


class State(pc.State):
    count: int = 0

    def increment(self):
        self.count += 1

    def decrement(self):
        self.count -= 1


def index():
    return pc.hstack(
        pc.button(
            "Decrement",
            color_scheme="red",
            border_radius="1em",
            on_click=State.decrement,
        ),
        pc.heading(State.count, font_size="2em"),
        pc.button(
            "Increment",
            color_scheme="green",
            border_radius="1em",
            on_click=State.increment,
        ),
    )


app = pc.App(state=State)
app.add_page(index)
app.compile()
```
Let's break this down.

* ### State
    
``` python
class State(pc.State):
    count: int = 0 
```
The state defines all the variables (called vars) in an app that can change, as well as the functions that change them.
Here our state has by a single var, count, which holds the current value of the counter.
The frontend of the app is a reflection of the current state.

    
* ### Event Handlers
```python
def increment(self):
    self.count += 1

def decrement(self):
    self.count -= 1   
```
Within the state, we define functions, called event handlers, that change the state vars.
Event handlers are the only way that we can modify the state in Pynecone. They can be called in response to user actions, such as clicking a button or typing in a text box. These actions are called events.
Our counter app has two event handlers, increment and decrement.
    
* ### Frontend

```python 
def index():
    return pc.hstack(
        pc.button(
            "Decrement",
            color_scheme="red",
            border_radius="1em",
            on_click=State.decrement,
        ),
        pc.heading(State.count, font_size="2em"),
        pc.button(
            "Increment",
            color_scheme="green",
            border_radius="1em",
            on_click=State.increment,
        ),
    )
```
This function defines the frontend of the app.
We use different components such as pc.box, pc.button, and pc.heading to build the frontend. Components can be nested to create complex layouts, and can be styled using the full power of CSS.
    
Pynecone comes with [50+ built-in components](https://pynecone.io/docs/library) to help you get started. 
We are actively adding more components, plus it's easy to create your own components.

* ### Routing 
    
Next we define our app and tell it what state to use.
```python
app = pc.App(state=State)
```
We add a route from the root of the app to the counter component. By default the route
```python
app.add_page('\', index)
```
You can create a multi-page app by adding more routes.
    
## Contributing

## More Information 
  
## License

Pynecone is open-source and licensed under the [Apache License 2.0](LICENSE)
