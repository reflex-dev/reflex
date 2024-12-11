# Reflex Contributing Guidelines

For an extensive guide on the different ways to contribute to Reflex see our [Contributing Guide on Notion](https://www.notion.so/reflex-dev/2107ab2bc166497db951b8d742748284?v=f0eaff78fa984b5ab15d204af58907d7).

## Running a Local Build of Reflex

Here is a quick guide on how to run Reflex repo locally so you can start contributing to the project.

**Prerequisites:**

- Python >= 3.9
- Poetry version >= 1.4.0 and add it to your path (see [Poetry Docs](https://python-poetry.org/docs/#installation) for more info).

**1. Fork this repository:**
Fork this repository by clicking on the `Fork` button on the top right.

**2. Clone Reflex and navigate into the repo:**

``` bash
git clone https://github.com/<YOUR-USERNAME>/reflex.git
cd reflex
```

**3. Install your local Reflex build:**

``` bash
poetry install
```

**4. Create an examples directory within the repository:**

The examples directory is used for testing your local changes. It's included in `.gitignore` so your test apps won't be committed.

``` bash
mkdir examples
cd examples
```

**5. Init and Run:**

Initialize a new Reflex app and run it in development mode:

``` bash
poetry run reflex init  # Select option 0 for blank template
poetry run reflex run  # Add --frontend-only for faster frontend-only development
```

The development server will start and your app will be available at http://localhost:3000. The server will automatically reload when you make changes to your code.

**Note:** In development mode, the server may occasionally need to be restarted when making significant changes. You can use Ctrl+C to stop the server and run it again.

To clean up your examples directory and start fresh, you can use the provided cleanup script:
```bash
poetry run python scripts/clean_examples.py
```

## 🧪 Testing and QA

Any feature or significant change added should be accompanied with unit tests.

Within the 'test' directory of Reflex you can add to a test file already there or create a new test python file if it doesn't fit into the existing layout.

#### What to unit test?

- Any feature or significant change that has been added.
- Any edge cases or potential problem areas.
- Any interactions between different parts of the code.

## ✅ Making a PR

Once you solve a current issue or improvement to Reflex, you can make a PR, and we will review the changes.

Before submitting a pull request, ensure the following steps are taken and tests are passing:

1. Run unit tests and coverage checks:
``` bash
poetry run pytest tests/units --cov --no-cov-on-fail --cov-report=
```
This will fail if code coverage is below 70%.

2. Run code quality checks:
``` bash
poetry run ruff check .
poetry run pyright reflex tests
find reflex tests -name "*.py" -not -path reflex/reflex.py | xargs poetry run darglint
```

3. Format your code:
``` bash
poetry run ruff format .
```

4. Install and run pre-commit hooks:
Consider installing git pre-commit hooks so Ruff, Pyright, Darglint and `make_pyi` will run automatically before each commit.
Note that pre-commit will only be installed when you use a Python version >= 3.9.

``` bash
pre-commit install
```

You can also run the pre-commit checks manually:
```bash
pre-commit run --all-files
```

## Type Stub Generation

When adding new components or modifying existing ones, you need to regenerate the type stub files (.pyi). This ensures proper type checking and IDE support.

To generate type stubs:
```bash
poetry run python scripts/make_pyi.py
```

After running this command:
1. Check `git status` to see if any .pyi files were modified
2. If changes were made, include them in your commit
3. If no changes were made, your types are up to date

## Editing Templates

To edit the templates in Reflex you can do so in two ways:

1. Change to the basic `blank` template can be done in the `reflex/.templates/apps/blank` directory.

2. Other templates can be edited in their own repository. For example the `sidebar` template can be found in the [`reflex-sidebar`](https://github.com/reflex-dev/sidebar-template) repository.


## Troubleshooting

Common issues and their solutions:

1. **Development Server Issues**
   - If the development server becomes unresponsive, stop it with Ctrl+C and restart
   - For frontend-only changes, use `--frontend-only` flag for faster development
   - Clear the examples directory using `scripts/clean_examples.py` if you encounter unexplained issues

2. **Pre-commit Hook Failures**
   - Run `pre-commit run --all-files` to identify specific issues
   - Ensure you've formatted code with `ruff format .` before committing
   - Check that type stubs are up to date with `make_pyi.py`

3. **Type Checking Errors**
   - Verify your changes haven't broken type definitions
   - Regenerate type stubs if you modified components
   - Check the error messages from pyright for specific type issues

## Other Notes

For some pull requests when adding new components you will have to generate a pyi file for the new component. This is done by running the following command in the `reflex` directory.

(Please check in with the team before adding a new component to Reflex we are cautious about adding new components to Reflex's core.)

``` bash
poetry run python scripts/make_pyi.py
```
