# Agents Guide

This guide helps AI coding agents and automation tools work effectively with the craft-application repository.

## Overview

**craft-application** is a Python library that serves as the base framework for all Starcraft applications (like snapcraft, charmcraft, etc.). It provides common mechanisms for application services, project models, and other shared functionality.

- **Language**: Python 3.10+
- **License**: LGPL-3.0
- **Build System**: setuptools with setuptools_scm
- **Package Manager**: uv
- **Documentation**: See [README.md](README.md) and [CONTRIBUTING.md](CONTRIBUTING.md)

## Development Workflow

### Initial Setup

1. **Clone the repository** (see [CONTRIBUTING.md](CONTRIBUTING.md) for details):

    ```bash
    git clone https://github.com/canonical/craft-application --recurse-submodules
    cd craft-application
    ```

2. **Set up the development environment**:

    ```bash
    make setup
    ```

    This installs all dependencies, sets up the virtual environment, and configures pre-commit hooks.

3. **Verify the setup**:
    ```bash
    make lint
    make test
    ```

### Common Development Tasks

Use these `make` targets for everyday development. Run `make help` to see all available targets.

#### Formatting Code

```bash
make format                # Run all automatic formatters
```

#### Linting Code

```bash
make lint                  # Run all linters
```

#### Running Tests

```bash
make test                  # Run all tests
```

To run specific tests directly (useful when only modifying tests):

```bash
# Run tests in a specific file
uv run pytest tests/unit/test_application.py

# Run tests matching a pattern
uv run pytest -k "test_pattern"
```

#### Building Documentation

```bash
make docs                  # Build documentation
```

#### Cleaning Up

```bash
make clean                 # Remove build artifacts and temporary files
```

### Pre-commit Hooks

This project uses pre-commit hooks that run automatically on `git commit`. The `make setup` command installs these hooks. Always ensure the pre-commit hooks are installed and run before committing. See [.pre-commit-config.yaml](.pre-commit-config.yaml) for the full configuration.

### Commit Message Format

Follow [Conventional Commits](https://www.conventionalcommits.org/) style:

```
<type>: <description>

[optional body]

[optional footer]
```

Common types (in priority order):

- `ci`: CI/CD changes
- `build`: Build system changes
- `feat`: New features
- `fix`: Bug fixes
- `perf`: Performance improvements
- `refactor`: Code refactoring
- `style`: Code style changes
- `test`: Test changes
- `docs`: Documentation changes
- `chore`: Maintenance tasks

See [CONTRIBUTING.md](CONTRIBUTING.md) for more details on commit conventions.

## Project Structure

See the repository's directory structure for details. Key directories:

- `craft_application/` - Main library code
- `tests/unit/` - Unit tests (mirror `craft_application/` structure)
- `tests/integration/` - Integration tests
- `tests/spread/` - Spread system tests
- `docs/` - Documentation source

## Testing Guidelines

### Test Organization

- **Unit tests**: In `tests/unit/` - mirror the structure of `craft_application/`
- **Integration tests**: In `tests/integration/` - test component interactions
- **Spread tests**: In `tests/spread/` - system-level tests using the [Spread framework](https://github.com/canonical/spread)
    - Install spread: `snap install spread`
    - Run spread tests: `spread` (from repository root)
    - Spread tests are defined in `task.yaml` files within test directories
    - Each test has `prepare`, `execute`, and optionally `restore` sections
    - Configuration in `spread.yaml` at repository root

### Writing Tests

- Use pytest for unit and integration tests
- Follow existing test patterns in the repository
- Add tests for all non-trivial code changes
- Mark slow tests with `@pytest.mark.slow` decorator
- Use fixtures and mocks appropriately
- Aim for complete line and branch coverage where feasible

## Code Quality Standards

### Type Checking and Linting

All configuration is in `pyproject.toml`. See that file for details on:

- Type checking (mypy, pyright)
- Linting (ruff, codespell)
- Code formatting standards

### Code Style

- Follow PEP 8 conventions
- Use type hints for all function parameters and return values
- Add docstrings for public APIs (Google/NumPy style)
- Keep functions focused and testable
- Prefer composition over inheritance

## Dependencies

### Adding Dependencies

1. Add the dependency to `pyproject.toml` under `[project.dependencies]`
2. For development-only dependencies, add to `[dependency-groups]`
3. Run: `uv lock && uv sync`
4. Test that it works: `make test`

### Dependency Groups

See `pyproject.toml` under `[dependency-groups]` for the complete list. Key groups include:

- `dev`: Core development dependencies (pytest, coverage, etc.)
- `lint`: Linting tools
- `types`: Type checking tools (mypy, type stubs)
- `docs`: Documentation tools (Sphinx, etc.)
- `remote`: Optional remote-build support (launchpadlib)
- `apt`: Optional python-apt support (required on Linux but not included in dev group due to platform-specific versioning; use appropriate `dev-{codename}` group)

## Common Patterns

### Working with Services

Services in `craft_application/services/` follow a consistent pattern:

- Inherit from appropriate base classes
- Use dependency injection
- Implement well-defined interfaces
- Are tested in isolation with mocks

### Working with Models

Pydantic models in `craft_application/models/`:

- Use Pydantic v2 syntax
- Include validators where appropriate
- Provide clear docstrings
- Support serialization/deserialization

### Error Handling

Custom exceptions in `craft_application/errors.py`:

- Inherit from `CraftError` or appropriate subclass
- Include error message templates in the class definition
- Store specific values as instance attributes
- Only require callers to pass specific values, not full messages

## Continuous Integration

GitHub Actions workflows are in `.github/workflows/`:

- `qa.yaml`: Main quality assurance (lint, type check, test)
- `spread.yaml`: Spread integration tests
- `tics.yaml`: TICS quality analysis
- `policy.yaml`: Security and policy checks
- `release-publish.yaml`: Release automation

## Documentation

### Building Docs

```bash
make docs          # Build static documentation
```

### Documentation Structure

- Source: `docs/` directory
- Common docs: `docs/common/` - Contains app-agnostic documentation that can be integrated into downstream craft tools (snapcraft, charmcraft, etc.). Write documentation here when documenting features inherited by downstream applications. Documentation from `docs/common/` should be included from the main `docs/` directory either by linking in a table of contents or using the Sphinx include directive.
- Built docs: `docs/_build/` (gitignored)
- Uses Sphinx with canonical-sphinx theme
- Follows Diátaxis framework (tutorials, how-to, reference, explanation)

## Tips for Agents

1. **Always run setup first**: `make setup` ensures a clean development environment
2. **Test incrementally**: Run `make test` to validate changes
3. **Run spread tests locally**: Run `spread` before committing to catch system-level issues
4. **Format before committing**: `make format` or rely on pre-commit hooks
5. **Check types early**: Run `make lint` to catch type errors and other issues
6. **Reference existing code**: Look at similar implementations for patterns and style
7. **Read CONTRIBUTING.md**: Contains detailed guidelines for contributors
8. **Use uv commands directly**: For fine-grained control, use `uv run <command>`
9. **Clean when stuck**: `make clean && rm -rf .venv && make setup` for a fresh start

## Important Notes

- **Minimal changes**: Make the smallest possible changes to achieve the goal
- **Don't remove working code**: Unless fixing a bug or security issue in changed code
- **Update docs**: If changing public APIs or adding features
- **Test all changes**: Don't skip tests even for "simple" changes
- **Follow conventions**: Match the style and patterns of existing code
- **Version pinning**: Be cautious with dependency versions (see pygit2 comments in pyproject.toml)

## Getting Help

- **Documentation**: https://canonical-craft-application.readthedocs-hosted.com/
- **Issues**: https://github.com/canonical/craft-application/issues

## Future Considerations

_Note: The maintainer (@lengau) requested to tackle specific pain points and constraints later. This section is a placeholder for that future documentation._

Areas to document:

- Common pitfalls when working with craft-application
- Breaking change patterns to avoid
- Complex dependency constraints
- Platform-specific considerations
- Performance optimization guidelines
