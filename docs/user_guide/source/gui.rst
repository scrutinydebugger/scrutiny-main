Graphical User Interface (GUI)
==============================

The graphical user interface is part of the Scrutiny pacakge and can be launched with the command ``scrutiny gui``.

the GUI is written in Python, using the QT library through the PySide6 python package. The GUI acts as a Scrutiny client
and uses the `Python SDK <page_sdk>` to communicate with the server. Anything doable with the GUI is doable with a script.

Let's have a first look at the GUI

.. figure:: _static/ui/scrutiny_light.png

    Scrutiny GUI in action

.. figure:: _static/ui/scrutiny_gui_sections.png

    Scrutiny GUI main sections


First steps
-----------

Opening the GUI without configuration will show a blank dashboard and a status abr that shows ``Server : Disconnected``.

In order to get a full communication with a device, we need to connect to a server, then configure that
server to scan for a device on the correct type of communication link (Serial, :ref:`CAN <glossary>`, :ref:`RTT <glossary>`, etc.)

Connecting to a server
######################

First, click the server connection label to ahve a popup menu, then select "Configure"

.. figure:: _static/ui/server_config_menu.png

    Server configuration menu

We have two options

1. Connect to an already running remote server using a :ref:`TCP<glossary>` endpoint (host and port).
2. Start a local server as a subprocess and connect to it.


.. figure:: _static/ui/remote_server_dialog.png
    :height: 6cm

    Remote server configuration dialog

.. figure:: _static/ui/local_server_dialog.png
    :height: 10cm

    Local server configuration dialog


Connecting to a device
######################

Once we have a working communication with a server, the enxt step is to configure the communication
link for the server to reach the device.

.. figure:: _static/ui/status_bar_link_label.png
    :height: 1cm

    Open the device link configuration

The available physical communication links are:

- Serial (based of ``pySerial``)
- :ref:`CAN<glossary>` / :ref:`CAN-FD<glossary>` (based of ``python-can``)
- :ref:`UDP/IP<glossary>`
- Jlink :ref:`RTT<glossary>` (based of pylink-square)

Additionally, it is possible to request the server to run a virtual device to try the user interface

.. note::

    The Scrutiny server has been designed to make it easy to extend the list of supported communication channels.
    If you would like to enable a new communication channel, please open an issue on GitHub to discuss the implementation.

.. figure:: _static/ui/serial_config_dialog.png
    :height: 8cm

    Serial Configuration Dialog

The information given in the dialog is passed to the SDK function ``ScrutinyClient::configure_device_link()``

Once the communication channel is configured, the server will open it and start polling for a device.

The color status next to the "Link" label indicates if the server has succeeded into initializing the communication channel.
In case of failure, the reason should be available in the server logs.

Example:

.. figure:: _static/ui/serial_com999.png
    :height: 1cm

    Unavailable communication channel (inexistant COM port)

If the port is correctly open, the light indicator should turn green and the device connection status should then reflect
the state of the device communication


.. figure:: _static/ui/port_opened_no_device.png
    :height: 1cm

    Open port, no device responding

Once again, if a device is expected to start reponding bu doe snot, the server logs will be the first place to look. Consider launching
the server with a log level of ``debug`` or even ``dumpdata`` to inspect each payload.

Once a device start reponding to the server, the 3rd light indicator should turn green.
By clicking the "Device" label, we can read the configuration polled during the handshake phase of the server.

.. figure:: _static/ui/device_connected_details_menu.png
    :height: 1cm

    Device Connected

.. figure:: _static/ui/device_details_dialog.png
    :height: 12cm

    Device Details Dialog


As soon as a device is connected the Runtime Published Values (green items) will become availables in the Variable List.

Finally, if the server has a :ref:`SFD<page_sfd>` installed that matches the Firwmare ID given by the device,
the server will automatically load it. Loading an SFD will add variables and aliases to the Variable List widget

When a SFD is loaded, the name of the project (coming from the metadata) is displayed in the status bar.

.. figure:: _static/ui/status_bar_link_label.png
    :height: 1cm

    Actively Loaded SFD

Clicking the label opens a dialog that shows the SFD metadata

.. figure:: _static/ui/sfd_details_dialog.png
    :height: 6cm

    Loaded SFD metadata dialog
