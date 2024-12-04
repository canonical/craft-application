******************************************
Add partition support to an application
******************************************

Partitions basics
=================

.. Insert link below to new Snapcraft docs when this is merged and live:
   https://github.com/canonical/snapcraft/issues/4857

Applications implementing ``craft-application`` and its dependent suite of
libraries can optionally make use of *partitions* when organizing the files in
their output artifact.  Partitions are used to organize files into different
artifacts or artifact sections, and the actual layout of partitions are defined
by the application.  For instance, partitions can be used to implement:

* Snapcraft's *components*
* `Disk partitions <https://en.wikipedia.org/wiki/Disk_partitioning>`_
* Any other level of organization you may want to add to the application's
  output, such as layers in an OCI image

The supported list of partitions must be defined by the application itself (at
runtime), and those defined partitions can then be used by application
consumers' project files.

Optionally, partitions can be namespaced, for organizational purposes.

Partition names and namespace names must consist of *only* lower-case
alphabetic characters, unless a partition exists under a namespace, in which
case it may also contain hyphen characters, though the first and last
characters must still be alphabetic.  Names containing hyphens also may not
contain two or more hyphens in a row.

``default`` must always be the first listed partition.

In the below examples, we work with three partitions: ``default``, ``kernel``,
and ``component/bar-baz``.  The ``default`` and ``kernel`` partitions do not
have a namespace.  The ``bar-baz`` partition is part of the ``component``
namespace.

.. _app_changes:

Required application changes
============================

To add partition support to an application, two basic changes are needed:

#. Enable the feature.

   In your Application subclass, override the following method and invoke the
   :class:`Features <craft_parts.Features>` class:

   .. code-block:: python

     from craft_parts import Features

     class ExampleApplication(Application):

         ...

         @override
         def _enable_craft_parts_features(self) -> None:
             Features(enable_partitions=True)

   You can only be enable partitions with the :class:`Features
   <craft_parts.Features>` class from craft-parts. In craft-application
   there's a similarly-named :class:`AppFeatures
   <craft_application.AppFeatures>` class which serves a similar purpose,
   but it can't enable partitions.

    .. Tip::
      In unit tests, the :class:`Features <craft_parts.Features>` global
      singleton may raise exceptions when successive tests repeatedly try to
      enable partitions.

      To prevent these errors, reset the features at the start of each test:

      .. code-block:: python

        Features.reset()



#. Define the list of partitions.

   Override the  ``_setup_partitions`` method of your :class:`Application
   <craft_application.Application>` class and return the list of the
   partitions.

   .. code-block:: python

     class ExampleApplication(Application):

         ...

         @override
         def _setup_partitions(self, yaml_data: dict[str, Any]) -> list[str] | None:
             return ["default", "kernel", "component/bar-baz"]

Using the partitions
====================

Partitions cannot be used until `after you have configured your application
<#app-changes>`_.

In a project file
-----------------

Defined partitions may be referenced in the ``organize``, ``stage``, and
``prime`` sections of your project files:

.. code-block:: yaml

  organize:
    <source-path>: (<partition>)/<path>
  stage:
    - (<partition>)/<path>
  prime:
    - (<partition>)/<path>

Paths in the project file not beginning with a partition label will implicitly
use the default partition.

The source path of an ``organize`` entry can only be from the default
partition.  For example, this organizes the file "usr/local/bin/hello" into the
"bar-baz" partition in the "component" namespace:

.. code-block:: yaml

  organize:
    usr/local/bin/hello: (component/bar-baz)/bin/hello

This is equivalent to the above:

.. code-block:: yaml

  organize:
    (default)/usr/local/bin/hello: (component/bar-baz)/bin/hello

But this is invalid:

.. code-block:: yaml

  organize:
    (component/bar-baz)/usr/local/bin/hello: bin/hello

.. code-block:: text

  Cannot organize files from 'component/bar-baz' partition.
  Files can only be organized from the 'default' partition

When the ``stage`` and ``prime`` keywords are not provided for a part,
craft-parts' default behavior is to stage and prime all files for the part in
all partitions.

(If a stage or prime filter *is* applied to a partition, the default behavior
will not be affected for the other partitions.)

See also
^^^^^^^^

* Craft parts: part properties: `organize`_
* Craft parts: filesets: `specifying paths`_

In environment variables
------------------------

You might use these variables in a lifecycle override section of a project
file.  For instance:

.. code-block:: yaml

  override-prime: |
    cp -R vmlinux $CRAFT_KERNEL_PRIME/
    chmod -R 444 $CRAFT_KERNEL_PRIME/*
    cp -R lib/modules/6.x/* $CRAFT_PRIME
    chmod -R 600 $CRAFT_PRIME/*

See also
^^^^^^^^

* Craft parts: parts and steps: `environment variables`_
* Craft parts: part properties: `override-prime`_

In code
-------

Application code that can access ``ProjectDirs`` objects may get partition
information from them:

.. code-block:: python-console

  >>> # from within the LifecycleService:

  >>> self.project_info.dirs.get_stage_dir(partition="kernel")
  Path("/root/partitions/kernel/stage")

  >>> self.project_info.dirs.get_prime_dir(partition="component/bar-baz")
  Path("/root/partitions/component/bar-baz/prime")


.. _organize: https://canonical-craft-parts.readthedocs-hosted.com/en/latest/common/craft-parts/reference/part_properties.html#organize
.. _specifying paths: https://canonical-craft-parts.readthedocs-hosted.com/en/latest/common/craft-parts/explanation/filesets.html#partitions
.. _environment variables: https://canonical-craft-parts.readthedocs-hosted.com/en/latest/reference/parts_steps.html#partition-specific-output-directory-environment-variables
.. _override-prime: https://canonical-craft-parts.readthedocs-hosted.com/en/latest/common/craft-parts/reference/part_properties.html#override-prime
