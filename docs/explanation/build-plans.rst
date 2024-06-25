Build plans
===========

A build plan is a collection of platforms to build. It can be defined in the
project's metadata file and filtered with command-line arguments.

Filtering build plans
---------------------

A build plan contains all possible platforms to build. When loading the project
model, the build plan is filtered to builds that match all of the following:

* where ``build-on`` matches the host's architecture
* where ``build-for`` matches the command line argument ``--build-for``
* where ``platform`` matches the command line argument ``--platform``

Note that ``--build-for`` and ``--platform`` are mutually exclusive.

Consider the following project metadata:

.. code-block:: yaml

  base: ubuntu@24.04
  platforms:
    amd64:
    riscv64:
      build-on: [amd64, riscv64]
      build-for: [riscv64]

The application will create a build plan with three elements:

.. code-block:: text

  platform: amd64, build-on amd64, build-for amd64, base: ubuntu@24.04
  platform: riscv64, build-on amd64, build-for riscv64, base: ubuntu@24.04
  platform: riscv64, build-on riscv64, build-for riscv64, base: ubuntu@24.04

If the application executes on an ``amd64`` platform, the build plan will be
filtered to:

.. code-block:: text

  platform: amd64, build-on amd64, build-for amd64, base: ubuntu@24.04
  platform: riscv64, build-on amd64, build-for riscv64, base: ubuntu@24.04

If the application executes on an ``amd64`` platform and ``--platform riscv64``
is provided, the build plan will be filtered to:

.. code-block:: text

  platform: riscv64, build-on amd64, build-for riscv64, base: ubuntu@24.04

If the application executes on a ``riscv64`` platform, the build plan will be
filtered to:

.. code-block:: text

  platform: riscv64, build-on riscv64, build-for riscv64, base: ubuntu@24.04

Building with a provider
------------------------

When using a provider like LXD or Multipass, each build in the build plan
occurs sequentially in its own build environment.

The build plan's ``base`` determines the container image to use.

Destructive mode
----------------

When using destructive mode, only one build will occur. If multiple items in
the build plan match the host environment, the application will fail to run.
The build plan must be filtered to a single item with the ``--build-for`` and
``-platform`` arguments.

The host OS much match the build plan's ``base``.
