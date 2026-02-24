#    pending_request.py
#        A base class for Future objects given to the suer
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2024 Scrutiny Debugger

__all__ = ['PendingRequest']

from datetime import datetime
import threading
import time

from scrutiny.tools import validation
from scrutiny import sdk

from scrutiny.tools.typing import *
if TYPE_CHECKING:
    from scrutiny.sdk.client import ScrutinyClient


class PendingRequest:
    """Base class for future-like request handles returned to the user.

    Tracks the lifecycle of an asynchronous server request: whether it is still in flight,
    whether it succeeded or failed, and the reason for any failure.
    Subclasses add domain-specific result data on top of this common infrastructure.
    """

    _client: "ScrutinyClient"
    """The :class:`ScrutinyClient<scrutiny.sdk.client.ScrutinyClient>` that owns this request"""

    _completed: bool
    """``True`` once the request has reached a terminal state (success or failure)"""
    _success: bool
    """``True`` if the request completed successfully"""
    _completion_datetime: Optional[datetime]
    """Wall-clock time at which the request transitioned to its terminal state, or ``None`` if still in flight"""
    _completed_event: threading.Event
    """Threading event that is set when the request reaches its terminal state"""
    _failure_reason: str
    """Human-readable description of why the request failed. Empty string when incomplete or succeeded"""
    _monotonic_creation_timestamp: float
    """Monotonic timestamp (seconds) recorded when the request object was created"""
    _monotonic_expiration_timestamp: float
    """Monotonic timestamp (seconds) reset each time new data arrives, used to detect stale requests"""
    _completion_lock: threading.Lock
    """Lock that ensures only the first completion call wins when concurrent completions race"""

    def __init__(self, client: "ScrutinyClient") -> None:
        self._client = client
        self._completed = False
        self._success = False
        self._completion_datetime = None
        self._completed_event = threading.Event()
        self._failure_reason = ""
        self._monotonic_creation_timestamp = time.monotonic()
        self._monotonic_expiration_timestamp = self._monotonic_creation_timestamp
        self._completion_lock = threading.Lock()

    def _is_expired(self, timeout: float) -> bool:
        """Return ``True`` if no new data has arrived for longer than ``timeout`` seconds.

        :param timeout: Inactivity threshold in seconds.
        """
        return time.monotonic() - self._monotonic_expiration_timestamp > timeout

    def _update_expiration_timer(self) -> None:
        """Reset the expiration timestamp to the current monotonic time, signalling that fresh data has arrived"""
        self._monotonic_expiration_timestamp = time.monotonic()

    def _mark_complete(self, success: bool, failure_reason: str = "", server_time_us: Optional[float] = None) -> None:
        """Transition the request to its terminal state.

        Thread-safe: only the first call takes effect; subsequent calls are ignored.
        Expected to be called by the worker thread, but any thread may call it.

        :param success: ``True`` if the request succeeded, ``False`` otherwise.
        :param failure_reason: Human-readable description of the failure. Ignored when ``success`` is ``True``.
        :param server_time_us: Server-side completion time in microseconds. When ``None``, the local wall clock is used.
        """
        # We use a lock in case there is 2 simultaneous failures, we keep the first one.
        # Some client method can spawn an ephemerous thread to do client request, like upload_sfd
        with self._completion_lock:
            if not self._completed:
                self._success = success
                self._failure_reason = failure_reason
                if server_time_us is None:
                    self._completion_datetime = datetime.now()
                else:
                    self._completion_datetime = self._client._server_timebase.micro_to_dt(server_time_us)
                self._completed = True
                self._completed_event.set()

    def _timeout_exception_msg(self, timeout: float) -> str:
        """Build the message for a :class:`TimeoutException<scrutiny.sdk.exceptions.TimeoutException>` when the request exceeds its deadline.

        :param timeout: The timeout value in seconds that was exceeded.
        """
        return f"Request did not complete in {timeout} seconds"

    def _failure_exception_msg(self) -> str:
        """Build the message for an :class:`OperationFailure<scrutiny.sdk.exceptions.OperationFailure>` exception when the request has failed"""
        return f"Request failed to complete. {self._failure_reason}"

    def wait_for_completion(self, timeout: Optional[float] = None) -> None:
        """Wait for the request to complete

        :params timeout: Maximum wait time in seconds. Waits forever if ``None``

        :raises TimeoutException: If the request does not complete in less than the specified timeout value
        :raises OperationFailure: If an error happened that prevented the request to successfully complete
        """
        timeout = validation.assert_float_range_if_not_none(timeout, 'timeout', minval=0)
        self._completed_event.wait(timeout=timeout)
        if not self._completed:
            assert timeout is not None
            raise sdk.exceptions.TimeoutException(self._timeout_exception_msg(timeout))
        assert self._completed_event.is_set()

        if not self._success:
            raise sdk.exceptions.OperationFailure(self._failure_exception_msg())

    @property
    def completed(self) -> bool:
        """Indicates whether the request has completed or not"""
        return self._completed_event.is_set()

    @property
    def is_success(self) -> bool:
        """Indicates whether the request has successfully completed or not"""
        return self._success

    @property
    def completion_datetime(self) -> Optional[datetime]:
        """The time at which the request has been completed. ``None`` if not completed yet"""
        return self._completion_datetime

    @property
    def failure_reason(self) -> str:
        """When the request failed, this property contains the reason for the failure. Empty string if not completed or succeeded"""
        return self._failure_reason
