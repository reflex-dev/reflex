# Reflex Contributing Guidelines

For an extensive guide on the different ways to contribute to Reflex please visite our notion's [Contributing Guide](https://www.notion.so/reflex-dev/2107ab2bc166497db951b8d742748284?v=f0eaff78fa984b5ab15d204af58907d7).



## Runing a Local Build of Reflex 
Here is a quick guide to how the run Reflex repo locally so you can start contributing to the project.

**Pre-requisites:**
- Python >= 3.7
- Poetry version >= 1.4.0 and add it to your path (see [Poetry Docs](https://python-poetry.org/docs/#installation) for more info).


**1.  Clone Reflex and navigate into the repo:**
``` bash
git clone https://github.com/reflex-dev/reflex.git
cd reflex
```

**2. Install your local Reflex build:**
``` bash
poetry install
```
**3. Now create an examples folder so you can test the local Python build in this repository.**
* We have the examples folder in the .gitignore, so your changes in reflex/examples won't be reflected in your commit.
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


## 🧪 Testing and QA

Within the 'test' directory of Reflex you can add to a test file already there or create a new test python file if it doesn't fit into the existing layout.

#### What to unit test?
- Any feature or significant change that has been added.
- Any edge cases or potential problem areas.
 -Any interactions between different parts of the code.


## ✅ Making a PR

Once you solve a current issue or improvement to Reflex, you can make a pr, and we will review the changes. 

Before submitting, a pull request, ensure the following steps are taken and test passing. To do this install pre-commit and run the tests.

``` bash
pre-commit install
```

``` bash
poetry run pre-commit
```

That's it you can now submit your pr. Thanks for contributing to Reflex!
