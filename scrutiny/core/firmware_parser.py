#    firmware_parser.py
#        Reads a compiled firmware and provide tools to read or write the firmware ID
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2022 Scrutiny Debugger

__all__ = ['FirmwareParser']

from dataclasses import dataclass
import hashlib
import mmap
import logging
import scrutiny.core.firmware_id as firmware_id
import os
from binascii import hexlify
import shutil
import enum

from scrutiny.tools.typing import *


def swap_bytes_16(data: bytes) -> bytes:
    if len(data) % 2 != 0:
        raise ValueError("Cannot convert to Little Endian 16 with an odd number of bytes")
    data_out = bytearray()
    for i in range(len(data) // 2):
        data_out.extend([data[2 * i + 1], data[2 * i]])
    return bytes(data_out)


@dataclass
class FirmwareID:
    class StorageFormat(enum.Enum):
        Unknown = 0
        BigEndian = 1
        LittleEndian16 = 2

    data: bytes
    format: StorageFormat


class FirmwareParser:
    """
    This class can read a freshly compiled firmware then generate a firmware ID and also write this
    firmware ID into the binary
    """

    BUF_SIZE = 0x10000
    NO_TAG_ERROR = "Binary file does not contains Scrutiny placeholder. Either it is already tagged or the file hasn't been compiled with a full scrutiny-lib"

    filename: str
    """The path to the input file"""
    logger: logging.Logger
    """The logger"""
    placeholder_location: Optional[int]
    """The location of the placeholder in the .ELF file. ``None`` if not found"""
    firmware_id: Optional[FirmwareID]
    """The firmware ID of this .ELF. ``None`` if we can't compute it"""

    def __init__(self, filename: str):
        self.filename = os.path.normpath(filename)
        if not os.path.isfile(self.filename):
            raise Exception('File %s does not exist' % filename)

        self.logger = logging.getLogger(self.__class__.__name__)
        self.firmware_id = None
        self.placeholder_location = None

        # The firmware ID is stored as an array of char.
        # It will always have the same endianness, unless the target has char bigger than 8bits (like TI C2000)
        # In this case, we need to search for a little endian version (big endian 16 will be is the same as big endian 8)
        for storage_format in (FirmwareID.StorageFormat.BigEndian, FirmwareID.StorageFormat.LittleEndian16):

            if storage_format == FirmwareID.StorageFormat.BigEndian:
                data_to_find = firmware_id.PLACEHOLDER
            elif storage_format == FirmwareID.StorageFormat.LittleEndian16:
                data_to_find = swap_bytes_16(firmware_id.PLACEHOLDER)
            else:
                raise NotImplementedError("Unknown storage format")

            with open(filename, "rb") as f:
                with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                    pos = mm.find(data_to_find)
                    if pos != -1:
                        self.logger.debug('Found scrutiny placeholder at address 0x%08x' % pos)
                        self.placeholder_location = pos

                        sha256 = hashlib.sha256()
                        while True:
                            data = f.read(self.BUF_SIZE)
                            if not data:
                                break
                            sha256.update(data)
                        hash256 = bytes.fromhex(sha256.hexdigest())
                        self.firmware_id = FirmwareID(
                            data=bytes([a ^ b for a, b in zip(hash256[0:16], hash256[16:32])]),    # Reduces from 256 to 128 bits
                            format=storage_format
                        )
                        break

    def has_placeholder(self) -> bool:
        """True if the parsed binary contains a placeholder ID ready to be replaced"""
        return self.placeholder_location is not None

    def throw_no_tag_error(self) -> None:
        """Raise an error that says that we can't find the placeholder in a file"""
        raise ValueError(self.NO_TAG_ERROR)

    def get_firmware_id(self) -> bytes:
        """Return the firmware ID generated while parsing an untagged binary"""
        if self.firmware_id is None:
            self.throw_no_tag_error()

        assert self.firmware_id is not None  # for mypy

        if self.firmware_id.format == FirmwareID.StorageFormat.BigEndian:
            return self.firmware_id.data
        elif self.firmware_id.format == FirmwareID.StorageFormat.LittleEndian16:
            return swap_bytes_16(self.firmware_id.data)
        else:
            raise NotImplementedError("Unsupported storage format")

    def get_firmware_id_ascii(self) -> str:
        """Return the firmware ID generated as an ASCII string"""
        return hexlify(self.get_firmware_id()).decode('ascii')

    def write_tagged(self, dst: Optional[str]) -> None:
        """
        Write back the firmware ID into an untagged one. If dst is set, make a copy, if None, write directly to it.
        """
        if self.firmware_id is None or not self.has_placeholder():
            self.throw_no_tag_error()

        # mypy assertions
        assert self.placeholder_location is not None
        assert self.firmware_id is not None

        src = os.path.normcase(os.path.normpath(os.path.abspath(os.path.realpath(self.filename))))
        if dst is None:
            dst = src
        dst = os.path.normcase(os.path.normpath(os.path.abspath(os.path.realpath(dst))))
        if src != dst:
            shutil.copyfile(src, dst)

        with open(dst, "rb+") as f:
            f.seek(self.placeholder_location)
            # We use the data without conversion to big endian. The device is expected to report a big endian version over the protocol.
            f.write(self.firmware_id.data)
            self.logger.debug('Wrote new hash %s at address 0x%08x' % (self.get_firmware_id_ascii(), self.placeholder_location))
