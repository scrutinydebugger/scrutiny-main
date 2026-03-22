Command Line Interface (CLI)
============================

Basic Usage
-----------

The Scrutiny Command Line Interface (CLI) is the main entry point for every functionality accomplished by the host system.

Every commands supports the following argument for log control :

 - ``--loglevel`` : To control the loglevel, valid values are : ``critical``, ``error``, ``warning``, ``info``, ``debug``, ``dumpdata``
 - ``--logfile`` : To redirect the log output to a file rather than stdout
 - ``--disable-loggers`` : Let the user hide some speecific loggers to reduce noise in the output

Here is an example of log from the command line

.. epigraph::

    1388.657 (#14033069)[DEBUG] <ElfDwarfVarExtractor> Registering base type: bool as boolean

.. list-table::
  :header-rows: 1


  * - Timestamp (ms)
    - Thread ID
    - Log Level
    - Logger Name
    - Log message
  * - ``1388.657``
    - ``#1403306169``
    - ``Debug``
    - ``ElfDwarfVarExtractor``
    - ``Registering...``

An example command could look like this:

.. code-block:: bash

    scrutiny server --loglevel debug --disable-loggers MemoryReader CommHandler --logfile output.log

The scrutiny CLI expect the first positional arguments (without ``--`` prefix) to be the name of a command. Each command has its own help message

.. code-block:: bash

    scrutiny server --help
    scrutiny install-sfd --help

The list of available command can be listed with

.. code-block:: bash

    scrutiny --help

The main commands to use Scrutiny are ``gui`` to launch the Graphical User Interface and ``server`` to run a server. Note that a server can be launched from the GUI too.

Server commands
---------------

Some commands are expected to be run on the machine that runs a server.

SFD manipulation
################

A server has a local storage of Scrutiny Firmware Description files (SFD). This storage can be manipulated from the CLI using the following commands

.. list-table::
  :header-rows: 0

  * - install-sfd
    - Install a .sfd file in the local storage
  * - uninstall-sfd
    - Remove a .sfd from the local storage
  * - list-sfd
    - List all installed .sfd files

Examples:

.. code-block::

    $ scrutiny install-sfd my_project.sfd
    [INFO] <install-sfd> SFD file my_project.sfd installed. (ID: bbabc9a02358b140cd441cedd62d2e77)

    $ scrutiny list-sfd
    My Project 1.2.3    (bbabc9a02358b140cd441cedd62d2e77) Scrutiny 0.12.0    Created on 2026-03-20 16:35:31
    STM32 Demo 1.1.0    (047143d0b62a95dc46a29a2d0645d468) Scrutiny 0.10.1    Created on 2025-12-04 10:20:38

    $ scrutiny uninstall-sfd bbabc9a02358b140cd441cedd62d2e77
    [INFO] <uninstall-sfd> SFD bbabc9a02358b140cd441cedd62d2e77 uninstalled


Datalogging manipulation
########################

Datalogging acquisitions gotten from the "Embedded Graph" component in the GUI or through the SDK ``ScrutinyClient::start_datalog`` method are saved on
the server into a SQLite database. Some commands are meant to interract with that database.

.. list-table::
  :header-rows: 0

  * - delete-datalog
    - Delete one or all datalogging acquisitions
  * - list-datalog
    - List all the acquisition stored in the server database
  * - export-datalog
    - Export a datalogging acquisition to a file
  * - datalog-info
    - Show the actual status of the datalogging database


**datalog-info**

.. code-block::

    $ scrutiny datalog-info

    Acquisitions count:      23
    Oldest acquisition:      2025-05-31 22:36:36
    Newest acquisition:      2025-06-09 22:49:01
    Storage location:        /home/bob/.local/share/server/scrutiny_datalog.sqlite
    Storage size:            164.0KiB
    Storage structure hash:  29f60b38c97215f8ac79d4fcc35f9b9cfa54840b

**list-datalog**

.. code-block::

    $ scrutiny list-datalog

    #     Time                   Name              ID                                  Signals
    0     2025-05-31 22:36:36    Acquisition #1    18184179c97b4c02bb843680d7e9cb15    Sine wave,Phase,Frequency
    1     2025-05-31 22:37:03    Acquisition #2    51e587152016492fb62a368034a2a925    Phase,Sine wave,Frequency
    2     2025-05-31 22:37:50    Acquisition #3    d2069465f003476e92cd85a600559c8b    Sine wave,Frequency,Phase
    3     2025-06-08 23:31:44    Acquisition #1    e54a8fcb627144e9ae139a78ee5480a7    sinewave,sinewave_freq,sinewave_phase
    ....

**delete-datalog**

.. code-block::

    $ scrutiny delete-datalog --id 18184179c97b4c02bb843680d7e9cb15
    [INFO] <delete-datalog> Datalog 18184179c97b4c02bb843680d7e9cb15 deleted

**export-datalog**

.. code-block::

    $ scrutiny export-datalog 51e587152016492fb62a368034a2a925 --csv my_file.csv
    [INFO] <export-datalog> CSV file my_file.csv written


Build toolchain commands
------------------------

When integrating Scrutiny intrumentation library in a firmware, the build toolchain must be slightly modified to
 invoke the Scrutiny postbuild tools to accomplish 2 main functions

 1. Inject a unique hash in the firmware ELF file
 2. Generate a Scrutiny Firmware Description (SFD) file

The commands listed in this sections are tools to accomplish these 2 steps.

.. note:: scrutiny-embedded library has a CMake functions calleds ``scrutiny_postbuild`` that invoke those commands automatically when required.

For more details about integration, see the `online instrumentation guide <https://scrutinydebugger.com/guide-instrumentation.html>`__
