.. _reference-commands:

Commands
========

.. py:module:: craft_application.commands.base

:py:class:`AppCommand` defines the baseline functionality for all of
Craft Application's commands.

.. py:class:: AppCommand

    The ``AppCommand`` is a subclass of Craft CLI's
    :external+craft-cli:class:`~craft_cli.BaseCommand` that adds attributes
    specific to Craft Application.

    **Metadata**

    The following attributes provide descriptors that are used when finding a
    command or showing it in help output.

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

    Each ``AppCommand`` instance can access the app's metadata, its services,
    and the project.

    .. py:attribute:: _app
        :type: AppMetadata

        The metadata for the running application.

    .. py:attribute:: _services
        :type: ServiceFactory

        The access point for the application's services.

    .. autoproperty:: AppCommand._project

.. autoclass:: ExtensibleCommand

    .. automethod:: ExtensibleCommand._fill_parser

    .. automethod:: ExtensibleCommand._run

    This allows for the addition of reusable parser fillers, prologues, and epilogues. Each
    entry in an ``ExtensibleCommand``'s inheritance tree can have exactly one of each.

    The following methods can be used to add a parser filler, prologue, and epilogue to
    a command:

    .. automethod:: ExtensibleCommand.register_parser_filler

        The registered function must be passed the ``ExtensibleCommand`` instance as its
        first argument and the ``ArgumentParser`` as its second.

    .. automethod:: ExtensibleCommand.register_prologue

    .. automethod:: ExtensibleCommand.register_epilogue
