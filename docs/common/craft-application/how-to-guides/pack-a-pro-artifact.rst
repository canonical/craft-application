Pack a Pro-compliant |artifact|
===============================

.. Begin overview

Follow this guide to pack |an-artifact| that contains extended security patches or meets
regulatory compliance needs.

.. End overview

Prerequisites
-------------

- An Ubuntu Pro system (https://ubuntu.com/pro)
- LXD version 5.21 or higher installed (https://documentation.ubuntu.com/lxd/)
- |app| version |app-min-pro-version| or higher installed (|app-link|)

Enable guest attachment
-----------------------

|app| makes use of Ubuntu Pro’s own support for LXD instances, but this support needs
to be explicitly enabled and configured. In a terminal, run:

.. code-block:: bash

    sudo pro config set lxd_guest_attach=available

This command lets |app| attach its LXD instances to the system’s Pro subscription,
and only needs to be executed once.

Restart LXD so the new configuration takes effect:

.. code-block:: bash

    sudo snap restart lxd

Identify the required Pro services
----------------------------------

Next, determine which Pro services fit your needs. |app| supports the following services:

- ``esm-apps`` or ``esm-infra``: If your goal is to pack |an-artifact| for an application and
  include the latest security patches for a base that is no longer under Standard Security
  Maintenance.
- ``fips``, ``fips-updates`` or ``fips-preview``: If you need to deploy |an-artifact| in a
  highly regulated environment that processes sensitive data.

The desired Pro services must be available. On a system with your Pro token
attached, run ``pro status`` and check the ``ENTITLED`` column for available
services. The Ubuntu Pro Client documentation has `detailed information on each service
<https://documentation.ubuntu.com/pro-client/en/v32/explanations/which_services/>`__.

Pack the |artifact|
-------------------

Pack your Pro-compliant |artifact| with the ``pack`` command, listing the desired
services with the ``--pro`` option:

.. code-block:: bash
    :substitutions:

    |app-command| pack --pro=<service>

To use multiple services, pass them to the option as comma-separated values. For example,
to pack |an-artifact| with the ``esm-apps`` and ``esm-infra`` services call:

.. code-block:: bash
    :substitutions:

    |app-command| pack --pro=esm-apps,esm-infra

|app| will automatically attach the Pro subscription and enable the requested services on
the LXD instance while packing the |artifact|.
