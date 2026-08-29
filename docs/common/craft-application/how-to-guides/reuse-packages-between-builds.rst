Reuse packages between builds
=============================

When |app| downloads packages while it builds |an-artifact|, it doesn't store them
persistently. On subsequent builds that rely on those same packages, on any project,
|app| will download them again, costing time and bandwidth.

.. Link the Snapcraft page in your app: https://documentation.ubuntu.com/snapcraft/stable/how-to/integrations/craft-an-ros-2-app/

By setting up a cache, your packages will be reused across all |artifact| builds.
For an example of the performance gain that a cache provides, the ROS2 Talker/Listener
snap packs 52% faster with a cache than without.


Requirements
------------

There are multiple ways to set up a package cache, depending on your deployment and
network and storage needs. What follows is a cache for all HTTP traffic that requires:

- A local Linux host
- LXD as the build provider


Set up the proxy
----------------

If you're on a host that has never run |app| before, start by packing |an-artifact| to
create the LXD image:

.. code-block:: bash
    :substitutions:

    |app-command| pack

Create a new Ubuntu 24.04 container instance for the proxy, reusing the |app| namespace
in LXD.

.. code-block:: bash
    :substitutions:

    lxc launch ubuntu:24.04 package-cache --project |app-command|


Install and configure the proxy
-------------------------------

Enter the container.

.. code-block:: bash
    :substitutions:

    lxc shell package-cache --project |app-command|

Once inside the container, install Squid.

.. code-block:: bash

    apt install squid

Next, we'll configure Squid. Before you begin, it's a good idea to back up the default
configuration.

.. code-block:: bash

    cp /etc/squid/squid.conf /etc/squid/squid.conf.orig
    chmod a-w /etc/squid/squid.conf.orig

In ``/etc/squid/squid.conf``, set the following options.

.. code-block::

    # Allow http for the local network
    http_access allow localnet
    # Amount of memory used for live objects
    cache_mem 1000 MB
    maximum_object_size_in_memory 256 MB
    # Cold storage of ~4GiB
    cache_dir ufs /var/spool/squid 4096 16 256
    # Cache more IPs than the default
    # APT can easily hit hundreds of URLs when installing deep dependencies
    ipcache_size 16384
    # Prevent others from tracking the traffic of the proxy server
    via off
    forwarded_for delete

.. admonition:: If you need to tailor the Squid configuration
    :class: hint

    `Configuring Squid
    <https://wiki.squid-cache.org/SquidFaq/ConfiguringSquid#how-do-i-configure-squid-to-work-behind-a-firewall>`_
    in the Squid Cache wiki covers many different networking and storage cases.

Restart Squid so the configuration takes effect:

.. code-block:: bash

    systemctl restart squid.service

Before exiting the container, run ``tail`` to continuously print the server's logs to
the output.

.. code-block:: bash

    tail -f /var/log/squid/access.log

Exit the container by pressing :kbd:`Ctrl` + :kbd:`D`.


.. Uncomment and customise this block for your app

.. Integrate with |app|
    --------------------

    With the container for the proxy server configured and running in the background, you
    can begin accessing the APT cache with |app|.

    When you launch |app|, pass the proxy server to |app| with the ``http_proxy``
    environment variable.

    .. code-block:: bash
        :substitutions:

        http_proxy="http://package-cache.lxd:3128/" |app-command| pack

    Alternatively, you can pass the IP address of the proxy server. Copy the IP address from
    LXC:

    .. code-block:: bash
        :substitutions:

        lxc list --project |app-command| | grep package-cache

    Then, when launching |app|, pass the IP address to ``http_proxy``:

    .. code-block:: bash
        :substitutions:

        http_proxy="http://<package-cache-ip>:3128/" |app-command| pack


Monitor the cache
-----------------

While a build is running, you can monitor the cache's activity in a separate terminal.
Run ``tail`` to continuously print the Squid log to the output.

.. code-block:: bash
    :substitutions:

    lxc exec package-cache --project |app-command| -- tail -f /var/log/squid/access.log
