*********
Changelog
*********

4.2.5 (2024-Oct-04)
-------------------

Services
========

- The config service handles snap issues better.

For a complete list of commits, check out the `4.2.5`_ release on GitHub.

4.2.4 (2024-Sep-19)
-------------------

Remote build
============

- Remote build errors are now a subclass of ``CraftError``.

For a complete list of commits, check out the `4.2.4`_ release on GitHub.

4.2.3 (2024-Sep-18)
-------------------

Application
===========

- ``get_arg_or_config`` now correctly checks the config service if the passed
  namespace has ``None`` as the value of the requested item.

For a complete list of commits, check out the `4.2.3`_ release on GitHub.

4.2.2 (2024-Sep-13)
-------------------

Application
===========

- Add a ``_run_inner`` method to override or wrap the core run logic.

For a complete list of commits, check out the `4.2.2`_ release on GitHub.

4.2.1 (2024-Sep-13)
-------------------

Models
======

- Fix a regression where numeric part properties could not be parsed.

For a complete list of commits, check out the `4.2.1`_ release on GitHub.

4.2.0 (2024-Sep-12)
-------------------

Application
===========

- Add a configuration service to unify handling of command line arguments,
  environment variables, snap configurations, and so on.
- Use the standard library to retrieve the host's proxies.

Commands
========

- Properly support ``--shell``, ``--shell-after`` and ``--debug`` on the
  ``pack`` command.

For a complete list of commits, check out the `4.2.0`_ release on GitHub.

4.1.2 (2024-Sep-05)
-------------------

Application
===========

- Managed runs now fail if the build plan is empty.
- Error message tweaks for invalid YAML files.

Models
======

- Platform models now correctly accept non-vectorised architectures.

For a complete list of commits, check out the `4.1.2`_ release on GitHub.

4.1.1 (2024-Aug-27)
-------------------

Application
===========

* When a build fails due to matching multiple platforms, those matching
  platforms will be specified in the error message.
* Show nicer error messages for invalid YAML files.

For a complete list of commits, check out the `4.1.1`_ release on GitHub.

4.1.0 (2024-Aug-14)
-------------------

Application
===========

If an app isn't running from snap, the installed app will install the snap
in the provider using the channel in the ``CRAFT_SNAP_CHANNEL`` environment
variable, defaulting to ``latest/stable`` if none is set.

Services
========

The ``LifecycleService`` now breaks out a ``_get_build_for`` method for
apps to override if necessary.

For a complete list of commits, check out the `4.1.0`_ release on GitHub.

4.0.0 (2024-Aug-09)
-------------------

Breaking changes
================

This release migrates to pydantic 2.
Most exit codes use constants from the ``os`` module. (This makes
craft-application 4 only compatible with Windows when using Python 3.11+.)

Models
======
Add constrained string fields that check for SPDX license strings or the
license string "proprietary".

CraftBaseModel now includes a ``to_yaml_string`` method.

Custom regex-based validators can be built with
``models.get_validator_by_regex``. These can be used to make a better error
message than the pydantic default.

Git
===

The ``git`` submodule under ``launchpad`` is now its own module and can clone
repositories and add remotes.


For a complete list of commits, check out the `4.0.0`_ release on GitHub.


3.2.0 (2024-Jul-07)
-------------------

Application
===========

Add support for *versioned* documentation urls - that is, urls that point to
the documentation for the specific version of the running application.

Documentation
=============

Add a how-to guide for using partitions.

For a complete list of commits, check out the `3.2.0`_ release on GitHub.

3.1.0 (2024-Jul-05)
-------------------

.. note::

   3.1.0 includes changes from the 2.9.0 release.

Remote build
============

Add a ``credentials_filepath`` property to the ``RemoteBuildService`` so that
applications can point to a different Launchpad credentials file.

For a complete list of commits, check out the `3.1.0`_ release on GitHub.

2.9.0 (2024-Jul-03)
-------------------

Application
===========

* Support doc slugs for craft-parts build errors, to point to the plugin docs.
* Support setting the base docs url on the AppMetadata, used in conjunction
  with slugs to build full urls.
* Add a method to enable craft-parts Features. This is called at a specific
  point so that things like command groups can rely on the features being set.
* Ensure the craft-providers' provider is available before launching.

Models
======

* Fix and normalize project validation errors. Never raise
  CraftValidationErrors directly in validators.
* Add a way to provide doc slugs for models. These are shown when a project
  fails validation, provided the base docs url is set on the AppMetadata.

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
.. _3.1.0: https://github.com/canonical/craft-application/releases/tag/3.1.0
.. _3.2.0: https://github.com/canonical/craft-application/releases/tag/3.2.0
.. _4.0.0: https://github.com/canonical/craft-application/releases/tag/4.0.0
.. _4.1.0: https://github.com/canonical/craft-application/releases/tag/4.1.0
.. _4.1.1: https://github.com/canonical/craft-application/releases/tag/4.1.1
.. _4.1.2: https://github.com/canonical/craft-application/releases/tag/4.1.2
.. _4.2.0: https://github.com/canonical/craft-application/releases/tag/4.2.0
.. _4.2.1: https://github.com/canonical/craft-application/releases/tag/4.2.1
.. _4.2.2: https://github.com/canonical/craft-application/releases/tag/4.2.2
.. _4.2.3: https://github.com/canonical/craft-application/releases/tag/4.2.3
.. _4.2.4: https://github.com/canonical/craft-application/releases/tag/4.2.4
.. _4.2.5: https://github.com/canonical/craft-application/releases/tag/4.2.5
