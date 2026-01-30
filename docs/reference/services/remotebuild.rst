.. meta::
    :description: API reference for the RemoteBuildService. In a craft application, the RemoteBuildService handles remote builds on Launchpad.

.. py:currentmodule:: craft_application.services.remotebuild

.. _reference-RemoteBuildService:

``RemoteBuildService``
======================

The ``RemoteBuildService`` provides an interface for performing remote builds using Launchpad.
This service manages the entire lifecycle of remote builds, including Git repository setup,
recipe creation, build monitoring, and artifact retrieval.

Remote build workflow
---------------------

The typical workflow for using the ``RemoteBuildService`` is:

1. Set up the service by calling :py:meth:`~RemoteBuildService.setup`.
2. Either:

   a. Start new builds using :py:meth:`~RemoteBuildService.start_builds`, or
   b. Resume existing builds using :py:meth:`~RemoteBuildService.resume_builds`.

3. Monitor build progress using :py:meth:`~RemoteBuildService.monitor_builds`.
4. Fetch build logs using :py:meth:`~RemoteBuildService.fetch_logs`.
5. Fetch build artifacts using :py:meth:`~RemoteBuildService.fetch_artifacts`.
6. Optionally cancel builds using :py:meth:`~RemoteBuildService.cancel_builds`.
7. Clean up resources using :py:meth:`~RemoteBuildService.cleanup`.

Project selection
-----------------

By default, the ``RemoteBuildService`` creates a remote build project on Launchpad with the naming
pattern ``{username}-craft-remote-build``. However, applications can use a custom project by calling
:py:meth:`~RemoteBuildService.set_project` before starting or resuming builds.

Custom projects must be:

* Accessible to the authenticated user
* Either public or private (the service automatically detects the project's privacy settings)

Data privacy
~~~~~~~~~~~~

When using a public project or no custom project, all code uploaded to Launchpad for building
will be publicly accessible. Users should be explicitly informed of this in the application's
remote-build command.

Build timeouts
--------------

The service can enforce a timeout for builds using :py:meth:`~RemoteBuildService.set_timeout`.
If a build does not complete before the deadline, a :py:exc:`TimeoutError` will be raised when
monitoring builds.

The timeout is calculated from the time it is set, not from when builds start. This means it
includes the time for:

* Uploading the project to Launchpad
* Waiting for builds to start
* Building on all architectures
* Uploading build results

Build interruption and recovery
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If a build times out or is interrupted by the user, it can be resumed later using
:py:meth:`~RemoteBuildService.resume_builds` with the build ID. The build ID can be obtained
using the :external+craft-application:func:`craft_application.remote.utils.get_build_id` function.

Build architectures
-------------------

The ``RemoteBuildService`` supports building for multiple architectures simultaneously.
Architectures can be specified when calling :py:meth:`~RemoteBuildService.start_builds`:

* If no architectures are specified, the service uses the application's default set.
* The special architecture value ``"all"`` is automatically converted to ``"amd64"`` for
  performance reasons, as amd64 runners are typically faster.
* Each architecture is built as a separate Launchpad build.

Launchpad interaction
---------------------

The ``RemoteBuildService`` automatically manages Launchpad resources on behalf of the user:

* **Authentication**: It uses Launchpad credentials stored in the user's platform-specific
  data directory. If no credentials exist, the service will prompt the user to log in on first use.
* **Project management**: It creates or retrieves a remote build project on Launchpad.
* **Repository management**: It creates a temporary Git repository on Launchpad to hold the
  project source code. This repository is automatically deleted after the build completes.
* **Recipe management**: It creates a build recipe with the appropriate configuration for
  the project. Recipes are also cleaned up after the build completes.
* **Access tokens**: For public repositories, temporary HTTPS access tokens (valid for 5 minutes)
  are generated to push the project source. For private repositories, SSH authentication is used.

Build state monitoring
----------------------

When monitoring builds using :py:meth:`~RemoteBuildService.monitor_builds`, the service yields
a mapping of architecture names to their current :external+craft-parts:class:`BuildState` values.
Possible states include:

* ``PENDING`` - Build is waiting to start
* ``BUILDING`` - Build is currently running
* ``UPLOADING`` - Build has finished, artifacts are being uploaded
* ``SUCCESS`` - Build completed successfully
* ``FAILURE`` - Build failed
* ``CANCELLED`` - Build was cancelled by the user

The monitor will automatically exit once all builds have stopped (regardless of whether they
succeeded or failed).

Build artifacts and logs
------------------------

After builds complete, applications can retrieve:

* **Build artifacts**: Packages and files created by the build using :py:meth:`~RemoteBuildService.fetch_artifacts`.
* **Build logs**: Output from each architecture's build using :py:meth:`~RemoteBuildService.fetch_logs`.

Log filenames follow the pattern: ``{build_id}_{architecture}_{timestamp}.txt``

Application-specific customization
----------------------------------

Applications can customize the ``RemoteBuildService`` by:

* Setting the :py:attr:`~RemoteBuildService.RecipeClass` class attribute to specify the recipe
  type to use for builds. This must be a subclass of :external+craft-parts:class:`Recipe`.
* Overriding protected methods such as :py:meth:`~RemoteBuildService._new_recipe` and
  :py:meth:`~RemoteBuildService._get_recipe` if the recipe requires additional configuration
  beyond the standard name and owner.
* Providing additional configuration options through the ``architectures`` keyword argument to
  :py:meth:`~RemoteBuildService.start_builds`.

Error handling
--------------

Common errors that may be raised:

* :py:exc:`RuntimeError` - If the service is used before being properly set up with
  :py:meth:`~RemoteBuildService.start_builds` or :py:meth:`~RemoteBuildService.resume_builds`.
* :py:exc:`TimeoutError` - If monitoring builds exceeds the deadline set by
  :py:meth:`~RemoteBuildService.set_timeout`.
* :py:exc:`ValueError` - If :py:meth:`~RemoteBuildService.start_builds` is called while
  builds are already running.
* :py:class:`~craft_application.errors.CraftError` - If a specified project cannot be found
  on Launchpad.
* :py:class:`~craft_application.errors.CancelFailedError` - If one or more builds cannot be
  cancelled when :py:meth:`~RemoteBuildService.cancel_builds` is called.
* :py:class:`~craft_application.remote.RemoteBuildGitError` - If there is an error pushing
  the project source to the Launchpad repository.

API documentation
-----------------

.. autoclass:: RemoteBuildService
    :member-order: bysource
    :members:
    :private-members: _get_lp_client,_ensure_project,_ensure_repository,_get_push_url,_get_repository,_ensure_recipe,_new_recipe,_get_recipe,_new_builds,_get_builds,_get_build_states,_refresh_builds,_get_artifact_urls,_check_timeout
    :undoc-members:
