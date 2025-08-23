Scrutiny Firmware Description (SFD)
===================================

A Scrutiny Firmware Description (SFD) is a file that's generated during the firmware's build phase. This file includes:

a. The device's static and global variables, which are identified from the debug symbols (including address, size, type, endianness)
b. A Firmware ID, which is used to match the SFD with the corresponding firmware
c. The metadata about the firmware, such as its name, project version, author, build date, etc.
d. Aliases definitions

The :abbr:`SFD (Scrutiny Firmware Description)` must be installed on the server using one of the following method : 

 - Through the :abbr:`CLI (Command Line Interface)`, using the ``install-sfd`` command. The command must be run on the server. (Example: `scrutiny install-sfd my_file.sfd`)
 - Through the SDK, using :meth:`upload_sfd()<scrutiny.sdk.client.ScrutinyClient.upload_sfd>`
 - Through the GUI. The GUI uses the SDK to upload the SFD file to the server

When a device connects, the server will automatically load the appropriate :abbr:`SFD (Scrutiny Firmware Description)` based on the 
firmware ID that the device broadcasts.

-----

.. automethod:: scrutiny.sdk.client.ScrutinyClient.get_installed_sfds

-----

.. automethod:: scrutiny.sdk.client.ScrutinyClient.uninstall_sfds

-----

.. automethod:: scrutiny.sdk.client.ScrutinyClient.download_sfd

-----

.. automethod:: scrutiny.sdk.client.ScrutinyClient.upload_sfd

-----

.. autoclass:: scrutiny.sdk.SFDInfo
    :exclude-members: __new__, __init__
    :members:
    :member-order: bysource

-----

.. autoclass:: scrutiny.sdk.SFDMetadata
    :exclude-members: __new__, __init__
    :members:
    :member-order: bysource

-----

.. autoclass:: scrutiny.sdk.SFDGenerationInfo 
    :exclude-members: __new__, __init__
    :members:
    :member-order: bysource

-----

.. autoclass:: scrutiny.sdk.client.SFDDownloadRequest 
    :exclude-members: __new__, __init__
    :members:
    :inherited-members:
    :member-order: bysource

-----

.. autoclass:: scrutiny.sdk.UploadSFDConfirmation 
    :exclude-members: __new__, __init__
    :members:
    :member-order: bysource
