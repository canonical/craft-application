:relatedlinks: https://ubuntu.com/docs/launchpad/,
               https://launchpad.net/builders

.. _how-to-build-remotely:

Build |star|\s remotely
=======================

By building remotely, you can concurrently pack |star|\s for all of your project's
supported architectures.

Remote builds can be started from the Launchpad web interface or the command line. If
you're interested in automating builds or releases and your environment allows for it,
the Launchpad web interface is preferred. If not, the ``remote-build`` command lets you
use the same builders without a dedicated Launchpad project or access to the Launchpad
web interface.


Prerequisites
-------------

Regardless of where you start the build, you'll need to log in to Launchpad. If you
don't already have a Launchpad account, `create one <https://login.launchpad.net>`__.

The project you're building must be version-controlled with Git. If it isn't, initialize
a local repository to work in before proceeding.


Start a build on Launchpad
--------------------------

The Launchpad documentation provides instructions on setting up your project, building
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

You'll be asked to acknowledge that your build will be publicly available and sign in to
Launchpad if you haven't already. Once authorized, your project is uploaded to a
temporary Launchpad repository and placed in the build queues for each target
architecture. If you wish to upload the project to an existing Launchpad project
instead, append the project's name to the ``remote-build`` command with the
``--project`` option.

Remote build queues can get quite long, so you likely won't want to monitor the entire
build from your shell. To stop monitoring the build, press :kbd:`Ctrl` + :kbd:`C` and,
when asked if you want to cancel the build, press :kbd:`N` so the build continues on
Launchpad. You can continue monitoring the build or retrieve the packed |star|\s at any
time by running:

.. code-block:: bash
    :substitutions:

    |app-command| remote-build --recover
