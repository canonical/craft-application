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

"""Basic lifecycle commands for a Craft Application."""

import abc
import textwrap
from typing import TYPE_CHECKING, Callable, Dict, Optional, cast, Type, List

from craft_cli import BaseCommand, CommandGroup, emit
from craft_parts.features import Features
from overrides import overrides  # pyright: ignore[reportUnknownVariableType]

from craft_application.commands.base import AppCommand

if TYPE_CHECKING:
    import argparse


def get_lifecycle_command_group():
    """Return the lifecycle related command group."""
    # Craft CLI mangles the order, but we keep it this way for when it won't
    # anymore.
    commands: List[Type[_LifecycleCommand]] = [
        CleanCommand,
        PullCommand,
    ]
    if Features().enable_overlay:
        commands.append(OverlayCommand)

    commands.extend(
        [
            BuildCommand,
            StageCommand,
            PrimeCommand,
            PackCommand,
        ]
    )

    return CommandGroup(
        "Lifecycle",
        commands,
    )


class _LifecycleCommand(AppCommand, abc.ABC):
    """Lifecycle-related commands."""

    @overrides
    def run(self, parsed_args: "argparse.Namespace") -> None:
        emit.trace(f"lifecycle command: {self.name!r}, arguments: {parsed_args!r}")
        self._callbacks = cast(Dict[str, Callable], self.config)


class _LifecyclePartsCommand(_LifecycleCommand):
    @overrides
    def fill_parser(self, parser: "argparse.ArgumentParser") -> None:
        super().fill_parser(parser)  # type: ignore
        parser.add_argument(
            "parts",
            metavar="part-name",
            type=str,
            nargs="*",
            help="Optional list of parts to process",
        )


class _LifecycleStepCommand(_LifecyclePartsCommand):

    is_managed = True

    @overrides
    def fill_parser(self, parser: "argparse.ArgumentParser") -> None:
        super().fill_parser(parser)

        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            "--shell",
            action="store_true",
            help="Shell into the environment in lieu of the step to run.",
        )
        group.add_argument(
            "--shell-after",
            action="store_true",
            help="Shell into the environment after the step has run.",
        )

    @overrides
    def run(
        self, parsed_args: "argparse.Namespace", step_name: Optional[str] = None
    ) -> None:
        super().run(parsed_args)

        if step_name is None:
            step_name = self.name

        run_part_step = self._callbacks["run_part_step"]

        run_part_step(step_name=step_name, part_names=parsed_args.parts)


class PullCommand(_LifecycleStepCommand):
    """Command to pull parts."""

    name = "pull"
    help_msg = "Download or retrieve artifacts defined for a part"
    overview = textwrap.dedent(
        """
        Download or retrieve artifacts defined for a part. If part names
        are specified only those parts will be pulled, otherwise all parts
        will be pulled.
        """
    )


class OverlayCommand(_LifecycleStepCommand):
    """Command to overlay parts."""

    name = "overlay"
    help_msg = "Create part layers over the base filesystem."
    overview = textwrap.dedent(
        """
        Execute operations defined for each part on a layer over the base
        filesystem, potentially modifying its contents.
        """
    )


class BuildCommand(_LifecycleStepCommand):
    """Command to build parts."""

    name = "build"
    help_msg = "Build artifacts defined for a part"
    overview = textwrap.dedent(
        """
        Build artifacts defined for a part. If part names are specified only
        those parts will be built, otherwise all parts will be built.
        """
    )


class StageCommand(_LifecycleStepCommand):
    """Command to stage parts."""

    name = "stage"
    help_msg = "Stage built artifacts into a common staging area"
    overview = textwrap.dedent(
        """
        Stage built artifacts into a common staging area. If part names are
        specified only those parts will be staged. The default is to stage
        all parts.
        """
    )


class PrimeCommand(_LifecycleStepCommand):
    """Command to prime parts."""

    name = "prime"
    help_msg = "Prime artifacts defined for a part"
    overview = textwrap.dedent(
        """
        Prepare the final payload to be packed, performing additional
        processing and adding metadata files. If part names are specified only
        those parts will be primed. The default is to prime all parts.
        """
    )

    @overrides
    def run(
        self, parsed_args: "argparse.Namespace", step_name: Optional[str] = None
    ) -> None:
        super().run(parsed_args, step_name=step_name)

        generate_metadata = self._callbacks["generate_metadata"]
        generate_metadata()


class PackCommand(PrimeCommand):
    """Command to pack the final artifact."""

    name = "pack"
    help_msg = "Create the final artifact"
    overview = textwrap.dedent(
        """
        Process parts and create the final artifact.
        """
    )

    @overrides
    def run(self, parsed_args: "argparse.Namespace") -> None:
        super().run(parsed_args, step_name="prime")

        create_package = self._callbacks["create_package"]
        package_name = create_package()

        emit.message(f"Packed {str(package_name)!r}")


class CleanCommand(_LifecyclePartsCommand):
    """Command to remove part assets."""

    name = "clean"
    help_msg = "Remove a part's assets"
    overview = textwrap.dedent(
        """
        Clean up artifacts belonging to parts. If no parts are specified,
        remove the packing environment.
        """
    )

    @overrides
    def run(self, parsed_args: "argparse.Namespace") -> None:
        super().run(parsed_args)

        clean = self._callbacks["clean"]
        clean(part_names=parsed_args.parts)
