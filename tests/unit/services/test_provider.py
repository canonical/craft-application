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

import enum
import pathlib
import pkgutil
import subprocess
import uuid
from typing import NamedTuple
from unittest import mock

import craft_application
import craft_platforms
import craft_providers
import pytest
import pytest_subprocess
from craft_application import errors
from craft_application.services import provider
from craft_application.services.service_factory import ServiceFactory
from craft_application.util import snap_config
from craft_cli import emit
from craft_providers import bases, lxd, multipass
from craft_providers.actions.snap_installer import Snap


@pytest.fixture
def mock_provider(monkeypatch, provider_service):
    mocked_provider = mock.MagicMock(spec=craft_providers.Provider)
    monkeypatch.setattr(
        provider_service,
        "get_provider",
        lambda name: mocked_provider,
    )

    return mocked_provider


@pytest.fixture(autouse=True)
def reset_provider_snaps() -> None:
    provider._REQUESTED_SNAPS.clear()


@pytest.fixture(scope="module")
def fake_build_info(fake_base):
    arch = craft_platforms.DebianArchitecture.from_host()
    return craft_platforms.BuildInfo(
        platform=str(arch),
        build_on=arch,
        build_for=arch,
        build_base=fake_base,
    )


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
    given_environment: dict[str, str],
    expected_environment: dict[str, str],
):
    for var, value in given_environment.items():
        monkeypatch.setenv(var, value)

    service = provider.ProviderService(
        app_metadata,
        fake_services,
        work_dir=pathlib.Path(),
    )
    service.setup()

    for key, value in expected_environment.items():
        assert service.environment[key] == value


@pytest.mark.parametrize(
    ("given_environment", "expected_environment"),
    [
        ({"CRAFT_DEBUG": "1"}, {"TESTCRAFT_DEBUG": "True"}),
        (
            {"TESTCRAFT_PARALLEL_BUILD_COUNT": "13"},
            {"TESTCRAFT_PARALLEL_BUILD_COUNT": "13"},
        ),
    ],
)
def test_setup_config_values(
    monkeypatch: pytest.MonkeyPatch,
    app_metadata,
    fake_services,
    fake_project,
    given_environment: dict[str, str],
    expected_environment: dict[str, str],
):
    for var, value in given_environment.items():
        monkeypatch.setenv(var, value)

    service = provider.ProviderService(
        app_metadata,
        fake_services,
        work_dir=pathlib.Path(),
    )
    service.setup()

    for key, value in expected_environment.items():
        assert service.environment[key] == value


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
    fake_process: pytest_subprocess.FakeProcess,
    fake_services,
    install_snap,
    environment,
    snaps,
):
    monkeypatch.setattr("snaphelpers._ctl.Popen", subprocess.Popen)
    fake_process.register(
        ["/usr/bin/snapctl", "get", "-d", fake_process.any()],
        stdout="{}",
        occurrences=1000,
    )
    monkeypatch.delenv("SNAP", raising=False)
    monkeypatch.delenv("CRAFT_SNAP_CHANNEL", raising=False)
    monkeypatch.delenv("SNAP_INSTANCE_NAME", raising=False)
    monkeypatch.delenv("SNAP_NAME", raising=False)
    monkeypatch.delenv("CRAFT_SNAP_CHANNEL", raising=False)
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    service = provider.ProviderService(
        app_metadata,
        fake_services,
        work_dir=pathlib.Path(),
        install_snap=install_snap,
    )
    service.setup()

    if install_snap:
        assert service.snaps == snaps
    else:
        assert service.snaps == []


@pytest.mark.parametrize(
    "additional_snaps",
    [
        pytest.param([], id="no_snaps"),
        pytest.param(
            [
                Snap(name="another-craft", channel="latest/edge"),
            ],
            id="single_snap",
        ),
        pytest.param(
            [
                Snap(name="another-craft", channel="latest/edge"),
                Snap(name="yet-another-craft", channel="latest/beta", classic=True),
                Snap(name="stable-craft", channel="stable"),
            ],
            id="multiple_snaps",
        ),
    ],
)
@pytest.mark.parametrize("install_snap", [True, False])
def test_install_registered_snaps_alongside_testcraft(
    monkeypatch,
    app_metadata,
    fake_project,
    fake_services,
    install_snap,
    additional_snaps: list[Snap],
):
    for snap in additional_snaps:
        provider.ProviderService.register_snap(snap.name, snap)
    snaps = [
        *additional_snaps,
        Snap(name="testcraft", channel="latest/stable", classic=True),
    ]

    monkeypatch.delenv("SNAP", raising=False)
    monkeypatch.delenv("CRAFT_SNAP_CHANNEL", raising=False)
    monkeypatch.delenv("SNAP_INSTANCE_NAME", raising=False)
    monkeypatch.delenv("SNAP_NAME", raising=False)
    monkeypatch.delenv("CRAFT_SNAP_CHANNEL", raising=False)
    service = provider.ProviderService(
        app_metadata,
        fake_services,
        work_dir=pathlib.Path(),
        install_snap=install_snap,
    )
    service.setup()

    if install_snap:
        assert service.snaps == snaps
    else:
        assert service.snaps == []


def test_snap_register(provider_service: provider.ProviderService) -> None:
    provider_service.register_snap("test-snap", Snap(name="test-snap", channel="test"))
    assert "test-snap" in provider._REQUESTED_SNAPS


def test_snap_unregister(provider_service: provider.ProviderService) -> None:
    provider_service.register_snap("test-snap", Snap(name="test-snap", channel="test"))

    provider_service.unregister_snap("test-snap")


def test_snap_unregister_twice(provider_service: provider.ProviderService) -> None:
    snap_name = "test-snap"
    provider_service.register_snap(snap_name, Snap(name="test-snap", channel="test"))

    provider_service.unregister_snap(snap_name)
    with pytest.raises(ValueError, match=f"Snap not registered: {snap_name!r}"):
        provider_service.unregister_snap(snap_name)


def test_snap_unregister_non_existent(
    provider_service: provider.ProviderService,
) -> None:
    snap_name = "test-snap"
    with pytest.raises(ValueError, match=f"Snap not registered: {snap_name!r}"):
        provider_service.unregister_snap(snap_name)


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


def test_forward_environment_variables(monkeypatch, provider_service, fake_services):
    var_contents = uuid.uuid4().hex
    for var in provider.DEFAULT_FORWARD_ENVIRONMENT_VARIABLES:
        monkeypatch.setenv(var, f"{var}__{var_contents}")

    provider_service.setup()

    # Exclude forwarded proxy variables from the host in this check.
    del_vars = set()
    for variable in provider_service.environment:
        if variable.lower().endswith("proxy"):
            del_vars.add(variable)
    for variable in del_vars:
        del provider_service.environment[variable]

    assert provider_service.environment == {
        provider_service.managed_mode_env_var: "1",
        **{
            var: f"{var}__{var_contents}"
            for var in provider.DEFAULT_FORWARD_ENVIRONMENT_VARIABLES
        },
        **{
            f"TESTCRAFT_{config.upper()}": (
                value.name if isinstance(value, enum.Enum) else str(value)
            )
            for config, value in fake_services.get("config").get_all().items()
            if config not in provider.IGNORE_CONFIG_ITEMS and value is not None
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


@pytest.mark.parametrize(
    ("platform", "platform_str"),
    [
        pytest.param("test-platform", "test-platform", id="simple"),
        pytest.param(
            "ubuntu@24.04:amd64", "ubuntu-24.04-amd64", id="special-characters"
        ),
    ],
)
def test_get_instance_name(platform, platform_str, new_dir, provider_service):
    build_info = craft_platforms.BuildInfo(
        platform,
        craft_platforms.DebianArchitecture.RISCV64,
        craft_platforms.DebianArchitecture.RISCV64,
        craft_platforms.DistroBase("ubuntu", "24.04"),
    )
    inode_number = str(new_dir.stat().st_ino)
    provider_service._build_plan = [build_info]
    expected_name = f"testcraft-full-project-{platform_str}-{inode_number}"

    assert (
        provider_service._get_instance_name(
            work_dir=new_dir, build_info=build_info, project_name="full-project"
        )
        == expected_name
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
    check.equal(
        base.compatibility_tag,
        f"testcraft-{base_class.compatibility_tag}{provider_service.compatibility_tag}",
    )
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
def test_instance(
    check,
    emitter,
    tmp_path,
    app_metadata,
    fake_project,
    provider_service,
    state_service,
    fake_build_info,
    allow_unstable,
    mock_provider,
):
    with provider_service.instance(
        fake_build_info, work_dir=tmp_path, allow_unstable=allow_unstable
    ) as instance:
        pass

    with check:
        mock_provider.launched_environment.assert_called_once_with(
            project_name=fake_project.name,
            project_path=tmp_path,
            instance_name=mock.ANY,
            base_configuration=mock.ANY,
            allow_unstable=allow_unstable,
            prepare_instance=None,
            use_base_instance=True,
            shutdown_delay_mins=None,
        )
    with check:
        assert instance.mount.mock_calls == [
            mock.call(
                host_source=tmp_path, target=app_metadata.managed_instance_project_path
            ),
            mock.call(
                host_source=state_service._state_dir,
                target=state_service._managed_state_dir,
            ),
        ]
        instance.push_file_io.assert_called_once_with(
            destination=pathlib.Path("/root/.bashrc"),
            content=mock.ANY,
            file_mode="644",
        )
    with check:
        emitter.assert_progress("Launching managed .+ instance...", regex=True)


@pytest.mark.parametrize("clean_existing", [True, False])
def test_instance_clean_existing(
    tmp_path,
    provider_service,
    mock_provider,
    clean_existing,
):
    arch = craft_platforms.DebianArchitecture.from_host()
    base_name = craft_platforms.DistroBase("ubuntu", "24.04")
    build_info = craft_platforms.BuildInfo("foo", arch, arch, base_name)

    with provider_service.instance(
        build_info, work_dir=tmp_path, clean_existing=clean_existing
    ) as _instance:
        pass

    clean_called = mock_provider.clean_project_environments.called
    assert clean_called == clean_existing

    if clean_existing:
        work_dir_inode = tmp_path.stat().st_ino
        expected_name = f"testcraft-full-project-{build_info.platform}-{work_dir_inode}"
        mock_provider.clean_project_environments.assert_called_once_with(
            instance_name=expected_name
        )


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
def test_load_bashrc_missing(
    monkeypatch,
    emitter,
    tmp_path,
    provider_service,
    fake_build_info,
    allow_unstable,
    mocker,
):
    """Test that we handle the case where the bashrc file is missing."""
    mock_provider = mock.MagicMock(spec=craft_providers.Provider)
    monkeypatch.setattr(
        provider_service,
        "get_provider",
        lambda name: mock_provider,
    )

    mocker.patch.object(pkgutil, "get_data", return_value=None)
    with provider_service.instance(
        fake_build_info, work_dir=tmp_path, allow_unstable=allow_unstable
    ) as instance:
        instance._setup_instance_bashrc(instance)
    emitter.assert_debug(
        "Could not find the bashrc file in the craft-application package"
    )


@pytest.fixture
def setup_fetch_logs_provider(monkeypatch, provider_service, mocker, tmp_path):
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
            lambda name: mock_provider,
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


def test_instance_fetch_logs(
    provider_service,
    setup_fetch_logs_provider,
    check,
    emitter,
    fake_build_info,
    mocker,
    tmp_path,
):
    """Test that logs from the build instance are fetched in case of success."""
    # Setup the build instance and pretend the command inside it finished successfully.
    provider_service = setup_fetch_logs_provider(should_have_logfile=True)
    mock_append = mocker.patch.object(emit, "append_to_log")
    with (
        provider_service.instance(
            build_info=fake_build_info,
            work_dir=pathlib.Path(),
        ) as mock_instance,
    ):
        pass

    # Now check that the logs from the build instance were collected.
    with check:
        mock_instance.temporarily_pull_file.assert_called_once_with(
            source=pathlib.PosixPath("/tmp/testcraft.log"), missing_ok=True
        )

    with check:
        emitter.assert_debug("Logs retrieved from managed instance:")

    mock_append.assert_called_once()


def test_instance_fetch_logs_error(
    provider_service,
    setup_fetch_logs_provider,
    check,
    emitter,
    fake_build_info,
    mocker,
    tmp_path,
):
    """Test that logs from the build instance are fetched in case of errors."""

    # Setup the build instance and pretend the command inside it finished with error.
    provider_service = setup_fetch_logs_provider(should_have_logfile=True)
    mock_append = mocker.patch.object(emit, "append_to_log")
    with (
        pytest.raises(RuntimeError),
        provider_service.instance(
            build_info=fake_build_info,
            work_dir=pathlib.Path(),
        ) as mock_instance,
    ):
        raise RuntimeError("Faking an error in the build instance!")

    # Now check that the logs from the build instance were collected.
    with check:
        mock_instance.temporarily_pull_file.assert_called_once_with(
            source=pathlib.PosixPath("/tmp/testcraft.log"), missing_ok=True
        )

    with check:
        emitter.assert_debug("Logs retrieved from managed instance:")

    mock_append.assert_called_once()


def test_instance_fetch_logs_missing_file(
    provider_service, setup_fetch_logs_provider, check, emitter, fake_build_info
):
    """Test that we handle the case where the logfile is missing."""

    # Setup the build instance and pretend the command inside it finished successfully.
    provider_service = setup_fetch_logs_provider(should_have_logfile=False)
    with provider_service.instance(
        build_info=fake_build_info,
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


@pytest.mark.parametrize(
    ("arch", "expected_platforms"),
    [  # Based on the fake project yaml in tests/conftest.py
        (
            craft_platforms.DebianArchitecture.AMD64,
            ["64-bit-pc", "some-phone", "risky", "s390x"],
        ),
        (craft_platforms.DebianArchitecture.ARM64, ["some-phone", "risky", "s390x"]),
        (craft_platforms.DebianArchitecture.ARMHF, ["s390x"]),
        (craft_platforms.DebianArchitecture.RISCV64, ["risky", "s390x"]),
        (craft_platforms.DebianArchitecture.PPC64EL, ["ppc64el", "risky", "s390x"]),
    ],
)
def test_clean_instances(provider_service, tmp_path, mocker, arch, expected_platforms):
    mocker.patch.object(
        craft_platforms.DebianArchitecture,
        "from_host",
        return_value=arch,
    )
    current_provider = provider_service.get_provider()
    mock_clean = mocker.patch.object(current_provider, "clean_project_environments")

    provider_service.clean_instances()

    work_dir_inode = tmp_path.stat().st_ino

    expected_mock_calls = [
        mock.call(instance_name=f"testcraft-full-project-{platform}-{work_dir_inode}")
        for platform in expected_platforms
    ]
    assert mock_clean.mock_calls == expected_mock_calls


@pytest.mark.parametrize("fetch", [False, True])
def test_run_managed(
    monkeypatch: pytest.MonkeyPatch,
    provider_service: provider.ProviderService,
    default_app_metadata: craft_application.AppMetadata,
    fake_services: ServiceFactory,
    fake_build_info: craft_platforms.BuildInfo,
    fetch: bool,
    mock_provider,
):
    mock_fetch = mock.MagicMock()
    fake_services.register("fetch", mock.Mock(return_value=mock_fetch))
    fake_services.get_class(
        "fetch"
    ).is_active.return_value = fetch  # # pyright: ignore[reportFunctionMemberAccess]
    monkeypatch.setattr("sys.argv", ["[unused]", "pack", "--verbose"])
    instance_context = (
        mock_provider.launched_environment.return_value.__enter__.return_value
    )

    provider_service.run_managed(fake_build_info, enable_fetch_service=fetch)
    instance_context.prepare_instance(instance_context)

    expected_env = {
        "CRAFT_VERBOSITY_LEVEL": mock.ANY,
        "CRAFT_PLATFORM": fake_build_info.platform,
    }

    instance_context.execute_run.assert_called_once_with(
        ["testcraft", "pack", "--verbose"],
        cwd=default_app_metadata.managed_instance_project_path,
        check=True,
        env=expected_env,
    )

    instance_context.prepare_instance.assert_called_once_with(mock.ANY)
