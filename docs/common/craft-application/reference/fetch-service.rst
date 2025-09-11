Fetch Service Integration
=========================

.. admonition:: Experimental
    :class: important

    The integration with the Fetch Service is an experimental feature and therefore
    subject to change.


The Fetch Service integration allows the inspection and validation of dependencies that
are downloaded during the regular packing of artifacts. These dependencies include
not only the sources that make up the project being built, but also anything that is
necessary during the build itself, like compilers and other development packages.

There are two modes of integration between |Starcraft| builds and Fetch Service
sessions: managed, and external.

Managed sessions
----------------

When the ``--enable-fetch-service`` option is passed to the ``pack`` command,
|Starcraft| will take care of creating a Fetch Service session before starting the
build and shutting it down afterwards. In this scenario the Fetch Service needs to be
available on the local host so that |Starcraft| can talk to it.

The session created by |Starcraft| can be either "permissive", in which case the Fetch
Service will inspect the traffic but not block accesses that would be otherwise
restricted, or "strict", in which case only traffic that is permitted under the Fetch
Service's own configuration will be allowed. This constitutes the session's *policy*,
and can be selected by passing either ``permissive`` or ``strict`` to
``--enable-fetch-service=<policy>``.

Since the application controls the session, it also creates the final session report
with the description of the items that were downloaded during the packing of the
artifact. This is provided as a JSON file with the same name as the artifact itself.

External sessions
-----------------

Alternatively, |Starcraft| can be configured to use a pre-existing Fetch Service session
in its builds. In this mode of operation, the application will still configure all
traffic to go through the session, but the user is responsible for creating and
destroying the session itself and otherwise managing the Fetch Service.

In order to make use of this mode, users must create a Fetch Service session and
configure the following environment variables before invoking the ``pack`` command:

- ``http_proxy`` and ``https_proxy`` must point to the full session url, including
  server and port.
- ``CRAFT_PROXY_CERT`` must point to the Fetch Service's CA certificate. This file must
  be locally accessible by |Starcraft|.
- ``CRAFT_USE_EXTERNAL_FETCH_SERVICE`` must be ``1``.

Because |Starcraft| has no control over the Fetch Service session, it cannot create
the session report containing the description of the downloaded items.
