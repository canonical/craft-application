Fetch Service integration
=========================

.. admonition:: Experimental
    :class: important

    The integration with the Fetch Service is an experimental feature and therefore
    subject to change.


|Starcraft| integrates Fetch Service, which validates all dependencies that
it downloads when it begins building a |star|. These dependencies are either 
software included in the |star| itself, or software that the build tool or build 
system needs.

There are two modes of integration between |Starcraft| builds and Fetch Service
sessions: managed, and external.

Managed sessions
----------------

When the ``--enable-fetch-service`` option is passed to the ``pack`` command,
|Starcraft| will open a Fetch Service session before starting the
build, and close it after the build is finished. In this scenario, the Fetch 
Service must be available on the host so that |Starcraft| can talk to it.

A Fetch Service session must have a working *policy*, which is either *permissive* or
*strict*. With a permissive policy, Fetch Service inspects but doesn't filter any
traffic. With a strict policy, it filters traffic according to a configuration in
|Starcraft|. The policy is selected by adding it to the Fetch Service flag, with
``--enable-fetch-service=<policy>``.

When |Starcraft| closes the session, it creates the final session report with the
description of the items that were downloaded during artifact build. This is provided
as a JSON file with the same name as the artifact itself.

External sessions
-----------------

Alternatively, |Starcraft| can be configured to use a pre-existing Fetch Service
session in its builds. In this mode of operation, |Starcraft| configures all
traffic filtering for the session, but you are responsible for opening and closing
the session itself, and otherwise managing Fetch Service.

In order to make use of this mode, users must create a Fetch Service session and
configure the following environment variables before invoking the ``pack`` command:

- ``http_proxy`` and ``https_proxy`` must point to the full session url, including
  server and port.
- ``CRAFT_PROXY_CERT`` must point to the Fetch Service's CA certificate. This file must
  be locally accessible by |Starcraft|.
- ``CRAFT_USE_EXTERNAL_FETCH_SERVICE`` must be ``1``.

Because |Starcraft| has no control over the Fetch Service session in this mode, it
can't create a session report.
