#  This file is part of craft-application.
#
#  Copyright 2025 Canonical Ltd.
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
"""Unit tests for the ProxyService."""

import pathlib
import subprocess
from unittest import mock
from unittest.mock import call

import pytest
from craft_application import services
from craft_providers.lxd import LXDInstance


@pytest.fixture
def proxy_service(app, fake_services, fake_project):
    return services.ProxyService(
        app,
        fake_services,
    )


def test_configure_build_instance(mocker, proxy_service, new_dir):
    proxy_cert = pathlib.Path("test.pem")
    proxy_cert.touch()
    proxy_service.configure(
        proxy_cert=pathlib.Path("test.pem"), http_proxy="test-proxy"
    )
    mock_instance = mock.MagicMock(spec_set=LXDInstance)

    env = proxy_service.configure_instance(mock_instance)
    assert env == {
        "http_proxy": "test-proxy",
        "https_proxy": "test-proxy",
        "REQUESTS_CA_BUNDLE": "/usr/local/share/ca-certificates/local-ca.crt",
        "CARGO_HTTP_CAINFO": "/usr/local/share/ca-certificates/local-ca.crt",
        "GOPROXY": "direct",
    }

    proxy_service.finalize_instance_configuration(mock_instance)

    # Execution calls on the instance
    default_args = {"check": True, "stdout": subprocess.PIPE, "stderr": subprocess.PIPE}
    assert mock_instance.execute_run.mock_calls == [
        call(
            ["mkdir", "-p", "/usr/local/share/ca-certificates"],
            **default_args,
        ),
        call(
            ["/bin/sh", "-c", "/usr/sbin/update-ca-certificates > /dev/null"],
            **default_args,
        ),
        call(
            ["test", "-d", "/etc/apt"],
            **default_args,
        ),
        call(
            ["/bin/rm", "-Rf", "/var/lib/apt/lists"],
            **default_args,
        ),
        call(
            ["apt", "update"],
            **default_args,
        ),
        call(
            ["mkdir", "-p", "/root/.pip"],
            **default_args,
        ),
        call(
            ["systemctl", "restart", "snapd"],
            **default_args,
        ),
        call(
            ["snap", "set", "system", "proxy.http=test-proxy"],
            **default_args,
        ),
        call(
            ["snap", "set", "system", "proxy.https=test-proxy"],
            **default_args,
        ),
    ]

    # Files pushed to the instance
    assert mock_instance.push_file.mock_calls == [
        call(
            source=proxy_cert,
            destination=pathlib.Path("/usr/local/share/ca-certificates/local-ca.crt"),
        )
    ]

    assert mock_instance.push_file_io.mock_calls == [
        call(
            destination=pathlib.Path("/etc/apt/apt.conf.d/99proxy"),
            content=mocker.ANY,
            file_mode="0644",
        ),
        call(
            destination=pathlib.Path("/root/.pip/pip.conf"),
            content=mocker.ANY,
            file_mode="0644",
        ),
    ]


def test_configure_skip_apt(mocker, proxy_service, new_dir, emitter):
    """Skip apt configuration if apt isn't available."""
    proxy_cert = pathlib.Path("test.pem")
    proxy_cert.touch()
    proxy_service.configure(
        proxy_cert=pathlib.Path("test.pem"), http_proxy="test-proxy"
    )

    def _has_apt(*args, **kwargs):
        if args == (["test", "-d", "/etc/apt"],):
            raise subprocess.CalledProcessError(1, [])
        return mock.DEFAULT

    mock_instance = mock.MagicMock(spec_set=LXDInstance)
    mock_instance.execute_run.side_effect = _has_apt

    proxy_service.configure_instance(mock_instance)
    proxy_service.finalize_instance_configuration(mock_instance)

    emitter.assert_debug(
        "Not configuring the proxy for apt because apt isn't available in the instance."
    )
    # Execution calls on the instance
    default_args = {"check": True, "stdout": subprocess.PIPE, "stderr": subprocess.PIPE}
    assert mock_instance.execute_run.mock_calls == [
        call(
            ["mkdir", "-p", "/usr/local/share/ca-certificates"],
            **default_args,
        ),
        call(
            ["/bin/sh", "-c", "/usr/sbin/update-ca-certificates > /dev/null"],
            **default_args,
        ),
        call(
            ["test", "-d", "/etc/apt"],
            **default_args,
        ),
        call(
            ["mkdir", "-p", "/root/.pip"],
            **default_args,
        ),
        call(
            ["systemctl", "restart", "snapd"],
            **default_args,
        ),
        call(
            ["snap", "set", "system", "proxy.http=test-proxy"],
            **default_args,
        ),
        call(
            ["snap", "set", "system", "proxy.https=test-proxy"],
            **default_args,
        ),
    ]

    # Files pushed to the instance
    assert mock_instance.push_file.mock_calls == [
        call(
            source=proxy_cert,
            destination=pathlib.Path("/usr/local/share/ca-certificates/local-ca.crt"),
        )
    ]

    assert mock_instance.push_file_io.mock_calls == [
        call(
            destination=pathlib.Path("/root/.pip/pip.conf"),
            content=mocker.ANY,
            file_mode="0644",
        ),
    ]


def test_not_configured(proxy_service, emitter):
    """No-op if the ProxyService isn't configured."""
    mock_instance = mock.MagicMock(spec_set=LXDInstance)

    proxy_service.configure_instance(mock_instance)
    proxy_service.finalize_instance_configuration(mock_instance)

    emitter.assert_debug(
        "Skipping proxy configuration because the proxy service isn't configured."
    )
    mock_instance.assert_not_called()
