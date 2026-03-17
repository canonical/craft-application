.. _explanation_cryptographic-technology:

Cryptographic technology in Craft Application
=============================================

Craft Application uses cryptographic technologies to fetch arbitrary files over the
internet. It does not directly implement its own cryptography, but it does depend on
external libraries to do so.

Remote building
~~~~~~~~~~~~~~~

Craft Application uses `launchpadlib`_ to interact with the `Launchpad`_ API and trigger
remote builds. Login credentials for Launchpad are stored in a plain text file in the
XDG data directory.

Arbitrary network connection
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Craft Application provides the infrastructure for arbitrary network connections with its
Request service. All connections are made through the `Requests`_ library using the
sensible defaults.

Internally, this library only uses the Request service as a backend for retrieving the
results of remote builds on `Launchpad`_. However, the library
is available and stabilized for general use by consuming applications.

Public key signing
~~~~~~~~~~~~~~~~~~

Craft Application supports the adding and verification of arbitrary package
repositories. For more information, see the cryptographic documentation for `Craft
Archives`_.

The parts system
~~~~~~~~~~~~~~~~

Craft Application makes use of *parts* in project files for declarative builds. Parts
specified by the user may download arbitrary files, install packages, and more. For more
information, see the cryptographic documentation for `Craft Parts`_.

Creating virtual build environments
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Craft Application instantiates and executes builds on self-allocated virtual instances.
For more information, see `Craft Providers`_.

Interaction with storefronts
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Craft Application is able to interface with supported storefronts over the internet. For
more information, see `Craft Store`_.

.. _launchpadlib: https://help.launchpad.net/API/launchpadlib
.. _Launchpad: https://launchpad.net
.. _Requests: https://requests.readthedocs.io/
.. _Craft Archives: https://canonical-craft-archives.readthedocs-hosted.com/en/latest/explanation/cryptography/
.. _Craft Parts: https://canonical-craft-parts.readthedocs-hosted.com/en/latest/explanation/cryptography/
.. _Craft Providers: https://canonical-craft-providers.readthedocs-hosted.com/en/latest/explanation/cryptography/
.. _Craft Store: https://canonical-craft-store.readthedocs-hosted.com/en/latest/explanation/cryptography/
