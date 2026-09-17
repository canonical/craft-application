Fetch Service sessions
======================

.. admonition:: Experimental
    :class: important

    The integration with the Fetch Service is an experimental feature and therefore
    subject to change.


|app| uses Fetch Service to validate all dependencies that are downloaded
during |artifact-indefinite| build. These dependencies are either software
included in the |artifact| itself, or software that the build tool or build system
needs.

Fetch Service operates in *sessions*, which run in one of two modes:
managed or external.

Managed sessions
----------------

When the ``--enable-fetch-service`` option is passed to the ``pack`` command,
|app| will open a Fetch Service session before starting the
build, and close it after the build is finished. In this scenario, the Fetch
Service must be available on the host so that |app| can talk to it.

A Fetch Service session must have a working *policy*, which is either *permissive* or
*strict*. With a permissive policy, Fetch Service inspects but doesn't filter any
traffic. With a strict policy, it filters traffic according to a configuration in
|app|. The policy is selected by adding it to the Fetch Service flag, with
``--enable-fetch-service=<policy>``.

When |app| closes the session, it creates the final session report with the
description of the items that were downloaded during artifact build. This is provided
as a JSON file with the same name as the artifact itself, in the same directory.

External sessions
-----------------

Alternatively, |app| can be configured to use a pre-existing Fetch Service
session for builds and tests. In this mode of operation, |app| configures all
traffic filtering for the session, but you are responsible for opening and closing
the session itself, and otherwise managing Fetch Service.

In order to make use of this mode, users must create a Fetch Service session and
configure the following environment variables before invoking the ``pack`` or
``test`` command:

.. list-table::
    :header-rows: 1

    * - Variable
      - Description
    * - ``http_proxy``, ``https_proxy``
      - Must point to the full session url, including scheme, server and port.
    * - ``CRAFT_PROXY_CERT``
      - Must point to the Fetch Service's CA certificate. This file must be locally
        accessible by |app|.
    * - ``CRAFT_USE_EXTERNAL_FETCH_SERVICE``
      - Must be ``1`` to use the session while building the artifact.
    * - ``CRAFT_USE_EXTERNAL_FETCH_SERVICE_FOR_TEST``
      - Must be ``1`` to use the session in spread test runners.

The two ``CRAFT_USE_EXTERNAL_FETCH_SERVICE`` variables are independent. Set both
to ``1`` to use the external session while building the artifact and running its
tests. When ``CRAFT_USE_EXTERNAL_FETCH_SERVICE_FOR_TEST`` is set, |app| copies
the certificate specified by ``CRAFT_PROXY_CERT``, if set, to each spread runner
and configures its package managers, snapd, and LXD to use the proxy.

Because |app| has no control over the Fetch Service session in this mode, it
can't create a session report.
