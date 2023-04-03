from typing import Dict, List, Optional, Type
from pathlib import Path
import sys
from .parts import PartsLifecycle
from .lifecycle_commands import get_lifecycle_command_group
from functools import cached_property
from . import errors
import abc
from .project import Project
from xdg import BaseDirectory
from craft_cli import (
    CraftError,
    CommandGroup,
    BaseCommand,
    GlobalArgument,
    emit,
    EmitterMode,
    Dispatcher,
    ProvideHelpException,
    ArgumentParsingError,
)

GLOBAL_VERSION = GlobalArgument(
    "version", "flag", "-V", "--version", "Show the application version and exit"
)


class Application(abc.ABC):
    """Craft Application Builder.

    :ivar name: application name
    :ivar version: application version
    """

    def __init__(
        self,
        name: str,
        version: str,
        summary: str,
        project_class: Type[Project] = Project,
        is_managed: bool = False,
    ) -> None:
        """Initialize an Application.

        :param name: application name
        :param version: applcation version
        :param summary: application summary
        :param is_managed: run in managed mode or not
        """
        self.name = name
        self.version = version
        self._summary = summary
        self._project_class = project_class
        self._is_managed = is_managed
        self._command_groups: List[CommandGroup] = []
        self._global_arguments: List[GlobalArgument] = [GLOBAL_VERSION]

    def _get_command_groups(self) -> List[CommandGroup]:
        """Return command groups."""
        lifecycle_commands = get_lifecycle_command_group()

        return [lifecycle_commands] + self._command_groups

    @property
    def log_path(self) -> Optional[Path]:
        if self._is_managed:
            return Path(f"/tmp/{self.name}.log")
        return None

    def add_global_argument(self, argument: GlobalArgument) -> None:
        """Add a global argument to the Application."""
        self._global_arguments.append(argument)

    def add_command_group(self, name: str, commands: List[BaseCommand]) -> None:
        """Add a CommandGroup to the Application."""
        self._command_groups.append(CommandGroup(name, commands))

    @property
    def cache_dir(self) -> str:
        return BaseDirectory.save_cache_path(self.name)

    def get_parts_lifecycle(self, *, project: Project) -> PartsLifecycle:
        return PartsLifecycle(
            project.parts,
            cache_dir=self.cache_dir,
            work_dir=Path.cwd(),
            base=project.get_effective_base(),
        )

    def get_project(self) -> Project:
        project_file = Path(f"{self.name}.yaml")
        return Project.from_file(project_file)

    def run_part_step(
        self, project: Project, step_name: str, part_names: List[str]
    ) -> None:
        """Run the parts lifecycle."""
        lifecycle = self.get_parts_lifecycle(project=project)
        lifecycle.run(step_name, part_names=part_names)

    def run(self) -> int:
        """Bootstrap and run the application."""
        emit.init(
            mode=EmitterMode.BRIEF,
            appname=self.name,
            greeting=f"Starting {self.name}",
            log_filepath=self.log_path,
        )

        dispatcher = Dispatcher(
            self.name,
            self._get_command_groups(),
            summary=self._summary,
            extra_global_args=self._global_arguments,
        )

        retcode = 1
        try:
            global_args = dispatcher.pre_parse_args(sys.argv[1:])
            if global_args.get("version"):
                emit.message(f"{self.name} {self.version}")
            else:
                dispatcher.load_command(
                    {
                        "run_part_step": self.run_part_step,
                        "get_project": self.get_project,
                    }
                )
                dispatcher.run()
            emit.ended_ok()
            retcode = 0
        except ProvideHelpException as err:
            print(err, file=sys.stderr)  # to stderr, as argparse normally does
            emit.ended_ok()
        except ArgumentParsingError as err:
            print(err, file=sys.stderr)  # to stderr, as argparse normally does
            emit.ended_ok()
        except KeyboardInterrupt as err:
            self._emit_error(CraftError("Interrupted."), cause=err)
            retcode = 1
        except CraftError as err:
            self._emit_error(err)
        except Exception as err:  # pylint: disable=broad-except
            self._emit_error(CraftError(f"{self.name} internal error: {err!r}"))

        return retcode

    def _emit_error(self, error, *, cause=None):
        """Emit the error in a centralized way so we can alter it consistently."""
        # set the cause, if any
        if cause is not None:
            error.__cause__ = cause

        # Do not report the internal logpath if running inside instance
        if self._is_managed:
            error.logpath_report = False

        emit.error(error)
