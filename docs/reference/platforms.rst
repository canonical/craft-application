Platforms
=========

.. code-block:: yaml

  platforms:
    <platform 1>:
      build-on: [<arch 1>, <arch 2>]
      build-for: [<arch 1>]
    <platform 2>:
      build-on: [<arch 3>]
      build-for: [<arch 4>]
    ...

platform
""""""""

The platform name describes a ``build-on``/``build-for`` pairing. If the
platform name is a valid debian architecture, then ``build-on`` and
``build-for`` can be omitted.

The recommended platform name is the ``build-for`` arch.

build-on
""""""""

The ``build-on`` field is an optional list of architectures where the artefact
can be built. It can contain multiple architectures.

If the platform name is a valid architecture and ``build-for`` is not defined,
then ``build-on`` can be omitted. ``build-on`` will assume the platform name.

build-for
"""""""""

The ``build-for`` field is an optional single-element list containing the
architecture where the artefact should run.

If the platform name is a valid architecture, then ``build-for`` will
assume the platform name.

``build-for: [all]`` is a special keyword to denote an architecture-independent
artefact. If the ``all`` keyword is used, no other ``build-on/build-for`` pairs
can be defined.
