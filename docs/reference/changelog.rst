:tocdepth: 2

*********
Changelog
*********

5.11.0 (2025-10-01)
-------------------

Documentation
=============

- Add common page *Reuse packages between builds* for use in apps' documentation.

5.10.3 (2025-09-22)
-------------------

Application
===========

- If keys are duplicated in a project file's dictionaries after the grammar is
  resolved, an error will be raised.

5.10.2 (2025-09-19)
-------------------

- Launchpad requests no longer ignore proxy settings.

5.10.1 (2025-09-12)
-------------------

- The :py:class:`~craft_application.application.Application` class no longer catches
  all ``BaseException`` instances, reverting back to the previous behaviour of
  catching ``Exception`` and ``KeyboardInterrupt`` exceptions.

5.10.0 (2025-09-10)
-------------------

Application
===========

- Add :py:attr:`~craft_application.application.AppMetadata.artifact_type` to
  ``AppMetadata`` to allow user-visible messages to refer to the app-specific output
  artifact type.
- Improved UX for end-of-life and near end-of-life bases with
  :py:attr:`~craft_application.application.AppMetadata.check_supported_base`.
- When packing with ``--debug``, the offending error message will now be displayed
  twice - once just before entering the shell, and again after the shell is closed.

Configuration
=============

- Add an ``idle_time`` configuration option that sets the Provider service's idle
  timer duration.

Models
======

- Support ``debug`` and ``debug-each`` in all locations in the ``spread.yaml`` model.
- Update the current development release for the ``Project`` model.

Services
========

- Add an idle timer to the Provider service, so app instances can reuse a dormant
  VM or container before it automatically shuts down.
- Bases that are in extended support are now correctly classified as EOL.

5.9.1 (2025-09-04)
------------------

Services
========

- The Lifecycle Service no longer improperly caches the project (fixes ``adopt-info``).

For a complete list of commits, check out the `5.9.1`_ release on GitHub.

5.9.0 (2025-08-29)
------------------

Services
========

- Previously, only top-level keys in a project file could be managed with ``craftctl``.
  Now, nested keys in a project file can be managed.

- Previously, all project variables could only be set by a single part. Now the
  handling is more granular — each project variable can be set by a different
  part.

- Applications can override the Project service's
  :py:meth:`~craft_application.project.ProjectService._create_project_vars`
  method to define which keys can be managed and which parts can set them.

For a complete list of commits, check out the `5.9.0`_ release on GitHub.

5.8.0 (2025-08-28)
------------------

Application
===========

- Add the ``for`` selector to the YAML grammar. With it, crafters can set different
  values depending on the active platform.

Services
========

- Project Service: Allow using ``base: bare`` with
  :py:attr:`~craft_application.application.AppMetadata.check_supported_base`.

For a complete list of commits, check out the `5.8.0`_ release on GitHub.

5.7.1 (2025-08-27)
------------------

Services
========

- Prevent the reuse of instances created before the State service was added by
  updating the Provider service's compatibility tag.

Pytest plugin
=============

- Automatically reset Craft Parts callbacks after each test run with the
  :py:func:`~craft_application.pytest_plugin._reset_craft_parts_callbacks` fixture.

For a complete list of commits, check out the `5.7.1`_ release on GitHub.

5.6.5 (2025-08-20)
------------------

Services
========

- Prevent the reuse of instances created before the State service by
  updating the Provider service's compatibility tag.

For a complete list of commits, check out the `5.6.5`_ release on GitHub.

5.7.0 (2025-08-15)
------------------

Application
===========

- Add a :py:attr:`~craft_application.application.AppMetadata.check_supported_base`
  option to ``AppMetadata``, allowing the application to opt into checking that the
  base is supported.

Services
========

- Add a new Proxy service that configures an instance to connect to a proxy.
- The Provider Service can now add early proxy configuration to instances.
- The Lifecycle service now configures the overlay to use ``old-releases.ubuntu.com`` if
  the release has been migrated to that domain.

For a complete list of commits, check out the `5.7.0`_ release on GitHub.

5.6.4 (2025-08-15)
------------------

Fixes
=====

- The ``--project-dir`` command option works again.

5.6.3 (2025-08-05)
------------------

Fixes
=====

- Check the craft backend type before testing. The type must be ``craft`` to
  allow the backend to be dynamically processed.

For a complete list of commits, check out the `5.6.2`_ release on GitHub.

5.6.2 (2025-08-01)
------------------

Services
========

- Fix a bug where the State service had insufficient permissions to write
  to the state directory.

For a complete list of commits, check out the `5.6.2`_ release on GitHub.

5.6.1 (2025-07-28)
------------------

Application
===========

- Applications must opt into skipping repack. This was done because it's not fully
  backwards compatible (see:
  `#821 <https://github.com/canonical/craft-application/issues/821>`_)

For a complete list of commits, check out the `5.6.1`_ release on GitHub.

5.6.0 (2025-07-24)
------------------

Application
===========

- Allow applications to override the execution of lifecycle actions.

For a complete list of commits, check out the `5.6.0`_ release on GitHub.

5.5.0 (2025-07-17)
------------------

Services
========

- Add a new State service that manages a global state between manager and managed
  instances of an application.
- Make the Project service compatible with multi-base platform definitions.

Commands
========

- The ``pack`` command will only repack if necessary. The ``test`` command will
  not recreate packages that already exist if the project has not been modified.
- The ``test`` command will test all packed platforms.

For a complete list of commits, check out the `5.5.0`_ release on GitHub.

5.4.0 (2025-06-30)
------------------

Models
======

- Expose the ``Part`` type.

Commands
========

- The ``test`` command now accepts Spread test expressions.

For a complete list of commits, check out the `5.4.0`_ release on GitHub.

5.3.0 (2025-05-28)
------------------

Application
===========

- ``_set_global_environment`` method marked as deprecated for removal in the next
  major release.

Commands
========

- Reduce spread verbosity level when running the ``test`` command.

Git
===

- Add API to modify repository configuration.

Services
========

- Add a ``get_all()`` method to the ``ConfigService``, which returns a ``dict`` of
  all current configuration values.
- The ``ProviderService`` now passes all values from the ``ConfigService`` to the
  inner instance's environment.

Fixes
=====

- Fix an issue where the fetch-service would fail to find the network used
  by LXD containers.
- Improve test result messages.
- ``InitService`` no longer leaves empty files if rendering template fails.
- Enable terminal output when testing with ``--debug``, ``--shell``, or
  ``--shell-after`` parameters.
- Don't repull sources on test files changes.
- Generate artifacts for testing in the project root directory.
- Normalize the list of artifacts packed in ``PackageService`` to be relative
  to the project root directory.

For a complete list of commits, check out the `5.3.0`_ release on GitHub.

5.2.1 (2025-05-23)
------------------

Services
========

- ``CRAFT_PARALLEL_BUILD_COUNT`` and ``CRAFT_MAX_PARALLEL_BUILD_COUNT`` are now
  forwarded to managed instances.

For a complete list of commits, check out the `5.2.1`_ release on GitHub.

5.2.0 (2025-04-25)
------------------

Commands
========

- The ``test`` command now accepts paths to specific tests as well as the
  ``--debug``, ``--shell`` and ``--shell-after`` parameters.

Models
======

- A new :doc:`how-to guide </how-to-guides/platforms>` describes how to implement
  application-specific ``platforms`` keys.

Services
========

- The ``TestingService`` now sets environment variables containing the
  names of the generated artifact and resource files.

For a complete list of commits, check out the `5.2.0`_ release on GitHub.

5.1.0 (2025-04-24)
------------------

Application
===========

- The application now has craft-cli capture logs from HTTPX by default,
  logging store requests for craft-store's Publisher Gateway.

Fixes
======

- `#698 <https://github.com/canonical/craft-application/issues/698>`_ - the spread
  backend model now allows string system names (not just mappings).
- Set a system matching the host when running the test command on CI.

For a complete list of commits, check out the `5.1.0`_ release on GitHub.

5.0.4 (2025-04-24)
------------------

Fixes
=====

- Fix inconsistent command output in ``GitRepo.remote_contains`` by removing
  colors and columns.

For a complete list of commits, check out the `5.0.4`_ release on GitHub.

5.0.3 (2025-04-14)
------------------

Fixes
=====

- `#716 <https://github.com/canonical/craft-application/issues/716>`_ - ``prime``
  command fails in managed mode
- Correctly set SSL_CERT_DIR during pygit2 import on non-Ubuntu systems.

For a complete list of commits, check out the `5.0.3`_ release on GitHub.

5.0.2 (2025-04-11)
------------------

Fixes
=====

- The craft-spread base model now contains an optional ``project`` key. It is currently
  overwritten by the ``test`` command.

For a complete list of commits, check out the `5.0.2`_ release on GitHub.

5.0.1 (2025-04-10)
------------------

Commands
========

- ``test`` raises a clear error message if ``spread.yaml`` or the
  spread executable is missing.
- The warning that the ``test`` command is experimental is only displayed once.
- ``test`` no longer overwrites ``spread.yaml``

Services
========

- The ``TestingService`` now outputs a correct discard script for spread.
- ``Platforms`` models are more strictly validated.
- Raise ``ProjectGenerationError`` instead of ``RuntimeError`` in ``ProjectService``
  when a project fails to generate.
- ``spread.yaml`` files are parsed strictly for top level keys, but pass through
  second level keys to the spread process.
- Spread tests run on their runners as root.

Fixes
=====

- Logs generated by the inner instance of the provider service no longer include
  doubled timestamps.
- Errors implementing the ``CraftError`` protocol are properly caught and
  presented.

For a complete list of commits, check out the `5.0.1`_ release on GitHub.

5.0.0 (2025-03-26)
------------------

Services
========

- A new :doc:`services/project` now handles project loading and rendering. Services
  and commands can use this to get a project. The abstract ``ProjectService`` is no
  longer available for inheritance.
- Setting the arguments for a service using the service factory's ``set_kwargs`` is
  deprecated. Use ``update_kwargs`` instead.

Testing
=======

- Add a :doc:`pytest-plugin` with a fixture that enables production mode for the
  application if a test requires it.

Breaking changes
================

- The pytest plugin includes an auto-used fixture that puts the app into debug mode
  by default for tests.
- Support for secrets has been removed.
- The abstract class ``ProjectService`` has been removed. Services can no longer
  designate that they require a project, but should instead use the
  :py:meth:`~craft_application.services.project.ProjectService.get()` method of the
  ``ProjectService`` to retrieve the project. It will error accordingly.
- The ``BuildPlanner`` pydantic model has been replaced with the
  :py:class:`~craft_application.services.services.buildplan.BuildPlanService`
- The internal ``BuildInfo`` model is replaced with
  :external+craft-platforms:class:`craft_platforms.BuildInfo`

For a complete list of commits, check out the `5.0.0`_ release on GitHub.

4.10.0 (2025-Feb-27)
--------------------

Application
===========

- Add an API for additional snaps to be installed in the managed instance by the
  provider service.
- Increase timeout in fetch-service queries.

For a complete list of commits, check out the `4.10.0`_ release on GitHub.

4.9.1 (2025-Feb-12)
-------------------

Application
===========

- Load python plugins after the emitter has been initialized so they can be logged.

For a complete list of commits, check out the `4.9.1`_ release on GitHub.

4.9.0 (2025-Feb-10)
-------------------

All bug fixes from the 4.8 and 4.4 series are included in 4.9.0.

Application
===========

- Add a feature to allow `Python plugins
  <https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/>`_
  to extend or modify the behaviour of applications that use craft-application as a
  framework. The plugin packages must be installed in the same virtual environment
  as the application.

Remote build
============

- Add hooks to further customize functionality
- Add a ``--project`` parameter for user-defined Launchpad projects, including
  private projects.
- Add "pending" as a displayed status for in-progress remote builds

For a complete list of commits, check out the `4.9.0`_ release on GitHub.

4.4.1 (2025-Feb-05)
-------------------

Application
===========

- Fix an issue with processing fetch-service output.
- The fetch-service integration now assumes that the fetch-service snap is
  tracking the ``latest/candidate`` channel.

Remote build
============

- Fix a bug where repositories and recipes for private Launchpad projects
  would be public while the build was in progress.

For a complete list of commits, check out the `4.4.1`_ release on GitHub.

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

* Adds a default ``Platform`` model. See :doc:`platforms</reference/models/platforms>`
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
.. _4.4.1: https://github.com/canonical/craft-application/releases/tag/4.4.1
.. _4.5.0: https://github.com/canonical/craft-application/releases/tag/4.5.0
.. _4.6.0: https://github.com/canonical/craft-application/releases/tag/4.6.0
.. _4.7.0: https://github.com/canonical/craft-application/releases/tag/4.7.0
.. _4.8.0: https://github.com/canonical/craft-application/releases/tag/4.8.0
.. _4.8.1: https://github.com/canonical/craft-application/releases/tag/4.8.1
.. _4.8.2: https://github.com/canonical/craft-application/releases/tag/4.8.2
.. _4.8.3: https://github.com/canonical/craft-application/releases/tag/4.8.3
.. _4.9.0: https://github.com/canonical/craft-application/releases/tag/4.9.0
.. _4.9.1: https://github.com/canonical/craft-application/releases/tag/4.9.1
.. _4.10.0: https://github.com/canonical/craft-application/releases/tag/4.10.0
.. _5.0.0: https://github.com/canonical/craft-application/releases/tag/5.0.0
.. _5.0.1: https://github.com/canonical/craft-application/releases/tag/5.0.1
.. _5.0.2: https://github.com/canonical/craft-application/releases/tag/5.0.2
.. _5.0.3: https://github.com/canonical/craft-application/releases/tag/5.0.3
.. _5.0.4: https://github.com/canonical/craft-application/releases/tag/5.0.4
.. _5.1.0: https://github.com/canonical/craft-application/releases/tag/5.1.0
.. _5.2.0: https://github.com/canonical/craft-application/releases/tag/5.2.0
.. _5.2.1: https://github.com/canonical/craft-application/releases/tag/5.2.1
.. _5.3.0: https://github.com/canonical/craft-application/releases/tag/5.3.0
.. _5.4.0: https://github.com/canonical/craft-application/releases/tag/5.4.0
.. _5.5.0: https://github.com/canonical/craft-application/releases/tag/5.5.0
.. _5.6.0: https://github.com/canonical/craft-application/releases/tag/5.6.0
.. _5.6.1: https://github.com/canonical/craft-application/releases/tag/5.6.1
.. _5.6.2: https://github.com/canonical/craft-application/releases/tag/5.6.2
.. _5.6.3: https://github.com/canonical/craft-application/releases/tag/5.6.3
.. _5.6.5: https://github.com/canonical/craft-application/releases/tag/5.6.5
.. _5.7.0: https://github.com/canonical/craft-application/releases/tag/5.7.0
.. _5.7.1: https://github.com/canonical/craft-application/releases/tag/5.7.1
.. _5.8.0: https://github.com/canonical/craft-application/releases/tag/5.8.0
.. _5.9.0: https://github.com/canonical/craft-application/releases/tag/5.9.0
.. _5.9.1: https://github.com/canonical/craft-application/releases/tag/5.9.1
.. _5.10.0: https://github.com/canonical/craft-application/releases/tag/5.10.0
.. _5.10.1: https://github.com/canonical/craft-application/releases/tag/5.10.1
