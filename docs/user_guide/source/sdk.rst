Python SDK
==========

Scrutiny provides a robust Software Development Kit (SDK) for developing client applications in Python.

The SDK supports both synchronous scripting, ideal for Hardware-in-the-Loop (HIL) testing, and an event-based
programming model designed for more advanced integrations.

The Scrutiny GUI itself is built using the same Python SDK that is available for download.

Below is an example of a simple synchronous script:

.. code-block:: python

    import time
    from scrutiny.sdk.client import ScrutinyClient

    client = ScrutinyClient()
    with client.connect('localhost', 8765):
        my_var = client.watch('/var/main.cpp/some_func/some_var')
        client.wait_new_value_for_all()

        my_var.value = 123  # Blocking write
        while True:
            print(f"my_var = {my_var.value}")   # Value updated by a background thread
            time.sleep(0.1)

The SDK documentation contains extensive cross-referencing, requires versioning, and is best experienced in an interactive format such as HTML.
For these reasons, the SDK documentation is not included in this document. Instead, it is hosted online.

See the `online SDK documentation <https://scrutiny-python-sdk.readthedocs.io>`__
