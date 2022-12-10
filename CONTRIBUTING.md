# Welcome to Pynecone contributing guide! 🥳

## Getting started

To navigate our codebase with confidence, see [Pynecone Docs](https://pynecone.io/docs/getting-started/introduction) :confetti_ball:. 

### Discussions

- Have a question? Want to discuss a feature? [Start a discussion](https://github.com/pynecone-io/pynecone/discussions)

    We welome and discussions and questions. We want to make sure that Pynecone is the best it can be, and we can't do that without your help.

### Issues

* #### Create a new issue

    If you spot a problem with anything in Pynecone feel free to create an issue. Even if you are not sure if its a problem with the framework or your own code, create an issue and we will do our best to answer or resolve it.

* #### Solve an issue

    Scan through our [existing issues](https://github.com/pynecone-io/pynecone/issues) to find one that interests you. You can narrow down the search using `labels` as filters. As a general rule, we don’t assign issues to anyone. If you find an issue to work on, you are welcome to open a PR with a fix. Any large issue changing the compiler of Pynecone should brought to the Pynecone maintainers for approval

Thank you for supporting Pynecone!🎊

## 💻 How to Run a Local Build of Pynecone 
Here is a quick guide to how the run Pynecone repo locally so you can start contributing to the project.

First clone Pynecone:
```
git clone https://github.com/pynecone-io/pynecone.git
```

Navigate into the repo:
```
cd pynecone
```

Install poetry:
```
pip install poetry
```

Install your local Pynecone build:
```
python -m pip install -e .
```

Now create an examples folder so you can test the local Python build in this repository:
```
mkdir examples
cd examples
```

Create a project in this folder can be named anything but for the sake of the directions we'll use `example`:
```
mkdir example
cd example
```

Now Init/Run
```
poetry run pc init
poetry run pc run
```

All the changes you make to the repository will be reflected in your running app.
* We have the examples folder in the .gitignore, so your changes in pynecone/examples won't be reflected in your commit.



