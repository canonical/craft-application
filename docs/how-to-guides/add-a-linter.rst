.. meta::
   :description: How to implement and integrate a linter in a craft app.

.. _how-to-add-a-new-linter:

Create a linter
===============

This guide shows how to add a linter to a craft app using the shared linter
service.

Implement the linter
--------------------

Create a new class that extends the ``AbstractLinter`` class and yields issues
in its ``run()`` method.

Use ``Stage.PRE`` when checks depend on source files and parsed project data
(``ctx.project``). Use ``Stage.POST`` when checks depend on packed output;
``ctx.artifact_dirs`` contains the extracted artifact directories to inspect.

Your ``run()`` method is your custom processing hook. Iterate the relevant
context data and yield ``LinterIssue`` entries when you find problems.

.. code-block:: python
   :caption: mycraft/lint/my_pre_linter.py

   from craft_application.lint.base import AbstractLinter
   from craft_application.lint import LintContext, LinterIssue, Severity, Stage

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

Here's an example linter that checks project and compiled part files:

When linting artifacts in ``Stage.POST``:

* Iterate every directory in ``ctx.artifact_dirs`` instead of assuming a single artifact.
* Validate packaged content (for example, required files, layout, or metadata).
* Keep checks read-only and deterministic (avoid mutating files or relying on network access).

This example linter checks the finalized files to be packed into the artifact:

.. code-block:: python
   :caption: mycraft/lint/my_post_linter.py

   from craft_application.lint.base import AbstractLinter
   from craft_application.lint import LintContext, LinterIssue, Severity, Stage

   class MyPostLinter(AbstractLinter):
       name = "example.post"
       stage = Stage.POST

       def run(self, ctx: LintContext):
           for artifact_dir in ctx.artifact_dirs:
               metadata_file = artifact_dir / "metadata.yaml"
               if not metadata_file.exists():
                   yield LinterIssue(
                       id="E100",
                       message="metadata.yaml is missing from packed artifact",
                       severity=Severity.ERROR,
                       filename=str(metadata_file),
                   )

Register the linter
-------------------

Register your linter class at import time:

.. code-block:: python
   :caption: mycraft/lint/__init__.py

   from craft_application.services.linter import LinterService
   LinterService.register(MyPreLinter)

Ensure that the module containing your linter is imported when your
application starts (for example, from an app plugin or a module import).

Run the service
---------------

Initialize the linter service in the app, and make it stream issues for the
desired stage:

.. code-block:: python
   :caption: mycraft/commands/lint.py

   from pathlib import Path
   from craft_application.lint import LintContext, Stage
   from craft_application.services.linter import LinterService

   svc = LinterService(app, services)
   svc.load_ignore_config(project_dir=Path.cwd())
   for issue in svc.run(Stage.PRE, LintContext(Path.cwd(), [])):
       print(issue)
   print(int(svc.summary()))  # 0 OK, 1 WARN, 2 ERROR

Linter ignores by the user
--------------------------

The user can suppress linter issues in the app's project file (if supported)
and CLI rules when exposed by the app. The underlying format is
``IgnoreConfig`` mapping linter names to ``IgnoreSpec`` objects.

The app developer controls whether these user-facing ignore mechanisms are
available:

* Project-file ignores: parse and normalize rules in the app's
  ``build_ignore_config`` implementation.
* CLI ignores: add command options (for example, ``--lint-ignore``) and pass
  parsed rules to ``load_ignore_config(..., cli_ignores=...)``.

.. code-block:: yaml
   :caption: <craft-app>.yaml

   example.pre:
     ids: ["E001"]

   # or, per-id globs
   example.pre:
     by_filename:
       E001: ["*/examples/*"]

Linter ignores by an app
------------------------

An app can override ``build_ignore_config`` in a ``LinterService`` subclass to
parse app-specific rules from the project file and merge them into the generic
format.

.. code-block:: python
   :caption: mycraft/services/linter.py

   from pathlib import Path
   from craft_application.lint import IgnoreConfig
   from craft_application.services.linter import LinterService

   class MyLinterService(LinterService):
       @classmethod
       def build_ignore_config(
           cls,
           project_dir: Path,
           cli_ignores: IgnoreConfig | None = None,
       ) -> IgnoreConfig:
           config: IgnoreConfig = {}

           raw_project_rules = _load_project_ignore_rules(project_dir)
           project_rules = cls._normalize_ignore_config(raw_project_rules)
           cls._merge_into(config, project_rules)

           if cli_ignores:
               cls._merge_into(config, cli_ignores)
           return config

.. code-block:: python
   :caption: mycraft/commands/lint.py

   cli_ignore_config = _build_cli_ignore_config(parsed_args.lint_ignores)
   linter.load_ignore_config(
       project_dir=project_dir,
       cli_ignores=cli_ignore_config or None,
   )
