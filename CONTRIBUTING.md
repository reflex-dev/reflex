# 🚀 Reflex Contributing Guidelines

For a comprehensive guide on how to contribute to Reflex, check out our [Contributing Guide on Notion](https://www.notion.so/reflex-dev/2107ab2bc166497db951b8d742748284?v=f0eaff78fa984b5ab15d204af58907d7).

## 🏃 Running a Local Build of Reflex

Here's a quick and fun guide to running the Reflex repository locally so you can start contributing to the project.

**Prerequisites:**
- Python >= 3.8 🐍
- Poetry version >= 1.4.0 📖 (add it to your path, see [Poetry Docs](https://python-poetry.org/docs/#installation) for more info).

**1. Clone Reflex and Navigate into the Repo:**
```bash
git clone https://github.com/reflex-dev/reflex.git
cd reflex
```

**2. Install Your Local Reflex Build:**
```bash
poetry install
```

**3. Create an Examples Folder:**
* We have the `examples` folder in the `.gitignore`, so your changes in `reflex/examples` won't be reflected in your commit.
```bash
mkdir examples
cd examples
```

**4. Init and Run:**
```bash
poetry run reflex init
poetry run reflex run
```
All the changes you make to the repository will be reflected in your running app.

## 🧪 Testing and QA

In the 'test' directory of Reflex, you can add to an existing test file or create a new test Python file if it doesn't fit the current layout.

#### What to Unit Test?
- Any new feature or significant change.
- Edge cases or potential problem areas.
- Interactions between different parts of the code.

Now, Init and Run:
```bash
poetry run reflex init
poetry run reflex run
```

All the changes you make to the repository will be reflected in your running app.
* We have the examples folder in the .gitignore, so your changes in reflex/examples won't be reflected in your commit.

## 🧪 Testing and QA

Any feature or significant change added should be accompanied by unit tests.

Within the 'test' directory of Reflex, you can add to an existing test file or create a new test Python file if it doesn't fit the current layout.

What to unit test?
- Any feature or significant change that has been added.
- Any edge cases or potential problem areas.
- Any interactions between different parts of the code.

## ✅ Making a PR

Once you've solved a current issue or made an improvement to Reflex, you can make a pull request (PR), and we'll review the changes.

Before submitting a PR, make sure the following steps are taken and tests are passing.

In your `reflex` directory, ensure all unit tests are still passing using the following command. This will fail if code coverage is below 80%.
```bash
poetry run pytest tests --cov --no-cov-on-fail --cov-report=
```

Next, make sure all the following tests pass. This ensures that every new change has proper documentation and type checking.
```bash
poetry run ruff check .
poetry run pyright reflex tests
find reflex tests -name "*.py" -not -path reflex/reflex.py | xargs poetry run darglint
```

Finally, run `black` to format your code.
```bash
poetry run black reflex tests
```

Consider installing git pre-commit hooks so Ruff, Pyright, Darglint, and Black will run automatically before each commit. Note that pre-commit will only be installed when you use a Python version >= 3.8.
```bash
pre-commit install
```

## That's it !, you can submit your PR now!! 🔥✨
# Thanks a lot for contributing to Reflex! 🚀⭐