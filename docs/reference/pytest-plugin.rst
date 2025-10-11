.. py:module:: craft_application.pytest_plugin

pytest plugin
=============

The `pytest`_ plugin helps ease the testing of apps that use craft-application.

By default, this plugin sets the application into debug mode, meaning the
:py:meth:`~craft_application.Application.run()` method will re-raise generic exceptions.


Fixtures
--------

.. autofunction:: production_mode

.. autofunction:: managed_mode

.. autofunction:: destructive_mode

.. autofunction:: fake_host_architecture

.. autofunction:: project_path

.. autofunction:: in_project_path

Auto-used fixtures
------------------

Some fixtures are automatically enabled for tests, changing the default behaviour of
applications during the testing process. Each auto-use fixture changes the default
behaviour of Craft Application during testing.

.. autofunction:: debug_mode

.. autofunction:: _reset_craft_parts_callbacks


.. _pytest: https://docs.pytest.org
