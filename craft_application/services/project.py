# Copyright 2025 Canonical Ltd.
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
"""A service for handling access to the project."""

from __future__ import annotations

import copy
import os
import pathlib
from typing import TYPE_CHECKING, Any, Literal, cast, final

import craft_parts
import craft_platforms
import pydantic
from craft_cli import emit

from craft_application import errors, grammar, util
from craft_application.models import Platform
from craft_application.models.grammar import GrammarAwareProject

from . import base

if TYPE_CHECKING:
    from craft_application import models
    from craft_application.application import AppMetadata

    from .service_factory import ServiceFactory


class ProjectService(base.AppService):
    """A service for handling access to the project."""

    __platforms: dict[str, craft_platforms.PlatformDict] | None
    __project_file_path: pathlib.Path | None
    __raw_project: dict[str, Any] | None
    _project_dir: pathlib.Path
    _project_model: models.Project | None

    def __init__(
        self, app: AppMetadata, services: ServiceFactory, *, project_dir: pathlib.Path
    ) -> None:
        super().__init__(app, services)
        self.__platforms = None
        self.__partitions: list[str] | None = None
        self.__project_file_path = None
        self.__raw_project: dict[str, Any] | None = None
        self._project_dir = project_dir
        self._project_model = None
        self._build_on: craft_platforms.DebianArchitecture | None = None
        self._build_for: str | None = None
        self._platform: str | None = None

    @final
    def configure(self, *, platform: str | None, build_for: str | None) -> None:
        """Configure the prime project to render.

        This method configures the settings of our prime project rendering -
        that is, the one that will be used for the project that is cached.
        """
        self._build_on = craft_platforms.DebianArchitecture.from_host()
        if self.is_configured:
            raise RuntimeError("Project is already configured.")

        platforms = self.get_platforms()
        # This is needed if a child class doesn't necessarily vectorise all platforms
        # in get_platforms. This is needed for charmcraft's multi-platforms.
        if None in platforms.values():
            self._vectorise_platforms(platforms)
        if platform and platform not in platforms:
            raise errors.InvalidPlatformError(platform, list(platforms.keys()))

        if platform and build_for:
            self._platform = platform
            self._build_for = self._convert_build_for(build_for)
            self.__is_configured = True
            return

        if not platform:
            # If we don't have a platform, select the first platform that matches
            # our build-on and build-for. If we don't have a build-for, select the
            # first platform that matches our build-on.
            for name, data in platforms.items():
                if self._build_on.value not in data["build-on"]:
                    continue
                if build_for and build_for not in data["build-for"]:
                    continue
                platform = name
                break
            else:
                if build_for:
                    # Gives a clean error if the value of build_for is invalid.
                    self._convert_build_for(build_for)
                    raise errors.ProjectGenerationError(
                        f"Cannot generate a project that builds on "
                        f"{self._build_on} and builds for {build_for}"
                    )
                # We won't be able to build in this case, but the project is
                # still valid for non-lifecycle commands. Our prime project will
                # just be the first item available.
                platform = next(iter(platforms))
                self._platform = platform
                build_for = platforms[platform]["build-for"][0]
                self._build_for = self._convert_build_for(build_for)
                self._build_on = self._convert_build_on(
                    platforms[platform]["build-on"][0]
                )
                self.__is_configured = True
                return
        self._platform = platform

        if not build_for:
            # Any build-for in the platform is fine. For most crafts this is the
            # only build-for in the platform.
            build_for = platforms[platform]["build-for"][0]
        self._build_for = self._convert_build_for(build_for)
        self.__is_configured = True

    @property
    @final
    def is_configured(self) -> bool:
        """Whether the project has already been rendered."""
        return None not in (self._build_on, self._build_for, self._platform)

    @property
    def project_file_name(self) -> str:
        """Get filename of the project file."""
        return f"{self._app.name}.yaml"

    def resolve_project_file_path(self) -> pathlib.Path:
        """Get the path to the project file from the root project directory.

        The default behaviour is to find the project file directly in the directory
        based on the app name or raise an exception. However, an application may
        override this if necessary. For example, Snapcraft needs to override this to
        check other possible directories.

        :param project_dir: The base project directory to search.
        :returns: The path to the extant project file
        :raises: ProjectFileMissingError if the project file could not be found.
        """
        if self.__project_file_path:
            return self.__project_file_path
        if not self._project_dir.is_dir():
            if not self._project_dir.exists():
                raise errors.ProjectDirectoryMissingError(self._project_dir)
            raise errors.ProjectDirectoryTypeError(self._project_dir)
        try:
            path = (self._project_dir / self.project_file_name).resolve(strict=True)
        except FileNotFoundError as err:
            raise errors.ProjectFileMissingError(
                f"Project file {self.project_file_name!r} not found in '{self._project_dir}'.",
                details="The project file could not be found.",
                resolution="Ensure the project file exists.",
                retcode=os.EX_NOINPUT,
            ) from err
        emit.trace(f"Project file found at {path}")
        self.__project_file_path = path
        return path

    @final
    def _load_raw_project(self) -> dict[str, Any]:
        """Get the raw project data structure.

        This loads the project file from the given path, parses the YAML, and returns
        that raw data structure. This method should be used with care, as the project
        does not have any preprocessors applied.
        """
        if self.__raw_project:
            return self.__raw_project
        project_path = self.resolve_project_file_path()
        with project_path.open() as project_file:
            emit.debug(f"Loading project file '{project_path!s}")
            raw_yaml = util.safe_yaml_load(project_file)
        if not isinstance(raw_yaml, dict):
            raise errors.ProjectFileInvalidError(raw_yaml)
        self.__raw_project = cast(dict[str, Any], raw_yaml)
        return self.__raw_project

    @final
    def get_raw(self) -> dict[str, Any]:
        """Get the raw project data structure."""
        return copy.deepcopy(self._load_raw_project())

    def _app_render_legacy_platforms(self) -> dict[str, craft_platforms.PlatformDict]:
        """Application-specific rendering function if no platforms are declared.

        This method is intended to be overridden by an application-specific service
        if the root project has no ``platforms`` key. In this case, it should return
        a dictionary structured the same way as the ``platforms`` key in a project
        for use in that project. This dictionary is less strict than what is expected
        in the project file's ``platforms`` key. For example, the ``build-for``
        key for each platform **MAY** contain multiple targets.
        """
        raise errors.CraftValidationError(
            f"{self._app.name}.yaml must contain a 'platforms' key."
        )

    @staticmethod
    def _vectorise_platforms(platforms: dict[str, Any]) -> None:
        """Vectorise the platforms dictionary in place."""
        for name, data in platforms.items():
            if data is None:
                try:
                    _, arch = craft_platforms.parse_base_and_architecture(name)
                except ValueError:
                    continue
                if arch == "all":
                    continue
                platforms[name] = {
                    "build-on": [name],
                    "build-for": [name],
                }
                continue
            # Non-vector versions of architectures. These are accepted,
            # but are not included in the schema.
            if "build-on" in data and isinstance(data["build-on"], str):
                data["build-on"] = [data["build-on"]]
            # Semi-shorthand where only build-on is provided. This
            # is also not validated by the schema, but is accepted.
            if data.get("build-for") is None and name in (
                *craft_platforms.DebianArchitecture,
                "all",
            ):
                data["build-for"] = [name]
            if "build-for" in data and isinstance(data["build-for"], str):
                data["build-for"] = [data["build-for"]]

    @classmethod
    def _preprocess_platforms(
        cls, platforms: dict[str, craft_platforms.PlatformDict]
    ) -> dict[str, craft_platforms.PlatformDict]:
        """Validate that the given platforms value is valid."""
        if platforms:
            cls._vectorise_platforms(platforms)
        platforms_project_adapter = pydantic.TypeAdapter(
            dict[Literal["platforms"], dict[str, Platform]],
        )
        return platforms_project_adapter.dump_python(  # type: ignore[no-any-return]
            platforms_project_adapter.validate_python({"platforms": platforms}),
            mode="json",
            by_alias=True,
            exclude_defaults=True,
        )["platforms"]

    @final
    def get_platforms(self) -> dict[str, craft_platforms.PlatformDict]:
        """Get the platforms definition for the project.

        The platforms definition must always be immediately able to be rendered from
        the raw YAML. This means that platforms cannot contain grammar, they cannot
        be defined by extensions, etc.
        """
        if self.__platforms:
            return copy.deepcopy(self.__platforms)
        raw_project = self.get_raw()
        if "platforms" not in raw_project:
            return self._app_render_legacy_platforms()

        try:
            self.__platforms = self._preprocess_platforms(raw_project["platforms"])
        except pydantic.ValidationError as exc:
            raise errors.CraftValidationError.from_pydantic(
                exc,
                file_name=self.project_file_name,
            ) from None
        self._validate_multi_base(self.__platforms)
        return copy.deepcopy(self.__platforms)

    def _validate_multi_base(
        self, platforms: dict[str, craft_platforms.PlatformDict]
    ) -> None:
        """Ensure that the given platforms are not multi-base.

        An application that supports multi-base platforms entries can override this
        method to do any validation of multi-base platforms it may need.

        :param platforms: The platforms mapping to ensure is multi-base.
        :raises: CraftValidationError if the app does not support multi-base and one
            or more platforms use multi-base structure.
        """
        if self._app.supports_multi_base:
            return
        multi_base_platforms: set[str] = set()
        for name, data in platforms.items():
            if not data:
                base, _ = craft_platforms.parse_base_and_architecture(name)
                if base:
                    multi_base_platforms.add(name)
            else:
                for value in (*data.get("build-on", ()), *data.get("build-for", ())):
                    base, _ = craft_platforms.parse_base_and_architecture(value)
                    if base:
                        multi_base_platforms.add(name)
        if multi_base_platforms:
            invalid_platforms_str = ", ".join(repr(p) for p in multi_base_platforms)
            raise errors.CraftValidationError(
                f"{self._app.name.title()} does not support multi-base platforms",
                resolution=f"Remove multi-base structure from these platforms: {invalid_platforms_str}",
                logpath_report=False,
                retcode=os.EX_DATAERR,
            )

    @final
    def _get_project_vars(self, yaml_data: dict[str, Any]) -> dict[str, str]:
        """Return a dict with project variables to be expanded."""
        return {var: str(yaml_data.get(var, "")) for var in self._app.project_variables}

    def get_partitions_for(
        self,
        *,  # The keyword args here may be used by child class overrides.
        platform: str,  # noqa: ARG002
        build_for: str,  # noqa: ARG002
        build_on: craft_platforms.DebianArchitecture,  # noqa: ARG002
    ) -> list[str] | None:
        """Get the partitions for a destination of this project.

        The default implementation gets partitions for an application that does not
        have partitions. Applications that will enable partitions must override this
        method.
        """
        return None

    @property
    @final
    def partitions(self) -> list[str] | None:
        """The partitions for the prime project."""
        if not self.is_configured:
            raise RuntimeError("Project not configured yet.")

        if not self.__partitions:
            self.__partitions = self.get_partitions_for(
                platform=cast(str, self._platform),
                build_for=cast(str, self._build_for),
                build_on=cast(craft_platforms.DebianArchitecture, self._build_on),
            )
        return self.__partitions

    @staticmethod
    def _app_preprocess_project(
        project: dict[str, Any],
        *,
        build_on: str,
        build_for: str,
        platform: str,
    ) -> None:
        """Run any application-specific pre-processing on the project, in-place.

        This includes any application-specific transformations on a project's raw data
        structure before it gets rendered as a pydantic model. Some examples of
        processing to do here include:

        - Applying extensions
        - Adding "hidden" app-specific parts
        - Processing grammar for keys other than parts
        """

    @final
    def _expand_environment(
        self,
        project_data: dict[str, Any],
        *,
        platform: str,
        build_for: str,
        build_on: craft_platforms.DebianArchitecture,
    ) -> None:
        """Perform expansion of project environment variables.

        :param project_data: The project's yaml data.
        :param build_for: The architecture to build for.
        """
        # We can use "all" directly after resolving:
        # https://github.com/canonical/craft-parts/issues/1019
        if build_for == "all":
            host_arch = craft_platforms.DebianArchitecture.from_host()
            for target in craft_platforms.DebianArchitecture:
                if target != host_arch:
                    build_for = target.value
                    break
            else:
                raise ValueError(
                    "Could not find an architecture other than the host architecture "
                    "to set as the build-for architecture. This is a bug in "
                    f"{self._app.name} or craft-application."
                )
            emit.debug(
                "Expanding environment variables with the architecture "
                f"{build_for!r} as the build-for architecture because 'all' was "
                "specified."
            )

        environment_vars = self._get_project_vars(project_data)
        partitions = self.get_partitions_for(
            platform=platform, build_for=build_for, build_on=build_on
        )
        work_dir = util.get_work_dir(self._project_dir)
        project_dirs = craft_parts.ProjectDirs(work_dir=work_dir, partitions=partitions)
        info = craft_parts.ProjectInfo(
            application_name=self._app.name,  # not used in environment expansion
            cache_dir=pathlib.Path(),  # not used in environment expansion
            arch=str(self._convert_build_for(build_for)),
            parallel_build_count=util.get_parallel_build_count(self._app.name),
            project_name=project_data.get("name", ""),
            project_dirs=project_dirs,
            project_vars=environment_vars,
            partitions=partitions,
        )

        self.update_project_environment(info)
        craft_parts.expand_environment(project_data, info=info)

    @final
    def _preprocess(
        self,
        *,
        build_for: str,
        build_on: str,
        platform: str,
    ) -> dict[str, Any]:
        """Preprocess the project for the given build-on, build-for and platform.

        This method provides a project dict that has gone through any app-specific
        pre-processing and has had its grammar validated, has not had environment
        expansion or parts grammar applied.

        This method is for internal use only, such as for getting partitions.

        :param build_for: The target architecture of the build.
        :param platform: The name of the target platform.
        :param build_on: The host architecture the build happens on.
        :returns: A dict containing a pre-processed project.
        """
        project = self.get_raw()
        GrammarAwareProject.validate_grammar(project)
        self._app_preprocess_project(
            project, build_on=build_on, build_for=build_for, platform=platform
        )
        return project

    @final
    def render_for(
        self,
        *,
        build_for: str,
        build_on: str,
        platform: str,
    ) -> models.Project:
        """Render the project for a specific combination of archs/platforms..

        This method does not guarantee that the project will be buildable with the
        given parameters or that the parameters even correspond to something a build
        plan would generate.

        :param build_for: The target architecture of the build.
        :param platform: The name of the target platform.
        :param build_on: The host architecture the build happens on.
        :returns: A Project model containing the project rendered as above.
        """
        platforms = self.get_platforms()
        if platform not in platforms:
            raise errors.InvalidPlatformError(platform, sorted(platforms.keys()))

        project = self._preprocess(
            build_for=build_for, build_on=build_on, platform=platform
        )
        project["platforms"] = platforms
        self._expand_environment(
            project,
            build_on=craft_platforms.DebianArchitecture(build_on),
            build_for=build_for,
            platform=platform,
        )

        # Process grammar.
        if "parts" in project:
            emit.debug(f"Processing grammar (on {build_on} for {build_for})")
            project["parts"] = grammar.process_parts(
                parts_yaml_data=project["parts"],
                arch=build_on,
                target_arch=build_for,
            )
        project_model = self._app.ProjectClass.from_yaml_data(
            project, self.resolve_project_file_path()
        )

        if not project_model.adopt_info:
            missing_fields: set[str] = set()
            for field in self._app.mandatory_adoptable_fields:
                if not getattr(project_model, field, None):
                    missing_fields.add(field)
            if missing_fields:
                missing = ", ".join(repr(field) for field in sorted(missing_fields))
                raise errors.CraftValidationError(
                    f"'adopt-info' not set and required fields are missing: {missing}"
                )

        return project_model

    def update_project_environment(self, info: craft_parts.ProjectInfo) -> None:
        """Update a ProjectInfo's global environment."""
        info.global_environment.update(
            {
                "CRAFT_PROJECT_VERSION": info.get_project_var("version", raw_read=True),
            }
        )

    @final
    def get(self) -> models.Project:
        """Get the rendered project.

        :returns: The project model.
        :raises: RuntimeError if the project has not been configured.
        """
        if not self.is_configured:
            raise RuntimeError("Project not configured yet.")

        if not self._project_model:
            self._project_model = self.render_for(
                build_for=cast(str, self._build_for),
                build_on=str(self._build_on),
                platform=cast(str, self._platform),
            )
        return self._project_model

    @staticmethod
    def _convert_build_for(
        architecture: str,
    ) -> craft_platforms.DebianArchitecture | Literal["all"]:
        """Convert a build-for value to a valid internal value.

        :param architecture: A valid build-for architecture as a string
        :returns: The architecture as a DebianArchitecture or the special case string "all"
        :raises: CraftValidationError if the given value is not valid for build-for.
        """
        # Convert distro@series:architecture to just the architecture.
        architecture = architecture.rpartition(":")[2]
        try:
            return (
                "all"
                if architecture == "all"
                else craft_platforms.DebianArchitecture(architecture)
            )
        except ValueError:
            raise errors.CraftValidationError(
                f"{architecture!r} is not a valid Debian architecture",
                resolution="Use a supported Debian architecture name.",
                reportable=False,
                logpath_report=False,
            ) from None

    @staticmethod
    def _convert_build_on(
        architecture: str,
    ) -> craft_platforms.DebianArchitecture:
        """Convert a build-on value to a valid internal value.

        :param architecture: A valid build-for architecture as a string
        :returns: The architecture as a DebianArchitecture
        :raises: CraftValidationError if the given value is not valid for build-for.
        """
        # Convert distro@series:architecture to just the architecture.
        architecture = architecture.rpartition(":")[2]
        try:
            return craft_platforms.DebianArchitecture(architecture)
        except ValueError:
            raise errors.CraftValidationError(
                f"{architecture!r} is not a valid Debian architecture",
                resolution="Use a supported Debian architecture name.",
                reportable=False,
                logpath_report=False,
            ) from None
