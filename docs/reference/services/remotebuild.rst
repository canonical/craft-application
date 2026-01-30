.. meta::
    :description: API reference for the RemoteBuildService. In a craft application, the RemoteBuildService handles remote builds on Launchpad.

.. py:currentmodule:: craft_application.services.remotebuild

.. _reference-RemoteBuildService:

``RemoteBuildService``
======================

The ``RemoteBuildService`` provides an interface for performing remote builds using Launchpad.

Workflow
--------

1. Start builds using :py:meth:`~RemoteBuildService.start_builds` or resume existing builds
   using :py:meth:`~RemoteBuildService.resume_builds`.
2. Monitor build progress using :py:meth:`~RemoteBuildService.monitor_builds`.
3. Fetch build logs using :py:meth:`~RemoteBuildService.fetch_logs` and build artifacts using
   :py:meth:`~RemoteBuildService.fetch_artifacts`.
4. Clean up resources using :py:meth:`~RemoteBuildService.cleanup`.

Configuration
--------------

Project selection
~~~~~~~~~~~~~~~~~

By default, the ``RemoteBuildService`` creates a project named ``{username}-craft-remote-build``.
A custom project can be specified using :py:meth:`~RemoteBuildService.set_project` before
starting or resuming builds. Custom projects may be private, but the authenticated user must
have permission to create recipes on that project. All code uploaded to public projects is
publicly accessible on Launchpad.

Timeouts
~~~~~~~~

A timeout can be set using :py:meth:`~RemoteBuildService.set_timeout`. The timeout is
measured from when it is set and includes time for uploading, waiting for builds to start,
building on all architectures, and uploading results. If a timeout is exceeded, a
:py:exc:`TimeoutError` is raised. Interrupted builds can be resumed later using
:py:meth:`~RemoteBuildService.resume_builds` with the build ID from
:func:`craft_application.remote.utils.get_build_id`.

Architectures
~~~~~~~~~~~~~

Architectures can be specified when calling :py:meth:`~RemoteBuildService.start_builds`.
If no architectures are specified, the service uses the application's default set. The
special value ``all`` is automatically converted to ``amd64`` for performance reasons.
Each architecture is built as a separate Launchpad build.

Launchpad management
--------------------

The service automatically manages the following Launchpad resources:

* **Authentication**: Launchpad credentials are stored in the platform-specific data directory.
  Users are prompted to log in on first use if credentials do not exist.
* **Resources**: Temporary repositories and recipes are automatically deleted after the build
  completes.
* **Access**: For public repositories, temporary HTTPS tokens with a five-minute expiry are
  generated to push the project source. For private repositories, SSH authentication is used.

Build monitoring
~~~~~~~~~~~~~~~~

The :py:meth:`~RemoteBuildService.monitor_builds` method yields a dictionary mapping
architecture names to their current build state. Each call to ``monitor_builds()`` returns
a new state mapping.

The possible build states are:

* ``PENDING`` — The build is waiting to start.
* ``BUILDING`` — The build is currently running.
* ``UPLOADING`` — The build has finished and artifacts are being uploaded.
* ``SUCCESS`` — The build completed successfully.
* ``FAILURE`` — The build failed.
* ``CANCELLED`` — The build was cancelled by the user.

The monitor automatically exits once all builds have stopped, regardless of whether they
succeeded or failed. If a timeout is set using :py:meth:`~RemoteBuildService.set_timeout`,
the monitor will raise a :py:exc:`TimeoutError` if the deadline is exceeded.

Customization
-------------

Applications can customize the ``RemoteBuildService`` by:

* Setting the :py:attr:`~RemoteBuildService.RecipeClass` class attribute to specify
  the recipe type to use for builds.
* Overriding :py:meth:`~RemoteBuildService._new_recipe` and
  :py:meth:`~RemoteBuildService._get_recipe` for recipes that require additional
  configuration beyond the standard name and owner.
* Passing additional options via the ``architectures`` keyword argument to
  :py:meth:`~RemoteBuildService.start_builds`.

Errors
------

* :py:exc:`RuntimeError` — The service is not properly set up before use.
* :py:exc:`TimeoutError` — The deadline set by :py:meth:`~RemoteBuildService.set_timeout`
  is exceeded.
* :py:exc:`ValueError` — :py:meth:`~RemoteBuildService.start_builds` is called while
  builds are already running.
* :py:class:`~craft_application.errors.CraftError` — A specified project is not found
  on Launchpad.
* :py:class:`~craft_application.errors.CancelFailedError` — One or more builds cannot
  be cancelled.
* :py:class:`~craft_application.remote.RemoteBuildGitError` — The project source cannot
  be pushed to the Launchpad repository.

API documentation
-----------------

.. autoclass:: RemoteBuildService
    :member-order: bysource
    :members:
    :private-members: _get_lp_client,_ensure_project,_ensure_repository,_get_push_url,_get_repository,_ensure_recipe,_new_recipe,_get_recipe,_new_builds,_get_builds,_get_build_states,_refresh_builds,_get_artifact_urls,_check_timeout
    :undoc-members:
