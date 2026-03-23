Command Line Interface (CLI)
============================

Basic Usage
-----------

The Scrutiny Command Line Interface (CLI) is the main entry point for every functionality accomplished by the host system.

Every commands supports the following argument for log control :

.. list-table:: Logging options
  :header-rows: 0
  :align: left

  * - \-\-loglevel
    - To control the loglevel, valid values are : critical, error, warning, info, debug, dumpdata
  * - \-\-logfile
    - To redirect the log output to a file rather than stdout
  * - \-\-disable-loggers
    - Let the user hide some speecific loggers to reduce noise in the output

Here is an example of log from the command line

.. code-block::

    1388.657 (#14033069)[DEBUG] <ElfDwarfVarExtractor> Registering base type: bool as boolean

.. list-table:: Log line fields
  :header-rows: 0
  :align: left

  * - **Timestamp (ms)**
    - 1388.657
  * - **Thread ID**
    - 1403306169
  * - **Log Level**
    - Debug
  * - **Logger Name**
    - ElfDwarfVarExtractor
  * - **Log message**
    - Registering base type: bool as boolean


A real command example could look like this:

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

.. _table_server_sfd_storage_command:

.. list-table:: Server SFD storage commands
  :header-rows: 1
  :align: left

  * - **Command**
    - **Description**
  * - **install-sfd**
    - Install a .sfd file in the local storage
  * - **uninstall-sfd**
    - Remove a .sfd from the local storage
  * - **list-sfd**
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

.. list-table:: Server datalogging commands
  :header-rows: 1
  :align: left

  * - **Command**
    - **Description**
  * - **delete-datalog**
    - Delete one or all datalogging acquisitions
  * - **list-datalog**
    - List all the acquisition stored in the server database
  * - **export-datalog**
    - Export a datalogging acquisition to a file
  * - **datalog-info**
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

When integrating the Scrutiny intrumentation library in a firmware, the build toolchain must be slightly modified to
invoke the Scrutiny postbuild tools to accomplish 2 main functions

 1. Inject a unique hash in the firmware ELF file
 2. Generate a Scrutiny Firmware Description (SFD) file

The commands listed in this sections are tools to accomplish these 2 steps.

.. note:: scrutiny-embedded library has a CMake functions calleds ``scrutiny_postbuild`` that invoke those commands automatically when required.

.. image:: _static/build_toolchain.png

For more details about how to integrate Scrutiny in a firmware and the postbuild process,
see the `online instrumentation guide <https://scrutinydebugger.com/guide-instrumentation.html>`__


.. list-table:: Build toolchain commands
  :header-rows: 1
  :align: left

  * - **Command**
    - **Description**
  * - **get-firmware-id**
    - Extract a unique hash from a .elf file used for device identification
  * - **tag-firmware-id**
    - Writes the firmware id into a freshly compiled binary
  * - **elf2varmap**
    - Extract the variables definition from an ELF file through DWARF debugging symbols
  * - **add-alias**
    - Append an alias to a SFD file or in-making SFD work folder. Definition can be passed with a file or command line arguments
  * - **make-metadata**
    - Generate a .json file containing the metadata used inside a SFD (Scrutiny Firmware Description)
  * - **make-sfd**
    - Generates a SFD file (Scrutiny Firmware Description) from a given folder containing the required files


**get-firmware-id**

This command can print the Firmware ID (128 bits hash) to stdout or to a folder

.. code-block::

    $ scrutiny get-firmware-id stm32f4_demo.elf
    c15e758da4efdcacc50b18220f92b33b

    $ scrutiny get-firmware-id stm32f4_demo.elf --output some_folder
    [INFO] <get-firmware-id> Firmware ID c15e758da4efdcacc50b18220f92b33b written to some_folder/firmwareid


**tag-firmware-id**

This command can create a new .elf with the firmware ID injected or modify an existing .elf file.

.. code-block::

    $ scrutiny tag-firmware-id stm32f4_demo.elf stm32f4_demo_tagged.elf
    [INFO] <tag-firmware-id> Binary stm32f4_demo_tagged.elf tagged with firmware ID: c15e758da4efdcacc50b18220f92b33b

    $ scrutiny tag-firmware-id stm32f4_demo.elf --inplace
    [INFO] <tag-firmware-id> Binary stm32f4_demo.elf tagged with firmware ID: c15e758da4efdcacc50b18220f92b33b


.. note::

    ``get-firmware-id`` and ``tag-firmware-id`` only work on ELF files that were not previously tagged with ``tag-firmware-id`` as it search for a known 128bits pattern.
    Tagging a binary replace that placeholder pattern with a new 128 hash


**elf2varmap**

This command is one of the core feature of Scrutiny. It reads the debugging symbols (DWARF format) generated by a compiler and outputs a VarMap
file that describe the memory layout of the firmware. The VarMap files expand every classes, structures, namespaces, unions into a flat list of
readable/writable elements identified by a unique tree path. These elements have properties such as type, address, enum, etc.

The command either write to stdout or generate a file named ``varmap.json`` in a folder specified by the ``--output`` option.

Examples:

.. code-block:: bash

    $ scrutiny elf2varmap stm32f4_demo.elf --cu_ignore_patterns "file1.cpp" "file2.cpp" > somefile.json
    $ scrutiny elf2varmap stm32f4_demo.elf --dereference-pointers --output some_folder   # Create ./some_folder/varmap.json

``elf2varmap`` often needs to demangle C++ symbol names. To do so, it relies on ``c++filt``, a GNU utility that generally ships with
GCC or Clang based compilers.
By default, ``elf2varmap`` will search the system paths for a program named ``c++filt``. The path for a different binary can be specified with ``--cppfilt``

.. code-block:: bash

    $ scrutiny elf2varmap stm32f4_demo.elf --cppfilt /path/to/my/compiler/c++filt

Two options allow the user to avoid bloating the output VarMap by giving "ignore" rules

- ``--cu_ignore_patterns`` : An ignore pattern that applies to Compile Unit names. essentially, the name of the source C++ file.
  This can be useful to remove variables coming from content injected by the compiler (startup code, stndard library, etc.)
  Examples: ``*main.cpp`` or ``*subfolder1/subfolder2/*``.
- ``--path_ignore_patterns`` : An ignore pattern that applies to the variable tree path in the output. This can filter namespaces, classes, etc.
  Examples: ``/global/MyNamespace/*``

Another option can affect greatly the content of the output is ``--dereference-pointers`` ask ``elf2varmap`` to create entries for what is pointed by a pointer.
As an more concrete example, consider the C++ code:

.. code-block:: c++

    // Global space
    struct MyStruct{
        int32_t member1
    };

    MyStruct TheStructInstance;
    MyStruct* TheStructPointer;

Running ``elf2varmap`` on this piece of code will create 2 entries: One for the member and one for the pointer

1. ``/global/TheStructInstance/member1`` of type ``int32_t``
2. ``/global/TheStructPointer`` of type ``ptrXX`` where XX is the size that depends on the architecture

But running ``elf2varmap`` with the ``--dereference-pointers`` will create an additional entry in the output varmap

3. ``/global/TheStructPointer*/member1`` of type ``int32_t`` with a link to ``/global/TheStructPointer``

The Scrutiny server is able to dereference pointed elements like this. It will first read the pointer value then adjust the offset of every variables pointed
by that pointer before reading the memory.
Only a single level of dereferencing is possible. Both the CLI and the Scrutiny server are designed to prevent double dereferencing.

See :ref:`The VarMap Format <varmap_file>` for more details about the VarMap file.

.. note::

    Every compiler has its own distinctive behavior when comes to generating debugging symbols. ``elf2varmap`` handles as many as possible, but a new compiler may
    produce an unexpected DWARF sequence. In such event, the expected behavior is for ``elf2varmap`` to skip the variable and produce a warning.


**add-alias**

As explained in the :ref:`Architecture section <page_architecture>`, a Scrutiny server can exposes Aliases when a device connect.
These aliases comes from a file named ``alias.json`` embedded in the SFD file.

This command can add one or many aliases to a SFD, being in construction or already installed.on a server. the behavior will depend on the
value of the destination. Let's look at examples

.. code-block:: bash

    $ scrutiny add-alias --file source1.json source2.json some_folder           # A SFD work folder
    $ scrutiny add-alias --file source1.json source2.json existing_file.sfd     # A zipped SFD
    $ scrutiny add-alias --file source1.json source2.json abcdef123456789       # The firmware ID of an installed SFD on this machine.

Also, rather than specifying the input as a .json file, it is possible to define the a single alias from the command line by specifying all its properties one by one.
When doing so, ``--fullpath`` and ``--target`` are mandatory. Optional parameter can be set such as ``--gain``, ``--offset``, ``--min``, ``--max``

.. code-block:: bash

    $ scrutiny add-alias --fullpath "/path/to/my/new/alias" --target "/static/main.cpp/namespace1/var1" myfile.sfd

See the :ref:`Alias file format <alias_file>` for more details


**make-metadata**

This command generate the :ref:`metadata file <metadata_file>` that goes in a .sfd.

Example:

.. code-block::

    $ scrutiny make-metadata --project-name "AcmeSoft" --version "2.0" --author "ACME" --output my_work_folder
    [INFO] <make-metadata> Metadata file my_work_folder/metadata.json written

**make-sfd**

This is the last step to be exwecuted when generating the .sfd file. This command somply validate the content of the work folder and compresses it
using the ZIP algorithm.

.. code-block::

    $ scrutiny make-sfd my_work_folder my_file.sfd


Misc commands
-------------

Few additional commands serves various purposes, generally for developpers.

.. list-table:: Developeprs command
  :header-rows: 1
  :align: left

  * - **Command**
    - **Description**
  * - **runtest:**
    - Run unit tests
  * - **version**
    - Display the Scrutiny version string
  * - **userguide**
    - Open this User Guide


**runtest**

Scrutiny unit tests are based on the native ``unittest`` Python module. This command launches the unit tests with a custom runner

Example:

.. code-block:: bash

    $ python -m scrutiny runtest            # Run all tests
    $ python -m scrutiny runtest server     # Run only the tests in the server folder
    $ python -m scrutiny runtest server.test_api # Runs all tests in the test_api.py file
    $ python -m scrutiny runtest server.test_api.TestAPI # Runs all tests in the TestAPI class
    $ python -m scrutiny runtest server.test_api.TestAPI.test_stop_watching_on_disconnect # Runs a single test case

The custom Scrutiny test runner does a little more than what the native unittest module would do.

1. It validates that the tests run comes from the Scrutiny package. Avoid confusing problem on a system where ``import test`` is a valid import.
2. It allows loading a folder module
3. It prints the execution time
4. It sets the default logging level to ``critical`` because many tests are expected to test error cases.

**version**

Simply prints the version. Convenience for CI and deployment scripts.

.. code-block::

    $ scrutiny version
    Scrutiny Debugger v0.12.0
    (c) Scrutiny Debugger (License : MIT)

    $ scrutiny version --format short
    0.12.0

**userguide**

.. code-block:: bash

    $ scrutiny userguide            # Open the guide in the default PDF viewer
    $ scrutiny userguide location   # Prints the file location
