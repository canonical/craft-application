.. _reference-remote-builds:

Remote builds
=============

Remote builds offload |star| builds to the `build farm
<https://launchpad.net/builders>`_ hosted by `Launchpad <https://launchpad.net/>`_. With
remote builds, you can assemble multiple |star|\s simultaneously and build for all
supported architectures.

Remote builds are launched by running the ``remote-build`` command. |Starcraft| will
upload the Git repository on the current working directory to Launchpad on your behalf,
under your account. Next, it will trigger builds for the |Starcraft| project present on
the root of the repository and continuously monitor the status of the new builds.

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


Limitations
-----------

The following is a list of the current limitations of the remote build feature, which
are planned to be addressed in the future:

- The prospective |star| must be open source and public, because the remote builds
  triggered by |Starcraft| are publicly available.
- All architectures defined in the |star|\'s project file are built -- there's currently
  no way to restrict the set of platforms to build remotely.
