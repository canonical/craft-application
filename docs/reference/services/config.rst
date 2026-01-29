.. meta::
    :description: API reference for the ConfigService. In a craft application, the ConfigService provides access to application configuration.

.. py:currentmodule:: craft_application.services.config

.. _reference-ConfigService:

``ConfigService``
=================

The ``ConfigService`` provides access to application configuration through the use of
a series of :class:`ConfigHandler` objects. An application can provide additional
Config Handlers if needed.

The configuration items available to the configuration service are defined in the
:class:`~craft_application._config.ConfigModel`, which

Handler Order
-------------

Configuration is retrieved from the handlers in the order in which they were registered
to the Config Service. By default this order is:

1. :py:class:`AppEnvironmentHandler` gets app-specific environment variables.
2. :py:class:`CraftEnvironmentHandler` gets general ``CRAFT_*`` environment variables
3. Extra handlers (if any) provided by the application
4. :py:class:`SnapConfigHandler` (if running as a snap) gets `snap configuration`_.
5. :py:class:`DefaultConfigHandler` gets the default value, if there is one.

If all handlers are exhausted when getting a configuration, a :external+python:class:`KeyError`
is raised to signify that no configuration could be found.

Configuration model
-------------------

Each application has a configuration model, by default ``craft_application.ConfigModel``,
which is provided to the application via the ``ConfigModel`` field of  :attr:`~craft_application.AppMetadata`. An app may extend its fields from those
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

.. _`snap configuration`: https://snapcraft.io/docs/configuration-in-snaps
