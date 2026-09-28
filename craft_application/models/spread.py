# This file is part of craft-application.
#
# Copyright 2024-2025 Canonical Ltd.
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
"""Models representing spread projects."""

import re
from typing import TYPE_CHECKING

import pydantic
from typing_extensions import Any, Self

if TYPE_CHECKING:
    from .state import PackedArtifact


from craft_application.models import CraftBaseModel

# Simplified spread configuration


class SpreadBase(CraftBaseModel):
    """Base model for spread.yaml, which can always take and ignore extra items."""

    model_config = pydantic.ConfigDict(
        CraftBaseModel.model_config,
        extra="allow",
    )


class CraftSpreadSystem(SpreadBase):
    """Simplified spread system configuration."""

    workers: int | None = pydantic.Field(
        default=None,
        description="The number of concurrent worker instances to create for this system.",
        examples=[2],
    )
    image: str | None = pydantic.Field(
        default=None,
        description=(
            "A custom container or virtual machine image to use for this system on non-``craft``"
            " backends."
        ),
        examples=["ubuntu:24.04", "ubuntu-noble-daily-amd64"],
    )


class CraftSpreadBackend(SpreadBase):
    """Simplified spread backend configuration."""

    type: str | None = pydantic.Field(
        default=None,
        description=(
            "The backend driver type, such as 'craft', 'lxd', or 'adhoc'. If not"
            " specified, the backend name is used as the type."
        ),
        examples=["craft"],
    )
    allocate: str | None = pydantic.Field(
        default=None,
        description="A command or script to allocate a remote instance for ad-hoc backends.",
        examples=["allocate-cloud-instance"],
    )
    discard: str | None = pydantic.Field(
        default=None,
        description="A command or script to release an allocated ad-hoc instance when finished.",
        examples=["release-cloud-instance"],
    )
    systems: list[str | dict[str, CraftSpreadSystem | None]] = pydantic.Field(
        examples=[["ubuntu-24.04", {"ubuntu-22.04": {"workers": 2}}]],
    )
    """A list of systems (operating system distributions or architectures) available for running tests.

    Can be specified as system names or mappings of system names to system configurations.
    """
    prepare: str | None = pydantic.Field(default=None, examples=["apt-get update"])
    """A shell script executed on the backend system before running any tests.

    This should only be used to run backend-specific preparation. It is *not compatible*
    with the ``craft`` backend.
    """
    restore: str | None = pydantic.Field(default=None, examples=["apt-get clean"])
    """A shell script executed on the backend system after all tests finish.

    This should only be used for backend-specific cleanup or restoration. It is *not
    compatible* with the ``craft`` backend.
    """
    debug: str | None = pydantic.Field(
        default=None,
        description="A shell script executed on the backend system if a test task encounters a failure.",
        examples=["cat /var/log/syslog"],
    )
    prepare_each: str | None = pydantic.Field(
        default=None,
        description="A shell script executed on the backend system before each test task.",
        examples=["systemctl restart test-service"],
    )
    restore_each: str | None = pydantic.Field(
        default=None,
        description="A shell script executed on the backend system after each test task completes.",
        examples=["systemctl stop test-service"],
    )
    debug_each: str | None = pydantic.Field(
        default=None,
        description="A shell script executed on the backend system if an individual test task fails.",
        examples=["systemctl status test-service"],
    )


class CraftSpreadSuite(SpreadBase):
    """Simplified spread suite configuration."""

    summary: str = pydantic.Field(
        description="A brief description of what the test suite covers.",
        examples=["General integration test suite"],
    )
    systems: list[str] | None = pydantic.Field(
        default=None,
        description=(
            "A list of systems on which to run this suite. If omitted, the suite"
            " runs on all systems defined in the backend."
        ),
        examples=[["ubuntu-24.04"]],
    )
    environment: dict[str, str] | None = pydantic.Field(
        default=None,
        description=(
            "Environment variables defined for all tests in this suite, expressed"
            " as key-value pairs."
        ),
        examples=[{"TEST_MODE": "production", "VERBOSE": "1"}],
    )
    prepare: str | None = pydantic.Field(
        default=None,
        description="A shell script executed once before executing any tests in this suite.",
        examples=['echo "Preparing suite"'],
    )
    restore: str | None = pydantic.Field(
        default=None,
        description="A shell script executed once after all tests in this suite complete.",
        examples=['echo "Restoring suite"'],
    )
    debug: str | None = pydantic.Field(
        default=None,
        description="A shell script executed if a suite prepare or restore step encounters an error.",
        examples=["cat /tmp/suite-error.log"],
    )
    prepare_each: str | None = pydantic.Field(
        default=None,
        description="A shell script executed before each individual test task in this suite.",
        examples=['test -f "${CRAFT_ARTIFACT}"'],
    )
    restore_each: str | None = pydantic.Field(
        default=None,
        description="A shell script executed after each individual test task in this suite completes.",
        examples=["rm -rf /tmp/task-cache"],
    )
    debug_each: str | None = pydantic.Field(
        default=None,
        description="A shell script executed if an individual test task in this suite fails.",
        examples=['echo "Task failed: $SPREAD_TASK"'],
    )
    kill_timeout: str | None = pydantic.Field(default=None, examples=["15m"])
    """The maximum duration allowed for an individual test task in this suite before ending the process.

    Overrides the top-level ``kill-timeout`` key.
    """


class CraftTestYaml(SpreadBase):
    """Simplified spread project configuration for a craft test file."""

    model_config = pydantic.ConfigDict(
        SpreadBase.model_config,
        extra="forbid",
    )

    backends: dict[str, CraftSpreadBackend] = pydantic.Field(
        description="A mapping of backend configurations used to execute tests.",
        examples=[{"craft": {"systems": ["ubuntu-24.04"]}}],
    )
    suites: dict[str, CraftSpreadSuite] = pydantic.Field(
        examples=[{"tests/spread/general/": {"summary": "General integration tests"}}],
    )
    """A mapping of test suite directories relative to the project root to their suite configurations.

    Each suite directory key must end with a trailing forward slash (/).
    """
    exclude: list[str] | None = pydantic.Field(
        default=None,
        description=(
            "A list of file and directory patterns relative to the project root to exclude"
            " from the test environment. Defaults to ['.git', '.tox']."
        ),
        examples=[[".git", ".tox", "docs/"]],
    )
    prepare: str | None = pydantic.Field(
        default=None,
        description="A shell script executed once on the test host before running any test suite.",
        examples=['echo "Setting up global test prerequisites"'],
    )
    restore: str | None = pydantic.Field(
        default=None,
        description="A shell script executed once after all test suites complete, regardless of outcome.",
        examples=['echo "Tearing down global test environment"'],
    )
    debug: str | None = pydantic.Field(
        default=None,
        description="A shell script executed if any step fails during the test run.",
        examples=["journalctl -xe"],
    )
    prepare_each: str | None = pydantic.Field(
        default=None,
        description="A shell script executed before each individual test task in every suite.",
        examples=["rm -rf /tmp/test-output"],
    )
    restore_each: str | None = pydantic.Field(
        default=None,
        description="A shell script executed after each individual test task in every suite completes.",
        examples=["rm -rf /tmp/test-output"],
    )
    debug_each: str | None = pydantic.Field(
        default=None,
        description="A shell script executed if an individual test task fails.",
        examples=["dmesg | tail -n 50"],
    )
    kill_timeout: str | None = pydantic.Field(
        default=None,
        description=(
            "The maximum duration allowed for tests before ending the process. Expressed"
            " as a duration string, such as '30m' or '1h'."
        ),
        examples=["30m"],
    )


class CraftSpreadYaml(CraftTestYaml):
    """Deprecated craft test spread.yaml.

    This is different than a standard spread.yaml, which is used directly with spread.

    The deprecated craft test spread.yaml is a subset of a standard spread.yaml. It
    doesn't allow the 'path', 'environment', and 'include' keys.
    """

    project: str | None = None


# Processed full-form spread configuration


class SpreadBaseModel(SpreadBase):
    """Base for spread models."""

    def model_post_init(self, /, __context: Any) -> None:  # noqa: ANN401
        """Remove attributes set to None."""
        none_items: list[Any] = []
        for k, v in self.__dict__.items():
            if v is None:
                none_items.append(k)

        for k in none_items:
            k.replace("_", "-")
            delattr(self, k)


class SpreadSystem(SpreadBaseModel):
    """Processed spread system configuration."""

    username: str | None = None
    password: str | None = None
    workers: int | None = None
    image: str | None = None

    @classmethod
    def from_craft(
        cls, simple: CraftSpreadSystem | None, image: str | None = None
    ) -> Self:
        """Create a spread system configuration from the simplified version."""
        workers = simple.workers if simple else 1
        return cls(workers=workers, image=image)


class SpreadBackend(SpreadBaseModel):
    """Processed spread backend configuration."""

    type: str | None = None
    allocate: str | None = None
    discard: str | None = None
    systems: list[str | dict[str, SpreadSystem]] = pydantic.Field(
        default_factory=list[str | dict[str, SpreadSystem]]
    )
    prepare: str | None = None
    restore: str | None = None
    debug: str | None = None
    prepare_each: str | None = None
    restore_each: str | None = None
    debug_each: str | None = None

    # For the openstack backend
    endpoint: str | None = None
    account: str | None = None
    key: str | None = None
    location: str | None = None
    plan: str | None = None
    halt_timeout: str | None = None

    @classmethod
    def from_craft(cls, simple: CraftSpreadBackend, images: dict[str, str]) -> Self:
        """Create a spread backend configuration from the simplified version."""
        return cls(
            type=simple.type,
            allocate=simple.allocate,
            discard=simple.discard,
            systems=cls.systems_from_craft(simple.systems, images=images),
            prepare=simple.prepare,
            restore=simple.restore,
            debug=simple.debug,
            prepare_each=simple.prepare_each,
            restore_each=simple.restore_each,
            debug_each=simple.debug_each,
        )

    @staticmethod
    def _get_system_image(name: str, images: dict[str, str]) -> str | None:
        """Return an image for a system name, tolerating the legacy -64 suffix."""
        return images.get(name) or images.get(name.removesuffix("-64"))

    @staticmethod
    def systems_from_craft(
        simple: list[str | dict[str, CraftSpreadSystem | None]], images: dict[str, str]
    ) -> list[str | dict[str, SpreadSystem]]:
        """Create spread systems from the simplified version.

        :param simple: List of system definitions as strings or name-to-system dicts.
        :param images: Mapping of system names to their container image URLs.
        """
        systems: list[str | dict[str, SpreadSystem]] = []
        for item in simple:
            entry: dict[str, SpreadSystem] = {}
            if isinstance(item, str):
                image = SpreadBackend._get_system_image(item, images)
                if image:
                    entry[item] = SpreadSystem(workers=1, image=image)
                    systems.append(entry)
                else:
                    systems.append(item)
                continue

            for name, ssys in item.items():
                if ssys:
                    image = ssys.image or SpreadBackend._get_system_image(name, images)
                else:
                    image = SpreadBackend._get_system_image(name, images)
                entry[name] = SpreadSystem.from_craft(ssys, image=image)
            systems.append(entry)

        return systems


class SpreadSuite(SpreadBaseModel):
    """Processed spread suite configuration."""

    summary: str
    systems: list[str] | None
    environment: dict[str, str] | None
    prepare: str | None
    restore: str | None
    prepare_each: str | None
    restore_each: str | None
    debug: str | None = None
    debug_each: str | None = None
    kill_timeout: str | None = None

    @classmethod
    def from_craft(cls, simple: CraftSpreadSuite) -> Self:
        """Create a spread suite configuration from the simplified version."""
        return cls(
            summary=simple.summary,
            systems=simple.systems or [],
            environment=simple.environment,
            prepare=simple.prepare,
            restore=simple.restore,
            prepare_each=simple.prepare_each,
            restore_each=simple.restore_each,
            kill_timeout=simple.kill_timeout,
            debug=simple.debug,
            debug_each=simple.debug_each,
        )


class SpreadYaml(SpreadBaseModel):
    """Processed spread project configuration."""

    project: str
    environment: dict[str, str]
    backends: dict[str, SpreadBackend]
    suites: dict[str, SpreadSuite]
    exclude: list[str]
    path: str
    prepare: str | None
    restore: str | None
    prepare_each: str | None
    restore_each: str | None
    debug: str | None = None
    debug_each: str | None = None
    kill_timeout: str | None = None
    reroot: str | None = None

    @classmethod
    def from_craft(
        cls,
        simple: CraftTestYaml,
        *,
        craft_backend: SpreadBackend,
        artifacts: list["PackedArtifact"],
        images: dict[str, str],
    ) -> Self:
        """Create the spread configuration from the simplified version."""
        environment = {
            "SUDO_USER": "",
            "SUDO_UID": "",
            "LANG": "C.UTF-8",
            "LANGUAGE": "en",
            "PROJECT_PATH": "/root/proj",
        }

        for artifact in artifacts:
            if artifact.name is None:
                environment["CRAFT_ARTIFACT"] = f"$PROJECT_PATH/{artifact.path}"
                continue

            var_name = cls._translate_resource_name(artifact.name)
            environment[f"CRAFT_ARTIFACT_{var_name}"] = f"$PROJECT_PATH/{artifact.path}"

        return cls(
            project="craft-test",
            environment=environment,
            backends=cls._backends_from_craft(simple.backends, craft_backend, images),
            suites=cls._suites_from_craft(simple.suites),
            exclude=simple.exclude or [".git", ".tox"],
            path="/root/proj",
            prepare=simple.prepare,
            restore=simple.restore,
            prepare_each=simple.prepare_each,
            restore_each=simple.restore_each,
            kill_timeout=simple.kill_timeout or None,
            debug=simple.debug,
            debug_each=simple.debug_each,
            reroot="..",
        )

    @staticmethod
    def _translate_resource_name(name: str) -> str:
        return re.sub(r"[^A-Za-z0-9_]", "_", name).upper()

    @staticmethod
    def _backends_from_craft(
        simple: dict[str, CraftSpreadBackend],
        craft_backend: SpreadBackend,
        images: dict[str, str],
    ) -> dict[str, SpreadBackend]:
        backends: dict[str, SpreadBackend] = {}
        for name, backend in simple.items():
            # Spread assumes the backend name as the type when it's not explicitly declared.
            if name == "craft" and (not backend.type or backend.type == "craft"):
                craft_backend.systems = SpreadBackend.systems_from_craft(
                    backend.systems, images=images
                )
                backends[name] = craft_backend
            else:
                backends[name] = SpreadBackend.from_craft(backend, images={})

        return backends

    @staticmethod
    def _suites_from_craft(
        simple: dict[str, CraftSpreadSuite],
    ) -> dict[str, SpreadSuite]:
        return {name: SpreadSuite.from_craft(suite) for name, suite in simple.items()}
