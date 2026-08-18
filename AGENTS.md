# Agents

## Overview

`canonical/craft-application` is a Python library for Craft Application project
metadata, lifecycle, and service helpers.

## Craft Application projects

This repository is used by Craft Application itself and by downstream craft apps that
depend on it.

The source code for those apps is at
https://github.com/canonical/<project-name-in-lowercase>.

## Development

Craft Application uses [uv](https://docs.astral.sh/uv/) for dependency management.

```bash
make setup          # Install all deps
```

### Running tests

```bash
make test           # Full test suite
make test-fast      # Fast tests only
uv run pytest tests/unit/path/to/test_file.py::test_name  # run a specific test
```

### Formatting and linting

```bash
make format
make lint
```

### Documentation

Documentation uses the [Diátaxis](https://diataxis.fr) framework
and the [Sphinx Stack](https://github.com/canonical/sphinx-stack).
All documentation must follow the [Craft Application style
guide](https://documentation.ubuntu.com/style-guide/)
and the overall [Canonical style guide](https://documentation.ubuntu.com/style-guide/).

```bash
make setup-docs
make docs
make lint-docs
```

## Practices

- Make the smallest safe change necessary to resolve the issue. Avoid unrelated bug
  fixes, opportunistic cleanup, and refactoring unless required. The right amount of
  complexity is the minimum needed for the current task.
- Never speculate about code you haven't inspected.
- Follow the project's existing conventions regarding style, docstrings, logging, and
  comments.
- Comments should explain complex business logic, non-obvious algorithms, regex, and
  other "gotchas". Comments should be brief, explain "why" not "how", and be helpful for
  future maintainers.
- Update relevant documentation and release notes to reflect code changes.

## Processes

- Commit headers are no more than 80 characters, follow [Conventional
  Commits](https://www.conventionalcommits.org/en/v1.0.0/), and use the following types:
    - ci, build, feat, fix, perf, refactor, style, test, docs, chore
- Always run `make format`, `make lint`, and `make test-fast` before completing your
  work.
