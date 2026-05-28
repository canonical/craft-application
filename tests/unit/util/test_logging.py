import logging
import os

import pydantic
import pytest
import pytest_check
from craft_application import errors, util
from craft_application.application import AppMetadata
from craft_application.util.logging import handle_runtime_error
from hypothesis import given, strategies


@given(names=strategies.lists(strategies.text()))
def test_setup_loggers_resulting_level(names):
    # The logging module is stateful and global, so first lets clear the logging level
    # that another test might have already set.
    for name in names:
        logger = logging.getLogger(name)
        logger.setLevel(logging.NOTSET)

    util.setup_loggers(*names)

    for name in names:
        logger = logging.getLogger(name)
        pytest_check.equal(logger.level, logging.DEBUG)


@pytest.fixture
def app_metadata():
    return AppMetadata(name="testcraft", summary="A summary")


def test_handle_runtime_error_pydantic_is_user_config_error(app_metadata):
    """A pydantic ValidationError is rendered as a structured config error.

    It must not fall through to the generic 'internal error' (exit 70) path.
    """

    class _Model(pydantic.BaseModel):
        base: int

    with pytest.raises(pydantic.ValidationError) as exc_info:
        _Model(base="ubuntu@26.04")  # pyright: ignore[reportArgumentType]
    error = exc_info.value

    captured = []
    return_code = handle_runtime_error(app_metadata, error, print_error=captured.append)

    pytest_check.equal(return_code, os.EX_DATAERR)
    pytest_check.is_instance(captured[0], errors.CraftValidationError)
    pytest_check.is_in("testcraft.yaml", captured[0].args[0])
    pytest_check.is_not_none(captured[0].resolution)
    pytest_check.is_true("internal error" not in captured[0].args[0])
    pytest_check.equal(captured[0].__cause__, error)


def test_handle_runtime_error_base_alias_value_error(app_metadata):
    """A host base-alias lookup ValueError becomes a structured error."""
    error = ValueError("'26.04' is not a valid BuilddBaseAlias")

    captured = []
    return_code = handle_runtime_error(app_metadata, error, print_error=captured.append)

    pytest_check.equal(return_code, os.EX_CONFIG)
    pytest_check.is_in("Unsupported base", captured[0].args[0])
    pytest_check.is_not_none(captured[0].resolution)
    pytest_check.is_true("internal error" not in captured[0].args[0])


def test_handle_runtime_error_generic_value_error_is_internal(app_metadata):
    """An unrelated ValueError still reports as an internal error."""
    error = ValueError("something unexpected")

    captured = []
    return_code = handle_runtime_error(app_metadata, error, print_error=captured.append)

    pytest_check.equal(return_code, os.EX_SOFTWARE)
    pytest_check.is_in("internal error", captured[0].args[0])
