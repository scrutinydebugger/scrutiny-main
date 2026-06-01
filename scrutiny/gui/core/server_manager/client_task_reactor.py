#    client_task_reactor.py
#        A reactor that can pipeline blocking requests to the server using the synchronous
#        SDK. Uses a threadpool
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

import queue
import threading
import logging
import functools
from dataclasses import dataclass

from scrutiny.sdk.client import ScrutinyClient
from scrutiny.tools.typing import *
from scrutiny.gui.core.threads import QT_THREAD_NAME
from scrutiny.tools.thread_enforcer import enforce_thread
from scrutiny.gui.tools.invoker import invoke_in_qt_thread

ReactorTask: TypeAlias = Callable[[ScrutinyClient], Any]
UICallbackFunc: TypeAlias = Callable[[Any, Optional[Exception]], None]


@dataclass(slots=True)
class TaskQueueEntry:
    task_id: int
    task: ReactorTask
    ui_callback: UICallbackFunc


class StoppedException(Exception):
    pass


class ClientTaskReactor:
    _client: ScrutinyClient
    """Reference to a ScrutinyClient that the user can use in its task"""
    _threads: List[threading.Thread]
    """The thread pool"""
    _exit_event: threading.Event
    """Stop event for the active session (time span between start and stop)"""
    _started_event: threading.Event
    """Start event for the active session (time span between start and stop). No task is taken by the thread pool until this is fired"""
    _task_queue: "queue.Queue[Optional[TaskQueueEntry]]"
    """The task queue filled by the different component and read by the thread pool"""
    _next_task_id: int
    """A simple numerical ID to make sens eof the logs"""
    _logger: logging.Logger
    """The logger"""

    def __init__(self, client: ScrutinyClient, nb_thread: int, queue_max_size: int) -> None:
        self._client = client
        self._nb_thread = nb_thread
        self._exit_event = threading.Event()
        self._started_event = threading.Event()
        self._logger = logging.getLogger(self.__class__.__name__)
        self._task_queue = queue.Queue(queue_max_size)
        self._next_task_id = 0

    @enforce_thread(QT_THREAD_NAME)
    def put_task(self, task: ReactorTask, ui_callback: UICallbackFunc) -> None:
        """Enqueue a task for the thread pool to execute"""
        task_id = self._next_task_id
        self._next_task_id += 1
        if self._logger.isEnabledFor(logging.DEBUG):
            self._logger.debug(f"Enqueuing task #{task_id}")
        try:
            entry = TaskQueueEntry(task_id, task, ui_callback)
            self._task_queue.put_nowait(entry)
        except queue.Full as e:
            self._logger.error("Task queue is full")
            ui_callback(None, e)

    @enforce_thread(QT_THREAD_NAME)
    def start(self) -> None:
        """Start the threads"""
        self._logger.debug("Starting")
        if self._started_event.is_set():
            raise RuntimeError("Already started")
        # Create new events. In case the threads refuses to exit, we want them to check
        # their own expired event.
        self._exit_event = threading.Event()
        self._started_event = threading.Event()

        self._exit_event.clear()
        self._started_event.clear()

        self._threads = []
        for i in range(self._nb_thread):
            thread = threading.Thread(target=self._thread_task, daemon=True)
            self._threads.append(thread)

        for thread in self._threads:
            thread.start()
        self._started_event.set()
        self._logger.debug("Started")

    @enforce_thread(QT_THREAD_NAME)
    def stop(self) -> None:
        """Request all threads to exit. This method does not wait on thread to exit."""
        self._logger.debug("Stopping")
        # By setting this, we guarantee that each thread will not take on new tasks.
        # Only finish the one started.
        # We expect the task to depend on the socket that should be closed at the same time as stopping this reactor
        self._exit_event.set()
        self._started_event.clear()

        # Deplete the queue of any remaining task so we can inform the QT event loop of their non-completion.
        try:
            while not self._task_queue.empty():
                entry = self._task_queue.get_nowait()
                if entry is None:
                    continue
                if self._logger.isEnabledFor(logging.DEBUG):
                    self._logger.debug(f"Cancelling task #{entry.task_id}")
                entry.ui_callback(None, StoppedException("Reactor stopped"))
        except queue.Empty:
            pass

        # Wake up all sleeping threads
        # Works because
        for i in range(self._nb_thread):
            self._task_queue.put_nowait(None)

        # Let the threads die by themselves. No need to join()
        self._threads = []
        self._logger.debug("Stopped")

    def _thread_task(self) -> None:
        """The function run by every thread"""
        started_event = self._started_event
        exit_event = self._exit_event
        started_event.wait(10)

        if not started_event.is_set():
            self._logger.critical("Failed to start")
            return

        while not exit_event.is_set():
            entry = self._task_queue.get()
            if entry is None:
                continue

            result: Any = None
            error: Optional[Exception] = None
            try:
                if self._logger.isEnabledFor(logging.DEBUG):
                    self._logger.debug(f"Executing task #{entry.task_id}")
                result = entry.task(self._client)
                if self._logger.isEnabledFor(logging.DEBUG):
                    self._logger.debug(f"Task #{entry.task_id} executed")
            except Exception as e:
                self._logger.debug(f"Task #{entry.task_id} failed")
                error = e

            invoke_in_qt_thread(functools.partial(entry.ui_callback, result, error))  # Non blocking
