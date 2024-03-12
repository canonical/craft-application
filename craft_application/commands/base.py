#  This file is part of craft-application.
#
#  Copyright 2023-2024 Canonical Ltd.
#
#  This program is free software: you can redistribute it and/or modify it
#  under the terms of the GNU Lesser General Public License version 3, as
#  published by the Free Software Foundation.
#
#  This program is distributed in the hope that it will be useful, but WITHOUT
#  ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
#  SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE.
#  See the GNU Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Base command for craft-application commands."""
from __future__ import annotations

import abc
import argparse
from typing import Any, Optional, Protocol, final

from craft_cli import BaseCommand, emit
from typing_extensions import Self

from craft_application import application, util
from craft_application.services import service_factory


class ParserCallback(Protocol):
    """A protocol that expresses the type for a parser callback."""

    @staticmethod
    def __call__(cmd: ExtensibleCommand, parser: argparse.ArgumentParser) -> None:
        """Call the parser callback function. Works the same as fill_parser."""


class RunCallback(Protocol):
    """A protocol that expresses the type for pre-run and post-run callbacks."""

    @staticmethod
    def __call__(
        cmd: ExtensibleCommand,
        parsed_args: argparse.Namespace,
        **kwargs: Any,  # noqa: ANN401
    ) -> int | None:
        """Call the prologue or epilogue. Takes the same parameters as run."""


class AppCommand(BaseCommand):
    """Command for use with craft-application."""

    always_load_project: bool = False
    """The project is also loaded in non-managed mode."""

    def __init__(self, config: dict[str, Any] | None) -> None:
        if config is None:
            # This should only be the case when the command is not going to be run.
            # For example, when requesting help on the command.
            emit.trace("Not completing command configuration")
            return

        super().__init__(config)

        self._app: application.AppMetadata = config["app"]
        self._services: service_factory.ServiceFactory = config["services"]

    def run_managed(
        self,
        parsed_args: argparse.Namespace,  # noqa: ARG002 (the unused argument is for subclasses)
    ) -> bool:
        """Whether this command should run in managed mode.

        By default returns `False`. Subclasses can override this method to change this,
        including by inspecting the arguments in `parsed_args`.
        """
        return False

    def provider_name(
        self,
        parsed_args: argparse.Namespace,  # noqa: ARG002 (the unused argument is for subclasses)
    ) -> str | None:
        """Name of the provider where the command should be run inside of.

        By default returns None. Subclasses can override this method to change this,
        including by inspecting the arguments in `parsed_args`.
        """
        return None

    def get_managed_cmd(
        self,
        parsed_args: argparse.Namespace,  # - Used by subclasses
    ) -> list[str]:
        """Get the command to run in managed mode.

        :param parsed_args: The parsed arguments used.
        :returns: A list of strings ready to be passed into a craft-providers executor.
        :raises: RuntimeError if this command is not supposed to run managed.

        Commands that have additional parameters to pass in managed mode should
        override this method to include those parameters.
        """
        if not self.run_managed(parsed_args):
            raise RuntimeError("Unmanaged commands should not be run in managed mode.")
        cmd_name = self._app.name
        verbosity = emit.get_mode().name.lower()
        return [cmd_name, f"--verbosity={verbosity}", self.name]


class ExtensibleCommand(AppCommand):
    """A command that allows applications to register modifications."""

    _parse_callback: ParserCallback | None
    _prologue: RunCallback | None
    _epilogue: RunCallback | None

    @property
    def services(self) -> service_factory.ServiceFactory:
        """Services available to this command."""
        return self._services  # pragma: no cover

    @classmethod
    def register_parser_filler(cls, callback: ParserCallback) -> None:
        """Register a function that modifies the argument parser.

        Only one parser filler callback can be registered to a particular command class.
        However, fillers registered to parent classes will still be run, from the
        top class in the inheritance tree on down.
        """
        cls._parse_callback = callback

    @classmethod
    def register_prologue(cls, callback: RunCallback) -> None:
        """Register a function that runs before the main run.

        Each command class may only have a single prologue. Prologues on the inheritance
        tree are run in reverse method resolution order. (That is, a child command's
        prologue is run after the parent command's.)
        """
        cls._prologue = callback

    @classmethod
    def register_epilogue(cls, callback: RunCallback) -> None:
        """Register a function that runs after the main run.

        Each command class may only have a single epilogue. Epilogues on the inheritance
        tree are run in reverse method resolution order. (That is, a child command's
        epilogue is run after the parent command's.)
        """
        cls._epilogue = callback

    def _fill_parser(self, parser: argparse.ArgumentParser) -> None:
        """Real parser filler for an ExtensibleCommand."""

    @final
    def fill_parser(self, parser: argparse.ArgumentParser) -> None:
        """Set the arguments for the parser.

        First, the real filler in ``_fill_parser`` is run, filling the base parser.
        After that, the parse callbacks are run in reverse method resolution order.
        (That is, starting with the top ancestor.)
        """
        self._fill_parser(parser)
        callbacks = util.get_unique_callbacks(self.__class__, "_parse_callback")
        for callback in callbacks:
            callback(self, parser)

    @abc.abstractmethod
    def _run(
        self: Self, parsed_args: argparse.Namespace, **kwargs: Any  # noqa: ANN401
    ) -> int | None:
        """Run the real run method for an ExtensibleCommand."""

    @final
    def run(
        self: Self, parsed_args: argparse.Namespace, **kwargs: Any  # noqa: ANN401
    ) -> Optional[int]:  # noqa: UP007
        """Run any prologue callbacks, the main command, and any epilogue callbacks."""
        result = None
        for prologue in util.get_unique_callbacks(self.__class__, "_prologue"):
            result = prologue(self, parsed_args, **kwargs) or result
        result = self._run(parsed_args, **kwargs) or result
        for epilogue in util.get_unique_callbacks(self.__class__, "_epilogue"):
            result = (
                epilogue(self, parsed_args, current_result=result, **kwargs) or result
            )
        return result
