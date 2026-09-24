.. Add an application-specific meta description in the document including this file,
.. for example using the ``.. meta::`` directive with a ``:description:`` option.

.. _reference-craft-test-yaml:

|app-command|\ -test.yaml
=========================

This reference describes the usage of and provides examples for every key in a
|Starcraft| test configuration file, :substitution-code:`|app-command|-test.yaml`.

When you run :substitution-code:`|app-command| test`, |Starcraft| reads this file and generates a
temporary configuration file for Spread to run integration and functional tests.

In contrast to native Spread files, :substitution-code:`|app-command|-test.yaml` disallows several keys
that are managed directly by |Starcraft|:

- ``path``: Managed exclusively by |Starcraft| to point to the workspace directory.
- ``project``: Set to ``craft-test`` in the generated Spread configuration.
- Top-level ``environment``: Injected dynamically by |Starcraft| with runtime variables
  such as ``CRAFT_ARTIFACT`` and ``PROJECT_PATH``.
- ``include``: Not supported.

In addition, some child keys of ``backend`` are allowed for other backends, but not for
the ``craft`` backend.

.. _reference-craft-test-yaml-top-level-keys:

Top-level keys
--------------

Top-level keys define global exclusion patterns, prepare and restore scripts, and
execution timeouts.

.. py:currentmodule:: craft_application.models.spread

.. kitbash-field:: CraftTestYaml exclude
    :override-description:
    :skip-examples:

    A list of file and directory patterns relative to the project root to exclude from
    the test environment. Defaults to ``['.git', '.tox']``.

    **Examples**

    .. code-block:: yaml

        exclude:
          - .git
          - .tox
          - docs/

.. kitbash-field:: CraftTestYaml prepare
    :override-description:
    :skip-examples:

    A shell script executed once on the test host before running any test suite.

    **Examples**

    .. code-block:: yaml

        prepare: |
          echo "Setting up global test prerequisites"

.. kitbash-field:: CraftTestYaml restore
    :override-description:
    :skip-examples:

    A shell script executed once after all test suites complete, regardless of outcome.

    **Examples**

    .. code-block:: yaml

        restore: |
          echo "Tearing down global test environment"

.. kitbash-field:: CraftTestYaml debug
    :override-description:
    :skip-examples:

    A shell script executed if any step fails during the test run.

    **Examples**

    .. code-block:: yaml

        debug: |
          journalctl -xe

.. kitbash-field:: CraftTestYaml prepare_each
    :override-description:
    :skip-examples:

    A shell script executed before each individual test task in every suite.

    **Examples**

    .. code-block:: yaml

        prepare-each: |
          rm -rf /tmp/test-output

.. kitbash-field:: CraftTestYaml restore_each
    :override-description:
    :skip-examples:

    A shell script executed after each individual test task in every suite completes.

    **Examples**

    .. code-block:: yaml

        restore-each: |
          rm -rf /tmp/test-output

.. kitbash-field:: CraftTestYaml debug_each
    :override-description:
    :skip-examples:

    A shell script executed if an individual test task fails.

    **Examples**

    .. code-block:: yaml

        debug-each: |
          dmesg | tail -n 50

.. kitbash-field:: CraftTestYaml kill_timeout
    :override-description:
    :skip-examples:

    The maximum duration allowed for tests before ending the process. Expressed as a
    duration string, such as ``30m`` or ``1h``.

    **Examples**

    .. code-block:: yaml

        kill-timeout: 30m


.. _reference-craft-test-yaml-backend-keys:

Backend keys
------------

Backend keys configure the runtime environments where tests execute. The ``craft``
backend is used by default by |Starcraft| to configure system images and worker
instances for tests. Other backends can be manually specified.

.. kitbash-field:: CraftTestYaml backends
    :override-description:
    :skip-examples:

    A mapping of backend configurations used to execute tests. Usually includes the
    ``craft`` backend, which |Starcraft| populates automatically with target system
    images.

    **Examples**

    .. code-block:: yaml

        backends:
          craft:
            systems:
              - ubuntu-24.04

.. kitbash-field:: CraftSpreadBackend type
    :prepend-name: backends.<backend-name>
    :override-description:
    :skip-examples:

    The backend driver type, such as ``craft``, ``lxd``, or ``adhoc``. If not specified,
    the backend name is used as the type.

    **Examples**

    .. code-block:: yaml

        backends:
          craft:
            type: craft

.. kitbash-field:: CraftSpreadBackend systems
    :prepend-name: backends.<backend-name>
    :override-description:
    :skip-examples:

    A list of systems (operating system distributions or architectures) available for
    running tests. Can be specified as system names or mappings of system names to system
    configurations.

    **Examples**

    .. code-block:: yaml

        backends:
          craft:
            systems:
              - ubuntu-24.04
              - ubuntu-22.04:
                  workers: 2

.. kitbash-field:: CraftSpreadBackend allocate
    :prepend-name: backends.<backend-name>
    :override-description:
    :skip-examples:

    A command or script to allocate a remote instance for ad-hoc backends.

    **Examples**

    .. code-block:: yaml

        backends:
          custom:
            type: adhoc
            allocate: allocate-cloud-instance

.. kitbash-field:: CraftSpreadBackend discard
    :prepend-name: backends.<backend-name>
    :override-description:
    :skip-examples:

    A command or script to release an allocated ad-hoc instance when finished.

    **Examples**

    .. code-block:: yaml

        backends:
          custom:
            type: adhoc
            discard: release-cloud-instance

.. kitbash-field:: CraftSpreadBackend prepare
    :prepend-name: backends.<backend-name>
    :override-description:
    :skip-examples:

    A shell script executed on the backend system before running any tests. This should
    only be used to run backend-specific preparation. It is *not compatible* with the
    ``craft`` backend.

    **Examples**

    .. code-block:: yaml

        backends:
          openstack:
            prepare: |
              apt-get update

.. kitbash-field:: CraftSpreadBackend restore
    :prepend-name: backends.<backend-name>
    :override-description:
    :skip-examples:

    A shell script executed on the backend system after all tests finish. This should
    only be used for backend-specific cleanup or restoration. It is *not compatible* with the
    ``craft`` backend.

    **Examples**

    .. code-block:: yaml

        backends:
          openstack:
            restore: |
              apt-get clean

.. kitbash-field:: CraftSpreadBackend debug
    :prepend-name: backends.<backend-name>
    :override-description:
    :skip-examples:

    A shell script executed on the backend system if a test task encounters a failure.

    **Examples**

    .. code-block:: yaml

        backends:
          openstack:
            debug: |
              cat /var/log/syslog

.. kitbash-field:: CraftSpreadBackend prepare_each
    :prepend-name: backends.<backend-name>
    :override-description:
    :skip-examples:

    A shell script executed on the backend system before each test task.

    **Examples**

    .. code-block:: yaml

        backends:
          openstack:
            prepare-each: |
              systemctl restart test-service

.. kitbash-field:: CraftSpreadBackend restore_each
    :prepend-name: backends.<backend-name>
    :override-description:
    :skip-examples:

    A shell script executed on the backend system after each test task completes.

    **Examples**

    .. code-block:: yaml

        backends:
          openstack:
            restore-each: |
              systemctl stop test-service

.. kitbash-field:: CraftSpreadBackend debug_each
    :prepend-name: backends.<backend-name>
    :override-description:
    :skip-examples:

    A shell script executed on the backend system if an individual test task fails.

    **Examples**

    .. code-block:: yaml

        backends:
          openstack:
            debug-each: |
              systemctl status test-service


.. _reference-craft-test-yaml-system-keys:

System keys
-----------

When a backend system requires specific configuration options rather than default
settings, it is specified as a mapping under the backend ``systems`` list.

.. kitbash-field:: CraftSpreadSystem workers
    :prepend-name: backends.<backend-name>.systems.<system-name>
    :override-description:
    :skip-examples:

    The number of concurrent worker instances to create for this system.

    **Examples**

    .. code-block:: yaml

        backends:
          craft:
            systems:
              - ubuntu-24.04:
                  workers: 2

.. kitbash-field:: CraftSpreadSystem image
    :prepend-name: backends.<backend-name>.systems.<system-name>
    :override-description:
    :skip-examples:

    A custom container or virtual machine image to use for this system on non-``craft``
    backends.
    In |app-command|\ -test.yaml, the ``craft`` backend uses this value to override the
    image selected by |Starcraft| for the system.

    **Examples**

    .. code-block:: yaml

        backends:
          lxd:
            systems:
              - ubuntu-24.04:
                  image: ubuntu:24.04
          craft:
            systems:
              - ubuntu-24.04:
                  image: custom-ubuntu-24.04


.. _reference-craft-test-yaml-suite-keys:

Suite keys
----------

Suite keys configure individual test suites. The suite key must match the path of the
directory containing the tests and end with a trailing forward slash (/).

.. kitbash-field:: CraftTestYaml suites
    :override-description:
    :skip-examples:

    A mapping of test suite directories relative to the project root to their suite
    configurations. Each suite directory key must end with a trailing forward slash (/).

    **Examples**

    .. code-block:: yaml

        suites:
          tests/spread/general/:
            summary: General integration tests

.. kitbash-field:: CraftSpreadSuite summary
    :prepend-name: suites.<suite-path>
    :override-description:
    :skip-examples:

    A brief description of what the test suite covers.

    **Examples**

    .. code-block:: yaml

        suites:
          tests/spread/general/:
            summary: General integration test suite

.. kitbash-field:: CraftSpreadSuite systems
    :prepend-name: suites.<suite-path>
    :override-description:
    :skip-examples:

    A list of systems on which to run this suite. If omitted, the suite runs on all
    systems defined in the backend.

    **Examples**

    .. code-block:: yaml

        suites:
          tests/spread/general/:
            summary: General integration test suite
            systems:
              - ubuntu-24.04

.. kitbash-field:: CraftSpreadSuite environment
    :prepend-name: suites.<suite-path>
    :override-description:
    :skip-examples:

    Environment variables defined for all tests in this suite, expressed as key-value
    pairs.

    **Examples**

    .. code-block:: yaml

        suites:
          tests/spread/general/:
            summary: General integration test suite
            environment:
              TEST_MODE: production
              VERBOSE: "1"

.. kitbash-field:: CraftSpreadSuite prepare
    :prepend-name: suites.<suite-path>
    :override-description:
    :skip-examples:

    A shell script executed once before executing any tests in this suite.

    **Examples**

    .. code-block:: yaml

        suites:
          tests/spread/general/:
            summary: General integration test suite
            prepare: |
              echo "Preparing suite"

.. kitbash-field:: CraftSpreadSuite restore
    :prepend-name: suites.<suite-path>
    :override-description:
    :skip-examples:

    A shell script executed once after all tests in this suite complete.

    **Examples**

    .. code-block:: yaml

        suites:
          tests/spread/general/:
            summary: General integration test suite
            restore: |
              echo "Restoring suite"

.. kitbash-field:: CraftSpreadSuite debug
    :prepend-name: suites.<suite-path>
    :override-description:
    :skip-examples:

    A shell script executed if a suite prepare or restore step encounters an error.

    **Examples**

    .. code-block:: yaml

        suites:
          tests/spread/general/:
            summary: General integration test suite
            debug: |
              cat /tmp/suite-error.log

.. kitbash-field:: CraftSpreadSuite prepare_each
    :prepend-name: suites.<suite-path>
    :override-description:
    :skip-examples:

    A shell script executed before each individual test task in this suite.

    **Examples**

    .. code-block:: yaml

        suites:
          tests/spread/general/:
            summary: General integration test suite
            prepare-each: |
              test -f "${CRAFT_ARTIFACT}"

.. kitbash-field:: CraftSpreadSuite restore_each
    :prepend-name: suites.<suite-path>
    :override-description:
    :skip-examples:

    A shell script executed after each individual test task in this suite completes.

    **Examples**

    .. code-block:: yaml

        suites:
          tests/spread/general/:
            summary: General integration test suite
            restore-each: |
              rm -rf /tmp/task-cache

.. kitbash-field:: CraftSpreadSuite debug_each
    :prepend-name: suites.<suite-path>
    :override-description:
    :skip-examples:

    A shell script executed if an individual test task in this suite fails.

    **Examples**

    .. code-block:: yaml

        suites:
          tests/spread/general/:
            summary: General integration test suite
            debug-each: |
              echo "Task failed: $SPREAD_TASK"

.. kitbash-field:: CraftSpreadSuite kill_timeout
    :prepend-name: suites.<suite-path>
    :override-description:
    :skip-examples:

    The maximum duration allowed for an individual test task in this suite before ending
    the process. Overrides the top-level ``kill-timeout`` key.

    **Examples**

    .. code-block:: yaml

        suites:
          tests/spread/general/:
            summary: General integration test suite
            kill-timeout: 15m
