.. _explanation-structure-of-a-craft-app:

Structure of a craft app
========================

A craft app is made up of several components and objects. This page explains the
relationships and communication between these components.

Here's a view of the structure of a craft app, starting from when a user calls
it:

.. figure:: assets/app_structure.svg

    Relationship between pieces of an app.

The app is invoked by an external process that runs the app with some command.
This instantiates an ``Application`` class and runs its run method, which configures the
``ServiceFactory`` instance before the Command instance's ``run()`` method. A
``Command`` may get any necessary services from the ``ServiceFactory`` using its
``get`` method, and it may make any service-specific calls to any service it gets.
Likewise, a service may interact with another service's public API by using
``ServiceFactory.get()`` to get another service. Services may store data in ``Model``
instances. When a service uses a ``Model`` to store data, that service is responsible
for maintaining that model and providing access either to the model or its underlying
features.

``Application``
---------------

The :py:class:`~craft_application.application.Application` class is the glue that
holds a craft app together.  The ``Application`` is primarily responsible for starting
up the app, loading the relevant services and calling the relevant Command class.
It also handles exceptions and turns them into error messages.

In an ideal world, the ``Application`` class would never need to have child
classes. Each thing the ``Application`` class currently does that requires an override
in a craft can be considered a shortcoming to be fixed at a later date. In practice,
however, this is not always feasible.

Commands
--------

A ``Command`` class is what's responsible for user interaction. It is a child class of
:py:class:`craft_application.commands.AppCommand` that gets registered with the ``Application`` class by using its
:py:meth:`~craft_application.application.Application.add_command_group` method.
It should:

1. Take parameters for every option, which can be set interactively (i.e. from
   the CLI) or non-interactively (i.e. from a script).
2. If an option is not provided, ask the user or provide a reasonable default.
3. Return final information to the user.

To do all of this, it is supported by :external+craft-cli:doc:`Craft CLI <index>`,
the application's metadata, and the
:py:class:`~craft_application.ServiceFactory` class. The ``ServiceFactory`` instance
is accessible at ``self._services``, while the app's metadata is accessible at
``self._app``.

Interactive functionality should generally be implemented within a Command class.
One such example is the ``remote-build`` command, which asks the user to confirm
that they are okay uploading the project to a public git repository. In addition to
that interactive item, it provides a way to do this non-interactively via
``--launchpad-accept-public-upload``. It is supported by a remote build service that
provides the actual business logic, but the user interface is primarily driven
by the Command.

Services
--------

:doc:`/reference/services/index` are where an app's business logic lives.
They are responsible for:

1. Implementing logic related to a specific workflow or piece of data.
2. Maintaining relevant internal state for that (assisted by the
   :py:class:`~craft_application.services.state.StateService` if the state needs to
   be passed between application instances running inside and outside of an
   isolated build environment, respectively referred to as managed and manager
   instances).
3. Acting as wrappers for any external libraries that get used (with a few exceptions).

.. caution::

    Avoid storing data from one service in another. Services may update data by
    replacing an existing object rather than mutating it. Unless stated otherwise, each
    call to a service should be treated as invalidating any cached items retrieved
    from that service.

A prime example of this is the :doc:`/reference/services/project`, which is the sole
provider of information about the loaded project. The contract of the ``ProjectService``
is such that an instance of a project model may be disposed and replaced, so a command
or another service must not keep a project model instance, but instead request the
project through the ``ProjectService`` in each method or after each call that may
modify the project model (for example,
:py:meth:`~craft_application.services.project.ProjectService.deep_update`).

The ``ProjectService`` is also responsible for loading the project file, parsing
the YAML, performing pre-processing on it, and rendering a
:ref:`reference-models-project` model. Additional project-related features should be
implemented by extending this service, not with ad-hoc logic in other places.

A service that implements workflow-related logic and acts as a wrapper for an external
library is the :py:class:`~craft_application.services.provider.ProviderService`, which
provides relevant hooks into :external+craft-providers:doc:`index`. This service
contains both global state (e.g. packages and snaps to install in a managed instance)
and per-instance state (e.g. the actual ``instance`` from Craft Providers).

Services may interact with each other, but it is strongly recommended that they only do
so at a high level in order to avoid too much complexity. This includes the fact that
services should default to using protected (underscore-prefixed) methods unless it is
specifically known that a method must be externally available. Likewise, when possible
a command should only interact with a service on a high level.

Models
------

`Pydantic`_ models validate data when reading and writing files. A
:py:class:`~craft_application.models.base.CraftBaseModel` is available to create a
model that has convenience methods that are commonly used by Craft apps. The only
logic in a model should ideally be its validation and serialization logic.
