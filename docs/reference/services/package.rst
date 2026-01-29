.. meta::
    :description: API reference for the PackageService. In a craft application, the PackageService turns one or more directories into software packages.

.. py:currentmodule:: craft_application.services.package

.. _reference-PackageService:

``PackageService``
====================

The ``PackageService`` takes the final output of the :external+craft-parts:ref:`prime step <craft_parts_steps>`
and turns it into a domain-specific package. Because this step is completely specific
to the application, the :meth:`~PackageService.pack` and :meth:`~PackageService.metadata`
methods are abstract and must be implemented by the application.

API documentation
-----------------

.. autoclass:: PackageService
    :member-order: bysource
    :members:
