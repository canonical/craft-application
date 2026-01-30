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

1. Either start new builds using :py:meth:`~RemoteBuildService.start_builds` or resume
   existing builds using :py:meth:`~RemoteBuildService.resume_builds`.
2. Monitor build progress using :py:meth:`~RemoteBuildService.monitor_builds`.
3. Fetch build logs using :py:meth:`~RemoteBuildService.fetch_logs` and artifacts using
   :py:meth:`~RemoteBuildService.fetch_artifacts`.
4. Clean up resources using :py:meth:`~RemoteBuildService.cleanup`.

Project selection
-----------------

By default, the ``RemoteBuildService`` creates a project named ``{username}-craft-remote-build``.
A custom project can be specified using :py:meth:`~RemoteBuildService.set_project` before
starting or resuming builds. Custom projects may be private, but the authenticated user must
have permission to create recipes on that project.

When using a public project, all uploaded code will be publicly accessible on Launchpad.
Users must be explicitly informed of this in the application's ``remote-build`` command.

Build timeouts
--------------

A timeout can be set using :py:meth:`~RemoteBuildService.set_timeout`. The timeout is
measured from when it is set and includes the time for uploading, waiting for builds to start,
building on all architectures, and uploading results. If a timeout is exceeded, a
:py:exc:`TimeoutError` is raised. Interrupted builds can be resumed later using
:py:meth:`~RemoteBuildService.resume_builds` with the build ID from
:func:`craft_application.remote.utils.get_build_id`.

Build architectures
-------------------

The ``RemoteBuildService`` supports building for multiple architectures. If no architectures
are specified, the service uses the application's default set. The special value ``all`` is
automatically converted to ``amd64`` for performance. Each architecture is built separately.

Launchpad interaction
---------------------

The ``RemoteBuildService`` automatically manages:

* **Authentication**: Using Launchpad credentials stored in the platform-specific data directory.
  Users are prompted to log in on first use if credentials do not exist.
* **Project and repository management**: Creating temporary Launchpad resources that are
  automatically cleaned up after the build completes.
* **Access tokens**: For public repositories, temporary HTTPS tokens (5-minute expiry) are
  generated. For private repositories, SSH authentication is used.

Build state monitoring
----------------------

:py:meth:`~RemoteBuildService.monitor_builds` yields a mapping of architecture names to their
current state. Possible states are: ``PENDING``, ``BUILDING``, ``UPLOADING``, ``SUCCESS``,
``FAILURE``, and ``CANCELLED``. The monitor exits automatically once all builds have stopped.

Build artifacts and logs
------------------------

:py:meth:`~RemoteBuildService.fetch_artifacts` retrieves build output, while
:py:meth:`~RemoteBuildService.fetch_logs` retrieves build logs. Log filenames follow the
pattern ``{build_id}_{architecture}_{timestamp}.txt``.

Application-specific customization
----------------------------------

Applications can customize the ``RemoteBuildService`` by:

* Setting the :py:attr:`~RemoteBuildService.RecipeClass` class attribute to specify the
  recipe type to use.
* Overriding :py:meth:`~RemoteBuildService._new_recipe` and :py:meth:`~RemoteBuildService._get_recipe`
  for recipes requiring additional configuration.
* Providing additional options through the ``architectures`` keyword argument to
  :py:meth:`~RemoteBuildService.start_builds`.

Error handling
--------------

* :py:exc:`RuntimeError` - If the service is not properly set up before use.
* :py:exc:`TimeoutError` - If the deadline set by :py:meth:`~RemoteBuildService.set_timeout`
  is exceeded.
* :py:exc:`ValueError` - If :py:meth:`~RemoteBuildService.start_builds` is called with
  builds already running.
* :py:class:`~craft_application.errors.CraftError` - If a specified project is not found
  on Launchpad.
* :py:class:`~craft_application.errors.CancelFailedError` - If builds cannot be cancelled.
* :py:class:`~craft_application.remote.RemoteBuildGitError` - If the source cannot be pushed
  to the Launchpad repository.

API documentation
-----------------

.. autoclass:: RemoteBuildService
    :member-order: bysource
    :members:
    :private-members: _get_lp_client,_ensure_project,_ensure_repository,_get_push_url,_get_repository,_ensure_recipe,_new_recipe,_get_recipe,_new_builds,_get_builds,_get_build_states,_refresh_builds,_get_artifact_urls,_check_timeout
    :undoc-members:
