#  This file is part of craft-application.
#
#  Copyright 2024 Canonical Ltd.
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

"""Service for initializing a project."""

import os
import pathlib
import shutil
from typing import Any

import jinja2
from craft_cli import emit

from craft_application.util import make_executable

from . import base


class InitService(base.AppService):
    """Service class for initializing a project."""

    def run(self, *, project_dir: pathlib.Path, name: str) -> None:
        """Initialize a new project."""
        context = self._get_context(name=name)
        template_dir = self._get_template_dir()
        environment = self._get_templates_environment(template_dir)
        executable_files = self._get_executable_files()

        self._create_project_dir(project_dir=project_dir, name=name)
        self._render_project(
            environment,
            project_dir,
            template_dir,
            context,
            executable_files,
        )

    def _copy_template_file(
        self,
        template_name: str,
        template_dir: pathlib.Path,
        project_dir: pathlib.Path,
    ) -> None:
        """Copy the non-ninja template from template_dir to project_dir.

        If the file already exists in the projects copying is skipped.

        :param project_dir: The directory to render the files into.
        :param template_dir: The directory where templates are stored.
        :param template_name: Name of the template to copy.
        """
        emit.debug(f"Copying file {template_name} to {project_dir}")
        template_file = template_dir / template_name
        destination_file = project_dir / template_name
        if destination_file.exists():
            emit.debug(f"Skipping file {template_name} because it is already present.")
            return
        destination_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(template_file, destination_file, follow_symlinks=False)

    def _render_project(
        self,
        environment: jinja2.Environment,
        project_dir: pathlib.Path,
        template_dir: pathlib.Path,
        context: dict[str, Any],
        executable_files: list[str],
    ) -> None:
        """Render files for a project from a template.

        :param environment: The Jinja environment to use.
        :param project_dir: The directory to render the files into.
        :param template_dir: The directory where templates are stored.
        :param context: The context to render the templates with.
        :param executable_files: The list of files that should be executable.
        """
        for template_name in environment.list_templates():
            if not template_name.endswith(".j2"):
                self._copy_template_file(template_name, template_dir, project_dir)
                continue
            template = environment.get_template(template_name)

            # trim off `.j2`
            rendered_template_name = template_name[:-3]
            emit.debug(f"Rendering {template_name} to {rendered_template_name}")

            path = project_dir / rendered_template_name
            if path.exists():
                emit.trace(f"Skipping file {template_name} as it is already present")
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("wt", encoding="utf8") as file:
                out = template.render(context)
                file.write(out)
                if rendered_template_name in executable_files and os.name == "posix":
                    make_executable(file)
                    emit.debug("  made executable")
        emit.message("Successfully initialised project.")

    def _get_template_dir(self) -> pathlib.Path:
        """Return the path to the template directory."""
        return pathlib.Path("templates")

    def _get_executable_files(self) -> list[str]:
        """Return the list of files that should be executable."""
        return []

    def _get_context(self, name: str) -> dict[str, Any]:
        """Get context to render templates with.

        :returns: A dict of context variables.
        """
        emit.debug(f"Set project name to '{name}'")

        return {"name": name}

    def _create_project_dir(
        self,
        project_dir: pathlib.Path,
        *,
        name: str,
    ) -> None:
        """Create the project path if it does not already exist."""
        if not project_dir.exists():
            project_dir.mkdir(parents=True)
        emit.debug(f"Using project directory {str(project_dir)!r} for {name}")

    def _get_loader(self, template_dir: pathlib.Path) -> jinja2.PackageLoader:
        """Return a Jinja template loader for the given template directory."""
        return jinja2.PackageLoader(self._app.name, str(template_dir))

    def _get_templates_environment(
        self, template_dir: pathlib.Path
    ) -> jinja2.Environment:
        """Create and return a Jinja environment to deal with the templates."""
        return jinja2.Environment(
            loader=self._get_loader(template_dir),
            autoescape=False,  # noqa: S701 (jinja2-autoescape-false)
            keep_trailing_newline=True,  # they're not text files if they don't end in newline!
            optimized=False,  # optimization doesn't make sense for one-offs
            undefined=jinja2.StrictUndefined,
        )  # fail on undefined
