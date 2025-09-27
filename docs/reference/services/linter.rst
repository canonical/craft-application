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

AbstractLinter
^^^^^^^^^^^^^^

``craft_application.lint.base.AbstractLinter``

- ``name: str`` – stable identifier (e.g. ``"snapcraft.desktop"``)
- ``stage: Stage`` – ``Stage.PRE`` or ``Stage.POST``
- ``run(self, ctx: LintContext) -> Iterable[LinterIssue]`` – generator of issues

Types
^^^^^

``craft_application.lint.types``

- ``Stage`` (``PRE``/``POST``), ``Severity`` (``INFO``, ``WARNING``, ``ERROR``)
- ``LintContext(project_dir: Path, artifact_dirs: list[Path])``
- ``LinterIssue(id, message, severity, filename, url="")``
- ``IgnoreSpec(ids: "*"|set[str], by_filename: dict[str, set[str]])``
- ``IgnoreConfig`` – ``dict[str, IgnoreSpec]`` (maps linter name to rules)
- ``should_ignore(linter_name, issue, cfg)`` – helper that applies id and
  filename glob rules

Service
^^^^^^^

``craft_application.services.linter.LinterService``

- ``@classmethod register(linter_cls)``
- ``@classmethod build_ignore_config(project_dir, cli_ignores=None, cli_ignore_files=None)``
  â€“ merge defaults â†’ files â†’ CLI (CLI takes precedence); intended to be
  overridden by apps like Snapcraft.
- ``load_ignore_config(project_dir, cli_ignores=None, cli_ignore_files=None)``
  â€“ store ignore config on the instance.
- ``pre_filter_linters(stage, ctx, candidates)`` â€“ hook to filter classes
  (no-op by default).
- ``post_filter_issues(linter, issues, ctx)`` â€“ hook to filter issues after
  central ignore (no-op by default).
- ``issues`` – flat list of issues collected in the last run.
- ``issues_by_linter`` – mapping of linter name → list of issues from the last run.
- ``summary() -> ExitCode`` â€“ highest-severity result.

How to add a new linter
-----------------------

1. Implement a linter class:

   .. code-block:: python

      from craft_application.lint.base import AbstractLinter
      from craft_application.lint.types import LintContext, LinterIssue, Severity, Stage
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
      from craft_application.lint.types import LintContext, Stage
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
