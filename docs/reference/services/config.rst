.. meta::
    :description: API reference for the ConfigService. In a craft application, the ConfigService provides access to application configuration.

.. py:currentmodule:: craft_application.services.config

.. _reference-ConfigService:

``ConfigService``
=================

The ``ConfigService`` provides read access to a user's application configuration
through a series of :class:`ConfigHandler` objects. The default config handlers provide
access to both per-application configuration and configuration for all crafts. An
application can provide additional config handlers for custom use cases.

The configuration items available to the configuration service are defined in the
:class:`~craft_application._config.ConfigModel`, which an application can extend.

Handler Order
-------------

The application's configuration is retrieved from the handlers in the order in which
they were registered to the config cervice. By default this order is:

1. :py:class:`AppEnvironmentHandler` gets app-specific environment variables.
2. :py:class:`CraftEnvironmentHandler` gets general ``CRAFT_*`` environment variables.
3. Extra handlers (if any) provided by the application.
4. :py:class:`SnapConfigHandler` (if running as a snap) gets a `snap configuration option`_.
5. :py:class:`DefaultConfigHandler` gets the default value, if there is one.

A handler raises a :external+python:class:`KeyError` if it doesn't have a relevant
config option set. If no handlers return a value when getting a configuration option, a
:external+python:class:`KeyError` is raised to signify that no configuration could be
found.

Configuration model
-------------------

Each application has a configuration model, by default ``craft_application.ConfigModel``,
which is provided to the application by the ``ConfigModel`` field of the app's :attr:`~craft_application.AppMetadata` instance. An app may extend its fields from those
in the configuration model.

.. autoclass:: craft_application.ConfigModel
    :members:
    :exclude-members: model_config


API documentation
-----------------

.. autoclass:: ConfigHandler
    :members:

.. autoclass:: AppEnvironmentHandler
    :members:

.. autoclass:: CraftEnvironmentHandler
    :members:

.. autoclass:: SnapConfigHandler
    :members:

.. autoclass:: DefaultConfigHandler
    :members:

.. autoclass:: ConfigService
    :member-order: bysource
    :members:
    :private-members:

.. _`snap configuration option`: https://snapcraft.io/docs/configuration-in-snaps
