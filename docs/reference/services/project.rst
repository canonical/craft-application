.. py:currentmodule:: craft_application.services.project

``ProjectService``
==================

The ``ProjectService`` is a service for handling access to the project.

Project loading
---------------

The project service is responsible for loading, validating and rendering the project
file to a :py:class:`~craft_application.models.Project` model. While the service can
render a project as though it is running on any architecture and building for
any platform or architecture, the most common use case is to render the project
as though running on the current architecture, for the targeted platform.
Here, the steps taken are as follows:

.. How do I make this numbered?
.. contents::
    :class: this-will-duplicate-information-and-it-is-still-useful-here
    :local:

Configure the ProjectService
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The first step is for the ``Application`` to configure the project service. This means
several things:

1. Set the project directory location.
2. Set any ``platform`` and ``build_for`` hints.

Find the project file
~~~~~~~~~~~~~~~~~~~~~

Once a project directory is declared,
:py:meth:`ProjectService.resolve_project_file_path` can be used to find the path to the
actual project file. By default, this is simply ``<app name>.yaml`` in the project
directory. However, applications may override this if they need to search for the
project file at other locations.

Parse the project file YAML
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Once the project file is found, it is parsed as a `YAML`_ file. The file has additional
requirements beyond being a valid YAML document:

1. A file may only contain a single document.
2. The top level of this document must be a map whose keys are strings.

Validate grammar
~~~~~~~~~~~~~~~~

At this step, any user-added grammar is validated using
:external+craft-grammar:doc:`Craft Grammar <index>`. No grammar is applied yet.

Perform application-specific transforms
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

At this step, any application-specific transformations of the document are applied
using the :py:meth:`ProjectService._app_preprocess_project` method. By default,
nothing happens here.

Expand environment
~~~~~~~~~~~~~~~~~~

Next, :external+craft-parts:func:`craft_parts.expand_environment` is called to replace
global parts variables with their expected values.

Process parts grammar
~~~~~~~~~~~~~~~~~~~~~

At this point, grammar is processed for each part defined. This includes parts added
during the application-specific transforms step, meaning that transforms may add
grammar-aware syntax if needed.

Validate Pydantic model
~~~~~~~~~~~~~~~~~~~~~~~

A Pydantic model of the project is loaded, validating more thoroughly.

Check mandatory adoptable fields
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The final step in loading the project is checking mandatory adoptable fields. If
the ``adopt-info`` key is not set on the project, any mandatory fields that are
presented as optional because of their adoptability are checked to ensure they are
set.


API documentation
-----------------


.. autoclass:: ProjectService
    :members:
    :private-members: _app_preprocess_project,_app_legacy_platforms_render
    :undoc-members:
