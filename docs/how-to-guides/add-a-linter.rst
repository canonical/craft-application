Add a new linter
================

This guide shows how to add a linter to a *craft application* using the
shared linter service.

1) Implement a linter
---------------------

Create a class that extends ``AbstractLinter`` and yields issues from ``run``.

.. code-block:: python

   from craft_application.lint.base import AbstractLinter
   from craft_application.lint.types import LintContext, LinterIssue, Severity, Stage

   class MyPreLinter(AbstractLinter):
       name = "example.pre"
       stage = Stage.PRE

       def run(self, ctx: LintContext):
           # Inspect ctx.project_dir and/or ctx.artifact_dirs
           yield LinterIssue(
               id="E001",
               message="Example warning",
               severity=Severity.WARNING,
               filename=str(ctx.project_dir / "README.md"),
           )

2) Register the linter
----------------------

Register your linter class at import time:

.. code-block:: python

   from craft_application.services.linter import LinterService
   LinterService.register(MyPreLinter)

Ensure that the module containing your linter is imported when your
application starts (for example, from an app plugin or a module import).

3) Run the service
------------------

Use the service to stream issues for the desired stage:

.. code-block:: python

   from pathlib import Path
   from craft_application.lint.types import LintContext, Stage
   from craft_application.services.linter import LinterService

   svc = LinterService(app, services)
   svc.load_ignore_config(project_dir=Path.cwd())
   for issue in svc.run(Stage.PRE, LintContext(Path.cwd(), [])):
       print(issue)
   print(int(svc.summary()))  # 0 OK, 1 WARN, 2 ERROR

4) Ignore configuration
-----------------------

Users can suppress issues via a ``craft-lint.yaml`` file or CLI rules
(when available in your application). The underlying format is
``IgnoreConfig`` mapping linter names to ``IgnoreSpec`` objects.

.. code-block:: yaml

   example.pre:
     ids: ["E001"]

   # or, per-id globs
   example.pre:
     by_filename:
       E001: ["*/examples/*"]

Applications can override ``build_ignore_config`` in a subclass of
``LinterService`` to merge app-specific rules into the generic format.
