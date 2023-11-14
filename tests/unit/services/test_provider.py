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
import pathlib
from unittest import mock

import craft_providers
import pytest
from craft_application import errors, models, util
from craft_application.services import provider
from craft_application.util import platforms
from craft_providers import bases, lxd, multipass
from craft_providers.actions.snap_installer import Snap


@pytest.mark.parametrize(
    ("install_snap", "snaps"),
    [(True, [Snap(name="testcraft", channel=None, classic=True)]), (False, [])],
)
def test_install_snap(app_metadata, fake_project, fake_services, install_snap, snaps):
    service = provider.ProviderService(
        app_metadata,
        fake_services,
        project=fake_project,
        work_dir=pathlib.Path(),
        install_snap=install_snap,
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
    check.equal(base.compatibility_tag, f"testcraft-{base_class.compatibility_tag}")
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
    build_info = models.BuildInfo("foo", arch, arch, base_name)

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


@pytest.fixture()
def setup_fetch_logs_provider(monkeypatch, provider_service, tmp_path):
    """Return a function that, when called, mocks the provider_service's instance()."""

    def _setup(*, should_have_logfile: bool):
        """
        param should_have_logfile: Whether the logfile in the fake "build instance"
          should exist (True) or not (False).
        """
        mock_provider = mock.MagicMock(spec=craft_providers.Provider)
        monkeypatch.setattr(provider_service, "get_provider", lambda: mock_provider)

        # This ugly call is to mock the "instance" returned by the "launched_environment"
        # context manager.
        mock_instance = (
            mock_provider.launched_environment.return_value.__enter__.return_value
        )
        mock_instance.temporarily_pull_file = mock.MagicMock()

        if should_have_logfile:
            fake_log = tmp_path / "fake.file"
            fake_log_data = "some\nlog data\nhere"
            fake_log.write_text(fake_log_data, encoding="utf-8")
            mock_instance.temporarily_pull_file.return_value.__enter__.return_value = (
                fake_log
            )
        else:
            mock_instance.temporarily_pull_file.return_value.__enter__.return_value = (
                None
            )

        return provider_service

    return _setup


def _get_build_info() -> models.BuildInfo:
    arch = util.get_host_architecture()
    return models.BuildInfo(
        platform=arch,
        build_on=arch,
        build_for=arch,
        base=bases.BaseName("ubuntu", "22.04"),
    )


def test_instance_fetch_logs(
    provider_service, setup_fetch_logs_provider, check, emitter
):
    """Test that logs from the build instance are fetched in case of success."""

    # Setup the build instance and pretend the command inside it finished successfully.
    provider_service = setup_fetch_logs_provider(should_have_logfile=True)
    with provider_service.instance(
        build_info=_get_build_info(),
        work_dir=pathlib.Path(),
    ) as mock_instance:
        pass

    # Now check that the logs from the build instance were collected.
    with check:
        mock_instance.temporarily_pull_file.assert_called_once_with(
            source=pathlib.PosixPath("/tmp/testcraft.log"), missing_ok=True
        )

    expected = [
        mock.call("debug", "Logs retrieved from managed instance:"),
        mock.call("debug", ":: some"),
        mock.call("debug", ":: log data"),
        mock.call("debug", ":: here"),
    ]

    with check:
        emitter.assert_interactions(expected)


def test_instance_fetch_logs_error(
    provider_service, setup_fetch_logs_provider, check, emitter
):
    """Test that logs from the build instance are fetched in case of errors."""

    # Setup the build instance and pretend the command inside it finished with error.
    provider_service = setup_fetch_logs_provider(should_have_logfile=True)
    with pytest.raises(RuntimeError), provider_service.instance(
        build_info=_get_build_info(),
        work_dir=pathlib.Path(),
    ) as mock_instance:
        raise RuntimeError("Faking an error in the build instance!")

    # Now check that the logs from the build instance were collected.
    with check:
        mock_instance.temporarily_pull_file.assert_called_once_with(
            source=pathlib.PosixPath("/tmp/testcraft.log"), missing_ok=True
        )

    expected = [
        mock.call("debug", "Logs retrieved from managed instance:"),
        mock.call("debug", ":: some"),
        mock.call("debug", ":: log data"),
        mock.call("debug", ":: here"),
    ]

    with check:
        emitter.assert_interactions(expected)


def test_instance_fetch_logs_missing_file(
    provider_service, setup_fetch_logs_provider, check, emitter
):
    """Test that we handle the case where the logfile is missing."""

    # Setup the build instance and pretend the command inside it finished successfully.
    provider_service = setup_fetch_logs_provider(should_have_logfile=False)
    with provider_service.instance(
        build_info=_get_build_info(),
        work_dir=pathlib.Path(),
    ) as mock_instance:
        pass

    # Now check that the logs from the build instance were *attempted* to be collected.
    with check:
        mock_instance.temporarily_pull_file.assert_called_once_with(
            source=pathlib.PosixPath("/tmp/testcraft.log"), missing_ok=True
        )
    expected = [
        mock.call("debug", "Could not find log file /tmp/testcraft.log in instance."),
    ]

    with check:
        emitter.assert_interactions(expected)


_test_base = bases.BaseName("ubuntu", "22.04")


@pytest.mark.parametrize(
    ("build_infos", "expected_on_fors"),
    [
        # A single build info, matching the current architecture
        (
            [models.BuildInfo("foo", "current", "current", _test_base)],
            ["on-current-for-current"],
        ),
        # Two build infos, both matching the current architecture
        (
            [
                models.BuildInfo("foo", "current", "current", _test_base),
                models.BuildInfo("foo2", "current", "other", _test_base),
            ],
            ["on-current-for-current", "on-current-for-other"],
        ),
        # Three build infos, only one matches current architecture
        (
            [
                models.BuildInfo("foo", "current", "current", _test_base),
                models.BuildInfo("foo2", "other", "other", _test_base),
                models.BuildInfo("foo3", "other", "other2", _test_base),
            ],
            ["on-current-for-current"],
        ),
        # Two build infos, none matches current architecture
        (
            [
                models.BuildInfo("foo2", "other", "other", _test_base),
                models.BuildInfo("foo3", "other", "other2", _test_base),
            ],
            [],
        ),
    ],
)
def test_clean_instances(
    provider_service, fake_project, tmp_path, mocker, build_infos, expected_on_fors
):
    mocker.patch.object(platforms, "get_host_architecture", return_value="current")
    mocker.patch.object(
        fake_project.__class__, "get_build_plan", return_value=build_infos
    )

    current_provider = provider_service.get_provider()
    mock_clean = mocker.patch.object(current_provider, "clean_project_environments")

    provider_service.clean_instances()

    work_dir_inode = tmp_path.stat().st_ino

    expected_mock_calls = [
        mock.call(instance_name=f"testcraft-full-project-{on_for}-{work_dir_inode}")
        for on_for in expected_on_fors
    ]
    assert mock_clean.mock_calls == expected_mock_calls
