Build slices
============

In addition to traditional Ubuntu packages and snaps, parts can be built from `Chisel slices`_.
Every slice in a project that's used for building is made available in a directory called
the build slices root. The root contains everything needed to build every part in the project,
including compilers, build tools, and build and test dependencies.

Like any packages and snaps used in the build, these slices are only involved during the
build step of the parts lifecycle, and have no direct impact on the final artifact.

However, build slices have one important difference – they can't be combined with build
packages or build snaps for a particular part. A project's slices always have integrity,
because any potential path conflicts between slices are already dealt with in the Chisel
release, and Chisel sees which files and directories are available in the build slices
root. Since Debian packages and snaps aren't tracked in Chisel releases and aren't in the
root, Chisel has no view of them, making the two systems incompatible.

Parts that don't explicitly declare build slices will use the standard build environment
with access to items from build packages and build snaps. This means that projects that
make use of build-slices have effectively two types of parts: those that declare at least
one build-slice and whose build runs in the build slice root, and those that don't declare
any build-slice and thus will build in the standard build environment, with full access
to build-packages and build-snaps.

Example project file
--------------------

Consider this project file snippet for a hypothetical program made up of a server written
in Go and a JavaScript frontend using Vue.js:

.. code-block:: yaml

    name: sample-package
    base: ubuntu@26.04
    # summary, description, and platform not shown for brevity

    build-slices:
      - bash_bins
      - base-files_base

    parts:
      backend:
        plugin: go
        source: backend/
        build-slices:
          - golang-go_core             # for the 'go' compiler
          - golang-google-cloud_src    # backend dependencies
          - go-tomb_src

      frontend:
        plugin: npm
        source: frontend/
        build-slices:
          - npm_core                   # to build the frontend
          - node-vue_dev               # frontend dependencies
          - node-lodash_dev

      docs:                            # user documentation
        plugin: make
        source: docs/
        build-packages:
          - python3-sphinx
        organize:
          _build/: docs/

With this configuration, the build slices root will be composed of the declared top-level
build slices (``bash_bins`` and ``base-files_base``) and part-level build slices
(``golang-go_core``, ``golang-google-cloud_src``, and so on), plus whatever slices the
declared slices need to work.

The builds of the ``backend`` and ``frontend`` parts will happen inside the build slices
root, while the build of the ``docs`` part, which compiles the documentation using Sphinx,
will happen in the standard build environment. In the end, the build output of all parts
will be unified into the single final build artifact.

.. _`Chisel slices`: https://ubuntu.com/chisel/docs/latest/
