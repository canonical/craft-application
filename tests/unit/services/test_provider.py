# This file is part of craft-application.
#
# Copyright 2023 Canonical Ltd.
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
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Unit tests for provider service"""
from unittest import mock

import craft_providers
import pytest
from craft_application import errors, models, util
from craft_application.services import provider
from craft_providers import bases, lxd, multipass
from craft_providers.actions.snap_installer import Snap


@pytest.mark.parametrize(
    ("install_snap", "snaps"),
    [(True, [Snap(name="testcraft", channel=None, classic=True)]), (False, [])],
)
def test_install_snap(app_metadata, fake_project, fake_services, install_snap, snaps):
    service = provider.ProviderService(
        app_metadata, fake_project, fake_services, install_snap=install_snap
    )

    assert service.snaps == snaps


@pytest.mark.parametrize(
    ("managed_value", "expected"),
    [
        ("1", True),
        ("", False),
        (None, False),
    ],
)
def test_is_managed(managed_value, expected, monkeypatch):
    monkeypatch.setenv(provider.ProviderService.managed_mode_env_var, managed_value)

    assert provider.ProviderService.is_managed() == expected


@pytest.mark.parametrize("lxd_remote", ["local", "something-else"])
def test_get_lxd_provider(monkeypatch, provider_service, lxd_remote, check):
    monkeypatch.setenv("CRAFT_LXD_REMOTE", lxd_remote)
    mock_provider = mock.Mock()
    monkeypatch.setattr(provider, "LXDProvider", mock_provider)

    actual = provider_service.get_provider("lxd")

    check.equal(actual, mock_provider.return_value)
    with check:
        mock_provider.assert_called_once_with(
            lxd_project="testcraft", lxd_remote=lxd_remote
        )


@pytest.mark.parametrize(
    ("platform", "provider_cls"),
    [
        ("linux", lxd.LXDProvider),
        ("not-linux", multipass.MultipassProvider),
    ],
)
def test_get_default_provider(monkeypatch, provider_service, platform, provider_cls):
    monkeypatch.setattr("sys.platform", platform)
    provider_service._provider = None
    provider_service.is_managed = lambda: False

    result = provider_service.get_provider()

    assert isinstance(result, provider_cls)


@pytest.mark.parametrize(
    ("name", "provider_cls"),
    [("lxd", lxd.LXDProvider), ("multipass", multipass.MultipassProvider)],
)
def test_get_provider_by_name_success(provider_service, name, provider_cls):
    provider_service._provider = None
    provider_service.is_managed = lambda: False

    result = provider_service.get_provider(name)

    assert isinstance(result, provider_cls)


@pytest.mark.parametrize("name", ["axolotl"])
def test_get_provider_invalid_name(provider_service, name):
    with pytest.raises(RuntimeError):
        provider_service.get_provider(name)


def test_get_provider_managed(monkeypatch, provider_service):
    monkeypatch.setenv(provider_service.managed_mode_env_var, "1")

    with pytest.raises(errors.CraftError):
        provider_service.get_provider()


def test_get_existing_provider(provider_service):
    provider_service._provider = expected = "This is totally a provider."

    assert provider_service.get_provider() == expected


@pytest.mark.parametrize("environment", [{}, {"a": "b"}])
@pytest.mark.parametrize(
    ("base_name", "base_class", "alias"),
    [
        (("ubuntu", "devel"), bases.BuilddBase, bases.BuilddBaseAlias.DEVEL),
        (("ubuntu", "22.04"), bases.BuilddBase, bases.BuilddBaseAlias.JAMMY),
        (("centos", "7"), bases.centos.CentOSBase, bases.centos.CentOSBaseAlias.SEVEN),
        (
            ("almalinux", "9"),
            bases.almalinux.AlmaLinuxBase,
            bases.almalinux.AlmaLinuxBaseAlias.NINE,
        ),
    ],
)
def test_get_base(check, provider_service, base_name, base_class, alias, environment):
    provider_service.environment = environment

    base = provider_service.get_base(base_name, instance_name="test")

    check.is_instance(base, base_class)
    check.equal(base.alias, alias)
    check.equal(base._environment, environment)


def test_get_base_packages(provider_service):
    provider_service.packages.append("fake-package")
    provider_service.packages.append("another-package")

    base = provider_service.get_base(("ubuntu", "22.04"), instance_name="test")

    assert "fake-package" in base._packages
    assert "another-package" in base._packages


@pytest.mark.parametrize("allow_unstable", [True, False])
@pytest.mark.parametrize(
    "base_name",
    [
        ("ubuntu", "devel"),
        ("ubuntu", "22.04"),
        ("centos", "7"),
        ("almalinux", "9"),
    ],
)
def test_instance(
    monkeypatch,
    check,
    emitter,
    tmp_path,
    app_metadata,
    fake_project,
    provider_service,
    base_name,
    allow_unstable,
    mocker,
):
    mock_provider = mock.MagicMock(spec=craft_providers.Provider)
    monkeypatch.setattr(provider_service, "get_provider", lambda: mock_provider)
    spy_pause = mocker.spy(provider.emit, "pause")
    arch = util.get_host_architecture()
    build_info = models.BuildInfo(arch, arch, base_name)

    with provider_service.instance(
        build_info, work_dir=tmp_path, allow_unstable=allow_unstable
    ) as instance:
        pass

    with check:
        mock_provider.launched_environment.assert_called_once_with(
            project_name=fake_project.name,
            project_path=tmp_path,
            instance_name=mock.ANY,
            base_configuration=mock.ANY,
            allow_unstable=allow_unstable,
        )
    with check:
        instance.mount.assert_called_once_with(
            host_source=tmp_path, target=app_metadata.managed_instance_project_path
        )
    with check:
        emitter.assert_progress("Launching managed .+ instance...", regex=True)
    with check:
        assert spy_pause.call_count == 1
