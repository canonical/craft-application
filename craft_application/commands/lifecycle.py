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
from __future__ import annotations

import abc
import pathlib
import textwrap
from typing import TYPE_CHECKING, Any, cast

from craft_cli import CommandGroup, emit
from craft_parts.features import Features
from typing_extensions import override

from craft_application import LifecycleService, services
from craft_application.commands import base

if TYPE_CHECKING:
    import argparse


def get_lifecycle_command_group() -> CommandGroup:
    """Return the lifecycle related command group."""
    commands: list[type[_LifecycleCommand]] = [
        CleanCommand,
        PullCommand,
        OverlayCommand,
        BuildCommand,
        StageCommand,
        PrimeCommand,
        PackCommand,
    ]
    if not Features().enable_overlay:
        commands.remove(OverlayCommand)

    return CommandGroup(
        "Lifecycle",
        commands,
    )


class _LifecycleCommand(base.AppCommand, metaclass=abc.ABCMeta):
    """Lifecycle-related commands."""

    _lifecycle_service: LifecycleService

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)

        self._lifecycle_service = cast(
            LifecycleService, config.get("lifecycle_service")
        )

    @override
    def run(self, parsed_args: "argparse.Namespace") -> None:
        emit.trace(f"lifecycle command: {self.name!r}, arguments: {parsed_args!r}")


class _LifecyclePartsCommand(_LifecycleCommand):
    @override
    def fill_parser(self, parser: "argparse.ArgumentParser") -> None:
        super().fill_parser(parser)  # type: ignore
        parser.add_argument(
            "parts",
            metavar="part-name",
            type=str,
            nargs="*",
            help="Optional list of parts to process",
        )

    @override
    def get_managed_cmd(self, parsed_args: argparse.Namespace) -> list[str]:
        cmd = super().get_managed_cmd(parsed_args)

        cmd.extend(parsed_args.parts)

        return cmd


class _LifecycleStepCommand(_LifecyclePartsCommand):
    run_managed = True

    @override
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

    @override
    def get_managed_cmd(self, parsed_args: argparse.Namespace) -> list[str]:
        """Get the command to run in managed mode.

        :param parsed_args: The parsed arguments used.
        :returns: A list of strings ready to be passed into a craft-providers executor.
        :raises: RuntimeError if this command is not supposed to run managed.
        """
        cmd = super().get_managed_cmd(parsed_args)

        if getattr(parsed_args, "shell", False):
            cmd.append("--shell")
        if getattr(parsed_args, "shell_after", False):
            cmd.append("--shell-after")

        return cmd

    @override
    def run(
        self, parsed_args: "argparse.Namespace", step_name: str | None = None
    ) -> None:
        """Run a lifecycle step command."""
        super().run(parsed_args)

        step_name = cast(str, step_name or self.name)

        self._lifecycle_service.run(step_name=step_name, part_names=parsed_args.parts)


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

    _package_service: services.PackageService

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self._package_service = cast(
            services.PackageService, config.get("package_service")
        )

    @override
    def run(
        self, parsed_args: "argparse.Namespace", step_name: str | None = None
    ) -> None:
        """Run the prime command."""
        super().run(parsed_args, step_name=step_name)

        self._package_service.write_metadata(self._lifecycle_service.prime_dir)


class PackCommand(PrimeCommand):
    """Command to pack the final artifact."""

    run_managed = False

    name = "pack"
    help_msg = "Create the final artifact"
    overview = textwrap.dedent(
        """
        Process parts and create the final artifact.
        """
    )

    @override
    def fill_parser(self, parser: "argparse.ArgumentParser") -> None:
        super().fill_parser(parser)

        parser.add_argument(
            "--output",
            "-o",
            type=pathlib.Path,
            default=pathlib.Path(),
            help="Output directory for created packages.",
        )

    @override
    def run(
        self, parsed_args: "argparse.Namespace", step_name: str | None = None
    ) -> None:
        """Run the pack command."""
        if step_name not in ("pack", None):
            raise RuntimeError(f"Step name {step_name} passed to pack command.")
        super().run(parsed_args, step_name="prime")

        packages = self._package_service.pack(parsed_args.output)

        if not packages:
            emit.message("No packages created.")
        elif len(packages) == 1:
            emit.message(f"Packed {packages[0].name}")
        else:
            package_names = ", ".join(pkg.name for pkg in packages)
            emit.message(f"Packed: {package_names}")


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

    @override
    def run(self, parsed_args: "argparse.Namespace") -> None:
        """Run the clean command."""
        super().run(parsed_args)

        self._lifecycle_service.clean(parsed_args.parts)
