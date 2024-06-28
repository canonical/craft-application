*********
Changelog
*********

3.0.0 (2024-Jun-28)
-------------------

Craft Application 3.0.0 implements the ``BuildPlanner`` class and can create
a build plan. This is a breaking change because it requires more fields to
be defined.

.. warning::

   ``platforms`` is now a required field in the ``Project``

   ``platforms``, ``base``, and ``build-base`` are now required fields in the
   ``BuildPlanner`` model

Application
===========

* Extends ``add_command_groups()`` to accept a sequence instead of a list.
* Adds support for building architecture-independent artefacts by accepting
  ``all`` as the ``build-for`` target.

Models
======

* Adds a default ``Platform`` model. See :doc:`platforms</reference/platforms>`
  for a reference of the model.
* Adds a default ``get_build_plan()`` function to the ``BuildPlanner`` class.
  See :doc:`Build plans</explanation/build-plans>` for an explanation of how
  the default ``get_build_plan()`` works.
* Changes ``BuildPlanner`` from an abstract class to a fully implemented class.
  Applications can now use the ``BuildPlanner`` class directly.

For a complete list of commits, check out the `3.0.0`_ release on GitHub.

2.8.0 (2024-Jun-03)
-------------------

Commands
========

* Fixes a bug where the pack command could accept a list of parts as command
  line arguments.
* Adds support for commands to accept multiple ``platform`` or ``build-for``
  values from the command line as comma-separated values.

Remote build
============

* Retries more API calls to Launchpad.
* Adds an exponential backoff to API retries with a maximum total delay of
  62 seconds.
* Fixes a bug where the full project name was not used in the remote build log
  files.

For a complete list of commits, check out the `2.8.0`_ release on GitHub.

2.7.0 (2024-May-08)
-------------------

Base naming convention
======================

Applications that use a non-default base naming convention must implement
``Project._providers_base()`` to translate application-specific base names into
a Craft Providers base.

The default base naming convention is ``<distribution>@<series>``. For example,
``ubuntu@24.04``, ``centos@7``, and ``almalinux@9``.

LifecycleCommand
================

Adds a new ``LifecycleCommand`` class that can be inherited for creating
application-specific lifecycle commands.

``_needs_project()``
====================

Adds a new command function ``_needs_project()`` that can be overridden by
subclasses. It's similar to the ``always_load_project`` class variable but takes
``parsed_args`` as a parameter. The default value is ``always_load_project``.

For a complete list of commits, check out the `2.7.0`_ release on GitHub.


.. _2.7.0: https://github.com/canonical/craft-application/releases/tag/2.7.0
.. _2.8.0: https://github.com/canonical/craft-application/releases/tag/2.8.0
.. _3.0.0: https://github.com/canonical/craft-application/releases/tag/3.0.0
