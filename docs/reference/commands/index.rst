.. _reference-commands:

Commands
========

.. py:module:: craft_application.commands.base

Craft Application provides several commands, all inheriting from :py:class:`AppCommand`.

.. py:class:: AppCommand

    The ``AppCommand`` is a special form of Craft CLI
    :external+craft-cli:class:`~craft_cli.BaseCommand` that adds Craft Application
    specific attributes. The full form is documented here.

    **Metadata**
    Several attributes provide metadata that is used when finding a command or when
    showing the help about the application or this command.

    .. autoattribute:: AppCommand.name

    .. autoattribute:: AppCommand.help_msg

    .. autoattribute:: AppCommand.overview

    .. autoattribute:: AppCommand.hidden

    .. autoattribute:: AppCommand.common

    **Argument configuration**

    .. automethod:: AppCommand.fill_parser

    **Runtime Configuration**

    .. automethod:: AppCommand.needs_project

    .. autoattribute:: AppCommand.always_load_project

    .. automethod:: AppCommand.run_managed

    .. automethod:: AppCommand.provider_name

    **Execution**

    .. automethod:: AppCommand.run

    **Object access**

    Each ``AppCommand`` instance has can access the app's metadata, its services,
    and the project.

    .. py:attribute:: _app
        :type: AppMetadata

        The metadata for the running application.

    .. py:attribute:: _services
        :type: ServiceFactory

        Provides access to all of the services.

    .. autoproperty:: AppCommand._project

.. autoclass:: ExtensibleCommand

    .. automethod:: ExtensibleCommand._fill_parser

    .. automethod:: ExtensibleCommand._run

    This allows for the addition of reusable parser fillers, prologues and epilogues. Each
    entry in an ``ExtensibleCommand``'s inheritance tree can have  exactly one of each.

    A parser filler can be added to any command using:

    .. automethod:: ExtensibleCommand.register_parser_filler

        The registered function must take the ``ExtensibleCommand`` instance as its
        first argument and the ``ArgumentParser`` as its second.

    .. automethod:: ExtensibleCommand.register_prologue

    .. automethod:: ExtensibleCommand.register_epilogue
