:relatedlinks: https://ubuntu.com/docs/launchpad/,
               https://launchpad.net/builders

.. _how-to-build-remotely:

Build |star|\s remotely
=======================

By building remotely, you can concurrently pack |star|\s for all of your project's
supported architectures and keep your local machine free for other work.

Remote builds can be started from the Launchpad web interface or the command line. If
you're interested in automating builds or releases and your environment allows for it,
start your build from the Launchpad web interface. If not, the ``remote-build`` command
lets you use the same builders without a dedicated Launchpad project or access to the
Launchpad web interface.


Prerequisites
-------------

Regardless of where you start the build, you'll need to log in to Launchpad. If you
don't already have a Launchpad account, `create one <https://login.launchpad.net>`__.

The code for the |star| you're building must be version-controlled with Git. If it
isn't, initialize the codebase as a local repository before proceeding.


Start a build on Launchpad
--------------------------

The Launchpad documentation provides instructions for setting up your project, building
your charm, and automating builds and releases in |lp-remote-build-guide|.


Start a build from the command line
-----------------------------------

.. admonition:: Experimental feature
    :class: warning

    The ``remote-build`` command is experimental and therefore subject to change.

In the directory containing your |star|\'s project file, start a remote build with:

.. code-block:: bash
    :substitutions:

    |app-command| remote-build

By default, a temporary public project is created for the build. If you wish to upload
the project to an existing Launchpad project instead, append the project's name to the
``remote-build`` command with the ``--project`` option.

Remote build queues can get quite long, so you likely won't want to monitor the entire
build from your terminal. If you stop running the command, be sure not to cancel the
build when prompted. You can continue monitoring the build or retrieve the packed
|star|\s at any time by running:

.. code-block:: bash
    :substitutions:

    |app-command| remote-build --recover
