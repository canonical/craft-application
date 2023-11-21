import logging

import pytest_check
from craft_application import util
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
