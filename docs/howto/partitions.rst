******************************************
Add partition support to an application
******************************************

Partitions basics
=================

.. Insert link below to new Snapcraft docs when this is merged and live:
   https://github.com/canonical/snapcraft/issues/4857

Applications implementing ``craft-application`` and its dependent suite of
libraries can optionally make use of *partitions* when organizing the files in their output artifact.  Partitions are a generic concept, and may be used to implement a concrete feature in your application.  For instance, partitions may refer to:

* Snapcraft's *components*
* `Disk partitions <https://en.wikipedia.org/wiki/Disk_partitioning>`_
* Any other level of organization you may want to add to the application's output, such as layers in an OCI image

The supported list of
partitions must be defined by the application itself (at runtime), and those
defined partitions can then be used by application consumers' configuration
yaml files.

Optionally, partitions can be namespaced, for organizational purposes.

Partition names and namespace names must consist of *only* lower-case
alphabetic characters, unless a partition exists under a namespace, in which
case it may also contain hyphen characters, though the first and last
characters must still be alphabetic.

``default`` must always be the first listed partition.

In the below examples, we work with three partitions: ``default``, ``kernel``,
and ``component/bar-baz``.  The ``default`` and ``kernel`` partitions do not
have a namespace.  The ``bar-baz`` partition is part of the ``component``
namespace.

.. _app_changes:

Required application changes
============================

To add partition support to an application, two basic changes are needed:

#. Enable the feature

   Use the :class:`Features <craft_parts.Features>` class to specify that the
   application will use partitions:

   .. code-block:: python

     from craft_parts import Features

     Features.reset()
     Features(enable_partitions=True)

   .. NOTE::
      The ``craft-application`` class :class:`AppFeatures
      <craft_application.AppFeatures>` has a similar name and serves a similar
      purpose to ``craft-parts``'s :class:`Features <craft_parts.Features>`,
      but partitions cannot be enabled via :class:`AppFeatures
      <craft_application.AppFeatures>`!

#. Define the list of partitions

   We need to tell the :class:`LifecycleManager <craft_parts.LifecycleManager>`
   class about our partitions, but applications do not usually directly
   instantiate the LifecycleManager.

   Instead, override your :class:`Application
   <craft_application.Application>`'s ``_setup_partitions`` method, and return
   a list of the partitions, which will eventually be passed to the
   :class:`LifecycleManager <craft_parts.LifecycleManager>`:

   .. code-block:: python

     class SnackcraftApplication(Application):

       ...

       @override
       def _setup_partitions(self, yaml_data: dict[str, Any]) -> list[str] | None:
           return ["default", "kernel", "component/bar-baz"]

Using the partitions
====================

Partitions cannot be used until `after you have configured your application
<#app-changes>`_.

In configuration yaml
---------------------

Defined partitions may be referenced in the ``organize``, ``stage``, and
``prime`` sections of your configuration yaml files:

.. code-block:: yaml

  organize:
    <source-path>: (<partition>)/<path>
  stage:
    - (<partition>)/<path>
  prime:
    - (<partition>)/<path>

Paths in the configuration yaml not beginning with a partition label will
implicitly use the default partition.

The source path of an ``organize`` entry can only be from the default
partition.  For example:

.. code-block:: yaml

  organize:
    (kernel)/usr/local/bin/hello: bin/hello

.. code-block:: text

  Cannot organize files from 'kernel' partition.
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

You might use these variables in a lifecycle override section of a
configuration yaml.  For instance:

.. code-block:: yaml

  override-prime: |
    cp -R $CRAFT_KERNEL_STAGE/vmlinux $CRAFT_KERNEL_PRIME/
    chmod -R 444 $CRAFT_KERNEL_PRIME/*
    cp -R $CRAFT_STAGE/lib/modules/6.x/* $CRAFT_PRIME
    chmod -R 600 $CRAFT_PRIME/*

See also
^^^^^^^^

 * Craft parts: parts and steps: `environment variables`_
 * Craft parts: part properties: `override-prime`_

In code
-------

Application code that can access ``Part`` or ``ProjectDirs`` objects may get
partition information from them:

.. code-block:: python-console

  >>> Part(name="my-part").part_install_dirs["kernel"]
  Path("partitions/kernel/parts/my-part/install")

  >>> ProjectDirs.get_stage_dir(partition="kernel")
  Path("/root/partitions/kernel/stage")

  >>> ProjectDirs.get_prime_dir(partition="component/bar-baz")
  Path("/root/partitions/component/bar-baz/prime")


.. _organize: https://canonical-craft-parts.readthedocs-hosted.com/en/latest/common/craft-parts/reference/part_properties.html#organize
.. _specifying paths: https://canonical-craft-parts.readthedocs-hosted.com/en/latest/common/craft-parts/explanation/filesets.html#partitions
.. _environment variables: https://canonical-craft-parts.readthedocs-hosted.com/en/latest/reference/parts_steps.html#partition-specific-output-directory-environment-variables
.. _override-prime: https://canonical-craft-parts.readthedocs-hosted.com/en/latest/common/craft-parts/reference/part_properties.html#override-prime
