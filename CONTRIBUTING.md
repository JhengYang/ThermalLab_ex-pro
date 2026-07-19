# Contributing to FLIR Thermal Analyzer

First off, thank you for considering contributing to FLIR Thermal Analyzer! It's people like you that make open source such a great community.

## Where do I go from here?

If you've noticed a bug or have a feature request, make sure to check our [Issues](https://github.com/yourusername/flir-thermal-analyzer/issues) first to see if someone else has already created a ticket. If not, go ahead and [make one](../../issues/new/choose)!

## Fork & create a branch

If this is something you think you can fix, then fork FLIR Thermal Analyzer and create a branch with a descriptive name.

A good branch name would be (where issue #325 is the ticket you're working on):

```sh
git checkout -b 325-add-new-segmentation-model
```

## Get the test suite running

Make sure you have a working development environment. We recommend using Python 3.10+ and a virtual environment.

```sh
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Mac/Linux
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r app/requirements.txt
```

Currently, we are in the process of building our test suite. Ensure the application runs without errors locally:

```sh
flask --app app.py run --debug
```

## Code Guidelines

- Adhere to [PEP 8](https://peps.python.org/pep-0008/) for Python code.
- Use meaningful variable names and add docstrings to new functions.
- Keep PRs small and focused on a single issue or feature.
- Please run a linter (like `flake8` or `black`) before submitting your code.

## Submitting a Pull Request

1. Push your branch to your fork.
2. Open a Pull Request against the `main` branch of this repository.
3. Use the provided Pull Request template to describe your changes.
4. A maintainer will review your code. Please be open to feedback and discussion!

By contributing, you agree that your contributions will be licensed under its MIT License.
