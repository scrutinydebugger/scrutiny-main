Graphical User Interface (GUI)
==============================

The graphical user interface (GUI) is included in the Scrutiny package and can be launched with the command ``scrutiny gui``.

The GUI is written in Python and built with the Qt framework via the PySide6 package.
It acts as a Scrutiny client and communicates with the server using the `Python SDK <page_sdk>`.
Anything that can be done through the GUI can also be achieved programmatically with a script.

Let's have a first look at the GUI

.. figure:: _static/ui/scrutiny_light.png

    Scrutiny GUI in action

.. figure:: _static/ui/scrutiny_gui_sections.png

    Scrutiny GUI main sections


First steps
-----------

Opening the GUI without any configuration will display a blank dashboard and a status bar indicating ``Server : Disconnected``.

To establish full communication with a device, you must first connect to a server and then configure that server
to scan for a device using the appropriate communication link (Serial, :ref:`CAN <glossary>`, :ref:`RTT <glossary>`, etc.)

Connecting to a server
######################

First, click the server connection label to open the popup menu, then select "Configure"

.. figure:: _static/ui/server_config_menu.png
    :height: 3cm

    Server configuration menu

We have two options:

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

Once communication with the server is established, the next step is to configure the
communication link so the server can reach the device.

.. figure:: _static/ui/status_bar_link_label.png
    :height: 1cm

    Open the device link configuration

The available physical communication links are:

- Serial (based of ``pySerial``)
- :ref:`CAN<glossary>` / :ref:`CAN-FD<glossary>` (based of ``python-can``)
- :ref:`UDP/IP<glossary>`
- Jlink :ref:`RTT<glossary>` (based of pylink-square)

Additionally, it is possible to request the server to run a virtual device to try the user interface.

.. note::

    The Scrutiny server is designed to make it easy to extend the list of supported communication channels.
    If you would like to add support for a new communication channel, please open an issue on GitHub so we can discuss the implementation.

.. figure:: _static/ui/serial_config_dialog.png
    :height: 8cm

    Serial configuration dialog

The information provided in the dialog is passed to the SDK function  ``ScrutinyClient::configure_device_link()``

Once the communication channel is configured, the server opens it and begins polling for a device.

The status indicator next to the "Link" label shows whether the server successfully initialized the communication channel.
If initialization fails, the reason should be available in the server logs.

Example:

.. figure:: _static/ui/serial_com999.png
    :height: 1cm

    Unavailable communication channel (inexistant COM port)

If the port opens successfully, the indicator light will turn green, and the device-connection status will update
to reflect the state of the communication with the device.


.. figure:: _static/ui/port_opened_no_device.png
    :height: 1cm

    Open port, no device responding

Once again, if a device is expected to start reponding bu doe snot, the server logs will be the first place to look. Consider launching
the server with a log level of ``debug`` or even ``dumpdata`` to inspect each payload.

Once a device start reponding to the server, the 3rd light indicator should turn green.
By clicking the "Device" label, we can read the configuration polled during the handshake phase of the server.

.. figure:: _static/ui/device_connected_details_menu.png
    :height: 1cm

    Device connected

.. figure:: _static/ui/device_details_dialog.png
    :height: 12cm

    Device details dialog


As soon as a device is connected, the Runtime Published Values (green items) become available in the Variable List.

If the server has an :ref:`SFD<page_sfd>` installed that matches the Firmware ID reported by the device, it will automatically load it.
Loading an SFD adds variables and aliases to the Variable List widget.

When an SFD is loaded, the project name (taken from the SFD metadata) is displayed in the status bar.

.. figure:: _static/ui/status_bar_link_label.png
    :height: 1cm

    Actively Loaded SFD

Clicking the label opens a dialog that shows the SFD metadata

.. figure:: _static/ui/sfd_details_dialog.png
    :height: 6cm

    Loaded SFD metadata dialog


The dashboard
-------------

The dashboard is based of the excelent `QT Advanced Docking System <https://githubuser0xffff.github.io/Qt-Advanced-Docking-System/>`__ project.
It consist of docking library allowing you to create a visual layout containing various kind of widgets.

To avoid the confusion with the QT ``Widget`` terminology, we will refer to doackable elements as ``Dashboard Components``.
The dashboard components that Scrutiny offers are available in the left Side Bar.

There is two types of dashboard components, those that can have only a single isntance (top) and those that can have multiple instances (bottom).

.. |WatchIcon| image:: _static/ui/icons/watch.png
   :width: 32px

.. |VarListIcon| image:: _static/ui/icons/varlist.png
   :width: 32px

.. |ContinuousGraphIcon| image:: _static/ui/icons/continuous-graph.png
   :width: 32px

.. |EmbeddedGraphIcon| image:: _static/ui/icons/embedded-graph.png
   :width: 32px

.. |InternalMetricIcon| image:: _static/ui/icons/stopwatch.png
   :width: 32px

.. csv-table::
    :widths: 10 15 10 65
    :header-rows: 1
    :align: left

    "Icon",                 "Components Name",  "Instance", "Description"
    "|VarListIcon|",        "Variable List",    "Single",   "Shows the available watchable elements (Variables, Aliases, :ref:`RPVs<glossary>`)"
    "|InternalMetricIcon|", "Internal Metrics", "Single",   "Shows statistics about actual Scrutiny performances including polling data rates"
    "|WatchIcon|",          "Watch Window",     "Multiple", "Display the real time values of watchables elements dropped through Drag&Drop. Can be reorganized at will"
    "|ContinuousGraphIcon|", "Continuous Graph", "Multiple", "Make a graph of the real-time values of the selected watcahble elements. Sampling rate is variable, acquisition length is not limited."
    "|EmbeddedGraphIcon|",  "Embedded Graph",   "Multiple", "Configure and display graphs obtained through the datalogging feature. Sampling rate depends on the device and can be stable. Acquisition length depends on the datalogging buffer size"


Watch Window Component
######################

.. figure:: _static/ui/dashboard/watch-window-component.png
    :height: 10cm

    Watch Window Component

In the screenshot above, we see a structure of variable, more precisely the ``htim2`` timer isntance coming from the STM32 demo.
The tree structure can be edited at will once in the Watch window. Each row is tied to their server path
and will keep their link to their data source even if renamed or reorganized.

When a folder is collapsed (making the variables invisible), the GUI unsubscribe immediately of the hidden variables to the server.
This can free up bandwidth in the device communication channel, allowing the server to increase its refresh rate for the other visible variables.
The same behavior happens when a whole watch window is made hidden behind another tab.

Values can be exported to file, in the ``.scval`` file format. When doing so, the a snapshot of the actual values are taken and
exported to a file that can be reimported later. This can be useful to load a set of parameters to put a device into a known state.

.. figure:: _static/ui/dashboard/import-values.png
    :height: 2cm

    Server value import

Additionally, note that in the screen capture, we have a pointed variable, identifiable by the asterisk in the name.
To know more about pointed variable, see the :ref:`elf2varmap <cmd_elf2varmap>` command.

In this particular case, we have a pointer to a structure. The pointer is called ``Instance`` and is of type ``ptr32``.
The pointed variable are nested under ``*Instance`` and are of any type. Any can be read or write, the server supports pointer dereferencing.

If a pointer is set to 0, the Scrutiny server will refuse to read it and will signal an invalid values

.. figure:: _static/ui/dashboard/watch-window-null-instance.png
    :height: 6cm

    Null pointer dereferencing refused by the server

.. warning::

    Be very careful when changing the value of a pointer as it can cause a runtime crash of your device.


Continuous Graph Component
##########################

The continuous graph is a graph made by the GUI only. The server and the device have no knowledge of it's existence.

.. figure:: _static/ui/dashboard/continuous-graph-window.png
    :height: 12cm

    Continuous Graph Component

When an acquisition is started, the GUI subscribe to the requested watchable elements to the server and plot
in real time the values broadcast by the server until the acquisition is stopped.

Watchable elements (Variables, Aliases and RPVs) can be dragged and dropped on the axes region.
Axes and watchables can be renamed freely for the acquisition.

Since the server broadcast rate is variable, the sampling rate of this graph is also variable and there is no guarantee
of sample synchronization. This means, that even if two variables are plotted together, samples may arrive independently.
Zooming close enough on a point will show that samples are not synchronized over the time axis.

.. figure:: _static/ui/dashboard/unaligned-samples.png
    :height: 6cm

    Unaligned samples

The continuous graph is designed to run continuously. The GUI only keep a limited amount of samples and display a moving window.
To keep every values received, CSV logging can be activated.

.. figure:: _static/ui/dashboard/continuous-graph-csv-logging.png
    :height: 6cm

    CSV Logging

The CSV export is splitted in multiple files, with a numbered suffix that increment each time a new file is created.

Each time a new value is received, a new row is inserted in the CSV file. Columns that received no new values
will keep their previous value. An extra columns with the label ``New Values`` indicate with a boolean flag,
which columns has been updated in this row.

.. figure:: _static/ui/dashboard/continuous_graph_round_robin.png
    :height: 6cm

    New Values column meaning

In the screenshot above, we see how not all values are updated on each row. We can also observe the behavior of the server
polling variables in a round-robin scheme.


Embedded Graph Component
########################

The embedded graph component is an interface to configure the datalogging feature of the Scrutiny Embedded library.

When making an acquisition, both the server and the device plays a role. The GUI merely display the result.
See the below timing diagram

.. figure:: _static/ui/dashboard/embedded_graph_timing.png
    :width: 10cm

    Embedded graph acquisition order of events
