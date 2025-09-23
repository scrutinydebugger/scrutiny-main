.. _page_accessing_variables:

Accessing variables
===================

In the SDK, Variables, Aliases, :abbr:`RPV (Runtime Published Values)` are presented to the client side through an interface called a ``watchable``, e.g. something you can watch.
Some watchables are available only when the server has loaded the :abbr:`SFD (Scrutiny Firmware Description)` matching the device firmware (alias, var), others are available as 
soon as a device is connected (RPV)

.. list-table:: Watchable types
    :widths: auto

    * - **Type**
      - **Description**
      - **SFD required**
    * - Variable
      - A variable maps to a static or global variable declared in the embedded device firmware. The variable's address, type, size and endianness are defined in the loaded :abbr:`SFD (Scrutiny Firmware Description)`
      - Yes
    * - Runtime Published Values (RPV)
      - Readable and writable elements identified by a numerical ID (16 bits) and declared by the device during the handshake phase with the server.
      - No
    * - Alias
      - Abstract writable/readable entity that maps to either a variable or a :abbr:`RPV (Runtime Published Values)`. Used to keep a consistent firmware interface with existing scripts using this SDK
      - Yes

-----

Basics
------

The first step to access a watchable, is to first tell the server that we want to subscribe to update event on that watchable.
To do so, we use the :meth:`watch<scrutiny.sdk.client.ScrutinyClient.watch>` method and specify the watchable's path. The path
depends on the firmware and must generally be known in advance. 
The path is dependent on the firmware and is typically known beforehand. 
It's also possible to query the server for a list of available watchables, a feature utilized by the GUI.

For scripts based on the :abbr:`SDK (Software Development Kit)`,  it is generally assumed that the elements to be accessed are predetermined 
and won't necessitate user input for selection.

-----

.. automethod:: scrutiny.sdk.client.ScrutinyClient.watch

Once an element is being watched, the server starts polling for the value of that element. 
Each time the value is updated, the server broadcast a value update to all subscribers, in this case, our client. 
Concurrently, a background thread is actively listening listen for these updates and accordingly 
modifies the value that the :class:`WatchableHandle<scrutiny.sdk.watchable_handle.WatchableHandle>` refers to.

Calling :meth:`watch<scrutiny.sdk.client.ScrutinyClient.watch>` multiple time on the same element will always return the same handle.
It is possible to query wether a handle already exists for a given element with 
:meth:`try_get_existing_watch_handle<scrutiny.sdk.client.ScrutinyClient.try_get_existing_watch_handle>` and 
:meth:`try_get_existing_watch_handle_by_server_id<scrutiny.sdk.client.ScrutinyClient.try_get_existing_watch_handle_by_server_id>`. 
A handle will exist if a previous call to  :meth:`watch<scrutiny.sdk.client.ScrutinyClient.watch>` has been done.

.. automethod:: scrutiny.sdk.client.ScrutinyClient.try_get_existing_watch_handle

-----

.. automethod:: scrutiny.sdk.client.ScrutinyClient.try_get_existing_watch_handle_by_server_id

-----

.. autoclass:: scrutiny.sdk.watchable_handle.WatchableHandle
    :exclude-members: __new__, __init__
    :member-order: bysource
    :members: display_path, name, type, datatype, value, value_bool, value_int, value_float, 
        value_enum, has_enum, get_enum, parse_enum_val, write_value_str,
        last_update_timestamp, last_write_timestamp, update_counter

-----

.. autoclass:: scrutiny.sdk.WatchableType
    :members:
    :member-order: bysource

-----

After getting a handle to the watchable, the :attr:`value<scrutiny.sdk.watchable_handle.WatchableHandle.value>` property and its derivative (
:attr:`value_int<scrutiny.sdk.watchable_handle.WatchableHandle.value_int>`, 
:attr:`value_float<scrutiny.sdk.watchable_handle.WatchableHandle.value_float>`, 
:attr:`value_bool<scrutiny.sdk.watchable_handle.WatchableHandle.value_bool>`,
:attr:`value_enum<scrutiny.sdk.watchable_handle.WatchableHandle.value_enum>`) undergo automatic updates. These values are invalid until their initial update, 
meaning that after the call to :meth:`watch<scrutiny.sdk.client.ScrutinyClient.watch>`, there is a period of time where accessing the 
:attr:`value<scrutiny.sdk.watchable_handle.WatchableHandle.value>`
property will raise a :class:`InvalidValueError<scrutiny.sdk.exceptions.InvalidValueError>`.

To await a single value update from the watchable, one can utilize the :meth:`WatchableHandle.wait_update<scrutiny.sdk.watchable_handle.WatchableHandle.wait_update>` 
method. Alternatively, to wait for updates from all watched variables at once, the
:meth:`ScrutinyClient.wait_new_value_for_all<scrutiny.sdk.client.ScrutinyClient.wait_new_value_for_all>` method can be invoked.

.. code-block:: python

    import time
    from scrutiny.sdk.client import ScrutinyClient
    
    client = ScrutinyClient()
    with client.connect('localhost', 8765):
        w1 = client.watch('/alias/my_alias1')
        w2 = client.watch('/rpv/x1234')
        w3 = client.watch('/var/main.cpp/some_func/some_var')
        client.wait_new_value_for_all() # Make sure all watchables have their first value available

        while w1.value_bool:            # Value updated by a background thread 
            print(f"w2 = {w2.value}")   # Value updated by a background thread
            time.sleep(0.1)
        
        w3.value = 123  # Blocking write. This statement blocks until the device has confirmed that the variable is correctly written (or raise on failure).
        w3.value = 'floor(1.23e5*cos(radians(5^2)))' # The expression will be parsed by the server. the value written will be 111475

.. note:: 

    Reading and writing a watchable may raise an exception.

    - Reading : When value is unavailable. This will happen if 
        a. The watchable has never been updated (small window of time after subscription)
        b. The server disconnects
        c. The device is disconnected

    - Writing : When the value cannot be written. This will happen if 
        a. The server disconnects
        b. The device is disconnected
        c. Writing is actively denied by the device. (Communication error or protected memory region)
        d. Timeout: The write confirmation takes more time than the client ``write_timeout``

As demonstrated in the preceding example, device access is executed in a fully synchronized manner. 
Consequently, a script utilizing the Scrutiny Python SDK can be perceived as a thread operating on the embedded device with a slower memory access time.

-----

Detecting a value change
------------------------

When developing a script that uses the SDK, it is common to have some back and forth between the device and the script. 
A good example would be the case of a test sequence, one could write a sequence that looks like this.

1. Write a GPIO
2. Wait for another GPIO to change its value
3. Start an EEPROM clear sequence
4. Wait for the sequence to finish

Each time the value is updated by the server, the :attr:`WatchableHandle.update_counter<scrutiny.sdk.watchable_handle.WatchableHandle.update_counter>` gets incremented. 
Looking for this value is helpful to detect a change. 
Two methods can help the user to wait for remote events. :meth:`WatchableHandle.wait_update<scrutiny.sdk.watchable_handle.WatchableHandle.wait_update>` and 
:meth:`WatchableHandle.wait_value<scrutiny.sdk.watchable_handle.WatchableHandle.wait_value>`

The server periodically broadcasts value updates, typically at a rapid pace. 
The delay in updates is primarily dependent on the saturation level of the communication link with the device. 
Factors such as the number of watchable subscriptions and the available bandwidth will influence the update rate. 
The server polls the device for each watchable in a round-robin scheme. When value updates are available, they are aggregated and flushed to all clients. 
In most common scenarios, a value update can be expected within a few hundred milliseconds.


.. automethod:: scrutiny.sdk.watchable_handle.WatchableHandle.wait_update

-----

.. automethod:: scrutiny.sdk.watchable_handle.WatchableHandle.wait_value

-----

.. automethod:: scrutiny.sdk.client.ScrutinyClient.wait_new_value_for_all

-----

Batch writing
-------------

Writing multiple values in a row is inefficient due to the latency associated with device access.
To optimize speed, one can consolidate multiple write operations into a single batched request using the
:meth:`ScrutinyClient.batch_write<scrutiny.sdk.client.ScrutinyClient.batch_write>` method. 

In a batch write operation, multiple write requests are queued and dispatched to the server in a single API call. 
The server then executes all write operations in the correct order and confirms the successful completion of the entire batch. 

It is permissible to perform multiple writes to the same watchable within the same batch. 
The server ensures that each write operation is completed and acknowledged by the device before proceeding to the next operation.

-----

.. automethod:: scrutiny.sdk.client.ScrutinyClient.batch_write

-----

Example 
#######

.. code-block:: python

    w1 = client.watch('/alias/my_alias1')
    w2 = client.watch('/rpv/x1234')
    w3 = client.watch('/var/main.cpp/some_func/some_var')
    try:
        with client.batch_write(timeout=3):
            w1.value = 1.234
            w2.value = 0x11223344
            w2.value = 0x55667788
            w3.value = 2.345
            w1.value = 3.456
            # Exiting the with block will block until the batch completion or failure (with an exception)

        print("Batch writing successfully completed")
    except ScrutinySDKException as e:
        print(f"Failed to complete a batch write. {e}")


-----

Accessing the raw memory
------------------------

In certain scenarios, it may be advantageous to directly access the device memory, 
bypassing the server's interpretive layer that transforms the data into a meaningful value. 
Such scenarios could include:

- Dumping a data buffer
- Uploading a firmware
- Pushing a ROM image
- etc.

For those cases, one can use :meth:`ScrutinyClient.read_memory<scrutiny.sdk.client.ScrutinyClient.read_memory>` and :meth:`ScrutinyClient.write_memory<scrutiny.sdk.client.ScrutinyClient.write_memory>`
to access the memory.

.. automethod:: scrutiny.sdk.client.ScrutinyClient.read_memory

-----

.. automethod:: scrutiny.sdk.client.ScrutinyClient.write_memory


-----

Available watchables
--------------------

It is possible to query the server for the current number of available watchable items and to download their definition

This feature is typically not required for automation scripts; however, it can be necessary for presenting users with selectable watchable items. 
It is currently used by the Scrutiny GUI to populate the Variable List widget

.. automethod:: scrutiny.sdk.client.ScrutinyClient.get_watchable_count

-----

.. automethod:: scrutiny.sdk.client.ScrutinyClient.download_watchable_list

-----

Following is the object returned :meth:`download_watchable_list<scrutiny.sdk.client.ScrutinyClient.download_watchable_list>` :

.. autoclass:: scrutiny.sdk.client.WatchableListDownloadRequest
    :exclude-members: __new__, __init__
    :member-order: groupwise
    :members:
    :inherited-members:

-----

.. autoclass:: scrutiny.sdk.WatchableConfiguration
    :exclude-members: __new__, __init__
    :member-order: bysource
    :members:
    
