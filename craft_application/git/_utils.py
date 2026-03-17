# Copyright 2025 Canonical Ltd.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Git repository class helper utilities."""

import os
import pathlib

import craft_cli
import yaml

_FALLBACK_PATH = "/snap/core22/current/etc/ssl/certs"


def find_ssl_cert_dir() -> str:
    """Find a correct path to the certificate files for the snap."""
    if snap_env := os.environ.get("SNAP"):
        snap_metadata_path = pathlib.Path(snap_env) / "meta" / "snap.yaml"

        if snap_metadata_path.exists():
            try:
                metadata_yaml = yaml.safe_load(snap_metadata_path.read_text())
            except (yaml.YAMLError, OSError) as err:
                craft_cli.emit.debug(f"Cannot load: {snap_metadata_path}")
                craft_cli.emit.debug(f"Error: {err}")
            else:
                if metadata_yaml:
                    base = metadata_yaml.get("base") or "core22"
                    return f"/snap/{base}/current/etc/ssl/certs"

    return _FALLBACK_PATH
