#    watchable_handle.py
#        A handle on a watchable element (Variable, Alias, RPV). This handle is created by
#        the client when watching
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2023 Scrutiny Debugger

__all__ = ['WatchableHandle']

import threading
from datetime import datetime
import time

from scrutiny.sdk.definitions import *
from scrutiny.core.basic_types import *
from scrutiny.core.embedded_enum import EmbeddedEnum
import scrutiny.sdk.exceptions as sdk_exceptions
from scrutiny.sdk.write_request import WriteRequest
from scrutiny.tools import validation, deprecated
from scrutiny.tools.typing import *
from scrutiny.core import path_tools

if TYPE_CHECKING:
    from scrutiny.sdk.client import ScrutinyClient


ValType = Union[int, float, bool]


class WatchableHandle:
    """A handle to a server watchable element (Variable / Alias / RuntimePublishedValue) that gets updated by the client thread."""

    __slots__ = (
        '_client',
        '_server_path',
        '_shortname',
        '_configuration',
        '_lock',
        '_status',
        '_value',
        '_last_value_dt',
        '_last_write_dt',
        '_update_counter',
        '_dead',
        '_requested_update_rate'
    )

    _client: "ScrutinyClient"
    """The client that created this handle"""
    _server_path: str
    """The tree-like path known to the server"""
    _shortname: str
    """Name of the last element in the server path"""
    _configuration: Optional[BaseDetailedWatchableConfiguration]
    """Details obtained by the server after a call to watch()"""

    _lock: threading.Lock
    """A lock to access the value"""
    _status: ValueStatus
    """Status of the value. Tells if the value is valid or not and why it is invalid if not"""

    _value: Optional[ValType]
    """Contains the latest value gotten by the client"""
    _last_value_dt: Optional[datetime]
    """Datetime of the last value update by the client"""
    _last_write_dt: Optional[datetime]
    """Datetime of the last completed write on this element"""
    _update_counter: int
    """A counter that gets incremented each time the value is updated"""
    _dead: bool
    """A one-shot flag that indicates if the handle is dead forever"""
    _requested_update_rate: Optional[float]
    """The update rate requested for this handle"""

    def __init__(self, client: "ScrutinyClient", server_path: str, requested_update_rate: Optional[float]) -> None:
        self._client = client
        self._server_path = server_path
        self._shortname = path_tools.make_segments(server_path)[-1]
        self._configuration = None
        self._lock = threading.Lock()
        self._update_counter = 0
        self._last_write_dt = None
        self._dead = False
        self._set_invalid(ValueStatus.NeverSet)
        self._requested_update_rate = requested_update_rate

    def _set_requested_update_rate(self, update_rate: Optional[float]) -> None:
        self._requested_update_rate = update_rate

    def __repr__(self) -> str:
        """Return a developer-friendly string representation including the name, datatype, and object address."""
        addr = "0x%0.8x" % id(self)
        if self._configuration is None:
            return f'<{self.__class__.__name__} "{self._shortname}" [Unconfigured] at {addr}>'

        return f'<{self.__class__.__name__} "{self._shortname}" [{self._configuration.datatype.name}] at {addr}>'

    def _configure(self, config: BaseDetailedWatchableConfiguration) -> None:
        """Store the server-provided configuration and reset the value state.

        Called by the client after the server confirms a subscription.

        :param config: The :class:`BaseDetailedWatchableConfiguration` returned by the server.
        """
        with self._lock:
            self._configuration = config
            self._status = ValueStatus.NeverSet
            self._value = None
            self._last_value_dt = None
            self._update_counter = 0

    def _set_last_write_datetime(self, dt: Optional[datetime] = None) -> None:
        """Record the datetime of the most recent completed write operation.

        :param dt: The completion datetime. Uses the current wall-clock time when ``None``.
        """
        if dt is None:
            dt = datetime.now()

        with self._lock:
            self._last_write_dt = dt

    def _update_value(self, val: Optional[ValType], timestamp: Optional[datetime] = None) -> None:
        """Update the cached value and mark the status as ``ValueStatus.Valid``.

        No-op if the status is ``ValueStatus.ServerGone``.
        Called by the client worker thread when a watchable-update message is received.

        :param val: The new value.
        :param timestamp: Server-side timestamp of the update. Uses the local wall clock when ``None``.
        """
        with self._lock:
            if self._status != ValueStatus.ServerGone:
                self._status = ValueStatus.Valid
                self._value = val
                self._last_value_dt = timestamp if timestamp is not None else datetime.now()
                self._update_counter += 1   # unbound in size in python 3
            else:
                self._value = None

    def _set_dead(self, status: ValueStatus) -> None:
        """Set the handle as "dead". Meaning it cannot be used anymore. the value is also marked invalid

        :param status: The new :class:`ValueStatus` to assign. Must not be ``ValueStatus.Valid``.
        """
        self._dead = True
        self._set_invalid(status)

    def _set_invalid(self, status: ValueStatus, timestamp: Optional[datetime] = None) -> None:
        """Clear the cached value and set a non-``Valid`` status.

        :param status: The new :class:`ValueStatus` to assign. Must not be ``ValueStatus.Valid``.
        :param timestamp: Time at which the value as been set invalid.
        """
        assert status != ValueStatus.Valid

        with self._lock:
            self._value = None
            self._status = status
            self._last_value_dt = timestamp if timestamp is not None else datetime.now()

    def _read(self) -> ValType:
        """Return the current cached value.

        :raises InvalidValueError: If the value is ``None`` or the status is not ``ValueStatus.Valid``.
        """
        val, val_status = self.get_value_and_status()   # Thread safe
        if val is None or val_status != ValueStatus.Valid:
            raise sdk_exceptions.InvalidValueError(f"Value of {self._shortname} is unusable. {val_status._get_error()}")

        return val

    def _write(self, val: Union[ValType, str], parse_enum: bool) -> WriteRequest:
        """Submit a value write to the server and wait for it to complete (unless a batch write is active).

        :param val: The value to write. A ``str`` is required when ``parse_enum`` is ``True``.
        :param parse_enum: When ``True``, ``val`` is interpreted as an enum name and converted to its integer value.
        :raises ValueError: If ``parse_enum`` is ``True`` but ``val`` is not a ``str``.
        :raises BadEnumError: If ``parse_enum`` is ``True`` and ``val`` is not a valid enumerator name.
        :returns: The :class:`WriteRequest<scrutiny.sdk.write_request.WriteRequest>` that was submitted.
        """
        if parse_enum:
            if not isinstance(val, str):
                raise ValueError(f"Value is not an enum string")
            val = self.parse_enum_val(val)  # check for enum is done inside this
        write_request = WriteRequest(self, val)
        self._client._process_write_request(write_request)
        if not self._client._is_batch_write_in_progress():
            write_request.wait_for_completion()
        return write_request

    def _assert_has_enum(self) -> None:
        """Assert that the watchable has an enum associated with it.

        :raises BadEnumError: If no enum is defined for this watchable.
        """
        if not self.has_enum():
            raise sdk_exceptions.BadEnumError(f"Watchable {self._shortname} has no enum defined")

    def _assert_configured(self) -> None:
        """Assert that the handle has been configured by the server after a successful watch subscription.

        :raises InvalidValueError: If the handle has not yet been configured.
        """
        if self._configuration is None:
            raise sdk_exceptions.InvalidValueError("This watchable handle is not ready to be used")

    def unwatch(self) -> None:
        """Stop watching this item by unsubscribing to the server. Marks the handle as "dead".
        See :attr:`is_dead<scrutiny.sdk.watchable_handle.WatchableHandle.is_dead>`

        :raises NameNotFoundError: If the required path is not presently being watched
        :raises OperationFailure: If the subscription cancellation failed in any way
        """
        self._client.unwatch(self._server_path)

    def wait_update(self, timeout: float, previous_counter: Optional[int] = None, sleep_interval: float = 0.02) -> None:
        """Wait for the value to be updated by the server

        :param timeout: Amount of time to wait for a value update
        :param previous_counter: Optional update counter to use for change detection. Can be set to ``update_counter+N`` to wait for N updates
        :param sleep_interval: Value passed to ``time.sleep`` while waiting

        :raises TypeError: Given parameter not of the expected type
        :raises ValueError: Given parameter has an invalid value
        :raises InvalidValueError: If the watchable becomes invalid while waiting
        :raises TimeoutException: If no value update happens within the given timeout
        """

        timeout = validation.assert_float_range(timeout, 'timeout', minval=0)
        validation.assert_int_range_if_not_none(previous_counter, 'previous_counter', minval=0)

        t1 = time.monotonic()
        entry_counter = self._update_counter if previous_counter is None else previous_counter
        while True:

            if time.monotonic() - t1 > timeout:
                raise sdk_exceptions.TimeoutException(f'Value of {self._shortname} did not update in {timeout}s')

            # No lock on purpose. Status can only go once to NeverSet or Valid
            if self._status != ValueStatus.NeverSet and self._status != ValueStatus.Valid:
                raise sdk_exceptions.InvalidValueError(self._status._get_error())

            if entry_counter != self._update_counter:
                break

            time.sleep(sleep_interval)

    def wait_value(self, value: Union[ValType, str], timeout: float, sleep_interval: float = 0.02) -> None:
        """
        Wait for the watchable to reach a given value. Raises an exception if it does not happen within a timeout value

        :param value: The value that this watchable must have to exit the wait state
        :param timeout: Maximum amount of time to wait for the given value
        :param sleep_interval: Value passed to ``time.sleep`` while waiting

        :raises TypeError: Given parameter not of the expected type
        :raises ValueError: Given parameter has an invalid value
        :raises BadEnumError: If ``value`` is a string and no enumerator value matches it
        :raises InvalidValueError: If the watchable becomes invalid while waiting
        :raises TimeoutException: If the watchable value never changes for the given value within the given timeout
        """

        timeout = validation.assert_float_range(timeout, 'timeout', minval=0)
        sleep_interval = validation.assert_float_range(sleep_interval, 'sleep_interval', minval=0)

        if isinstance(value, str):
            value = self.parse_enum_val(value)

        if value < 0 and not self.datatype.is_signed():
            raise ValueError(f"{self._shortname} is unsigned and will never have a negative value as requested")

        t1 = time.monotonic()
        while True:
            if time.monotonic() - t1 > timeout:
                raise sdk_exceptions.TimeoutException(f'Value of {self._shortname} did not set to {value} in {timeout}s')

            if self._status != ValueStatus.NeverSet:
                if self.datatype.is_float():
                    if float(value) == self.value_float:
                        break
                elif self.datatype.is_integer():
                    if int(value) == self.value_int:
                        break
                elif self.datatype == EmbeddedDataType.boolean:
                    if bool(value) == self.value_bool:
                        break

            time.sleep(sleep_interval)

    def has_enum(self) -> bool:
        """Tells if the watchable has an enum associated with it"""
        self._assert_configured()
        assert self._configuration is not None
        return self._configuration.has_enum()

    def get_enum(self) -> EmbeddedEnum:
        """ Returns the enum associated with this watchable

        :raises BadEnumError: If the watchable has no enum assigned
        """
        self._assert_configured()
        assert self._configuration is not None
        return self._configuration.get_enum()

    def parse_enum_val(self, val: str) -> int:
        """Converts an enum value name (string) to the underlying integer value

        :param val: The enumerator name to convert

        :raises BadEnumError: If the watchable has no enum assigned or the given value is not a valid enumerator
        :raises TypeError: Given parameter not of the expected type
        """
        self._assert_configured()
        assert self._configuration is not None
        return self._configuration.parse_enum_val(val)

    def get_value_and_status(self) -> Tuple[Optional[ValType], ValueStatus]:
        """Returns a tuple with the value and the value status.
        If the status is :attr:`Valid<scrutiny.sdk.ValueStatus.Valid>`, then the value is guaranteed to contain a value.
        If status != :attr:`Valid<scrutiny.sdk.ValueStatus.Valid>`, the value will be ``None``. This method does not raise an exception on invalid values.
        """
        with self._lock:
            val = self._value
            val_status = self._status

        return (val, val_status)

    def change_update_rate(self, update_rate: Optional[float]) -> Optional[float]:
        """Request the server to change the target update rate for this watchable (optionally set when
        calling :meth:`watch()<scrutiny.sdk.client.ScrutinyClient.watch>`).
        When there are multiple clients watching the same watchable, the server applies the fastest required rate.

        :param update_rate: The new polling rate. A value of ``None`` indicates that updates should happen as fast as possible.
            Must be ``None`` or  greater or equal to 1

        :return: The effective update rate at the moment of change. May be higher or change later if another client requires it.

        :raises TypeError: Given parameter not of the expected type
        :raises ValueError: Given parameter has an invalid value
        :raises OperationFailure: If the request fails to complete
        """
        return self._client._change_update_rate(self, update_rate)

    @property
    @deprecated("Replaced by server_path")
    def display_path(self) -> str:
        """[DEPRECATED] Replaced by :attr:`server_path`"""
        return self._server_path

    @property
    def server_path(self) -> str:
        """Returns the watchable full tree path given by the server"""
        return self._server_path

    @property
    def name(self) -> str:
        """Returns the watchable name, e.g. the basename in the server_path"""
        return self._shortname

    @property
    def type(self) -> WatchableType:
        """The watchable type. Variable, Alias or RuntimePublishedValue"""
        self._assert_configured()
        assert self._configuration is not None
        return self._configuration.watchable_type

    @property
    def datatype(self) -> EmbeddedDataType:
        """The data type of the device element pointed by this watchable. (sint16, float32, etc.)"""
        self._assert_configured()
        assert self._configuration is not None
        return self._configuration.datatype

    @property
    def server_id(self) -> str:
        """The unique ID assigned by the server for this watchable"""
        self._assert_configured()
        assert self._configuration is not None
        return self._configuration.server_id

    @property
    def value(self) -> ValType:
        """The value without cast.

        - When reading, returns a ``int``, ``float`` or ``bool``.
        - When writing, accepts ``int``, ``float``, ``bool`` or a ``str``.

        If a string is assigned, the value is sent "as is" to the server which will then try to parse it.
        The server will accepts "true", "false" or a mathematical expression supporting arithmetic operators (``+``, ``-``, ``*``, ``/``, ``^``),
        base prefix (``0x``, ``0b``), scientific notation (1.5e-2), constants (such as pi) and common math functions. including:  ``abs``, ``exp``, ``pow``, ``sqrt``, ``mod``,
        ``ceil``, ``floor``, ``log``, ``ln``, ``log10``,
        ``hypot``, ``degrees``, ``radians``,
        ``cos``, ``cosh``, ``acos``, ``sin``, ``sinh``, ``asin``, ``tan``, ``tanh``, ``atan``, ``atan2``

        :raises InvalidValueError: When reading, if the value has never been set or the handle is no longer valid.
        :raises OperationFailure: When writing, if the server fails to complete the write.
        """
        return self._read()

    @value.setter
    def value(self, val: Union[ValType, str]) -> None:
        self._write(val, parse_enum=False)

    @property
    def value_bool(self) -> bool:
        """The value cast as ``bool``"""
        return bool(self.value)

    @property
    def value_int(self) -> int:
        """The value cast as ``int``"""
        return int(self.value)

    @property
    def value_float(self) -> float:
        """The value cast as ``float``"""
        return float(self.value)

    @property
    def value_enum(self) -> str:
        """The value converted to its first enum name (alphabetical order). Returns a string. Can be written with a string.

        :raises BadEnumError: When reading, if the watchable has no enum defined. When writing, if ``val`` is not a valid enumerator name.
        :raises ValueError: When writing, if the assigned value is not a ``str``.
        :raises OperationFailure: When writing, if the server fails to complete the write.
        """
        val_int = self.value_int
        self._assert_configured()
        assert self._configuration is not None
        self._assert_has_enum()
        assert self._configuration.enum is not None
        for k in sorted(self._configuration.enum.vals.keys()):
            if self._configuration.enum.vals[k] == val_int:
                return k
        raise sdk_exceptions.InvalidValueError(
            f"Watchable {self._shortname} has value {val_int} which is not a valid enum value for enum {self._configuration.enum.name}")

    @value_enum.setter
    def value_enum(self, val: str) -> None:
        self._write(val, parse_enum=True)

    @property
    def last_update_timestamp(self) -> Optional[datetime]:
        """Time of the last value update. ``None`` if not updated at least once. Not reliable for change detection"""
        return self._last_value_dt

    @property
    def last_write_timestamp(self) -> Optional[datetime]:
        """Time of the last successful write operation. ``None`` if never written"""
        return self._last_write_dt

    @property
    def update_counter(self) -> int:
        """Number of value update gotten since the creation of the handle. Can be safely used for change detection"""
        return self._update_counter

    @property
    def is_dead(self) -> bool:
        """Flag indicating if this handle is dead, meaning it will never be updated in the future. Once a handle is dead, it can be disposed of.
        Unwatching a handle will mark it "dead". """
        return self._dead

    @property
    def status(self) -> ValueStatus:
        """Return the value status. Refer the :meth:`get_value_and_status()<scrutiny.sdk.watchable_handle.WatchableHandler.get_value_and_status>` to
        read the value and the status together atomicly."""
        return ValueStatus(self._status)

    @property
    def var_details(self) -> DetailedVarWatchableConfiguration:
        """Returns the variable-specific metadata.

        :raises BadTypeError: If the watchable :attr:`type` is not :attr:`Variable<scrutiny.sdk.WatchableType.Variable>`.
        """
        self._assert_configured()
        if not isinstance(self._configuration, DetailedVarWatchableConfiguration):
            raise sdk_exceptions.BadTypeError(f"Watchable {self._shortname} is not a variable. Type={self.type.name}")
        return self._configuration

    @property
    def alias_details(self) -> DetailedAliasWatchableConfiguration:
        """Returns the alias-specific metadata.

        :raises BadTypeError: If the watchable :attr:`type` is not :attr:`Alias<scrutiny.sdk.WatchableType.Alias>`.
        """
        self._assert_configured()
        if not isinstance(self._configuration, DetailedAliasWatchableConfiguration):
            raise sdk_exceptions.BadTypeError(f"Watchable {self._shortname} is not an alias. Type={self.type.name}")
        return self._configuration

    @property
    def rpv_details(self) -> DetailedRPVWatchableConfiguration:
        """Returns the RPV-specific metadata.

        :raises BadTypeError: If the watchable :attr:`type` is not :attr:`RuntimePublishedValue<scrutiny.sdk.WatchableType.RuntimePublishedValue>`.
        """
        self._assert_configured()
        if not isinstance(self._configuration, DetailedRPVWatchableConfiguration):
            raise sdk_exceptions.BadTypeError(f"Watchable {self._shortname} is not a Runtime Published Value. Type={self.type.name}")
        return self._configuration

    @property
    def requested_update_rate(self) -> Optional[float]:
        return self._requested_update_rate
