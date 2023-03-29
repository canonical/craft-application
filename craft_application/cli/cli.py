# This file is part of starcraft.
#
# Copyright 2023 Canonical Ltd.
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 3, as published
# by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
# SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.

from typing import Optional, List
import logging
import sys

from craft_cli import (
    emit,
    GlobalArgument,
    CraftError,
    EmitterMode,
    CommandGroup,
    Dispatcher,
    ProvideHelpException,
    ArgumentParsingError,
)


from .lifecycle_commands import get_lifecycle_command_group


GLOBAL_ARGS = [
    GlobalArgument(
        "version", "flag", "-V", "--version", "Show the application version and exit"
    )
]


def _emit_error(error: CraftError, cause: Optional[Exception] = None) -> None:
    """Emit the error in a centralized way so we can alter it consistently."""
    # set the cause, if any
    if cause is not None:
        error.__cause__ = cause

    # TODO if running inside a managed instance, do not report the internal logpath
    # if is_managed_mode():
    #     error.logpath_report = False

    # finally, emit
    emit.error(error)


def run(
    appname: str,
    greeting: str,
    summary: str,
    version: str,
    additional_command_groups: Optional[List[CommandGroup]] = None,
) -> None:
    """Run the CLI."""
    # set lib loggers to debug level so that all messages are sent to Emitter
    for lib_name in ("craft_providers", "craft_parts"):
        logger = logging.getLogger(lib_name)
        logger.setLevel(logging.DEBUG)

    # Capture debug-level log output in a file in managed mode, even if the
    # application is executing with a lower log level
    # log_filepath = get_managed_environment_log_path() if is_managed_mode() else None
    log_filepath = None

    command_groups = [get_lifecycle_command_group()]
    if additional_command_groups:
        command_groups.extend(additional_command_groups)

    emit.init(
        mode=EmitterMode.BRIEF,
        appname=appname,
        greeting=greeting,
        log_filepath=log_filepath,
    )

    dispatcher = Dispatcher(
        appname,
        command_groups,
        summary=summary,
        extra_global_args=GLOBAL_ARGS,
    )

    try:
        global_args = dispatcher.pre_parse_args(sys.argv[1:])
        if global_args.get("version"):
            emit.message(f"{appname} {version}")
        else:
            dispatcher.load_command(None)
            dispatcher.run()
        emit.ended_ok()
    except ProvideHelpException as err:
        print(err, file=sys.stderr)  # to stderr, as argparse normally does
        emit.ended_ok()
    except ArgumentParsingError as err:
        print(err, file=sys.stderr)  # to stderr, as argparse normally does
        emit.ended_ok()
        sys.exit(1)
    except Exception as err:  # pylint: disable=broad-except
        _emit_error(CraftError(f"rockcraft internal error: {err!r}"))
        sys.exit(1)
