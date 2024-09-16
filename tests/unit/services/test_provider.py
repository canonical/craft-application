# This file is part of craft-application.
#
# Copyright 2023-2024 Canonical Ltd.
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
import pkgutil
import uuid
from typing import NamedTuple
from unittest import mock

import craft_providers
import pytest
from craft_application import errors, models, util
from craft_application.services import provider
from craft_application.util import platforms, snap_config
from craft_providers import bases, lxd, multipass
from craft_providers.actions.snap_installer import Snap


@pytest.mark.parametrize(
    ("given_environment", "expected_environment"),
    [
        ({}, {}),
        ({"http_proxy": "thing"}, {"http_proxy": "thing", "HTTP_PROXY": "thing"}),
        ({"HTTP_PROXY": "thing"}, {"http_proxy": "thing", "HTTP_PROXY": "thing"}),
        ({"ssh_proxy": "thing"}, {"ssh_proxy": "thing", "SSH_PROXY": "thing"}),
        ({"no_proxy": "thing"}, {"no_proxy": "thing", "NO_PROXY": "thing"}),
        ({"NO_PROXY": "thing"}, {"no_proxy": "thing", "NO_PROXY": "thing"}),
        # Special case handled by upstream:
        # https://docs.python.org/3/library/urllib.request.html#urllib.request.getproxies
        (
            {
                "REQUEST_METHOD": "GET",
                "HTTP_PROXY": "thing",
            },
            {},
        ),
        (  # But lower-case http_proxy is still allowed
            {
                "REQUEST_METHOD": "GET",
                "http_proxy": "thing",
            },
            {"http_proxy": "thing", "HTTP_PROXY": "thing"},
        ),
    ],
)
def test_setup_proxy_environment(
    monkeypatch: pytest.MonkeyPatch,
    app_metadata,
    fake_services,
    fake_project,
    fake_build_plan,
    given_environment: dict[str, str],
    expected_environment: dict[str, str],
):
    for var, value in given_environment.items():
        monkeypatch.setenv(var, value)

    expected_environment |= {"CRAFT_MANAGED_MODE": "1"}

    service = provider.ProviderService(
        app_metadata,
        fake_services,
        project=fake_project,
        work_dir=pathlib.Path(),
        build_plan=fake_build_plan,
    )
    service.setup()

    assert service.environment == expected_environment


@pytest.mark.parametrize(
    ("environment", "snaps"),
    [
        pytest.param(
            {},
            [Snap(name="testcraft", channel="latest/stable", classic=True)],
            id="install-from-store-default-channel",
        ),
        pytest.param(
            {"CRAFT_SNAP_CHANNEL": "something"},
            [Snap(name="testcraft", channel="something", classic=True)],
            id="install-from-store-with-channel",
        ),
        pytest.param(
            {
                "SNAP_NAME": "testcraft",
                "SNAP_INSTANCE_NAME": "testcraft_1",
                "SNAP": "/snap/testcraft/x1",
            },
            [Snap(name="testcraft_1", channel=None, classic=True)],
            id="inject-from-host",
        ),
        pytest.param(
            {
                "SNAP_NAME": "testcraft",
                "SNAP_INSTANCE_NAME": "testcraft_1",
                "SNAP": "/snap/testcraft/x1",
                "CRAFT_SNAP_CHANNEL": "something",
            },
            [Snap(name="testcraft_1", channel=None, classic=True)],
            id="inject-from-host-ignore-channel",
        ),
        pytest.param(
            # SNAP_INSTANCE_NAME may not exist if snapd < 2.43 or feature is disabled
            {
                "SNAP_NAME": "testcraft",
                "SNAP": "/snap/testcraft/x1",
            },
            [Snap(name="testcraft", channel=None, classic=True)],
            id="missing-snap-instance-name",
        ),
        pytest.param(
            # SNAP_INSTANCE_NAME may not exist if snapd < 2.43 or feature is disabled
            {
                "SNAP_NAME": "testcraft",
                "SNAP": "/snap/testcraft/x1",
                # CRAFT_SNAP_CHANNEL should be ignored
                "CRAFT_SNAP_CHANNEL": "something",
            },
            [Snap(name="testcraft", channel=None, classic=True)],
            id="missing-snap-instance-name-ignore-snap-channel",
        ),
        pytest.param(
            # this can happen when running testcraft from a venv in a snapped terminal
            {
                "SNAP_NAME": "kitty",
                "SNAP_INSTANCE_NAME": "kitty",
                "SNAP": "/snap/kitty/x1",
            },
            [Snap(name="testcraft", channel="latest/stable", classic=True)],
            id="running-inside-another-snap",
        ),
    ],
)
@pytest.mark.parametrize("install_snap", [True, False])
def test_install_snap(
    monkeypatch,
    app_metadata,
    fake_project,
    fake_build_plan,
    fake_services,
    install_snap,
    environment,
    snaps,
):
    monkeypatch.delenv("SNAP", raising=False)
    monkeypatch.delenv("CRAFT_SNAP_CHANNEL", raising=False)
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    service = provider.ProviderService(
        app_metadata,
        fake_services,
        project=fake_project,
        work_dir=pathlib.Path(),
        build_plan=fake_build_plan,
        install_snap=install_snap,
    )
    service.setup()

    if install_snap:
        assert service.snaps == snaps
    else:
        assert service.snaps == []


@pytest.mark.parametrize(
    ("managed_value", "expected"),
    [
        ("1", True),
        ("", False),
        (None, False),
    ],
)
def test_is_managed(managed_value, expected, monkeypatch):
    monkeypatch.setenv(
        provider.ProviderService.managed_mode_env_var, str(managed_value)
    )

    assert provider.ProviderService.is_managed() == expected


def test_forward_environment_variables(monkeypatch, provider_service):
    var_contents = uuid.uuid4().hex
    for var in provider.DEFAULT_FORWARD_ENVIRONMENT_VARIABLES:
        monkeypatch.setenv(var, f"{var}__{var_contents}")

    provider_service.setup()

    assert provider_service.environment == {
        provider_service.managed_mode_env_var: "1",
        **{
            var: f"{var}__{var_contents}"
            for var in provider.DEFAULT_FORWARD_ENVIRONMENT_VARIABLES
        },
    }


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


class TestGetProvider:
    """Test cases for `get_provider()`."""

    class ProviderInfo(NamedTuple):
        name: str
        cls: type

    @pytest.fixture(
        params=[
            ProviderInfo(name="lxd", cls=lxd.LXDProvider),
            ProviderInfo(name="LXD", cls=lxd.LXDProvider),
            ProviderInfo(name=" LxD ", cls=lxd.LXDProvider),
            ProviderInfo(name="multipass", cls=multipass.MultipassProvider),
            ProviderInfo(name="MULTIPASS", cls=multipass.MultipassProvider),
            ProviderInfo(name=" MultiPass ", cls=multipass.MultipassProvider),
        ]
    )
    def providers(self, request):
        """Return a provider name and its expected class.

        Names can contain upper and lower cases and surrounding whitespace.
        """
        return request.param

    @pytest.fixture(autouse=True)
    def _mock_env_vars(self, monkeypatch):
        """Ensure the env var does not exist."""
        monkeypatch.delenv("CRAFT_BUILD_ENVIRONMENT", raising=False)

    @pytest.mark.parametrize("name", ["axolotl"])
    def test_get_provider_unknown_name(self, provider_service, name):
        """Raise an error for unknown provider names."""
        with pytest.raises(RuntimeError) as raised:
            provider_service.get_provider(name)

        assert str(raised.value) == "Unknown provider: 'axolotl'"

    def test_get_existing_provider(self, provider_service):
        """Short circuit `get_provider()` when the provider is already set."""
        provider_service._provider = expected = "This is totally a provider."

        assert provider_service.get_provider() == expected

    def test_get_provider_managed_mode(self, provider_service):
        """Raise an error when running in managed mode."""
        provider_service._provider = None
        provider_service.is_managed = lambda: True

        with pytest.raises(errors.CraftError) as raised:
            provider_service.get_provider()

        assert raised.value == errors.CraftError("Cannot nest managed environments.")

    def test_get_provider_from_argument(self, provider_service, providers):
        """(1) use provider specified in the function argument."""
        provider_service._provider = None
        provider_service.is_managed = lambda: False

        result = provider_service.get_provider(name=providers.name)

        assert isinstance(result, providers.cls)

    def test_get_provider_from_env(self, monkeypatch, provider_service, providers):
        """(2) get the provider from the environment (CRAFT_BUILD_ENVIRONMENT)."""
        provider_service._provider = None
        provider_service.is_managed = lambda: False
        monkeypatch.setenv("CRAFT_BUILD_ENVIRONMENT", providers.name)

        result = provider_service.get_provider()

        assert isinstance(result, providers.cls)

    def test_get_provider_from_snap(self, mocker, provider_service, providers):
        """(3) use provider specified with snap configuration."""
        provider_service._provider = None
        provider_service.is_managed = lambda: False
        mocker.patch(
            "craft_application.services.provider.snap_config.get_snap_config",
            return_value=snap_config.SnapConfig(provider=providers.name),
        )

        result = provider_service.get_provider()

        assert isinstance(result, providers.cls)

    def test_get_provider_no_snap_config(self, mocker, provider_service, emitter):
        """Do not error when snap config does not exist.

        Instead, proceed to the next step."""
        provider_service._provider = None
        provider_service.is_managed = lambda: False
        mocker.patch(
            "craft_application.services.provider.snap_config.get_snap_config",
            return_value=None,
        )

        provider_service.get_provider()

        emitter.assert_debug("No snap config found.")

    def test_get_provider_no_provider_in_snap_config(
        self, mocker, provider_service, emitter
    ):
        """Do not error when the snap config does not contain a provider.

        Instead, proceed to the next step."""
        provider_service._provider = None
        provider_service.is_managed = lambda: False
        mocker.patch(
            "craft_application.services.provider.snap_config.get_snap_config",
            return_value={},
        )

        provider_service.get_provider()

        emitter.assert_debug("Provider not set in snap config.")

    @pytest.mark.parametrize(
        ("platform", "provider_cls"),
        [
            ("linux", lxd.LXDProvider),
            ("darwin", multipass.MultipassProvider),
            ("win32", multipass.MultipassProvider),
            ("unknown", multipass.MultipassProvider),
        ],
    )
    def test_get_provider_from_platform(
        self, mocker, provider_service, platform, provider_cls
    ):
        """(4) default to platform default (LXD on Linux, otherwise Multipass)."""
        provider_service._provider = None
        provider_service.is_managed = lambda: False
        mocker.patch("sys.platform", platform)

        result = provider_service.get_provider()

        assert isinstance(result, provider_cls)


@pytest.mark.parametrize("environment", [{}, {"a": "b"}])
@pytest.mark.parametrize(
    ("base_name", "base_class", "alias"),
    [
        (("ubuntu", "devel"), bases.BuilddBase, bases.BuilddBaseAlias.DEVEL),
        (("ubuntu", "24.04"), bases.BuilddBase, bases.BuilddBaseAlias.NOBLE),
        (("ubuntu", "22.04"), bases.BuilddBase, bases.BuilddBaseAlias.JAMMY),
        (("ubuntu", "20.04"), bases.BuilddBase, bases.BuilddBaseAlias.FOCAL),
    ],
)
def test_get_base_buildd(
    check, provider_service, base_name, base_class, alias, environment
):
    """Check that a BuilddBase is properly retrieved for Ubuntu-like bases."""
    provider_service.environment = environment

    base = provider_service.get_base(base_name, instance_name="test")

    check.is_instance(base, base_class)
    check.equal(base.alias, alias)
    check.equal(base.compatibility_tag, f"testcraft-{base_class.compatibility_tag}")
    check.equal(base._environment, environment)

    # Verify that the two packages we care about in order to support Craft Archives
    # on Buildd bases are listed to be provisioned.
    assert "gpg" in base._packages
    assert "dirmngr" in base._packages


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
        ("ubuntu", "24.10"),
        ("ubuntu", "24.04"),
        ("ubuntu", "22.04"),
        ("ubuntu", "20.04"),
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
):
    mock_provider = mock.MagicMock(spec=craft_providers.Provider)
    monkeypatch.setattr(
        provider_service,
        "get_provider",
        lambda name: mock_provider,  # noqa: ARG005 (unused argument)
    )
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
        instance.push_file_io.assert_called_once_with(
            destination=pathlib.Path("/root/.bashrc"),
            content=mock.ANY,
            file_mode="644",
        )
    with check:
        emitter.assert_progress("Launching managed .+ instance...", regex=True)


def test_load_bashrc(emitter):
    """Test that we are able to load the bashrc file from the craft-application package."""
    bashrc = pkgutil.get_data("craft_application", "misc/instance_bashrc")
    assert bashrc is not None
    assert bashrc.decode("UTF-8").startswith("#!/bin/bash")
    with pytest.raises(AssertionError):
        emitter.assert_debug(
            "Could not find the bashrc file in the craft-application package"
        )


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
def test_load_bashrc_missing(
    monkeypatch,
    emitter,
    tmp_path,
    provider_service,
    base_name,
    allow_unstable,
    mocker,
):
    """Test that we handle the case where the bashrc file is missing."""
    mock_provider = mock.MagicMock(spec=craft_providers.Provider)
    monkeypatch.setattr(
        provider_service,
        "get_provider",
        lambda name: mock_provider,  # noqa: ARG005 (unused argument)
    )
    arch = util.get_host_architecture()
    build_info = models.BuildInfo("foo", arch, arch, base_name)

    mocker.patch.object(pkgutil, "get_data", return_value=None)
    with provider_service.instance(
        build_info, work_dir=tmp_path, allow_unstable=allow_unstable
    ) as instance:
        instance._setup_instance_bashrc(instance)
    emitter.assert_debug(
        "Could not find the bashrc file in the craft-application package"
    )


@pytest.fixture
def setup_fetch_logs_provider(monkeypatch, provider_service, tmp_path):
    """Return a function that, when called, mocks the provider_service's instance()."""

    def _setup(*, should_have_logfile: bool):
        """
        param should_have_logfile: Whether the logfile in the fake "build instance"
          should exist (True) or not (False).
        """
        mock_provider = mock.MagicMock(spec=craft_providers.Provider)
        monkeypatch.setattr(
            provider_service,
            "get_provider",
            lambda name: mock_provider,  # noqa: ARG005 (unused argument)
        )

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
    provider_service, tmp_path, mocker, build_infos, expected_on_fors
):
    mocker.patch.object(platforms, "get_host_architecture", return_value="current")

    current_provider = provider_service.get_provider()
    mock_clean = mocker.patch.object(current_provider, "clean_project_environments")

    provider_service._build_plan = build_infos
    provider_service.clean_instances()

    work_dir_inode = tmp_path.stat().st_ino

    expected_mock_calls = [
        mock.call(instance_name=f"testcraft-full-project-{on_for}-{work_dir_inode}")
        for on_for in expected_on_fors
    ]
    assert mock_clean.mock_calls == expected_mock_calls
