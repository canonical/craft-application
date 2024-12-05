*********************
Environment variables
*********************

Applications built on craft-application have several environment variables that
can configure their behaviour. They and the behaviour they modify are listed
below.

Variables passed to managed builders
------------------------------------

Several environment variables from the host environment are passed to the
managed build environment. While an application may adjust these by adjusting
the ``environment`` dictionary attached to the ``ProviderService``,
craft-application will by default forward the ``http_proxy``, ``https_proxy``
and ``no_proxy`` environment variables from the host.

Supported variables
-------------------

These variables are explicitly supported for user configuration.

.. _env-var-craft-build-environment:

``CRAFT_BUILD_ENVIRONMENT``
===========================

If the value is ``host``, allows an environment to tell a craft application
to run directly on the host rather than in managed mode. This method is
roughly equivalent to using ``--destructive-mode``, but is designed for
configurations where the application is already being run in an appropriate
container or VM, such as
`Snapcraft rocks <https://github.com/canonical/snapcraft-rocks/>`_ or
when controlled by a CI system such as `Launchpad <https://launchpad.net>`_.

**CAUTION**: Setting the build environment is only recommended if you are
aware of the exact packages needed to reproduce the build containers created
by the app.

``CRAFT_BUILD_FOR``
===================

Sets the default architecture to build for. Overridden by ``--build-for`` in
lifecycle commands.

``CRAFT_PLATFORM``
==================

Sets the default platform to build. Overridden by ``--platform`` in lifecycle
commands.

``CRAFT_SNAP_CHANNEL``
======================

Overrides the default channel that a craft application's snap is installed from
if the manager instance is not running as a snap. If unset, the application
will be installed from the ``latest/stable`` channel. If the application is
running from a snap, this variable is ignored and the same snap used on
the host system is injected into the managed builder.

``CRAFT_VERBOSITY_LEVEL``
=========================

Set the verbosity level for the application. Valid values are: ``quiet``,
``brief``, ``verbose``, ``debug`` and ``trace``. This is overridden by the
``--quiet``, ``--verbose`` or ``--verbosity={value}`` global command options.

Development variables
---------------------

The following variables exist to help developers writing applications using
craft-application more easily debug their code:

``CRAFT_DEBUG``
===============

Controls whether the application is in debug mode. If this variable is set to
``1``, general exceptions will not be caught, instead showing a traceback on
the command line. This is normally only useful for developers working on
craft-application or an app that uses the framework, as a traceback is always
written to the log file as well.

``CRAFT_LAUNCHPAD_INSTANCE``
============================

For remote builds, allows the user to set an alternative launchpad instance.
Accepts any string that can be used as the ``service_root`` value in
`Launchpadlib <https://help.launchpad.net/API/launchpadlib>`_.

Unsupported variables
---------------------

The following variables cause behaviour changes in craft-application, but
should not be set except by craft-application itself.

``CRAFT_LXD_REMOTE``
====================

If using LXD, the application will start containers in the configured remote
rather than ``local``.

**CAUTION:** Using non-default remotes is experimental and not recommended at
this time.

``CRAFT_MANAGED_MODE``
======================

Alerts the application that it is running in managed mode. This should only be
set by craft-application when creating a provider. Systems designed to wrap
craft applications may use the :ref:`env-var-craft-build-environment`
environment variable to make the app run on the host.
