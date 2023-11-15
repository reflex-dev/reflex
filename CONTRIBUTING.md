# Nextpy Contributing Guidelines

For an extensive guide on the different ways to contribute to Nextpy see our [Contributing Guide on Notion]



## Running a Local Build of Nextpy 
Here is a quick guide on how to run Nextpy repo locally so you can start contributing to the project.

**Prerequisites:**
- Python >= 3.7
- Poetry version >= 1.4.0 and add it to your path (see [Poetry Docs](https://python-poetry.org/docs/#installation) for more info).


**1. Clone Nextpy and navigate into the repo:**
``` bash
git clone https://github.com/dot-agent/nextpy.git
cd nextpy
```

**2. Install your local Nextpy build:**
``` bash
poetry install
```
**3. Now create an examples folder so you can test the local Python build in this repository.**
* We have the `examples` folder in the `.gitignore`, so your changes in `nextpy/examples` won't be reflected in your commit.
``` bash
mkdir examples
cd examples
```

**4. Init and Run**
``` bash
poetry run nextpy init
poetry run nextpy run
```
All the changes you make to the repository will be reflected in your running app.


## 🧪 Testing and QA

Within the 'test' directory of Nextpy you can add to a test file already there or create a new test python file if it doesn't fit into the existing layout.

#### What to unit test?
- Any feature or significant change that has been added.
- Any edge cases or potential problem areas.
- Any interactions between different parts of the code.

Now Init/Run
``` bash
poetry run nextpy init
poetry run nextpy run
```

All the changes you make to the repository will be reflected in your running app.
* We have the examples folder in the .gitignore, so your changes in nextpy/examples won't be reflected in your commit.

## 🧪 Testing and QA

Any feature or significant change added should be accompanied with unit tests.

Within the 'test' directory of Nextpy you can add to a test file already there or create a new test python file if it doesn't fit into the existing layout.

What to unit test?
- Any feature or significant change that has been added.
- Any edge cases or potential problem areas.
 -Any interactions between different parts of the code.


## ✅ Making a PR

Once you solve a current issue or improvement to Nextpy, you can make a pr, and we will review the changes. 

Before submitting, a pull request, ensure the following steps are taken and test passing.

In your `nextpy` directory run make sure all the unit tests are still passing using the following command.
This will fail if code coverage is below 80%.
``` bash
poetry run pytest tests --cov --no-cov-on-fail --cov-report= 
```
Next make sure all the following tests pass. This ensures that every new change has proper documentation and type checking.
``` bash
poetry run ruff check .
poetry run pyright nextpy tests
find nextpy tests -name "*.py" -not -path nextpy/nextpy.py | xargs poetry run darglint
```
Finally, run `black` to format your code.
``` bash
poetry run black nextpy tests
```

Consider installing git pre-commit hooks so Ruff, Pyright, Darglint and Black will run automatically before each commit.
Note that pre-commit will only be installed when you use a Python version >= 3.8.
``` bash
pre-commit install
```

That's it you can now submit your pr. Thanks for contributing to Nextpy!