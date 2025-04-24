.. _explanation_cryptographic-technology:

Cryptographic technology in Craft Application
=============================================

Craft Application uses cryptographic technologies to fetch arbitrary files over the
internet. It does not directly implement its own cryptography, but it does depend on
external libraries to do so.

Arbitrary network connection
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Craft Application provides the infrastructure for arbitrary network connections with its
Request service. All connections are made through the `Requests`_ library using the
sensible defaults.

Internally, this library only uses the Request service as a backend for triggering
remote builds on `Launchpad <https://launchpad.net>`_. However, the library is available
and stabilized for general use by consuming applications.

Public key signing
~~~~~~~~~~~~~~~~~~

Craft Application supports the adding and verification of arbitrary package
repositories. For more information, see the cryptographic documentation for `Craft
Archives`_.

The "parts" system
~~~~~~~~~~~~~~~~~~

Craft Application makes use of "parts" in the project file for enabling declarative
builds. Parts specified by the user may download arbitrary files, install packages, and
more. For more information, see the cryptographic documentation for `Craft Parts`_.

Creating virtual build environments
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Craft Application instantiates and executes builds on self-allocated virtual instances.
For more information, see `Craft Providers`_.

Interaction with storefronts
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Craft Application is able to interface with supported storefronts over the internet. For
more information, see `Craft Store`_.

.. _Requests: https://requests.readthedocs.io/
.. _Craft Archives: https://canonical-craft-archives.readthedocs-hosted.com/en/latest/explanation/cryptography/
.. _Craft Parts: https://canonical-craft-parts.readthedocs-hosted.com/en/latest/explanation/cryptography/
.. _Craft Providers: https://canonical-craft-providers.readthedocs-hosted.com/en/latest/explanation/cryptography/
.. _Craft Store: https://canonical-craft-store.readthedocs-hosted.com/en/latest/explanation/cryptography/
