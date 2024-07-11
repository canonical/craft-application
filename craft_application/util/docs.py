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


def render_doc_url(url: str, version: str) -> str:
    """Render ``url`` with the correct version for readthedocs.

    This function generates urls following the readthedocs standard. Given an
    input url containing a "{version}" placeholder, this function will return
    an url where "{version}" is replaced with:
    - ``latest``, if ``version`` is a development value like "1.0+g115121",
      "1.0+git0293141" or "dev,
    - the value of ``version`` otherwise.

    :param url: an url with a possible {version} placeholder.
    :param version: the application version.
    """
    version_var = "{version}"

    if version_var not in url:
        return url

    if version == "dev" or "+g" in version:
        version = "latest"

    return url.replace(version_var, version)
