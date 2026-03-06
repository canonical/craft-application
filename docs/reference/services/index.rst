.. meta::
    :description: API reference for services. In a craft application, each service is responsible for a different category of tasks.

.. _reference-services:

Services
========

These pages provide reference information for services provided by Craft Application.

Service factory API documentation
---------------------------------

.. autoclass:: craft_application.services.ServiceFactory
    :members: register,reset,update_kwargs,get_class,get
    :member-order: bysource
    :exclude-members: __new__

.. toctree::
   :maxdepth: 1
   :hidden:

   app
   buildplan
   config
   lifecycle
   package
   project
