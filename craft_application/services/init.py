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

from craft_application.errors import InitError

from . import base


class InitService(base.AppService):
    """Service class for initializing a project."""

    def initialise_project(
        self,
        *,
        project_dir: pathlib.Path,
        project_name: str,
        template_dir: pathlib.Path,
    ) -> None:
        """Initialise a new project from a template.

        If a file already exists in the project directory, it is not overwritten.
        Use `check_for_existing_files()` to see if this will occur before initialising
        the project.

        :param project_dir: The directory to initialise the project in.
        :param project_name: The name of the project.
        :param template_dir: The directory containing the templates.
        """
        emit.debug(
            f"Initialising project {project_name!r} in {str(project_dir)!r} from "
            f"template in {str(template_dir)!r}."
        )
        context = self._get_context(name=project_name)
        environment = self._get_templates_environment(template_dir)
        self._create_project_dir(project_dir=project_dir)
        self._render_project(environment, project_dir, template_dir, context)

    def check_for_existing_files(
        self,
        *,
        project_dir: pathlib.Path,
        template_dir: pathlib.Path,
    ) -> None:
        """Check if there are any existing files in the project directory that would be overwritten.

        :param project_dir: The directory to initialise the project in.
        :param template_dir: The directory containing the templates.

        :raises InitError: If there are files in the project directory that would be overwritten.
        """
        template_files = self._get_template_files(template_dir)
        existing_files = [
            template_file
            for template_file in template_files
            if (project_dir / template_file).exists()
        ]

        if existing_files:
            existing_files_formatted = "\n  - ".join(existing_files)
            raise InitError(
                message=(
                    f"Cannot initialise project in {str(project_dir)!r} because it "
                    "would overwrite existing files.\nExisting files are:\n  - "
                    f"{existing_files_formatted}"
                ),
                resolution=(
                    "Initialise the project in an empty directory or remove the existing files."
                ),
                retcode=os.EX_CANTCREAT,
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
    ) -> None:
        """Render files for a project from a template.

        :param environment: The Jinja environment to use.
        :param project_dir: The directory to render the files into.
        :param template_dir: The directory where templates are stored.
        :param context: The context to render the templates with.
        """
        emit.progress("Rendering project.")
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
                file.write(template.render(context))
            shutil.copystat((template_dir / template_name), path)
        emit.progress("Rendered project.")

    def _get_context(self, name: str) -> dict[str, Any]:
        """Get context to render templates with.

        :returns: A dict of context variables.
        """
        emit.debug(f"Set project name to '{name}'")

        return {"name": name}

    @staticmethod
    def _create_project_dir(project_dir: pathlib.Path) -> None:
        """Create the project directory if it does not already exist."""
        emit.debug(f"Creating project directory {str(project_dir)!r}.")
        project_dir.mkdir(parents=True, exist_ok=True)

    def _get_loader(self, template_dir: pathlib.Path) -> jinja2.BaseLoader:
        """Return a Jinja loader for the given template directory.

        :param template_dir: The directory containing the templates.

        :returns: A Jinja loader.
        """
        return jinja2.PackageLoader(self._app.name, str(template_dir))

    def _get_templates_environment(
        self, template_dir: pathlib.Path
    ) -> jinja2.Environment:
        """Create and return a Jinja environment to deal with the templates.

        :param template_dir: The directory containing the templates.

        :returns: A Jinja environment.
        """
        return jinja2.Environment(
            loader=self._get_loader(template_dir),
            autoescape=False,  # noqa: S701 (jinja2-autoescape-false)
            keep_trailing_newline=True,  # they're not text files if they don't end in newline!
            optimized=False,  # optimization doesn't make sense for one-offs
            undefined=jinja2.StrictUndefined,
        )  # fail on undefined

    def _get_template_files(self, template_dir: pathlib.Path) -> list[str]:
        """Return a list of files that would be created from a template directory.

        Note that the '.j2' suffix is removed from templates.

        :param template_dir: The directory containing the templates.

        :returns: A list of filenames that would be created.
        """
        templates = self._get_templates_environment(template_dir).list_templates()

        return [
            template[:-3] if template.endswith(".j2") else template
            for template in templates
        ]
