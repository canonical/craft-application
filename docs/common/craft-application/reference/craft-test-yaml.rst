|app-command|\ -test.yaml
=========================

This reference describes the usage of and provides examples for every key in a
configuration file for a |star|'s tests, :substitution-code:`|app-command|-test.yaml`.

.. This should be moved to an explanation text at some point:

    When you run :substitution-code:`|app-command| test`, |Starcraft| reads this file and generates a
    temporary configuration file for Spread to run integration and functional tests.

    In contrast to native Spread files, :substitution-code:`|app-command|-test.yaml` disallows several keys
    that are managed directly by |Starcraft|:

    - ``path``: Managed exclusively by |Starcraft| to point to the workspace directory.
    - ``project``: Set to ``craft-test`` in the generated Spread configuration.
    - Top-level ``environment``: Injected dynamically by |Starcraft| with runtime variables
    such as ``CRAFT_ARTIFACT`` and ``PROJECT_PATH``.
    - ``include``: Not supported.

    When the ``craft`` backend's ``type`` is omitted or set to ``craft``, |Starcraft|
    only reads its ``systems`` key. All other child keys are replaced by backend
    configuration managed by |Starcraft|.

.. _reference-craft-test-yaml-top-level-keys:

Top-level keys
--------------

Top-level keys define global exclusion patterns, prepare and restore scripts, and
execution timeouts.

.. py:currentmodule:: craft_application.models.spread

.. kitbash-field:: CraftTestYaml exclude


.. kitbash-field:: CraftTestYaml prepare


.. kitbash-field:: CraftTestYaml prepare_each


.. kitbash-field:: CraftTestYaml restore


.. kitbash-field:: CraftTestYaml restore_each


.. kitbash-field:: CraftTestYaml debug


.. kitbash-field:: CraftTestYaml debug_each


.. kitbash-field:: CraftTestYaml kill_timeout

.. _reference-craft-test-yaml-backend-keys:

Backend keys
------------

Backend keys configure the runtime environments where tests execute. The ``craft``
backend is used by default by |Starcraft| to configure system images and worker
instances for tests. Other backends can be manually specified.


.. kitbash-field:: CraftTestYaml backends

    Usually includes the ``craft`` backend, which |Starcraft| populates automatically with
    target system images.


.. kitbash-field:: CraftSpreadBackend type
    :prepend-name: backends.<backend-name>


.. kitbash-field:: CraftSpreadBackend systems
    :prepend-name: backends.<backend-name>


.. kitbash-field:: CraftSpreadBackend allocate
    :prepend-name: backends.<backend-name>


.. kitbash-field:: CraftSpreadBackend discard
    :prepend-name: backends.<backend-name>


.. kitbash-field:: CraftSpreadBackend prepare
    :prepend-name: backends.<backend-name>


.. kitbash-field:: CraftSpreadBackend prepare_each
    :prepend-name: backends.<backend-name>


.. kitbash-field:: CraftSpreadBackend restore
    :prepend-name: backends.<backend-name>


.. kitbash-field:: CraftSpreadBackend restore_each
    :prepend-name: backends.<backend-name>


.. kitbash-field:: CraftSpreadBackend debug
    :prepend-name: backends.<backend-name>


.. kitbash-field:: CraftSpreadBackend debug_each
    :prepend-name: backends.<backend-name>

.. _reference-craft-test-yaml-system-keys:

System keys
-----------

When a backend system requires specific configuration options rather than default
settings, it is specified as a mapping under the backend ``systems`` list.


.. kitbash-field:: CraftSpreadSystem workers
    :prepend-name: backends.<backend-name>.systems.<system-name>


.. kitbash-field:: CraftSpreadSystem image
    :prepend-name: backends.<backend-name>.systems.<system-name>

    In |app-command|\ -test.yaml, the ``craft`` backend uses the backend's image
    identifier format to override the image selected by |Starcraft| for the system.

.. _reference-craft-test-yaml-suite-keys:

Suite keys
----------

Suite keys configure individual test suites. The suite key must match the path of the
directory containing the tests and end with a trailing forward slash (/).


.. kitbash-field:: CraftTestYaml suites


.. kitbash-field:: CraftSpreadSuite summary
    :prepend-name: suites.<suite-path>


.. kitbash-field:: CraftSpreadSuite systems
    :prepend-name: suites.<suite-path>


.. kitbash-field:: CraftSpreadSuite environment
    :prepend-name: suites.<suite-path>


.. kitbash-field:: CraftSpreadSuite prepare
    :prepend-name: suites.<suite-path>


.. kitbash-field:: CraftSpreadSuite prepare_each
    :prepend-name: suites.<suite-path>


.. kitbash-field:: CraftSpreadSuite restore
    :prepend-name: suites.<suite-path>


.. kitbash-field:: CraftSpreadSuite restore_each
    :prepend-name: suites.<suite-path>


.. kitbash-field:: CraftSpreadSuite debug
    :prepend-name: suites.<suite-path>


.. kitbash-field:: CraftSpreadSuite debug_each
    :prepend-name: suites.<suite-path>


.. kitbash-field:: CraftSpreadSuite kill_timeout
    :prepend-name: suites.<suite-path>
