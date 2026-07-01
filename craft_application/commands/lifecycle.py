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
import os
import pathlib
import subprocess
import textwrap
from typing import Any, Literal, cast

import pydantic
from craft_cli import CommandGroup, CraftError, emit
from craft_parts.features import Features
from typing_extensions import override

from craft_application import errors, util
from craft_application.commands import base
from craft_application.errors import TestFileError
from craft_application.util import ProServices
from craft_application.util.error_formatting import format_pydantic_errors
from craft_application.util.logging import handle_runtime_error


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

    return CommandGroup("Lifecycle", commands, ordered=True)


class _BaseLifecycleCommand(base.ExtensibleCommand):
    """Base class for lifecycle-related commands.

    All lifecycle commands must know where to execute (locally or in a build
    environment) but do not have to provide shell access into the environment.
    """

    _allow_destructive: bool = True
    _show_lxd_arg: bool = True

    @override
    def _run(self, parsed_args: argparse.Namespace, **kwargs: Any) -> None:
        emit.trace(f"lifecycle command: {self.name!r}, arguments: {parsed_args!r}")
        if (
            not self._use_provider(parsed_args)
            and not util.is_managed_mode()
            and os.geteuid() != 0
        ):
            emit.warning(
                "Running in destructive mode as a non-super user is not recommended and may cause unexpected behavior."
            )

        self._pro_precheck(parsed_args)

    def _pro_precheck(self, parsed_args: argparse.Namespace) -> None:
        # If no pro services were requested, this is `ProServices()` rather than None
        # None is for commands that explicitly don't choose to support pro
        pro_services = cast(ProServices | None, getattr(parsed_args, "pro", None))
        if pro_services is None:
            return

        pro_services.check_pro_context(
            run_managed=self._use_provider(parsed_args),
            is_managed=util.is_managed_mode(),
        )

    @override
    def _fill_parser(self, parser: argparse.ArgumentParser) -> None:
        super()._fill_parser(parser)

        group = parser.add_mutually_exclusive_group()
        if self._allow_destructive:
            group.add_argument(
                "--destructive-mode",
                action="store_true",
                help="Build in the current host",
            )
        if self._show_lxd_arg:
            group.add_argument(
                "--use-lxd",
                action="store_true",
                help="Build in a LXD container.",
            )

    @override
    def provider_name(self, parsed_args: argparse.Namespace) -> str | None:
        return "lxd" if getattr(parsed_args, "use_lxd", None) else None

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

    _allow_build_for: bool = True

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

        if self._app.enable_pro_support:
            supported_pro_services = ", ".join(
                [f"'{name}'" for name in sorted(ProServices.supported_services)]
            )

            parser.add_argument(
                "--pro",
                type=ProServices.from_csv,
                metavar="<pro-services>",
                help=(
                    "Enable Ubuntu Pro services for this command. "
                    f"Supported values include: {supported_pro_services}. "
                    "Multiple values can be passed separated by commas. "
                    "Note: This feature requires an Ubuntu Pro compatible host and build base."
                ),
                default=ProServices(),
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
        if self._allow_build_for:
            group.add_argument(
                "--build-for",
                type=str,
                metavar="arch",
                help="Set architecture to build for",
            )
        ignore_restrictions: set[str] = set()
        if self._app.check_supported_base:
            ignore_restrictions.add("unmaintained")
        if ignore_restrictions:
            parser.add_argument(
                "--ignore",
                nargs="*",
                default=[],
                choices=sorted(ignore_restrictions),
                help="Bypass a restriction to use an unsupported feature.",
            )

    def _check_supported_base(self, parsed_args: argparse.Namespace) -> None:
        """Check whether the base is supported.

        :raises: CraftValidationError if building on an unsupported base without
            explicitly acknowledging that fact.
        """
        if not self._app.check_supported_base:
            return
        project_service = self._services.get("project")
        project = project_service.get()
        ignore_items = getattr(parsed_args, "ignore", [])
        if "unmaintained" in ignore_items:
            if project_service.is_effective_base_eol():
                emit.progress(
                    f"Using end-of-life base {project.effective_base!r}.",
                    permanent=True,
                )
        else:
            project_service.check_base_is_supported(verb=self.name)
            base = project.effective_base
            if eol_date := project_service.base_eol_soon_date():
                emit.progress(
                    f"Using base {base!r}, which will enter end-of-life on {eol_date.isoformat()}.",
                    permanent=True,
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

        # If we check for supported bases, fail early for all unsupported bases.
        self._check_supported_base(parsed_args)

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
                self._services.get("fetch").set_policy(fetch_service_policy)
            self._run_manager_for_build_plan(fetch_service_policy)
            return

        lifecycle = self.services.get("lifecycle")

        shell = getattr(parsed_args, "shell", False)
        shell_after = getattr(parsed_args, "shell_after", False)
        debug = getattr(parsed_args, "debug", False)

        step_name = step_name or self.name

        if shell:
            previous_step = lifecycle.previous_step_name(step_name)
            step_name = previous_step
            shell_after = True

        try:
            self._run_lifecycle(parsed_args, step_name)
        except Exception as err:
            if debug:
                handle_runtime_error(self._app, err)
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
        self._services.get("lifecycle").run(step_name=step_name)

    def _run_post_prime_steps(self) -> None:
        """Run post-prime steps."""
        self._services.package.update_project()
        self._services.package.write_metadata(self.services.get("lifecycle").prime_dir)

    def _run_post_prime_steps_with_debug_handler(self, *, debug: bool) -> None:
        """Run post-prime steps, launching a shell on failure if debug is enabled."""
        try:
            self._run_post_prime_steps()
        except Exception as err:
            if debug:
                handle_runtime_error(self._app, err)
                _launch_shell()
            raise

    @staticmethod
    def _should_add_shell_args() -> bool:
        return True


class LifecyclePartsCommand(LifecycleCommand):
    """A command that can run the lifecycle for a particular part."""

    # All lifecycle-related commands need a project to work
    always_load_project = True

    @override
    def _fill_parser(self, parser: argparse.ArgumentParser) -> None:
        super()._fill_parser(parser)
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
        self.services.get("lifecycle").run(
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
        self._run_post_prime_steps_with_debug_handler(
            debug=getattr(parsed_args, "debug", False)
        )


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
        output_dir = getattr(parsed_args, "output", pathlib.Path())

        super()._run(parsed_args, step_name="prime")
        self._run_post_prime_steps_with_debug_handler(debug=debug)
        self._services.package.set_output_dir(output_dir)

        if shell:
            _launch_shell()
            return

        if self._services.package.supports_conditional_repack is True:
            self._run_pack(parsed_args, shell_after=shell_after, debug=debug)
            return

        emit.progress("Packing...")
        try:
            packages = self._services.package.pack(
                self.services.get("lifecycle").prime_dir, parsed_args.output
            )
        except Exception as err:
            if debug:
                emit.progress(str(err), permanent=True)
                _launch_shell()
            raise

        packages = self._relativize_paths(packages, root=pathlib.Path())

        if getattr(parsed_args, "fetch_service_policy", None) and packages:
            self._services.fetch.create_project_manifest(packages)

        if not packages:
            emit.progress("No packages created.", permanent=True)
            artifact, resources = None, None
        elif len(packages) == 1:
            emit.progress(f"Packed {packages[0].name}", permanent=True)
            artifact, resources = packages[0], None
        else:
            package_names = ", ".join(pkg.name for pkg in packages)
            emit.progress(f"Packed: {package_names}", permanent=True)
            artifact, resources = packages[0], self._services.package.resource_map

        self._services.package.write_state(artifact=artifact, resources=resources)

        if shell_after:
            _launch_shell()

    def _run_pack(
        self,
        parsed_args: argparse.Namespace,
        *,
        shell_after: bool,
        debug: bool,
    ) -> None:
        """Run the artifact-aware packing flow."""
        emit.progress("Packing...")
        package_service = self._services.package

        try:
            packed = package_service.pack_artifacts()
        except Exception as err:
            if debug:
                emit.progress(str(err), permanent=True)
                _launch_shell()
            raise

        artifact_paths = package_service.get_artifacts()
        normalized_all_paths = self._relativize_paths(
            list(artifact_paths.values()), root=pathlib.Path()
        )
        normalized_by_name = dict(
            zip(artifact_paths.keys(), normalized_all_paths, strict=True)
        )

        # Split the declared artifacts into the subset that was packed in this run and
        # the subset that was already current, while keeping the same artifact names
        # used by get_artifacts() for state writes and user-facing messages.
        normalized_packed_paths = [
            normalized_by_name[name] for name, did_pack in packed.items() if did_pack
        ]
        normalized_skipped_paths = [
            normalized_by_name[name] for name, did_pack in packed.items() if not did_pack
        ]

        if getattr(parsed_args, "fetch_service_policy", None) and normalized_packed_paths:
            self._services.fetch.create_project_manifest(normalized_packed_paths)

        package_service.write_artifacts_state(normalized_by_name)

        if not normalized_by_name:
            emit.progress("No packages created.", permanent=True)
        elif not normalized_packed_paths:
            emit.progress("Skipping pack (already ran)")
            files = ", ".join(str(path) for path in normalized_skipped_paths)
            emit.progress(f"Already packed: {files}", permanent=True)
        elif len(normalized_packed_paths) == 1 and not normalized_skipped_paths:
            emit.progress(f"Packed {normalized_packed_paths[0].name}", permanent=True)
        else:
            if normalized_packed_paths:
                packed_names = ", ".join(path.name for path in normalized_packed_paths)
                emit.progress(f"Packed: {packed_names}", permanent=True)
            if normalized_skipped_paths:
                skipped_names = ", ".join(str(path) for path in normalized_skipped_paths)
                emit.progress(f"Already packed: {skipped_names}", permanent=True)

        if shell_after:
            _launch_shell()

    @staticmethod
    def _relativize_paths(
        packages: list[pathlib.Path], root: pathlib.Path
    ) -> list[pathlib.Path]:
        """Normalize package paths to be relative to the project root.

        Convert absolute paths of the packed artifacts to paths relative
        to the project top directory, or raise an error if artifact paths
        are not inside the project tree.

        :param packages: The list of packaged artifact paths.
        :param root: The project root directory.

        :return: The normalized list of artifact paths.
        :raises: ArtifactCreationError if a path is invalid.
        """
        resolved_root = root.resolve()
        normalized: list[pathlib.Path] = []
        invalid: list[pathlib.Path] = []
        emit.debug(f"packages paths: {packages}")
        emit.debug(f"resolved root: {resolved_root}")

        for package in packages:
            path = package.resolve()
            if path.is_relative_to(resolved_root):
                normalized.append(path.relative_to(resolved_root))
            else:
                invalid.append(package)

        if invalid:
            invalid_files = "\n".join([f"- {name}" for name in invalid])
            raise errors.ArtifactCreationError(
                "Cannot create packages outside of the project tree.",
                details=f"The following file paths are invalid:\n{invalid_files}",
                resolution="Change the output directory when packing.",
            )

        emit.debug(f"normalized packages paths: {normalized}")
        return normalized

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
    _allow_destructive = False
    _show_lxd_arg = False
    _allow_build_for = False

    # Stop pytest from thinking this is an actual test to run
    __test__ = False

    @override
    def _fill_parser(self, parser: argparse.ArgumentParser) -> None:
        # Skip the parser additions that `pack` adds.
        super(PackCommand, self)._fill_parser(parser)
        parser.add_argument(
            "test_expressions",
            nargs="*",
            type=str,
            default=(),
            help="Optional spread test expressions. If not provided, all craft backend tests are run.",
        )

    @override
    def _run(
        self,
        parsed_args: argparse.Namespace,
        step_name: str | None = None,
        **kwargs: Any,
    ) -> None:
        # Add values for super classes like pack.
        parsed_args.output = pathlib.Path.cwd()

        testing_service = self._services.get("testing")
        # Fail early if spread.yaml is invalid.
        try:
            testing_service.parse_spread_yaml()
        except pydantic.ValidationError as exc:
            raise TestFileError(
                format_pydantic_errors(exc.errors(), file_name="spread.yaml"),
                reportable=False,
                retcode=os.EX_DATAERR,
            )

        if util.is_managed_mode():
            # If we're in managed mode, we just need to pack.
            return super()._run(parsed_args=parsed_args, step_name=step_name, **kwargs)
        emit.progress(
            "The test command is experimental and subject to change without warning.",
            permanent=True,
        )

        build_planner = self._services.get("build_plan")
        if parsed_args.platform:
            os.environ["CRAFT_PLATFORM"] = parsed_args.platform
            build_planner.set_platforms(parsed_args.platform)
        package = self._services.get("package")
        provider = self._services.get("provider")

        fetch_service_policy = cast(
            Literal["strict", "permissive"] | None,
            getattr(parsed_args, "fetch_service_policy", None),
        )
        if fetch_service_policy:
            self._services.get("fetch").set_policy(fetch_service_policy)

        # Don't enter a shell during the packing step, but save those values
        # for the testing service.
        shell, shell_after = parsed_args.shell, parsed_args.shell_after
        parsed_args.shell, parsed_args.shell_after = (False, False)

        # This loop allows us to (pack, test) for each platform.
        for build_info in build_planner.plan():
            emit.progress(f"Packing platform '{build_info.platform}'")
            parsed_args.platform = build_info.platform
            provider.run_managed(
                build_info, enable_fetch_service=bool(fetch_service_policy)
            )
            pack_state = package.read_state(build_info.platform)
            if pack_state.artifact is None:
                raise CraftError(
                    f"No artifact was packed for platform '{build_info.platform}'",
                    resolution=f"Ensure platform '{build_info.platform}' packs correctly.",
                )
            emit.progress(f"Testing platform '{build_info.platform}'")
            testing_service.test(
                pathlib.Path.cwd(),
                pack_state=pack_state,
                test_expressions=parsed_args.test_expressions,
                shell=shell,
                shell_after=shell_after,
                debug=parsed_args.debug,
            )

        emit.progress("Testing successful.", permanent=True)
        return None


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
        super()._fill_parser(parser)
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
