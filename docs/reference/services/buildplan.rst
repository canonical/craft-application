.. meta::
    :description: API reference for the BuildPlanService. In a craft application, the BuildPlanService creates build plans for a project on the current machine.

.. py:currentmodule:: craft_application.services.buildplan

.. _reference-BuildPlanService:

``BuildPlanService``
====================

The ``BuildPlanService`` uses :external+craft-platforms:doc:`index` to create build plans.
Apps that need to generate custom build plans that Craft Platforms cannot handle can
override :py:meth:`~BuildPlanService._gen_exhaustive_build_plan`.


API documentation
-----------------

.. autoclass:: BuildPlanService
    :member-order: bysource
    :members:
    :private-members: _gen_exhaustive_build_plan,_filter_plan
    :undoc-members:
