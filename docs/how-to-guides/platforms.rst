Customize platforms in a project model
======================================

Most applications can use the default model for platforms. If an application needs to
extend the ``Platform`` model (for example to limit the available architectures or add
more fields to a platform description) or adjust the valid platform names (for example
to provide alternative shorthand values), it must do so in the following prescribed
manner.

Override the ``Platform`` model
-------------------------------

The first thing to override is the :py:class:`craft_application.models.Platform`
model with your own platform definition. If possible, it is best to make a child
model that inherits from ``Platform`` and overrides the various validators as needed.
The ``Platform`` model does not need to take into account shorthand forms that are
missing either the ``build-on`` or ``build-for`` fields.

Make a ``PlatformsDict``
------------------------

Once you have overridden the ``Platform`` model, it's time to create an app-specific
form of :class:`~craft_application.models.PlatformsDict`. This model is a custom
``dict`` type that provides definitions for both a Pydantic core schema and the JSON
schema.

Begin by inheriting from :class:`craft_application.models.GenericPlatformsDict` to
include (if necessary) your custom ``Platform`` model. If this is the only difference
needed, the body of the class can be empty:

.. code-block:: python
    :caption: mycraft/models/project.py

    class MyPlatformsDict(GenericPlatformsDict[MyPlatform]):
        """A custom Platforms dict for MyCraft."""

If different keys can be considered shorthand values, you can replace
:attr:`~craft_application.models.GenericPlatformsDict._shorthand_keys` with an
appropriate set of shorthand keys:

.. code-block:: python
    :caption: mycraft/models/project.py

    class OnlyRiscv64ShorthandDict(GenericPlatformsDict[Platform]):
        """A custom PlatformsDict class that only allows "riscv64" as shorthand."""

        _shorthand_keys = [craft_platforms.DebianArchitecture.RISCV64]

If further customization is necessary, you may need to override
:meth:`~craft_application.models.GenericPlatformsDict.__get_pydantic_json_schema__`.
The
`Pydantic documentation <get_pydantic_json_schema_>`_
is a good place to start to understand this method.

Override ``platforms`` on the ``Project`` model
-----------------------------------------------

Once you have a non-generic child class of
:class:`~craft_application.models.GenericPlatformsDict`, override its type in your
project model:

.. code-block:: python
    :caption: mycraft/models/project.py
    :emphasize-lines: 4

    class MyProject(Project):
        """A Project class for MyCraft."""

        platforms: MyPlatformsDict

This will provide both your custom validation as necessary and a schema that implements
said validation.

Test your validation and schema
-------------------------------

After building a custom platforms model, it is important to ensure that your schema
and the actual project
are treated the same way. This is necessary because the :ref:`ProjectService`
pre-processes the ``platforms`` key before validating the model. The best way to
audit is through a series of integration tests that compare the loading of valid files
to validation from the schema, and the other way around.

Craft Application does this with `a pair of integration tests
<platforms_integration_tests_>`_
that check both valid files and invalid files. It is recommended that you copy these
tests into your application and modify them as needed.
