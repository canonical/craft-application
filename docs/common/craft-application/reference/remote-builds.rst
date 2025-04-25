.. _reference-remote-builds:

Remote builds
=============

.. admonition:: Experimental
    :class: important

    The ``remote-build`` command is an experimental feature and therefore subject to
    change.

Remote builds offload |star| builds to the `build farm
<https://launchpad.net/builders>`_ hosted by `Launchpad <https://launchpad.net/>`_. With
remote builds, you can assemble multiple |star|\s simultaneously and build for all
supported architectures.

Remote builds are launched by running the ``remote-build`` command. |Starcraft| will
upload the Git repository on the current working directory to Launchpad on your behalf,
under your account. To upload the repository to an existing Launchpad project, append
the ``--project`` option and the project's name. Once the ``remote-build`` command is
entered, it will trigger builds for the |Starcraft| project present on the root of the
repository and continuously monitor the status of the new builds.

Note that all architectures defined in the |star|\'s project file are built -- there's
currently no way to restrict the set of platforms to build remotely.

Once all builds are done (either through a successful build or a failure), the |star|
files will be downloaded to the current directory, together with the build logs.


Prerequisites
-------------

In order to perform remote builds, the following conditions must be met:

- You must have a `Launchpad account <https://launchpad.net/+login>`_, as the remote
  builds are performed on Launchpad.
- The |Starcraft| project must be version-controlled by Git. This is because |Starcraft|
  uses a Git-based workflow to upload the project to Launchpad.
- The repository hosting the |Starcraft| project must not be a shallow clone, because
  Git does not support pushing shallow clones.
