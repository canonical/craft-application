.. py:module:: craft_application.pytest_plugin

pytest plugin
=============

craft-application includes a pytest plugin to help ease the testing of apps that use
it as a framework.

By default, this plugin sets the application into debug mode, meaning the
:py:meth:`~craft_application.Application.run()` method will re-raise generic exceptions.


Fixtures
--------

.. autofunction:: production_mode
