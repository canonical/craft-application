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
