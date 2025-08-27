import argparse

from craft_application.commands import base
from craft_cli import emit


class NeedsRepack(base.AppCommand):
    """Show the application version."""

    name = "needs-pack"
    always_load_project = True
    help_msg = "Show whether the package needs a repack."
    overview = "Show whether the package needs a repack."
    common = False

    def run(
        self,
        parsed_args: argparse.Namespace,  # noqa: ARG002 (Unused method argument)
    ) -> None:
        """Run the command."""
        emit.message(str(self._services.get("package").needs_repack()))
