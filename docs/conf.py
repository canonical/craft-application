# Copyright 2023-2024 Canonical Ltd.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License version 3 as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#
"""Configuration for craft-application documentation."""

import datetime

project = "Craft Application"
author = "Canonical"

copyright = "2023-%s, %s" % (datetime.date.today().year, author)

# region Configuration for canonical-sphinx
ogp_site_url = "https://canonical-craft-application.readthedocs-hosted.com/"
ogp_site_name = project
ogp_image = "https://assets.ubuntu.com/v1/253da317-image-document-ubuntudocs.svg"

html_context = {
    "product_page": "github.com/canonical/craft-application",
    "github_url": "https://github.com/canonical/craft-application",
}

# Target repository for the edit button on pages
html_theme_options = {
    "source_edit_link": "https://github.com/canonical/craft-application",
}

# endregion

exclude_patterns = [
    "_build",
    "Thumbs.db",
    ".DS_Store",
    "**venv",
    "base",
    "sphinx-resources",
    "common/README.md",
    "common/craft-application/how-to-guides/build-remotely.rst",
    "common/craft-application/how-to-guides/reuse-packages-between-builds.rst",
    "common/craft-application/reference/remote-builds.rst",
    "common/craft-application/reference/fetch-service.rst",
    # There's no tutorials right now, so just hide the scaffolding
    "tutorials",
]

# links to ignore when checking links
linkcheck_ignore = [
    # Ignore releases, since we'll include the next release before it exists.
    "https://github.com/canonical/[a-z]*craft[a-z-]*/releases/.*",
]

extensions = [
    "canonical_sphinx",
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
    "sphinx_substitution_extensions",
    "sphinxext.rediraffe",
    "pydantic_kitbash",
]

templates_path = ["_templates"]

show_authors = False

# endregion
# region Options for HTML output
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "furo"
html_static_path = ["_static"]
html_css_files = [
    "css/custom.css",
]

# endregion
# region Options for extensions
# Intersphinx extension
# https://www.sphinx-doc.org/en/master/usage/extensions/intersphinx.html#configuration

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

# Type hints configuration
set_type_checking_flag = True
typehints_fully_qualified = False
always_document_param_types = True

# Github config
github_username = "canonical"
github_repository = "craft-application"

intersphinx_mapping = {
    "craft-cli": (
        "https://canonical-craft-cli.readthedocs-hosted.com/en/latest",
        None,
    ),
    "craft-grammar": ("https://craft-grammar.readthedocs.io/en/latest", None),
    "craft-parts": (
        "https://canonical-craft-parts.readthedocs-hosted.com/en/latest",
        None,
    ),
    "craft-platforms": (
        "https://canonical-craft-platforms.readthedocs-hosted.com/en/latest",
        None,
    ),
    "craft-providers": (
        "https://canonical-craft-providers.readthedocs-hosted.com/en/latest", None
    ),
}

# Client-side page redirects.
rediraffe_redirects = "redirects.txt"

# Reuse epilog
rst_epilog = """
.. include:: /reuse/links.txt
"""
