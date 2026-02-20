.. _reference-strict-platform-names:

Naming rules
------------

A platform's name typically matches its target architecture. However, names can deviate
from this norm if they satisfy the following rules:

* A platform name must be at least one character in length.
* A platform name must begin and end with a letter, a number, or a unicode character
  classified as "Symbol, other".
  
  - In addition to those categories, characters other than the beginning and end of a
    platform name may contain a hyphen (``-``), an at sign (``@``), a full stop (``.``),
    or a colon (``:``).
* The platform name ``any`` is reserved and cannot be used.

|Starcraft| uses platform names as part of the file name when packing a |star|. A few valid
but unusual platform names include:

- ``amd64``
- ``my-platform``
- ``🇧🇷❣️``
