.. meta::
    :description: API reference for the RemoteBuildService. In a craft application, the RemoteBuildService handles remote builds on Launchpad.

.. py:currentmodule:: craft_application.services.remotebuild

.. _reference-RemoteBuildService:

``RemoteBuildService``
======================

The ``RemoteBuildService`` provides an interface for performing remote builds using Launchpad.

Workflow
--------

1. Start builds with :py:meth:`~RemoteBuildService.start_builds` or resume with
   :py:meth:`~RemoteBuildService.resume_builds`.
2. Monitor progress using :py:meth:`~RemoteBuildService.monitor_builds`.
3. Fetch logs and artifacts using :py:meth:`~RemoteBuildService.fetch_logs` and
   :py:meth:`~RemoteBuildService.fetch_artifacts`.
4. Clean up with :py:meth:`~RemoteBuildService.cleanup`.

Configuration
--------------

Project selection
~~~~~~~~~~~~~~~~~

By default, a project named ``{username}-craft-remote-build`` is created. Use
:py:meth:`~RemoteBuildService.set_project` to specify a custom project. All code
uploaded to public projects is publicly accessible.

Timeouts
~~~~~~~~

Set a timeout with :py:meth:`~RemoteBuildService.set_timeout`. If exceeded, a
:py:exc:`TimeoutError` is raised. Interrupted builds can be resumed using
:py:meth:`~RemoteBuildService.resume_builds` with the build ID from
:func:`~craft_application.remote.utils.get_build_id`.

Architectures
~~~~~~~~~~~~~

Specify architectures in :py:meth:`~RemoteBuildService.start_builds`. The value
``all`` is automatically converted to ``amd64``. Each architecture builds separately.

Launchpad management
--------------------

The service automatically manages:

* **Authentication**: Launchpad credentials stored in the platform data directory.
* **Resources**: Temporary repositories and recipes deleted after builds complete.
* **Access**: HTTPS tokens (5-minute expiry) for public repos; SSH for private repos.

Build monitoring
----------------

:py:meth:`~RemoteBuildService.monitor_builds` yields architecture → state mappings.
States: ``PENDING``, ``BUILDING``, ``UPLOADING``, ``SUCCESS``, ``FAILURE``, ``CANCELLED``.
The monitor exits when all builds stop.

Customization
-------------

* Set :py:attr:`~RemoteBuildService.RecipeClass` for the recipe type.
* Override :py:meth:`~RemoteBuildService._new_recipe` and
  :py:meth:`~RemoteBuildService._get_recipe` for custom configuration.
* Pass extra options via ``architectures`` keyword argument to
  :py:meth:`~RemoteBuildService.start_builds`.

Errors
------

* :py:exc:`RuntimeError` — Service not set up before use.
* :py:exc:`TimeoutError` — Deadline exceeded.
* :py:exc:`ValueError` — :py:meth:`~RemoteBuildService.start_builds` called with active builds.
* :py:class:`~craft_application.errors.CraftError` — Project not found on Launchpad.
* :py:class:`~craft_application.errors.CancelFailedError` — Build cancellation failed.
* :py:class:`~craft_application.remote.RemoteBuildGitError` — Source push failed.

API documentation
-----------------

.. autoclass:: RemoteBuildService
    :member-order: bysource
    :members:
    :private-members: _get_lp_client,_ensure_project,_ensure_repository,_get_push_url,_get_repository,_ensure_recipe,_new_recipe,_get_recipe,_new_builds,_get_builds,_get_build_states,_refresh_builds,_get_artifact_urls,_check_timeout
    :undoc-members:
