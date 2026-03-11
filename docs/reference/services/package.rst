.. meta::
    :description: API reference for the PackageService. In a craft app, the PackageService turns one or more directories into software packages.

.. py:currentmodule:: craft_application.services.package

.. _reference-PackageService:

``PackageService``
==================

The ``PackageService`` takes the final output of the :external+craft-parts:ref:`prime step <craft_parts_steps>`
and assembles it into the final package. Because this step is unique to the app,
the :meth:`~PackageService.pack` and :meth:`~PackageService.metadata` methods are abstract
and must be implemented by the app.

API documentation
-----------------

.. autoclass:: PackageService
    :member-order: bysource
    :members:
