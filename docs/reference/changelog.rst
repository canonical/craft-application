*********
Changelog
*********

2.9.0 (2024-Jul-03)
-------------------

Application
===========

* Support doc slugs for craft-parts build errors, to point to the plugin docs.
* Support setting the base docs url on the AppMetadata, used in conjunction
  with slugs to build full urls.
* Add a method to enable craft-parts Features. This is called at a specific
  point so that things like command groups can rely on the features being set.
* Ensure the craft-providers' provider is available before launching.

Models
======

* Fix and normalize project validation errors. Never raise
  CraftValidationErrors directly in validators.
* Add a way to provide doc slugs for models. These are shown when a project
  fails validation, provided the base docs url is set on the AppMetadata.
