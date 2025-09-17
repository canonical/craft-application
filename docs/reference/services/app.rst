.. _AppService:

.. py:currentmodule:: craft_application.services.base

``AppService``
==============

The ``AppService`` is the base class from which all services must inherit.

A service may override the :py:meth:`~AppService.setup` method to perform any
service setup that does not require configuration. If a service requires configuration,
this should be done using a ``configure()`` method. This is not implemented in
``AppService`` because the parameters will be service-specific.

Convenience properties :py:attr:`~AppService._build_info` and
:py:attr:`~AppService._project` allow convenient retrieval of the rendered project and
the info for the current build.

API documentation
-----------------

.. autoclass:: AppService
    :members:
    :private-members: _build_info,_project
    :undoc-members:
