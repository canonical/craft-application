Platforms
=========

A project's ``platforms`` key has a default schema as well as a way for
applications to override it.

The following mockup shows all the valid ways to create platform entries:

.. code-block:: yaml

  platforms:
    <platform 1 name as a string>:
      build-on: [<arch 1>, <arch 2>]
      build-for: [<arch 1>]
    <platform 2>:
      build-on: <arch 3>
      build-for: [<arch 4>]
    <platform 3>:
      build-on: [<arch 3>]
      build-for: <arch 4>
    <platform 4>:
      build-on: <arch 1>
      build-for: <arch 2>
    <arch 1>:
    <arch 2>:
      build-on: <arch 1>
    <arch 3>:
      build-on: [<arch 1>, <arch 2>]
      build-for: <arch 2>

.. _platform-schema:

``Platform`` schema
-------------------

.. kitbash-model:: craft_application.models.Platform

Default ``PlatformsDict``
-------------------------

The ``platforms`` dictionary is implemented as a non-generic child class of
:class:`~craft_application.models.GenericPlatformsDict`.

.. autoclass:: craft_application.models.PlatformsDict
   :show-inheritance:


Inheritance
-----------

Applications may override the default model for each platform by inheriting from the
``craft_application.models.Platform`` class and modifying it as needed. There is a
how-to guide to :doc:`/how-to-guides/platforms` with implementation instructions. The
class has several validators that may need to be modified.

.. autoclass:: craft_application.models.Platform
   :private-members: _validate_architectures, _validate_build_on_real_arch

.. autoclass:: craft_application.models.GenericPlatformsDict
   :members:
   :undoc-members:
   :private-members: _shorthand_keys, __get_pydantic_core_schema__
   :special-members: __get_pydantic_core_schema__, __get_pydantic_json_schema__
