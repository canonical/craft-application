# Copyright 2023-2025 Canonical Ltd.
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
"""Basic lifecycle commands for a Craft Application."""

from __future__ import annotations

import argparse
import pathlib
import subprocess
import textwrap
from typing import Any

from craft_cli import CommandGroup, emit
from craft_parts.features import Features
from typing_extensions import override

from craft_application import util
from craft_application.commands import base

TEMP_SPREAD_FILE_NAME = ".craft-spread.yaml"


def get_lifecycle_command_group() -> CommandGroup:
    """Return the lifecycle related command group."""
    commands: list[type[_BaseLifecycleCommand]] = [
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
        commands,  # type: ignore[arg-type] # https://github.com/canonical/craft-cli/pull/157
        ordered=True,
    )


class _BaseLifecycleCommand(base.ExtensibleCommand):
    """Base class for lifecycle-related commands.

    All lifecycle commands must know where to execute (locally or in a build
    environment) but do not have to provide shell access into the environment.
    """

    @override
    def _run(self, parsed_args: argparse.Namespace, **kwargs: Any) -> None:
        emit.trace(f"lifecycle command: {self.name!r}, arguments: {parsed_args!r}")

    @override
    def _fill_parser(self, parser: argparse.ArgumentParser) -> None:
        super()._fill_parser(parser)  # type: ignore[arg-type]

        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            "--destructive-mode",
            action="store_true",
            help="Build in the current host",
        )
        group.add_argument(
            "--use-lxd",
            action="store_true",
            help="Build in a LXD container.",
        )

    @override
    def provider_name(self, parsed_args: argparse.Namespace) -> str | None:
        return "lxd" if parsed_args.use_lxd else None

    def _run_manager_for_build_plan(self, fetch_service_policy: str | None) -> None:
        """Run this command in managed mode, iterating over the generated build plan."""
        provider = self._services.get("provider")
        for build in self._services.get("build_plan").plan():
            provider.run_managed(build, bool(fetch_service_policy))

    def _use_provider(self, parsed_args: argparse.Namespace) -> bool:
        """Determine whether to build in a managed provider."""
        if util.is_managed_mode():
            return False
        if parsed_args.destructive_mode:
            emit.debug(
                "Not running managed mode because `--destructive-mode` was passed"
            )
            return False

        build_env = self._services.get("config").get("build_environment")
        if build_env and build_env.lower().strip() == "host":
            emit.debug(
                f"Not running managed mode because CRAFT_BUILD_ENVIRONMENT={build_env}"
            )
            return False

        return True


class LifecycleCommand(_BaseLifecycleCommand):
    """A command that will run the lifecycle and can shell into the environment.

    LifecycleCommands do not require a part. For example 'pack' will run
    the lifecycle but cannot be run on a specific part.
    """

    @override
    def _fill_parser(self, parser: argparse.ArgumentParser) -> None:
        super()._fill_parser(parser)

        if self._should_add_shell_args():
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

        parser.add_argument(
            "--debug",
            action="store_true",
            help="Shell into the environment if the build fails.",
        )

        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            "--platform",
            type=str,
            metavar="name",
            help="Set platform to build for",
        )
        group.add_argument(
            "--build-for",
            type=str,
            metavar="arch",
            help="Set architecture to build for",
        )

    @override
    def _run(
        self,
        parsed_args: argparse.Namespace,
        step_name: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Run a lifecycle step command."""
        super()._run(parsed_args)

        build_planner = self.services.get("build_plan")
        config = self.services.get("config")
        platform = getattr(parsed_args, "platform", None) or config.get("platform")
        if platform:
            build_planner.set_platforms(platform)
        build_for = getattr(parsed_args, "build_for", None) or config.get("build_for")
        if build_for:
            build_planner.set_build_fors(build_for)

        if self._use_provider(parsed_args):
            fetch_service_policy = getattr(parsed_args, "fetch_service_policy", None)
            if fetch_service_policy:
                self._services.get("fetch").set_policy(
                    fetch_service_policy  # type: ignore[reportArgumentType]
                )
            self._run_manager_for_build_plan(fetch_service_policy)
            return

        shell = getattr(parsed_args, "shell", False)
        shell_after = getattr(parsed_args, "shell_after", False)
        debug = getattr(parsed_args, "debug", False)

        step_name = step_name or self.name

        if shell:
            previous_step = self._services.lifecycle.previous_step_name(step_name)
            step_name = previous_step
            shell_after = True

        try:
            self._run_lifecycle(parsed_args, step_name)
        except Exception as err:
            if debug:
                emit.progress(str(err), permanent=True)
                _launch_shell()
            raise

        if shell_after:
            _launch_shell()

    def _run_lifecycle(
        self,
        parsed_args: argparse.Namespace,  # noqa: ARG002 (unused argument is for subclasses)
        step_name: str | None = None,
    ) -> None:
        """Run the lifecycle."""
        self._services.lifecycle.run(step_name=step_name)

    def _run_post_prime_steps(self) -> None:
        """Run post-prime steps."""
        self._services.package.update_project()
        self._services.package.write_metadata(self._services.lifecycle.prime_dir)

    @staticmethod
    def _should_add_shell_args() -> bool:
        return True


class LifecyclePartsCommand(LifecycleCommand):
    """A command that can run the lifecycle for a particular part."""

    # All lifecycle-related commands need a project to work
    always_load_project = True

    @override
    def _fill_parser(self, parser: argparse.ArgumentParser) -> None:
        super()._fill_parser(parser)  # type: ignore[arg-type]
        parser.add_argument(
            "parts",
            metavar="part-name",
            type=str,
            nargs="*",
            help="Optional list of parts to process",
        )

    @override
    def _run_lifecycle(
        self, parsed_args: argparse.Namespace, step_name: str | None = None
    ) -> None:
        """Run the lifecycle, optionally for a part or list of parts."""
        self._services.lifecycle.run(
            step_name=step_name,
            part_names=parsed_args.parts,
        )


class PullCommand(LifecyclePartsCommand):
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


class OverlayCommand(LifecyclePartsCommand):
    """Command to overlay parts."""

    name = "overlay"
    help_msg = "Create part layers over the base filesystem."
    overview = textwrap.dedent(
        """
        Execute operations defined for each part on a layer over the base
        filesystem, potentially modifying its contents.
        """
    )


class BuildCommand(LifecyclePartsCommand):
    """Command to build parts."""

    name = "build"
    help_msg = "Build artifacts defined for a part"
    overview = textwrap.dedent(
        """
        Build artifacts defined for a part. If part names are specified only
        those parts will be built, otherwise all parts will be built.
        """
    )


class StageCommand(LifecyclePartsCommand):
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


class PrimeCommand(LifecyclePartsCommand):
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

    @override
    def _run(
        self,
        parsed_args: argparse.Namespace,
        step_name: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Run the prime command."""
        super()._run(parsed_args, step_name=step_name)
        if self._use_provider(parsed_args=parsed_args):
            return
        # Only run the post prime steps in the process that
        # ran the lifecycle
        self._run_post_prime_steps()


class PackCommand(LifecycleCommand):
    """Command to pack the final artifact."""

    always_load_project = True

    name = "pack"
    help_msg = "Create the final artifact"
    overview = textwrap.dedent(
        """
        Process parts and create the final artifact.
        """
    )

    @override
    def _fill_parser(self, parser: argparse.ArgumentParser) -> None:
        super()._fill_parser(parser)

        parser.add_argument(
            "--output",
            "-o",
            type=pathlib.Path,
            default=pathlib.Path(),
            help="Output directory for created packages.",
        )

        parser.add_argument(
            "--enable-fetch-service",
            help=argparse.SUPPRESS,
            choices=("strict", "permissive"),
            metavar="policy",
            dest="fetch_service_policy",
        )

    def _run_real(
        self,
        parsed_args: argparse.Namespace,
        step_name: str | None = None,
    ) -> None:
        """Run the actual pack command."""
        if step_name not in ("pack", None):
            raise RuntimeError(f"Step name {step_name} passed to pack command.")

        shell = getattr(parsed_args, "shell", False)
        shell_after = getattr(parsed_args, "shell_after", False)
        debug = getattr(parsed_args, "debug", False)

        # Prevent the steps in the prime command from using `--shell` or `--shell-after`
        parsed_args.shell = False
        parsed_args.shell_after = False

        super()._run(parsed_args, step_name="prime")
        self._run_post_prime_steps()

        if shell:
            _launch_shell()
            return

        emit.progress("Packing...")
        try:
            packages = self._services.package.pack(
                self._services.lifecycle.prime_dir, parsed_args.output
            )
        except Exception as err:
            if debug:
                emit.progress(str(err), permanent=True)
                _launch_shell()
            raise

        if parsed_args.fetch_service_policy and packages:
            self._services.fetch.create_project_manifest(packages)

        if not packages:
            emit.progress("No packages created.", permanent=True)
        elif len(packages) == 1:
            emit.progress(f"Packed {packages[0].name}", permanent=True)
        else:
            package_names = ", ".join(pkg.name for pkg in packages)
            emit.progress(f"Packed: {package_names}", permanent=True)

        if shell_after:
            _launch_shell()

    @override
    def _run(
        self,
        parsed_args: argparse.Namespace,
        step_name: str | None = None,
        **kwargs: Any,
    ) -> None:
        if self._use_provider(parsed_args=parsed_args):
            return super()._run(parsed_args=parsed_args, step_name=step_name)
        return self._run_real(parsed_args=parsed_args, step_name=step_name)


class TestCommand(PackCommand):
    """Command to run project tests.

    The test command invokes the spread command with a processed spread.yaml
    configuration file.

    This command is opt-in for applications in craft-application 5 and will become
    a standard lifecycle command in a future major release.
    """

    name = "test"
    help_msg = "Run project tests"
    overview = textwrap.dedent(
        """
        Run spread tests for the project.
        """
    )
    common = True

    @override
    def _fill_parser(self, parser: argparse.ArgumentParser) -> None:
        # Skip the parser additions that `pack` adds.
        super(LifecycleCommand, self)._fill_parser(parser)

    @override
    def _run(
        self,
        parsed_args: argparse.Namespace,
        step_name: str | None = None,
        **kwargs: Any,
    ) -> None:
        if not util.is_managed_mode():
            emit.progress(
                "The test command is experimental and subject to change without warning.",
                permanent=True,
            )
        # Output into the spread directory.
        parsed_args.output = pathlib.Path.cwd() / "spread"
        parsed_args.output.mkdir(exist_ok=True)
        parsed_args.fetch_service_policy = None

        # Pack the packages.
        super()._run(parsed_args, step_name, **kwargs)

        if util.is_managed_mode():
            # Run the rest of this outside the managed instance.
            return

        emit.progress("Testing project")
        self._services.get("testing").test(pathlib.Path.cwd())
        emit.progress("Tests succeeded")


class CleanCommand(_BaseLifecycleCommand):
    """Command to remove part assets."""

    always_load_project = True
    name = "clean"
    help_msg = "Remove a part's assets"
    overview = textwrap.dedent(
        """
        Clean up artifacts belonging to parts. If no parts are specified,
        remove the packing environment.
        """
    )

    @override
    def _fill_parser(self, parser: argparse.ArgumentParser) -> None:
        super()._fill_parser(parser)  # type: ignore[arg-type]
        parser.add_argument(
            "parts",
            metavar="part-name",
            type=str,
            nargs="*",
            help="Optional list of parts to process",
        )
        parser.add_argument(
            "--platform",
            type=str,
            metavar="name",
            help="Platform to clean",
        )

    @override
    def _run(
        self,
        parsed_args: argparse.Namespace,
        **kwargs: Any,
    ) -> None:
        """Run the clean command.

        The project's work directory will be cleaned if:
        - the `--destructive-mode` flag is provided OR
        - `CRAFT_BUILD_ENVIRONMENT` is set to `host` OR
        - no list of specific parts to clean is provided

        Otherwise, it will clean an instance.
        """
        super()._run(parsed_args)

        build_managed = self._use_provider(parsed_args)
        clean_instances = self._should_clean_instances(parsed_args)

        if build_managed and clean_instances:
            self._services.provider.clean_instances()
        elif build_managed:
            self._run_manager_for_build_plan(fetch_service_policy=None)
        else:
            self._services.get("lifecycle").clean(parsed_args.parts)

    @staticmethod
    def _should_clean_instances(parsed_args: argparse.Namespace) -> bool:
        return not bool(parsed_args.parts)


def _launch_shell() -> None:
    """Launch a user shell for debugging environment."""
    emit.progress("Launching shell on build environment...", permanent=True)
    with emit.pause():
        subprocess.run(["bash"], check=False)
