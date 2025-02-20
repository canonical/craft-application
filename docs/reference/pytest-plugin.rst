.. py:module:: craft_application.pytest_plugin

pytest plugin
=============

craft-application includes a `pytest`_ plugin to help ease the testing of apps that use
it as a framework.

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
~~~~~~~~~~~~~~~~~~

Some fixtures are automatically enabled for tests, changing the default behaviour of
applications during the testing process. This is kept to a minimum, but is done when
the standard behaviour could cause subtle testing issues.

.. autofunction:: debug_mode


.. _pytest: https://docs.pytest.org
