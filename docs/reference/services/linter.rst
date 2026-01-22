.. _reference-services-linter:

Linter Service
==============

Overview
--------

The linter service provides a shared framework to run pre- and post-linters
with central ignore handling.

- Abstract linter API: name, stage, and a ``run(ctx)`` generator that yields
  ``LinterIssue`` objects.
- Class-level registration: linters call
  ``LinterService.register(MyLinter)`` at import time to self-register.
- Central ignore rules: the service owns ``IgnoreConfig`` and enforces user
  intent via ``should_ignore`` before applying app-specific policy hooks.

API
---

Abstract linter
^^^^^^^^^^^^^^^

.. autoclass:: craft_application.lint.base.AbstractLinter
   :members:
   :show-inheritance:

Types
^^^^^

.. autoclass:: craft_application.lint.Stage
   :members:

.. autoclass:: craft_application.lint.Severity
   :members:

.. autoclass:: craft_application.lint.ExitCode
   :members:

.. autoclass:: craft_application.lint.LintContext
   :members:

.. autoclass:: craft_application.lint.LinterIssue
   :members:

.. autoclass:: craft_application.lint.IgnoreSpec
   :members:

``IgnoreConfig`` is a ``dict[str, IgnoreSpec]`` mapping linter names to their ignore rules.

.. autofunction:: craft_application.lint.should_ignore

Service
^^^^^^^

.. autoclass:: craft_application.services.linter.LinterService
   :members:
   :undoc-members:
   :show-inheritance:

For a step-by-step guide on adding linters, see :doc:`/how-to-guides/add-a-linter`.

Ignore configuration
--------------------

Users can suppress issues by creating a ``craft-lint.yaml`` at the project root
or passing CLI rules (see the default ``build_ignore_config`` implementation):

.. code-block:: yaml

   snapcraft.desktop:
     ids: ["MISSING_ICON"]

   # or glob-based suppression per issue id
   snapcraft.desktop:
     by_filename:
       MISSING_ICON: ["*/examples/*"]

Apps can override ``build_ignore_config`` (e.g., Snapcraft can parse
``snapcraft.yaml: lint.ignore`` rules and fold them into the generic
``IgnoreConfig`` format).
