# This file is part of craft_application.
#
# Copyright 2023-2024 Canonical Ltd.
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

"""Grammar-aware package repositories."""

from craft_archives.repo.package_repository import KeyIdStr
from craft_grammar.models import Grammar

from ._base import _GrammarAwareModel


class _GrammarPackageRepositoryApt(_GrammarAwareModel):
    url: Grammar[str]
    key_id: Grammar[KeyIdStr]
    architectures: Grammar[list[str]] | None = None
    formats: Grammar[list[str]] | None = None
    path: Grammar[str] | None = None
    components: Grammar[list[str]] | None = None
    key_server: Grammar[str] | None = None
    suites: Grammar[list[str]] | None = None


class _GrammarPackageRepositoryAptPPA(_GrammarAwareModel):
    ppa: Grammar[str]


class _GrammarPackageRepositoryAptUCA(_GrammarAwareModel):
    cloud: Grammar[str]
    pocket: Grammar[str] = "updates"


_GrammarRepositoryTypes = (
    _GrammarPackageRepositoryApt
    | _GrammarPackageRepositoryAptPPA
    | _GrammarPackageRepositoryAptUCA
)


def get_grammar_aware_repository_keywords() -> list[str]:
    """Return all supported grammar keywords for package repositories."""
    repo_classes: list[type[_GrammarAwareModel]] = [
        _GrammarPackageRepositoryApt,
        _GrammarPackageRepositoryAptPPA,
        _GrammarPackageRepositoryAptUCA,
    ]
    keywords: set[str] = set()

    for repo_class in repo_classes:
        keywords.update(item.alias for item in repo_class.__fields__.values())

    return list(keywords)
