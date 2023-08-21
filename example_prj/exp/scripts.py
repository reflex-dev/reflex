from functools import wraps


class State:
    val = 20

    def __init__(self):
        self._init_mutable_fields()
        # self.

    def _init_mutable_fields(self):
        val = _convert_mutable_datatypes()
        print(f"val: {val}")

    def random(self):
        a = _convert_mutable_datatypes()
        print(a + 3)

    def add(self):
        v = _convert_mutable_datatypes()
        self.val += v
        print(f"self.val : {self.val}")

    def __setattr__(self, key, value):
        c = _convert_mutable_datatypes()
        print(f"c here: {c}")
        super().__setattr__(key, value)


def _convert_mutable_datatypes():
    print(" got to this line")
    return 10


def funA():
    pass


def funcB():
    pass


def cpuseconds(func):
    """This is a decorator"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        """printing this wrapper"""
        print("something here")
        resp = func(*args, **kwargs)
        return resp

    return wrapper


from contextlib import contextmanager
import os


@contextmanager
def cd(path):
    cwd = os.getcwd()
    print(f"dir now is {cwd}")
    try:
        os.chdir(path)
        print(f"changed to {os.getcwd()}")
        yield
    finally:
        os.chdir(cwd)
        print(f"finally dir is : {os.getcwd()}")


from sqlalchemy import create_engine
# class Parenta:
#     val: str
#
#     def __init__(self, **kwargs):
#         self.val = "hey there"
#
#     @classmethod
#     def __init_subclass__(cls, **kwargs):
#         super().__init_subclass__(**kwargs)
#         # breakpoint()
#
#
# class Child(Parenta):
#     my_var: str
#
#     def _reset(self):
#         pass
#
#
# class GrandChild(Child):
#     another: str
#
#     def _some(self):
#         pass


####################################################
import inspect


class Parent:
    def parent_method(self):
        pass

    def _user_method(self):
        pass


class Child(Parent):
    def __init__(self):
        pass

    def _user_method(self):
        pass

    def parent_method(self):
        pass  # Overriding the parent_method from the Parent class

    def __dunder_method(self):
        pass


def get_overridden_methods(child_cls):
    overridden_methods = []
    for name, method in inspect.getmembers(child_cls, inspect.isfunction):
        # Check if the method is overridden and not a dunder method
        if not name.startswith("__") and method.__name__ in dir(Parent) and getattr(Parent, method.__name__) != method:
            overridden_methods.append(method.__name__)
    return overridden_methods


##################################################################

import asyncio


# Function to simulate a time-consuming task
async def some_long_running_task(seconds):
    print("some long running task")
    await asyncio.sleep(seconds)
    print("some long running tasks 2")
    await asyncio.sleep(seconds)
    print("some long running tasks 3")
    await asyncio.sleep(seconds)
    return f"Task completed in {seconds} seconds"


async def another_task():
    print("another task")
    await asyncio.sleep(2)
    print("another task 2")
    await asyncio.sleep(2)
    print("another task 3")
    await asyncio.sleep(2)
    return "Here I am man"


# Asynchronous function to run the task and handle the result
async def main():
    # Start the task
    event_loop = asyncio.get_event_loop()
    task = asyncio.create_task(some_long_running_task(3))
    task2 = asyncio.create_task(another_task())
    # Do other stuff while the task is running asynchronously
    print("Doing other things...")
    event_loop.run_until_complete(task)
    event_loop.run_until_complete(task2)
    # Wait for the result
    # result = await task
    # res = await task2
    
    # print("brahhaa this as well")
    # # Print the result
    # print(result)
    # print(res)
    # print("Doing this as well")


# Run the main asynchronous function

import subprocess

fnm_executable_path = "/Users/eli/Library/Application Support/reflex/fnm/fnm"

if __name__ == "__main__":

    asyncio.run(main())
