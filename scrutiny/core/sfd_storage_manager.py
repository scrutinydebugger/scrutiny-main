#    sfd_storage_manager.py
#        A class that manipulates the Scrutiny storage for .sfd files.
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2022 Scrutiny Debugger

__all__ = ['SFDStorageManager']

import os
import re
import logging
import tempfile
import types

from scrutiny.core.firmware_description import FirmwareDescription, SFDMetadata
from scrutiny.core.demo_device_sfd import DemoDeviceSFD
from scrutiny import tools

from scrutiny.tools.typing import *


class TempStorageWithAutoRestore:
    """Context manager that temporarily redirects a ``SFDStorageManager`` to a temp folder and
    restores the original storage on exit. Mainly used for unit tests."""

    storage: "SFDStorageManager"
    """The ``SFDStorageManager`` instance whose storage directory is temporarily overridden."""

    def __init__(self, storage: "SFDStorageManager") -> None:
        self.storage = storage

    def __enter__(self) -> "TempStorageWithAutoRestore":
        """Enter the context and return this instance."""
        return self

    def __exit__(self, exc_type: Optional[Type[BaseException]], exc_val: Optional[BaseException], exc_tb: Optional[types.TracebackType]) -> Literal[False]:
        """Exit the context and restore the original storage directory.

        :returns: ``False``, so any exception raised inside the block is propagated.
        """
        self.restore()
        return False

    def restore(self) -> None:
        """Restore the ``SFDStorageManager`` to its original storage directory."""
        self.storage.restore_storage()


InstallCallback: TypeAlias = Callable[[str], None]
UninstallCallback: TypeAlias = Callable[[str], None]


class SFDStorageManager:
    """Manages the on-disk storage of Scrutiny Firmware Description (SFD) files.

    Provides install, uninstall, and lookup operations for SFD files, identified by their
    firmware ID. Supports temporarily redirecting storage to a temp directory for testing.
    """

    temporary_dir: Optional["tempfile.TemporaryDirectory[str]"]
    """Temporary directory used when testing. When set, all storage operations target this
    directory instead of ``folder``."""
    folder: str
    """Path to the permanent on-disk directory where SFD files are stored."""
    install_callbacks: List[InstallCallback]
    """Callbacks invoked with the firmware ID string after a successful SFD installation."""
    uninstall_callbacks: List[UninstallCallback]
    """Callbacks invoked with the firmware ID string after a successful SFD uninstallation."""
    demo_device_sfd: DemoDeviceSFD
    """Built-in demo device SFD served without requiring an installed file. For showcasing the GUI without a device"""
    logger: logging.Logger
    """Logger for this class."""

    @classmethod
    def clean_firmware_id(cls, firmwareid: str) -> str:
        """Normalize the firmware ID"""
        if not isinstance(firmwareid, str):
            raise ValueError('Firmware ID must be a string')

        return firmwareid.lower().strip()

    def __init__(self, folder: str) -> None:
        self.folder = folder
        self.temporary_dir = None
        self.install_callbacks = []
        self.uninstall_callbacks = []
        self.demo_device_sfd = DemoDeviceSFD()
        self.logger = logging.getLogger(self.__class__.__name__)

    def register_install_callback(self, callback: InstallCallback) -> None:
        """Register a callback to be invoked after each successful SFD installation.

        :param callback: Callable receiving the installed firmware ID string.
        """
        self.install_callbacks.append(callback)

    def register_uninstall_callback(self, callback: UninstallCallback) -> None:
        """Register a callback to be invoked after each successful SFD uninstallation.

        :param callback: Callable receiving the uninstalled firmware ID string.
        """
        self.uninstall_callbacks.append(callback)

    def use_temp_folder(self) -> TempStorageWithAutoRestore:
        """Require the storage manager to switch to a temporary directory. Used for unit testing"""
        self.temporary_dir = tempfile.TemporaryDirectory()
        return TempStorageWithAutoRestore(self)

    def restore_storage(self) -> None:
        """Require the storage manager to work on the real directory and not a temporary directory"""
        self.temporary_dir = None

    def get_storage_dir(self, create: bool = False) -> str:
        """Ge the actual storage directory"""
        if self.temporary_dir is not None:
            return self.temporary_dir.name

        if create:
            os.makedirs(self.folder, exist_ok=True)
        return self.folder

    def install(self, filename: str, ignore_exist: bool = False) -> FirmwareDescription:
        """Install a Scrutiny Firmware Description file (SFD) from a filename into the global storage.
        Once installed, it can be loaded when communication starts with a device that identify
        itself with an ID that matches this SFD"""
        if not os.path.isfile(filename):
            raise ValueError('File "%s" does not exist' % (filename))

        sfd = FirmwareDescription.load_from_file(filename)
        self.install_sfd(sfd, ignore_exist=ignore_exist)
        return sfd

    def install_sfd(self, sfd: FirmwareDescription, ignore_exist: bool = False) -> None:
        """Install a Scrutiny Firmware Description (SFD) object into the global storage.
        Once installed, it can be loaded when communication starts with a device that identify
        itself with an ID that matches this SFD"""
        firmware_id_ascii = self.clean_firmware_id(sfd.get_firmware_id_ascii())
        output_file = os.path.join(self.get_storage_dir(create=True), firmware_id_ascii)

        if os.path.isfile(output_file) and ignore_exist == False:
            self.logger.warning('A Scrutiny Firmware Description file with the same firmware ID was already installed. Overwriting.')

        sfd.write(output_file)  # Write the Firmware Description file in storage folder with firmware ID as name
        for callback in self.install_callbacks:
            callback(firmware_id_ascii)

    def uninstall(self, firmwareid: str, ignore_not_exist: bool = False) -> None:
        """Remove a Scrutiny Firmware Description (SFD) with given ID from the global storage"""
        firmwareid = self.clean_firmware_id(firmwareid)
        if not self.is_valid_firmware_id(firmwareid):
            raise ValueError('Invalid firmware ID')

        target_file = os.path.join(self.get_storage_dir(create=True), firmwareid)

        if os.path.isfile(target_file):
            os.remove(target_file)
            for callback in self.uninstall_callbacks:
                callback(firmwareid)
        else:
            if not ignore_not_exist:
                raise ValueError('SFD file with firmware ID %s not found' % (firmwareid))

    def is_installed(self, firmwareid: str) -> bool:
        """Tells if a SFD file with given ID exists in global storage"""
        firmwareid = self.clean_firmware_id(firmwareid)
        if not self.is_valid_firmware_id(firmwareid):
            return False

        storage = self.get_storage_dir()
        filename = os.path.join(storage, firmwareid)
        return os.path.isfile(filename)

    def is_installed_or_demo(self, firmwareid: str) -> bool:
        """Return ``True`` if the given firmware ID can resolve to a SFD.
        e.g. matches an installed SFD file or the built-in demo device.

        :param firmwareid: Firmware ID to look up.
        """
        return (firmwareid == self.demo_device_sfd.get_firmware_id_ascii()) or (self.is_installed(firmwareid))

    def get(self, firmwareid: str) -> FirmwareDescription:
        """Returns the FirmwareDescription object from the global storage that has the given firmware ID """
        if firmwareid == self.demo_device_sfd.get_firmware_id_ascii():
            return self.get_demo_sfd()

        file = self.get_file_location(firmwareid)
        return FirmwareDescription.load_from_file(file)

    def get_file_location(self, firmwareid: str) -> str:
        """Return the full filesystem path of the SFD file for the given firmware ID.

        :param firmwareid: Firmware ID whose file location is requested.
        :raises ValueError: If ``firmwareid`` does not have a valid format.
        :raises FileNotFoundError: If no SFD file with that firmware ID is installed.
        """
        firmwareid = self.clean_firmware_id(firmwareid)
        if not self.is_valid_firmware_id(firmwareid):
            raise ValueError('Invalid firmware ID')

        storage = self.get_storage_dir()
        filename = os.path.join(storage, firmwareid)
        if not os.path.isfile(filename):
            raise FileNotFoundError(f'Scrutiny Firmware description with firmware ID {firmwareid} not installed on this system')
        return filename

    def get_filesize(self, firmware_id: str) -> int:
        """Return the size in bytes of the installed SFD file for the given firmware ID.

        :param firmware_id: Firmware ID of the installed SFD file.
        """
        return os.stat(self.get_file_location(firmware_id)).st_size

    def get_metadata(self, firmwareid: str) -> SFDMetadata:
        """Reads only the metadata from the Firmware Description file in the global storage identified by the given ID"""
        if firmwareid == self.demo_device_sfd.get_firmware_id_ascii():
            return self.demo_device_sfd.get_metadata()

        storage = self.get_storage_dir()
        firmwareid = self.clean_firmware_id(firmwareid)
        filename = os.path.join(storage, firmwareid)
        return FirmwareDescription.read_metadata_from_sfd_file(filename)

    def get_demo_sfd(self) -> DemoDeviceSFD:
        """Return the built-in demo device SFD."""
        return self.demo_device_sfd

    def list(self) -> List[str]:
        """Return the list of firmware IDs for all SFD files installed in the global storage."""
        thelist = []
        if os.path.isdir(self.get_storage_dir()):
            for filename in os.listdir(self.get_storage_dir()):   # file name is firmware ID
                if os.path.isfile(os.path.join(self.get_storage_dir(), filename)) and self.is_valid_firmware_id(filename):
                    thelist.append(filename)
        return thelist

    @classmethod
    def is_valid_firmware_id(cls, firmware_id: str) -> bool:
        """Returns ``True`` if the given string respect the expected format for a firmware ID"""
        with tools.SuppressException(Exception):
            firmware_id = cls.clean_firmware_id(firmware_id)
            regex = '[0-9a-f]{%d}' % (FirmwareDescription.firmware_id_length() * 2)   # Match only check first line, which is good
            if re.match(regex, firmware_id):
                return True

        return False
