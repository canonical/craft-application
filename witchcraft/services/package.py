# This file is part of craft_application.
#
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
"""Witchcraft package service."""

import pathlib
import re
import subprocess
import tarfile
import textwrap
from collections.abc import Iterator
from typing import cast

from craft_application.services import package


def package_file(path: str | pathlib.Path, partition: str | None = None):
    dest = pathlib.Path(path)
    if dest.is_absolute():
        raise ValueError(f"Destination must be relative, not {dest}")

    def _function_wrapper(func):
        func.__package_file_write_to__ = pathlib.Path(path)
        func.__partition__ = partition
        return func

    return _function_wrapper


def get_newest_mtime_ns(root: pathlib.Path) -> int:
    newest = root.stat().st_mtime_ns
    # for path in root.rglob("*"):
    #     newest = max(newest, path.stat().st_mtime_ns)
    return newest


class PackageService(package.PackageService):
    """Package service for witchcraft."""

    @property
    def metadata(self):
        """Get the metadata for this model."""
        return "No longer necessary"

    def write_metadata(self, path: pathlib.Path) -> None:
        self.write_package_files(path)

    def gen_artifact_names(self) -> Iterator[str]:
        project = self._services.get("project").get()
        platform = self._services.get("build_plan").plan()[0].platform
        yield f"{project.name}-{project.version}-{platform}.witchcraft"

    def _app_needs_repack(self) -> bool:
        if Path(project.icon).mtime > snap_file.mtime:
            return True
        return False

    def needs_repack(self) -> bool:
        if self._app_needs_repack():
            return True
        for name in self.gen_artifact_names():
            if not pathlib.Path(name).exists():
                return True
        lifecycle_service = self._services.get("lifecycle")
        artifact_repacks = {}
        for partition, part_path in lifecycle_service.prime_dirs.items():
            partition_path = lifecycle_service.prime_dirs[partition]
            if not partition_path.is_dir():
                artifact_repacks[partition] = True
                continue
            newest_prime_change = get_newest_mtime_ns(partition_path)
            for path, generator in self.gen_partition_files(partition or "default"):
                full_path = partition_path / path
                new_content = generator(partition)
                if full_path.exists() == (new_content is None):
                    artifact_repacks[partition] = True
                    break
                if not full_path.exists():
                    artifact_repacks[partition] = True
                    break
                if isinstance(new_content, str):
                    old_content = full_path.read_text()
                else:
                    old_content = full_path.read_bytes()
                if new_content != old_content:
                    artifact_repacks[partition] = True
                    break
            else:
                artifact_repacks[partition] = False
        if artifact_repacks.keys() == {None}:
            return artifact_repacks[None]
        if isinstance(artifact_repacks, bool):
            return artifact_repacks
        return True in artifact_repacks.values()

    def gen_partition_files(self, partition: str = "default"):
        for name in dir(self):
            gen = getattr(self, name)
            if callable(gen) and (
                dest := getattr(gen, "__package_file_write_to__", None)
            ):
                part_re = cast(str | None, getattr(gen, "__partition__", None))
                if part_re is not None and not re.fullmatch(part_re, partition):
                    continue
                yield (dest, gen)

    def pack(self, prime_dir: pathlib.Path, dest: pathlib.Path) -> list[pathlib.Path]:
        """Pack a witchcraft artifact."""
        project = self._services.get("project").get()
        platform = self._services.get("build_plan").plan()[0].platform
        tarball_name = f"{project.name}-{project.version}-{platform}.witchcraft"
        with tarfile.open(dest / tarball_name, mode="w:xz") as tar:
            tar.add(prime_dir, arcname=".")
        return [dest / tarball_name]

    def write_package_files(
        self, prime_dir: pathlib.Path, partition: str = "default"
    ) -> None:
        for dest, generator in self.gen_partition_files(partition):
            path = prime_dir / dest
            result = generator(partition)
            if result is None:
                continue
            if isinstance(result, str):
                path.write_text(result)
            else:
                path.write_bytes(result)

    #     @package_file("meta/snap.yaml", "default")
    #     def get_snap_yaml(...):
    #         ...
    #
    #
    #     @package_file("meta/hooks/configure", "default")
    #     def get_configure_hook(...):
    #         return get_hook_file("configure")

    @package_file("metadata.yaml")  # All partitions
    def get_metadata(self, partition: str | None) -> str:
        return textwrap.dedent(
            """\
            this: is yaml!
            """
        )

    @package_file("env", r"(?!default\b)\b\w+")  # Everywhere but the default partition
    def get_other_env(self, partition: str | None) -> bytes:
        return subprocess.run(["env"], check=False, capture_output=True).stdout
