# Reflex Contributing Guidelines

For an extensive guide on the different ways to contribute to Reflex see our [Contributing Guide on Notion](https://www.notion.so/reflex-dev/2107ab2bc166497db951b8d742748284?v=f0eaff78fa984b5ab15d204af58907d7).



## Running a Local Build of Reflex 
Here is a quick guide on how to run Reflex repo locally so you can start contributing to the project.

**Prerequisites:**
- Python >= 3.8
- Poetry version >= 1.4.0 and add it to your path (see [Poetry Docs](https://python-poetry.org/docs/#installation) for more info).


**1. Clone Reflex and navigate into the repo:**
``` bash
git clone https://github.com/<YOUR-USERNAME>/reflex.git
cd reflex
```

**2. Install your local Reflex build:**
``` bash
poetry install
```
**3. Now create an examples folder so you can test the local Python build in this repository.**
* We have the `examples` folder in the `.gitignore`, so your changes in `reflex/examples` won't be reflected in your commit.
``` bash
mkdir examples
cd examples
```

**4. Init and Run**
``` bash
poetry run reflex init
poetry run reflex run
```

All the changes you make to the repository will be reflected in your running app.
* We have the examples folder in the .gitignore, so your changes in reflex/examples won't be reflected in your commit.

## 🧪 Testing and QA

Any feature or significant change added should be accompanied with unit tests.

Within the 'test' directory of Reflex you can add to a test file already there or create a new test python file if it doesn't fit into the existing layout.

#### What to unit test?
- Any feature or significant change that has been added.
- Any edge cases or potential problem areas.
- Any interactions between different parts of the code.


## ✅ Making a PR

Once you solve a current issue or improvement to Reflex, you can make a PR, and we will review the changes. 

Before submitting, a pull request, ensure the following steps are taken and test passing.

In your `reflex` directory run make sure all the unit tests are still passing using the following command.
This will fail if code coverage is below 70%.
``` bash
poetry run pytest tests --cov --no-cov-on-fail --cov-report= 
```
Next make sure all the following tests pass. This ensures that every new change has proper documentation and type checking.
``` bash
poetry run ruff check .
poetry run pyright reflex tests
find reflex tests -name "*.py" -not -path reflex/reflex.py | xargs poetry run darglint
```
Finally, run `black` to format your code.
``` bash
poetry run black reflex tests
```

Consider installing git pre-commit hooks so Ruff, Pyright, Darglint and Black will run automatically before each commit.
Note that pre-commit will only be installed when you use a Python version >= 3.8.
``` bash
pre-commit install
```

That's it you can now submit your PR. Thanks for contributing to Reflex!
