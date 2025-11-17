# noqa: A005
# This file is part of craft_application.
#
# Copyright 2023 Canonical Ltd.
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License version 3, as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
# SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Logging helpers."""

from __future__ import annotations

import logging
import os
import signal
import sys
from typing import TYPE_CHECKING

import craft_cli
import craft_parts
import craft_platforms
import craft_providers

from craft_application import errors

if TYPE_CHECKING:
    from collections.abc import Callable

    from craft_application.application import AppMetadata


def setup_loggers(*names: str) -> None:
    """Set up loggers by name so that craft-cli handles them correctly."""
    for lib in names:
        logger = logging.getLogger(lib)
        logger.setLevel(logging.DEBUG)


def handle_runtime_error(
    app: AppMetadata,
    error: BaseException,
    *,
    print_error: Callable[[craft_cli.CraftError], None] = craft_cli.emit.report_error,
    debug_mode: bool = False,
) -> int:
    """Handle a runtime error by transforming and printing it, then return the appropriate retcode.

    The printing behavior can be customized by passing a different `print_error`, otherwise
    `Emitter.report_error` is used.
    """
    unrecognized_error = False
    match error:
        case craft_cli.ArgumentParsingError():
            print(error, file=sys.stderr)
            return os.EX_USAGE
        case KeyboardInterrupt():
            return_code = 128 + signal.SIGINT
            transformed = craft_cli.CraftError("Interrupted.", retcode=return_code)
            transformed.__cause__ = error
        case craft_cli.CraftError():
            return_code = error.retcode
            transformed = error
        case craft_parts.PartsError():
            return_code = 1
            transformed = errors.PartsLifecycleError.from_parts_error(error)
            transformed.__cause__ = error
        case craft_providers.ProviderError():
            return_code = 1
            transformed = craft_cli.CraftError(
                error.brief, details=error.details, resolution=error.resolution
            )
            transformed.__cause__ = error
        case craft_platforms.CraftPlatformsError():
            return_code = error.retcode
            transformed = craft_cli.CraftError(
                error.args[0],
                details=error.details,
                resolution=error.resolution,
                reportable=error.reportable,
                docs_url=error.docs_url,
                doc_slug=error.doc_slug,
                logpath_report=error.logpath_report,
                retcode=error.retcode,
            )
            transformed.__cause__ = error
        case _:
            unrecognized_error = True
            if isinstance(error, craft_platforms.CraftError):
                return_code = getattr(error, "retcode", 1)
                transformed = craft_cli.CraftError(
                    error.args[0],
                    details=error.details,
                    resolution=error.resolution,
                    docs_url=getattr(error, "docs_url", None),
                    doc_slug=getattr(error, "doc_slug", None),
                    logpath_report=getattr(error, "logpath_report", True),
                    reportable=getattr(error, "reportable", True),
                    retcode=return_code,
                )
            else:
                return_code = os.EX_SOFTWARE
                transformed = craft_cli.CraftError(
                    f"{app.name} internal error: {error!r}",
                    retcode=return_code,
                )
            transformed.__cause__ = error

    print_error(transformed)
    if debug_mode and unrecognized_error:
        raise error
    return return_code
