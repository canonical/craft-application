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
"""Service class for network requests."""
from __future__ import annotations

import pathlib
from collections.abc import Iterator, Mapping
from typing import TYPE_CHECKING

import craft_cli
import requests

from craft_application import util
from craft_application.services import base

if TYPE_CHECKING:
    from craft_application.application import AppMetadata
    from craft_application.services import service_factory


class RequestService(base.AppService):
    """A service for handling network requests."""

    def __init__(
        self, app: AppMetadata, services: service_factory.ServiceFactory
    ) -> None:
        super().__init__(app, services)
        self._session = requests.Session()
        self._session.headers["User-Agent"] = f"{self._app.name}/{self._app.version}"

        # Passthroughs for requests methods so other services can use the session.
        self.request = self._session.request
        self.delete = self._session.delete
        self.get = self._session.get
        self.head = self._session.head
        self.options = self._session.options
        self.patch = self._session.patch
        self.post = self._session.post
        self.put = self._session.put

    def download_chunks(self, url: str, dest: pathlib.Path) -> Iterator[int]:
        """Download a file.

        :param url: The source URL of the file.
        :param dest: The destination. Either a directory or a file.
        :yields: First the length in bytes of the file (or -1 if unknown), then the
            size of each downloaded chunk.
        """
        if dest.is_dir():
            filename = util.get_filename_from_url_path(url)
            dest = dest / filename

        with self.get(url, stream=True) as download:
            with dest.open("wb") as file:
                yield int(download.headers.get("Content-Length", -1))
                for chunk in download.iter_content(None):
                    file.write(chunk)
                    yield len(chunk)

    def download_with_progress(self, url: str, dest: pathlib.Path) -> pathlib.Path:
        """Download a single file with a progress bar."""
        return self.download_files_with_progress({url: dest})[url]

    def download_files_with_progress(
        self, files: Mapping[str, pathlib.Path]
    ) -> Mapping[str, pathlib.Path]:
        """Download a set of files to `dest_dir` from various URLs, with a progress bar.

        :param files: A mapping of urls to their destination files or directories
        :returns: The files mapping, updated with the actual file paths.
        """
        if not files:
            return {}
        files = dict(files)
        downloads: set[Iterator[int]] = set()

        for url, path in files.items():
            filename = util.get_filename_from_url_path(url)
            if path.is_dir():
                path = files[url] = path / filename  # noqa: PLW2901
            downloads.add(self.download_chunks(url, path))

        if len(files) == 1:
            title = f"Downloading {next(iter(files))}"
        else:
            title = f"Downloading {len(files)} files"

        sizes = [next(dl) for dl in downloads]
        total_size = sum(size for size in sizes if size > 0)

        with craft_cli.emit.progress_bar(title, total_size) as progress:
            while downloads:
                for dl in downloads.copy():
                    try:
                        chunk_size = next(dl)
                    except StopIteration:
                        downloads.remove(dl)
                    else:
                        progress.advance(chunk_size)

        return files
