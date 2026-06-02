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
import pydantic

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
        case pydantic.ValidationError():
            # An unhandled pydantic ValidationError almost always means the
            # user's project configuration contains an invalid value (for
            # example an unsupported ``base``). Without this case it falls
            # through to the generic handler below and is reported as an
            # "internal error" (exit 70) along with a raw pydantic traceback
            # and an errors.pydantic.dev link, even though it is a plain user
            # configuration error. Render it as a structured config error.
            # NB: pydantic.ValidationError is a subclass of ValueError, so this
            # case must come before any bare ValueError handling.
            return_code = os.EX_DATAERR
            transformed = errors.CraftValidationError.from_pydantic(
                error,
                file_name=f"{app.name}.yaml",
                resolution=(
                    "Check the reported field(s) against the supported "
                    "values in the documented project schema."
                ),
            )
            transformed.__cause__ = error
        case ValueError() if "BuilddBaseAlias" in str(error):
            # Host base-alias lookup failures (e.g.
            # ``ValueError("'26.04' is not a valid BuilddBaseAlias")``)
            # currently bubble up as a bare ValueError and are reported as an
            # "internal error". Surface them as a structured error instead.
            # This is a shallow guard keyed off the exception message; the
            # proper fix is to raise a typed error at the base-alias lookup
            # site in craft-providers. Tracked in #1086 (blocked by
            # canonical/craft-providers#969).
            return_code = os.EX_CONFIG
            transformed = craft_cli.CraftError(
                f"Unsupported base for this host: {error}",
                resolution=(
                    "Build on a host whose Ubuntu release matches a supported "
                    "base, or set a supported 'base'/'build-base' in your "
                    "project configuration."
                ),
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
