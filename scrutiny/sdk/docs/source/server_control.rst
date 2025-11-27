Server Control
==============

Establishing a connection
-------------------------

The communication with the server is done through a TCP socket. One can call :meth:`connect()<scrutiny.sdk.client.ScrutinyClient.connect>` 
and :meth:`disconnect()<scrutiny.sdk.client.ScrutinyClient.disconnect>`.  It is also possible to use :meth:`connect()<scrutiny.sdk.client.ScrutinyClient.connect>`
in a ``with`` block

.. automethod:: scrutiny.sdk.client.ScrutinyClient.connect

-----

.. automethod:: scrutiny.sdk.client.ScrutinyClient.disconnect

-----

Example
#######

.. code-block:: python

    with client.connect('localhost', 1234):
        pass # Do something

    # disconnect automatically called

-----

Getting the server status
-------------------------

Upon establishing a connection with a client, and at regular intervals thereafter, the server broadcasts a status. 
This status is a data structure that encapsulates all the pertinent information about what is happening at the other end of the TCP socket. 
It includes:

- The type of connection used by the device
- A unique session ID with the device (if connected).
- The state of the datalogger within the device
- The loaded :abbr:`SFD (Scrutiny Firmware Description)`.
- etc.

-----

.. automethod:: scrutiny.sdk.client.ScrutinyClient.get_latest_server_status

-----

.. automethod:: scrutiny.sdk.client.ScrutinyClient.wait_server_status_update

-----

.. automethod:: scrutiny.sdk.client.ScrutinyClient.request_server_status_update

-----

.. automethod:: scrutiny.sdk.client.ScrutinyClient.wait_device_ready

-----

.. automethod:: scrutiny.sdk.client.ScrutinyClient.get_device_info

-----

.. autoclass:: scrutiny.sdk.ServerInfo
    :exclude-members: __init__, __new__
    :members:
    :member-order: bysource

-----

.. autoclass:: scrutiny.sdk.DeviceCommState
    :exclude-members: __init__, __new__
    :members:
    :member-order: bysource

-----

.. autoclass:: scrutiny.sdk.DeviceInfo
    :exclude-members: __init__, __new__
    :members:
    :member-order: bysource

-----

.. autoclass:: scrutiny.sdk.DeviceLinkInfo
    :exclude-members: __init__, __new__
    :members:
    :member-order: bysource

-----

.. autoclass:: scrutiny.sdk.SupportedFeatureMap
    :exclude-members: __init__, __new__
    :members:
    :member-order: bysource

-----

.. autoclass:: scrutiny.sdk.MemoryRegion
    :exclude-members: __init__, __new__
    :members:
    :member-order: bysource

-----

.. autoclass:: scrutiny.sdk.DataloggingInfo
    :exclude-members: __init__, __new__
    :members:
    :member-order: bysource

-----

.. autoclass:: scrutiny.sdk.DataloggingState
    :exclude-members: __init__, __new__
    :members:
    :member-order: bysource

-----


Diagnostic metrics
------------------

The client can also provide some diagnostic metrics to monitor the well being of the system.  
Local metrics (measured by the client) are available through :meth:`get_local_stats()<scrutiny.sdk.client.ScrutinyClient.get_local_stats>`.
Server metrics (measured by the server) are available through :meth:`get_server_stats()<scrutiny.sdk.client.ScrutinyClient.get_server_stats>`.

-----

.. automethod:: scrutiny.sdk.client.ScrutinyClient.get_local_stats

-----

.. autoclass:: scrutiny.sdk.client.ScrutinyClient.Statistics
    :exclude-members: __init__, __new__
    :members:
    :member-order: bysource

-----

.. automethod:: scrutiny.sdk.client.ScrutinyClient.get_server_stats

-----

.. autoclass:: scrutiny.sdk.ServerStatistics
    :exclude-members: __init__, __new__
    :members:
    :member-order: bysource

-----

Configuring the device link
----------------------------

The device link is the communication channel between the server and the device. 

This link can be configured by the client. If a device is present, the server will automatically connect to it. If no device is found, the server will simply report 
that no device is connected

-----

.. automethod:: scrutiny.sdk.client.ScrutinyClient.configure_device_link

-----

.. autoclass:: scrutiny.sdk.DeviceLinkType
    :exclude-members: __new__, __init__
    :members: 
    :member-order: bysource

-----

TCP
###

.. autoclass:: scrutiny.sdk.TCPLinkConfig
    :exclude-members: __new__, __init__
    :members:

-----

UDP
###

.. autoclass:: scrutiny.sdk.UDPLinkConfig
    :exclude-members: __new__, __init__
    :members:

-----

Serial
######

.. autoclass:: scrutiny.sdk.SerialLinkConfig
    :exclude-members: __new__, __init__, StopBits, DataBits, Parity
    :members:

.. autoclass:: scrutiny.sdk.SerialLinkConfig.StopBits
    :exclude-members: __new__, __init__
    :members:
    :undoc-members:

.. autoclass:: scrutiny.sdk.SerialLinkConfig.DataBits
    :exclude-members: __new__, __init__
    :members:
    :undoc-members:

.. autoclass:: scrutiny.sdk.SerialLinkConfig.Parity
    :exclude-members: __new__, __init__
    :members: 
    :undoc-members:   
    
-----

Seger RTT
#########

.. autoclass:: scrutiny.sdk.RTTLinkConfig
    :exclude-members: __new__, __init__, JLinkInterface
    :members:


.. autoclass:: scrutiny.sdk.RTTLinkConfig.JLinkInterface
    :exclude-members: __new__, __init__
    :members:
    :member-order: bysource

------

CAN Bus
#######

.. autoclass:: scrutiny.sdk.CANLinkConfig
    :exclude-members: __new__, __init__, CANInterface, ETASConfig, KVaserConfig, PCANConfig, SocketCANConfig, VectorConfig
    :members:


.. autoclass:: scrutiny.sdk.CANLinkConfig.CANInterface
    :exclude-members: __new__, __init__
    :members:
    :member-order: bysource

.. autoclass:: scrutiny.sdk.CANLinkConfig.ETASConfig
    :exclude-members: __new__, __init__
    :members:
    :member-order: bysource

.. autoclass:: scrutiny.sdk.CANLinkConfig.KVaserConfig
    :exclude-members: __new__, __init__
    :members:
    :member-order: bysource

.. autoclass:: scrutiny.sdk.CANLinkConfig.PCANConfig
    :exclude-members: __new__, __init__
    :members:
    :member-order: bysource

.. autoclass:: scrutiny.sdk.CANLinkConfig.SocketCANConfig
    :exclude-members: __new__, __init__
    :members:
    :member-order: bysource

.. autoclass:: scrutiny.sdk.CANLinkConfig.VectorConfig
    :exclude-members: __new__, __init__
    :members:
    :member-order: bysource


------

None
####

.. autoclass:: scrutiny.sdk.NoneLinkConfig
    :exclude-members: __new__, __init__
    :members:
    :member-order: bysource


Demo Mode
---------

One can enable the server demo mode with :meth:`request_demo_mode()<scrutiny.sdk.client.ScrutinyClient.request_demo_mode>`.

When the demo mode is enabled, the server connects to an emulated device that runs in a python thread and simulate the scrutiny-embedded library. 
This mode is meant to try Scrutiny without having to go through the process of instrumenting a firmware.

The demo mode is deactivated by the server when the device connection parameters are updated with :meth:`configure_device_link()<scrutiny.sdk.client.ScrutinyClient.configure_device_link>`

.. automethod:: scrutiny.sdk.client.ScrutinyClient.request_demo_mode
