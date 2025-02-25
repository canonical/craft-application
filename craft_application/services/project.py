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
from typing import TYPE_CHECKING, Any, cast, final

import craft_parts
import craft_platforms
from craft_cli import emit

from craft_application import errors, grammar, util
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
        self.__project_file_path = None
        self.__raw_project: dict[str, Any] | None = None
        self._project_dir = project_dir
        self._project_model = None

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
            path = (self._project_dir / f"{self._app.name}.yaml").resolve(strict=True)
        except FileNotFoundError as err:
            raise errors.ProjectFileMissingError(
                f"Project file '{self._app.name}.yaml' not found in '{self._project_dir}'.",
                details="The project file could not be found.",
                resolution="Ensure the project file exists.",
                retcode=os.EX_NOINPUT,
            ) from err
        emit.trace(f"Project file found at {path}")
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

    def _app_preprocess_project(
        self,
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

    @final
    def get_platforms(self) -> dict[str, craft_platforms.PlatformDict]:
        """Get the platforms definition for the project."""
        if self.__platforms:
            return self.__platforms.copy()
        raw_project = self._load_raw_project()
        if "platforms" not in raw_project:
            return self._app_render_legacy_platforms()

        platforms: dict[str, craft_platforms.PlatformDict] = raw_project["platforms"]
        for name, data in platforms.items():
            if data is None:
                platforms[name] = {"build-on": [name], "build-for": [name]}

        return platforms

    def _get_project_vars(self, yaml_data: dict[str, Any]) -> dict[str, str]:
        """Return a dict with project variables to be expanded."""
        return {var: str(yaml_data.get(var, "")) for var in self._app.project_variables}

    def get_partitions(self) -> list[str] | None:
        """Get the partitions this application needs for this project.

        Applications should override this method depending on how they determine
        partitions.
        """
        if craft_parts.Features().enable_partitions:
            return ["default"]
        return None

    @final
    def _expand_environment(
        self,
        project_data: dict[str, Any],
        build_for: str,
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
        partitions = self.get_partitions()
        project_dirs = craft_parts.ProjectDirs(
            work_dir=self._project_dir, partitions=partitions
        )
        info = craft_parts.ProjectInfo(
            application_name=self._app.name,  # not used in environment expansion
            cache_dir=pathlib.Path(),  # not used in environment expansion
            arch=build_for,
            parallel_build_count=util.get_parallel_build_count(self._app.name),
            project_name=project_data.get("name", ""),
            project_dirs=project_dirs,
            project_vars=environment_vars,
            partitions=partitions,
        )

        self.update_project_environment(info)
        craft_parts.expand_environment(project_data, info=info)

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

        project = copy.deepcopy(self._load_raw_project())

        GrammarAwareProject.validate_grammar(project)
        self._app_preprocess_project(
            project, build_on=build_on, build_for=build_for, platform=platform
        )
        self._expand_environment(project, build_for=build_for)

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

    @property
    @final
    def is_rendered(self) -> bool:
        """Whether the project has already been rendered."""
        return self._project_model is not None

    @final
    def get(self) -> models.Project:
        """Get the rendered project.

        :returns: The project model.
        :raises: RuntimeError if the project has not been rendered.
        """
        if not self._project_model:
            raise RuntimeError("Project not rendered yet.")
        return self._project_model

    @final
    def render_once(
        self,
        *,
        platform: str | None = None,
        build_for: str | None = None,
    ) -> models.Project:
        """Render the project model for this run.

        This should only be called by the Application for initial setup of the project.
        Everything else should use :py:meth:`get`.

        If build_for or platform is not set, it tries to select the appropriate one.
        Which value is selected is not guaranteed unless both a build_for and platform
        are passed. If an application requires that each platform only build for
        exactly one target, passing only platform will guarantee a repeatable output.

        :param platform: The platform build name.
        :param build_for: The destination architecture (or base:arch)
        :returns: The rendered project
        :raises: RuntimeError if the project has already been rendered.
        """
        if self._project_model:
            raise RuntimeError("Project should only be rendered once.")

        build_on = craft_platforms.DebianArchitecture.from_host()
        if not platform or not build_for:
            platforms = self.get_platforms()
            if not platform:
                # If we don't have a platform, select the first platform that matches
                # our build-on and build-for. If we don't have a build-for, select the
                # first platform that matches our build-for.
                for name, data in platforms.items():
                    if build_on.value not in data["build-on"]:
                        continue
                    if build_for and build_for not in data["build-for"]:
                        continue
                    platform = name
                    break
                else:
                    if build_for:
                        raise RuntimeError(
                            f"Cannot generate a project that builds on {build_on} and "
                            f"builds for {build_for}"
                        )
                    # We won't be able to build in this case, but the project is
                    # still valid for non-lifecycle commands. Render for anything.
                    platform = next(iter(platforms))
                    self._project_model = self.render_for(
                        platform=platform,
                        build_for=platforms[platform]["build-for"][0],
                        build_on=platforms[platform]["build-on"][0],
                    )
                    return self._project_model
            # Any build-for in the platform is fine. For most crafts this is the
            # only build-for in the platform.
            build_for = platforms[platform]["build-for"][0]

        self._project_model = self.render_for(
            build_for=build_for, build_on=build_on, platform=platform
        )
        return self._project_model
