# This file is part of craft_application.
#
# Copyright 2024 Canonical Ltd.
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License version 3, as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
# SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Utility functions and helpers related to documentation."""


def render_doc_url(
    url: str,
    version: str,
    major_only: bool = True,  # noqa: FBT001 FBT002
) -> str:
    """Render a URL with the correct version for readthedocs.

    This function generates URLs for documentation hosted on Read the Docs. Given an
    input URL containing ``{version}``, this function will return the URL with
    ``{version}`` formatted:

    - ``latest``, if ``version`` is a development value like ``1.0+g115121``,
      ``1.0+git0293141``, or ``dev``.
    - The major version, if ``major_only`` is set to ``True``.
    - The plain ``version`` otherwise.

    :param url: A URL with a possible ``{version}`` placeholder.
    :param version: The app version
    :param major_only: Whether to cut after the major number (default: True)
    """
    version_var = "{version}"

    if version_var not in url:
        return url

    if version == "dev" or "+g" in version:
        version = "latest"
    elif major_only:
        version, *_ = version.split(".")

    return url.replace(version_var, version)
