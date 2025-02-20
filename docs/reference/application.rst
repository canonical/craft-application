.. py:currentmodule:: craft_application.application

The Application
===============

The :py:class:`Application` class is the main entry point to your craft-application
application. Ideally, your application's ``main()`` method would simply look something
like:

..  code-block:: python

    def main() -> int:
        """Run witchcraft."""
        register_services()  # register any custom services.
        app = craft_application.Application(
            app=APP_METADATA,
            services=craft_application.ServiceFactory(app=APP_METADATA)
        )
        return app.run()

In practice, you may need to subclass ``Application`` in order to provide custom
functionality.

Startup process
---------------

The startup process for a craft application can be broken into the following steps that
kick off when running the :py:meth:`Application.run` method.

1. Set up logging. Here :external+craft-cli:doc:`craft-cli <index>` is configured and
   any relevant loggers are added to the emitter. This set of loggers can be extended
   using the ``extra_loggers`` parameter when instantiating the ``Application``.
#. Load any application plugins. Any module that is configured as a craft-application
   plugin is loaded at this point and configured.
#. Start up ``craft-parts``. This activates any relevant features and registers
   default plugins.
#. Create the craft-cli :external+craft-cli:class:`~craft_cli.Dispatcher`.
#. Configure the application based on extra global arguments.
#. Load the command
#. Set the project directory.
#. Determine the fetch service policy.
#. Determine whether the command should run in managed mode
#. Determine whether the command needs a project.
#. Configure the services
#. Run the command class.

At this point, run control is handed to the ``Command`` class, which has access to
the application metadata and the service factory. The only remaining responsibility
of the ``Application`` is error handling.

Error handling
--------------

The ``Application`` takes care of most errors raised by commands. In general, these
errors fall into two categories:

- Craft errors: Any error that matches the ``CraftError`` protocol.
- Internal errors: Any other child class of :external+python:class:`Exception`

Craft errors are treated as user errors. They are presented to the user in the amount
of detail presented by craft-cli, including documentation links and whether or not
the log location is shown.

Internal errors, on the other hand, are treated as errors with the application. If
a command raises (or passes through) an Exception, the ``Application`` alerts the
user of an internal error and includes the log path. Almost any internal error can be
considered to be a bug. If the error is due to erroneous user input or other
circumstances beyond the control of either the application or craft-application, the
bug is that the error was not properly converted to a Craft error. These should be
reported to the application and, if relevant, raised to craft-application on
`our own issue tracker <https://github.com/canonical/craft-application/issues>`_.

``KeyboardInterrupts`` are also handled, in this case to silence the stack trace
that Python raises and exit with the common exit code ``130`` (``128 + SIGINT``).

API documentation
-----------------

.. autoclass:: AppMetadata
    :members:

.. autoclass:: Application
    :members:
