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

How to add a new linter
-----------------------

1. Implement a linter class:

   .. code-block:: python

      from craft_application.lint.base import AbstractLinter
      from craft_application.lint import LintContext, LinterIssue, Severity, Stage
      from craft_application.services.linter import LinterService

      class DesktopLinter(AbstractLinter):
          name = "snapcraft.desktop"
          stage = Stage.PRE

          def run(self, ctx: LintContext):
              # inspect ctx.project_dir and/or ctx.artifact_dirs
              yield LinterIssue(
                  id="MISSING_ICON",
                  message="Missing icon in .desktop file",
                  severity=Severity.WARNING,
                  filename=str(ctx.project_dir / "snap/gui/app.desktop"),
              )

      LinterService.register(DesktopLinter)

2. Ensure the module containing your linter is imported by your application
   (for example in your app plugin, or at startup), so registration runs.

3. Run the service:

   .. code-block:: python

      from pathlib import Path
      from craft_application.lint import LintContext, Stage
      from craft_application.services.linter import LinterService

      svc = LinterService(app, services)
      svc.load_ignore_config(project_dir=Path.cwd())
      for issue in svc.run(Stage.PRE, LintContext(Path.cwd(), [])):
          print(issue)
      print("Exit:", int(svc.summary()))

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
