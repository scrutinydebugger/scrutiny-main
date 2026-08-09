This module provides a Graphical User Interface that can be launched through the ``scrutiny gui`` command.
The GUI acts as a client in the Scrutiny ecosystem and uses the Scrutiny SDK to communicate with the server.
This GUI uses QT for Python (PySide6) and a 3rd-party module called QT Advanced Docking System (ADS) for its
docking mechanism, which is central to the GUI.


# Folder structure

- assets : Contains static files to be loaded by the GUI such as fonts, images, stylesheets
- components : Contains the dashboard Components. See the section about them
- core : Main feature of the GUI, this includes the communication with the server, a registry to store the data received, drag&drop logic, etc.
- dialogs : Contains custom made QT dialogs
- themes : Custom made theming mechanism
- tools : Common software tools that have no other dependencies
- widgets : Custom made widgets

# Composition structure

When launching the GUI through the command line, the call graph or ownership graph looks roughly like that

- CLI GUI command
    - `ScrutinyGUI` (gui.py)
        - `MainWindow` (main_window.py)
            - Menu bars (top, left, bottom)
            - `ServerManager`
                - SDK client
            - `WatchableRegistry`
            - `Dashboard`
                - QT ADS Dock manager
                - Component 1
                - Component 2
                - ...

Each component is a cohesive module that is mostly standalone, except that it is given a reference to the ``WatchableRegistry`` and ``ServerManager``
since those are app wide services.

## Server Manager

The ``ServerManager`` is the layer of code talking with the server. Every SDK objects are owned by it.
when started, the ``ServerManager`` constantly tries to connect to a server (using a ``ScrutinyClient``).
The integration with the SDK uses the event queue mechanism. A thread continuously monitor the SDK event queue
and emit a QT signal so they get processed in the QT thread.

A custom extension of a ``ScrutinyListener`` is made to handle the stream of value updates coming from the server.
In this listener, updates are queued and a periodic "flush" QT signal comes to empty the queue, therefore updates are propagated in the GUI in batches.
A component can chose to only pick the most recent one (like the Watch component) or keep them all (like the `Continuous Graph`).

The ``ServerManager`` exposes the most common feature provided by the ``ScrutinyClient`` to the rest of the application, such as connection status, device status. It takes care
of downloading the watchable list (the content of the server datastore) and fills a local ``WatchableRegistry`` with the content. When a device connects, it downloads
the RPVs and when a SFD is loaded, it downloads the variables and aliases. This is done asynchronously and a QT signal is emitted when the datastore content changes. It is the responsibility of the consumer modules to pick those and also handles server and device connection/disconnection.

The ``ServerManager`` offers an API for the other GUI modules (mainly the dashboard components) to access the SDK capabilities directly without transferring ownership of the client.
A module can invoke ``schedule_client_request`` and pass function that receives the ``ScrutinyClient`` object so a synchronous call can be made. That callback will be executed by a worker in a thread pool. The response of that callback is transferred to the QT thread and invoked synchronously as a QT slot.


## Watchable Registry

The ``WatchableRegistry`` is another central piece to the GUI.
It stores the watchables, their metadata and offer a mechanism for watchers subscription and update broadcasting, very analogous to the server ``Datastore``.
Contrary to the server ``Datastore``, the ``WatchableRegistry`` only stores what is exposed by the server API, does not keep the latest values received and the watchables are organized in a tree structure.

Watchables in the registry have a type (Variable/Alias/RPV) and a path. We used a Fully Qualified Name (referred to as FQN) to describe the element with a single string.
A FQN should point to single entry in the registry. the entry does not have to be present, it can be missing oif the device is disconnected for example.

## Dashboard components

The GUI is built around a docking system. Each widget that can be added in the docking system is called a "Component" to avoid confusion with a QT widget.
Each component have an icon in the side bar and can be instantiated once or many times, depending on the component.

To create a new component, one must inherits ``ScrutinyGUIBaseGlobalComponent`` for single instance components and ``ScrutinyGUIBaseLocalComponent`` for multi-instance components. Each component must define

 - A unique name
 - A display name and an icon shown in the side bar
 - a ``setup()`` / ``teardown()`` method called when inserting/removing the instance in the dashboard
 - a ``get_state()`` and ``load_state()`` method to serialize the dashboard and save the work environment to a file

There are also optional method that can be extended
 - ``ready()`` : Called when the instance of the component has been rendered by QT
 - ``visibilityChanged()`` : When the component is shown or hidden (top or behind a tabs)
 - ``has_unsaved_changes()`` : To tell the dashboard if a save is required before clearing
 - ``saved()`` : a callback invoked after a save operation

Each component can access the rest of the application through the ``app_interface`` property that implements the ``AbstractComponentAppInterface``.
this object has a reference to the ``ServerManager`` and the ``WatchableRegistry`` and components are free to use them through their public API.

# QT ADS integration

The integration of QT ADS has few quirks that needs to eb mentioned. The state of the dashboard does not use the native state export provided by QTADS.
The reason is that this feature exports the configuration flags of the widget and does not allow to add custom data. We want to eb able to change the docking
behavior between software updates and still be compatible with dashboards saved from previous version. Also, custom data such as component type and configuration
was not easily exportable.

For these reasons, we make our own export/reload mechanism that uses a non-public property, so it might break in the future, but this seems unlikely.

Also, QT ADS has a factory mechanism that does not cope very well with Shiboken lifecycle. We need to take extra cares to keep reference of the widgets we create through a factory created in Python to avoid double-free crashes.

# Thread enforcing

The server manager is the bridge between the procedural world and event-based world of QT. It deals with more than a single thread and sometime methods are expected to be called by a thread but not the other. Functions that needs to be called by the QT thread usually have the prefix ``qt_``. To catch problems early, we have a mechanism to
create a runtime crash if a function meant for a dedicated thread is called by the wrong thread. For example,  many methods will have the decorator ``@enforce_thread(QT_THREAD_NAME)`` or ``@enforce_thread(SERVER_MANAGER_THREAD_NAME)``. Their purpose is to catch developer mistakes.

# Drag & Drop

The application uses Drag&Drop extensively as one can drag a watchables across components. We therefore needs a way to represent watchable data in a way
that every components understands. ``ScrutinyDragData`` class aims at implementing this, it encodes data and assign a known data type that may or may not supported by
a component. The simplest one and most supported is the ``WatchableList`` format, which is just and array of watchable defined by their FQN and a display name.

The ``VariableListComponent`` component can provide a tree structure that is more than just a list. Each node of the tree must point to an existing entry in the registry.
The ``WatchComponent`` can transfer full trees of watchables only identified by a FQN, meaning the entry may or may not be in the registry.
