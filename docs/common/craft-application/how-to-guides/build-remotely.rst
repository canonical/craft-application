.. _how-to-build-remotely:

Build a |star| remotely
=======================

This guide shows you how to offload |star| builds to the Launchpad `build farm
<https://launchpad.net/builders>`_. By building remotely, you can concurrently assemble
|star|\s for all supported architectures.

.. admonition:: Experimental
    :class: important

    The ``remote-build`` command is an experimental feature and therefore subject to
    change.


Get ready
---------

.. _sign-up-for-a-launchpad-account:

Sign up for a Launchpad account
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To build remotely, you need a `Launchpad <https://launchpad.net>`_ account.

If you don't already have an account, you can sign up `here
<https://login.launchpad.net>`_.


Ensure project is version-controlled by Git
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To start a remote build on Launchpad, your project must be version-controlled by Git.
Note that the repository doesn't need to be hosted on Launchpad prior to build, as
|Starcraft| will automatically upload the Git repository in the current working
directory to Launchpad on your behalf.


.. _start-a-remote-build:

Start a remote build
--------------------

In the root directory of your project, begin a remote build with:

.. parsed-literal::

    |app-command| remote-build

This will create a temporary Launchpad repository to house your project. If you instead
wish to upload the repository to an existing Launchpad project, append the ``--project``
option and the project's name to the previous command.

If the Launchpad project is public, |Starcraft| will then ask you to acknowledge that
all remote builds are publicly available on Launchpad.

.. terminal::

    remote-build is experimental and is subject to change. Use with caution.
    All data sent to remote builders will be publicly available. Are you sure you
    want to continue? [y/N]:

If you aren't logged in or haven't yet :ref:`registered for Launchpad
<sign-up-for-a-launchpad-account>`, |Starcraft| will ask you to do so in your web
browser. If this is your first time initiating a remote build from your current host,
you will then be asked to authorize access to your Launchpad account.

Once authorized, your project is uploaded to Launchpad and placed in the build queues
for each architecture defined in your project file. Unless interrupted or timed out, the
status of each build will be continuously monitored and reported back to you.

If you wish to stop monitoring the build at any time, you can :ref:`interrupt it
<interrupt-a-build>`.

Once all of your builds have either built successfully or failed, your |star|\s are
downloaded to the root of your project along with their build logs.


.. _interrupt-a-build:

Interrupt a build
-----------------

Due to build queue lengths varying per architecture, you may want to append the
``--launchpad-timeout=<seconds>`` option to ``remote-build`` to stop monitoring the
build locally after a certain amount of time has elapsed.

If a build is in progress, it can also be interrupted using :kbd:`Ctrl` + :kbd:`C`,
which will give you the option to cancel the build and perform cleanup. If cancelled,
you will not have the option to :ref:`recover this build later
<recover-interrupted-builds>`.


.. _recover-interrupted-builds:

Recover interrupted builds
--------------------------

To resume a build that was interrupted or timed out, navigate to the root of your
project and run:

.. parsed-literal::

    |app-command| remote-build --recover
