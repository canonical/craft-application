from typing import Optional, Iterable

from craft_cli import CraftError
from craft_parts import PartsError


class ProjectFileMissing(CraftError):
    """Error finding project file."""


class ProjectValidationError(CraftError):
    """Error validating project yaml."""


class PartsLifecycleError(CraftError):
    """Error during parts processing."""

    @staticmethod
    def from_parts_error(err: PartsError) -> "PartsLifecycleError":
        """Shortcut to create a PartsLifecycleError from a PartsError."""
        return PartsLifecycleError(
            message=err.brief, details=err.details, resolution=err.resolution
        )


class CraftEnvironmentError(CraftError):
    """An environment variable contains an invalid value."""

    def __init__(
        self,
        variable: str,
        value: str,
        *,
        docs_url: Optional[str] = None,
        valid_values: Optional[Iterable[str]] = None,
    ):
        details = f"Value could not be parsed: {value}"
        if valid_values is not None:
            details += "\nValid values: "
            details += ", ".join(valid_values)
        super().__init__(
            message=f"Invalid value in environment variable {variable}",
            details=details,
            resolution=f"Unset variable or fix value.",
            docs_url=docs_url,
            logpath_report=False,
            reportable=False,
            retcode=2
        )
