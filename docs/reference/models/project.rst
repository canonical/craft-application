.. _reference-models-project:

.. py:module:: craft_application.models.project

Project
=======

The ``Project`` model is a base schema that craft applications can modify to meet the
needs of their respective domains.


Schema
------

.. kitbash-field:: Project name

.. kitbash-field:: Project title

.. kitbash-field:: Project version

.. kitbash-field:: Project summary

.. kitbash-field:: Project description

.. kitbash-field:: Project base

**Description**

The base layer used as the project's run-time environment.

If the ``build-base`` key is unset, then the ``base`` key also determines
the project's build environment.

.. kitbash-field:: Project build_base

**Description**

This key determines the project's build environment.

.. kitbash-field:: Project platforms
    :override-type: dict[str, Platform]

.. kitbash-field:: Project contact
    :override-type: str | list[str]

.. kitbash-field:: Project issues
    :override-type: str | list[str]

.. kitbash-field:: Project source_code
    :override-type: str | list[str]

.. kitbash-field:: Project license

.. kitbash-field:: Project adopt_info

.. kitbash-field:: Project parts
    :override-type: dict[str, Part]

.. kitbash-field:: Project package_repositories
    :override-type: list[dict[str, Any]]
