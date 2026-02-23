#    stream_datagrams.py
#        Internal tool to transmit datagrams over a stream. Used by the server and the clients
#        to exchange JSON objects over TCP
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2024 Scrutiny Debugger

__all__ = ['StreamMaker', 'StreamParser']

from dataclasses import dataclass
from hashlib import md5
import queue
import re
import logging
import time
import zlib

from scrutiny.tools.typing import *
from scrutiny.tools.queue import ScrutinyQueue

HASH_SIZE = 16
HASH_FUNC = md5  # Fastest 128bits+
MAX_MTU = 2**32 - 1
DEFAULT_COMPRESS = True
COMPRESSION_LEVEL = 1
MAX_HEADER_LENGTH = len("<SCRUTINY size=00000000 flags=ch>")


class StreamMaker:
    """Tool that encapsulates a chunk of data in a sized datagram with a header that can be sent onto a stream for reconstruction.

    :param mtu: Maximum Transmission Unit size.
    :param use_hash: Whether to use hash verification (default ``True``).
    :param compress: Whether to use compression (default ``True``).
    """
    _use_hash: bool
    """Whether to use hash verification."""
    _mtu: int
    """Maximum Transmission Unit size."""
    _compress: bool
    """Whether to use compression."""
    _flags: str
    """Flags string for the header."""

    def __init__(self, mtu: int, use_hash: bool = True, compress: bool = DEFAULT_COMPRESS) -> None:
        self._use_hash = use_hash
        self._compress = compress
        if mtu > MAX_MTU:
            raise ValueError(f"MTU is too big. Max={MAX_MTU}")
        self._mtu = mtu
        self._flags = ""
        if self._compress:
            self._flags += 'c'
        if self._use_hash:
            self._flags += 'h'

    def encode(self, data: Any) -> bytearray:
        """Encode data into a datagram with header.

        :param data: The data to encode.
        :returns: The encoded datagram as a bytearray.
        :raises RuntimeError: If the data is too big for the MTU.
        """
        if self._compress:
            data = zlib.compress(data, level=COMPRESSION_LEVEL)
        datasize = len(data)
        if datasize > self._mtu:
            raise RuntimeError(f"Message too big. MTU={self._mtu}")
        out = bytearray()
        out.extend(f"<SCRUTINY size={datasize:x} flags={self._flags}>".encode('utf8'))
        out.extend(data)
        if self._use_hash:
            out.extend(HASH_FUNC(data).digest())
        return out


@dataclass(slots=True)
class PayloadProperties:
    """Properties of a datagram payload."""

    data_length: int
    """Length of the data in bytes"""
    compressed: bool
    """Whether the data is compressed"""
    use_hash: bool
    """Whether hash verification is used."""


class StreamParser:
    """A parser that reads a stream and extracts datagrams.

    :param mtu: Maximum Transmission Unit size.
    :param interchunk_timeout: Timeout between chunks in seconds (optional).
    """
    _payload_properties: Optional[PayloadProperties]
    """Properties of the current payload being parsed."""
    _bytes_read: int
    """Number of bytes read."""
    _buffer: bytearray
    """Buffer for incoming data."""
    _remainder: bytearray
    """Remainder data after processing."""
    _msg_queue: "ScrutinyQueue[bytes]"
    """Queue of parsed datagrams."""
    _pattern: "re.Pattern[bytes]"
    """Regex pattern for parsing headers."""
    _logger: logging.Logger
    """The logger."""
    _last_chunk_timestamp: float
    """Timestamp of the last chunk received."""
    _interchunk_timeout: Optional[float]
    """Timeout between chunks in seconds."""
    _mtu: int
    """Maximum Transmission Unit size."""

    def __init__(self, mtu: int, interchunk_timeout: Optional[float] = None):
        if mtu > MAX_MTU:
            raise ValueError(f"MTU is too big. Max={MAX_MTU}")

        self._payload_properties = None
        self._buffer = bytearray()
        self._msg_queue = ScrutinyQueue(maxsize=100)
        self._pattern = re.compile(b"<SCRUTINY size=([a-fA-F0-9]+) flags=(c?h?)>")
        self._logger = logging.getLogger(self.__class__.__name__)
        self._last_chunk_timestamp = time.perf_counter()
        self._interchunk_timeout = interchunk_timeout
        self._mtu = mtu

    def parse(self, chunk: Union[bytes, bytearray]) -> None:
        """Parse a chunk of data from the stream.

        :param chunk: The data chunk to parse.
        """
        done = False
        if self._payload_properties is not None and self._interchunk_timeout is not None:
            if time.perf_counter() - self._last_chunk_timestamp > self._interchunk_timeout:
                self.reset()

        self._buffer.extend(chunk)
        while not done:
            if self._payload_properties is None:   # We are waiting for a header
                m = self._pattern.search(self._buffer)
                if m:   # We found a header
                    try:
                        size_capture = cast(bytes, m.group(1))
                        flags_capture = cast(bytes, m.group(2))
                        self._payload_properties = PayloadProperties(
                            data_length=int(size_capture.decode('utf8'), 16),  # Read the data length (excluding the hash)
                            use_hash=b'h' in flags_capture,
                            compressed=b'c' in flags_capture
                        )

                    except Exception:
                        self._payload_properties = None
                        self._logger.error("Received an unparsable message length")
                        done = True

                    if self._payload_properties is not None:
                        if self._payload_properties.data_length > self._mtu:
                            self._logger.error(
                                f"Received a message with length={self._payload_properties.data_length} which is bigger than the MTU ({self._mtu})")
                            self._payload_properties = None  # Do not go in reception mode. Leave subsequent data be considered as garbage until the next header
                        elif self._payload_properties.use_hash:
                            self._payload_properties.data_length += HASH_SIZE
                    self._buffer = self._buffer[m.end():]   # Drop header and previous garbage
                else:
                    self._buffer = self._buffer[-MAX_HEADER_LENGTH:]   # Drop garbage
                    done = True

            if self._payload_properties is not None:  # Header is received already, we read successive data
                if len(self._buffer) >= self._payload_properties.data_length:  # Message is complete
                    try:
                        # Make a copy of the message in the output queue and remove it from the work buffer
                        end_of_data = self._payload_properties.data_length
                        if self._payload_properties.use_hash:
                            end_of_data -= HASH_SIZE
                            thehash = self._buffer[end_of_data:self._payload_properties.data_length]
                            if thehash == HASH_FUNC(self._buffer[0:end_of_data]).digest():
                                self._receive_data(bytes(self._buffer[0:end_of_data]), self._payload_properties.compressed)
                            else:
                                self._logger.error("Bad hash. Dropping datagram")   # Dropped in "finally" block
                        else:
                            self._receive_data(bytes(self._buffer[0:end_of_data]), self._payload_properties.compressed)
                    finally:
                        # Remove the message, keeps the remainder. We may have the start of another message
                        self._buffer = self._buffer[self._payload_properties.data_length:]
                        self._payload_properties = None    # Indicates we are not reading a datagram
                else:
                    # We have no more data to process, wait next chunk
                    done = True

        self._last_chunk_timestamp = time.perf_counter()

    def _receive_data(self, data: bytes, compressed: bool) -> None:
        """Process received data, decompressing if necessary.

        :param data: The raw data bytes.
        :param compressed: Whether the data is compressed.
        """
        try:
            if compressed:
                data = zlib.decompress(data)
            self._msg_queue.put_nowait(data)
        except zlib.error:
            self._logger.error("Failed to decompress received data. Is the sender using compression?")
        except queue.Full:
            self._logger.error("Receive queue full. Dropping datagram")

    def queue(self) -> "ScrutinyQueue[bytes]":
        """Get the queue of parsed datagrams.

        :returns: The queue containing parsed datagrams.
        """
        return self._msg_queue

    def reset(self) -> None:
        """Reset the parser state, clearing the buffer and payload properties."""
        self._buffer.clear()
        self._payload_properties = None
