.. _reference-strict-platform-names:

Naming rules
------------

Platform names have broad rules. Although in practice they will typically be an architecture
name (such as ``riscv64``), platform names can be more broadly defined, as long as they
follow a basic set of rules.

The rules are as follows:

1. A platform name must be at least one character in length.
2. A platform name must begin and end with a letter, a number, or a unicode character classified as "Symbol, other".
3. In addition to those categories, characters other than the beginning and end of a platform name may contain a hyphen (``-``), an at sign (``@``), a full stop (``.``), or a colon (``:``).
4. The platform name ``any`` is reserved and cannot be used.

|Starcraft| uses platform names as part of the file name when packing a |star|. A few valid
but unusual platform names include:

- ``amd64``
- ``my-platform``
- ``🇧🇷❣️``
