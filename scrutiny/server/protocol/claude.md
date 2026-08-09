This module contains the definition of the protocol used for the communication with the device,
as well as functions to craft requests and responses.

It is a custom binary protocol inspired by UDS (ISO-14229).
Details about this protocol can be downloaded [from the website](https://scrutinydebugger.com/doc-device-protocol.html).

Each request contains these fields:
 - Direction (1bit, value=0)
 - Command ID (7 bits)
 - Subfunction ID (8bits)
 - Data Length (16 bits)
 - Data Payload (N bytes, max 65520)
 - CRC32 (4 bytes)

A response is almost identical:
 - Direction (1bit, value=1)
 - Command ID (7 bits)
 - Subfunction ID (8bits)
 - Response code (8bits)
 - Data Length (16 bits)
 - Data Payload (N bytes, max 65520)
 - CRC32 (4 bytes)

The module is self explanatory.

The size limit of 65520 is set to accommodate the device that needs to store the total message size, including the payload but also the overhead in a single 16bits value.
