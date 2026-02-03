.. meta::
    :description: API reference for services. In a craft application, the services perform categories of tasks.

.. _reference-services:

Services
========

.. toctree::
   :maxdepth: 1

   app
   lifecycle
   project


Service factory API documentation
---------------------------------

.. autoclass:: craft_application.services.ServiceFactory
    :members: register,reset,update_kwargs,get_class,get
    :member-order: bysource
    :exclude-members: __new__
