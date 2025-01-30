:tocdepth: 2

*********
Changelog
*********

4.8.3 (2025-Jan-31)
-------------------

Remote build
============

- Fix a bug where repositories and recipes for private Launchpad projects
  would be public while the build was in progress.
- Fix a bug where the remote-build command would suggest running an invalid
  command.
- Fix a bug where a timeout would cause the remote builder to remove an
  ongoing build.

For a complete list of commits, check out the `4.8.3`_ release on GitHub.

4.8.2 (2025-Jan-16)
-------------------

Application
===========

- Fix an issue with processing fetch-service output.

For a complete list of commits, check out the `4.8.2`_ release on GitHub.

4.8.1 (2025-Jan-13)
-------------------

Application
===========

- Do not log encoded secrets in managed mode if ``build_secrets``
  ``AppFeature`` is enabled.

Documentation
=============

- Add missing links to the GitHub releases.

For a complete list of commits, check out the `4.8.1`_ release on GitHub.

4.8.0 (2025-Jan-13)
-------------------

Services
========

- Fix a bug where the same build environment was reused for platforms with
  the same build-on and build-for architectures.

Utils
=====

- Add ``format_timestamp()`` helper that helps with formatting time
  in command responses.
- Add ``is_managed_mode()`` helper to check if running in managed mode.
- Add ``get_hostname()`` helper to get a name of current host.

For a complete list of commits, check out the `4.8.0`_ release on GitHub.

4.7.0 (2024-Dec-19)
-------------------

Application
===========

- Allow applications to implement multi-base build plans.

For a complete list of commits, check out the `4.7.0`_ release on GitHub.

4.6.0 (2024-Dec-13)
-------------------

Application
===========

- Add support for keeping order in help for commands provided to
  ``add_command_group()``.
- Add support for rock launchpad recipes, allowing the remote build of rocks.

Commands
========

- Add a ``remote-build`` command. This command is not registered by default,
  but is available for application use.

Git
===

- Extend the ``craft_application.git`` module with the following APIs:

  - Add ``is_commit(ref)`` and ``is_short_commit(ref)`` helpers for checking if
    a given ref is a valid commit hash.
  - Add a ``Commit`` model to represent the result of ``get_last_commit()``.

- Extend the ``GitRepo`` class with additional methods:

  - Add ``set_remote_url()`` and ``set_remote_push_url()`` methods and their
    getter counterparts.
  - Add ``set_no_push()`` method, which explicitly disables ``push`` for
    specific remotes.
  - Add ``get_last_commit()`` method, which retrieves the last commit hash and
    message.
  - Add ``get_last_commit_on_branch_or_tag()`` method, which retrieves the last
    commit associated with a given ref.
  - Add ``fetch()`` method, which retrieves remote objects.

- Use ``craft.git`` for Git-related operations run with ``subprocess`` in
  ``GitRepo``.

For a complete list of commits, check out the `4.6.0`_ release on GitHub.

4.5.0 (2024-Nov-28)
-------------------

Application
===========

- The fetch-service integration now assumes that the fetch-service snap is
  tracking the ``latest/candidate``.
- Fix an issue where the fetch-service output was not correctly logged when
  running in a snapped craft tool.

Commands
========

- Provide a documentation link in help messages.
- Updates to the ``init`` command:

  - If the ``--name`` argument is provided, the command now checks if the value
    is a valid project name, and returns an error if it isn't.
  - If the ``--name`` argument is *not* provided, the command now checks whether
    the project directory is a valid project name. If it isn't, the command sets
    the project name to ``my-project``.

Services
========

- Add version to the template generation context of ``InitService``.


For a complete list of commits, check out the `4.5.0`_ release on GitHub.

4.4.0 (2024-Nov-08)
-------------------

Application
===========

- ``AppCommand`` subclasses now will always receive a valid ``app_config``
  dict.
- Fixes a bug where the fetch-service integration would try to spawn the
  fetch-service process when running in managed mode.
- Cleans up the output from the fetch-service integration.

Commands
========

- Adds an ``init`` command for initialising new projects.
- Lifecycle commands are ordered in the sequence they run rather than
  alphabetically in help messages.
- Preserves order of ``CommandGroups`` defined by the application.
- Applications can override commands defined by Craft Application in the
  same ``CommandGroup``.

Services
========

- Adds an ``InitService`` for initialising new projects.

For a complete list of commits, check out the `4.4.0`_ release on GitHub.

4.3.0 (2024-Oct-11)
-------------------

Application
===========

- Added compatibility methods for craft-platforms models.

Commands
========

- The ``clean`` command now supports the ``--platform`` argument to filter
  which build environments to clean.

Services
========

- Added an experimental integration with the fetch-service, to generate
  manifests listing assets that were downloaded during the build.

For a complete list of commits, check out the `4.3.0`_ release on GitHub.

4.2.7 (2024-Oct-08)
-------------------

- Don't depend on requests >= 2.32.0.
- Fix: set CRAFT_PARALLEL_BUILD_COUNT correctly in ``override-`` scripts.

For a complete list of commits, check out the `4.2.7`_ release on GitHub.

4.2.6 (2024-Oct-04)
-------------------

- Remove the ``requests<2.32.0`` constraint to resolve CVE-2024-35195.

For a complete list of commits, check out the `4.2.6`_ release on GitHub.

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

4.1.3 (2024-Sep-12)
-------------------

Models
======

- Fix a regression where numeric part properties could not be parsed.

For a complete list of commits, check out the `4.1.3`_ release on GitHub.

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
.. _4.1.3: https://github.com/canonical/craft-application/releases/tag/4.1.3
.. _4.2.0: https://github.com/canonical/craft-application/releases/tag/4.2.0
.. _4.2.1: https://github.com/canonical/craft-application/releases/tag/4.2.1
.. _4.2.2: https://github.com/canonical/craft-application/releases/tag/4.2.2
.. _4.2.3: https://github.com/canonical/craft-application/releases/tag/4.2.3
.. _4.2.4: https://github.com/canonical/craft-application/releases/tag/4.2.4
.. _4.2.5: https://github.com/canonical/craft-application/releases/tag/4.2.5
.. _4.2.6: https://github.com/canonical/craft-application/releases/tag/4.2.6
.. _4.2.7: https://github.com/canonical/craft-application/releases/tag/4.2.7
.. _4.3.0: https://github.com/canonical/craft-application/releases/tag/4.3.0
.. _4.4.0: https://github.com/canonical/craft-application/releases/tag/4.4.0
.. _4.5.0: https://github.com/canonical/craft-application/releases/tag/4.5.0
.. _4.6.0: https://github.com/canonical/craft-application/releases/tag/4.6.0
.. _4.7.0: https://github.com/canonical/craft-application/releases/tag/4.7.0
.. _4.8.0: https://github.com/canonical/craft-application/releases/tag/4.8.0
.. _4.8.1: https://github.com/canonical/craft-application/releases/tag/4.8.1
.. _4.8.2: https://github.com/canonical/craft-application/releases/tag/4.8.2
.. _4.8.3: https://github.com/canonical/craft-application/releases/tag/4.8.3
