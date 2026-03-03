.. meta::
    :description: API reference for the BuildPlanService. In a craft application, the BuildPlanService creates build plans for a project.

.. py:currentmodule:: craft_application.services.buildplan

.. _reference-BuildPlanService:

``BuildPlanService``
====================

The ``BuildPlanService`` uses :external+craft-platforms:doc:`index` to create
:doc:`build plans </explanation/build-plans>`.
Apps that need to generate custom build plans that Craft Platforms can't handle must
override :py:meth:`~BuildPlanService._gen_exhaustive_build_plan`.


API documentation
-----------------

.. autoclass:: BuildPlanService
    :member-order: bysource
    :members:
    :private-members: _gen_exhaustive_build_plan,_filter_plan
    :undoc-members:
