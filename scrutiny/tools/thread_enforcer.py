#    thread_enforcer.py
#        A runtime checker that enforces the thread ID of function caller. Prevents race conditions
#        from misusage of internal APIs
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2024 Scrutiny Debugger

__all__ = [
    'ThreadValidationError',
    'ThreadEnforcer',
    'enforce_thread',
    'thread_func',
    'register_thread',
    'unregister_thread'
]

import threading
from scrutiny.tools.typing import *


class ThreadValidationError(Exception):
    """Exception raised when thread validation fails."""
    pass


class ThreadEnforcer:
    """Runtime checker that enforces the thread ID of function callers.

    Prevents race conditions from misusage of internal APIs.
    """
    _thread_to_name_map: Dict[int, Set[str]] = {}
    """Map of thread IDs to sets of thread names."""

    @classmethod
    def register_thread(cls, name: str, thread_id: Optional[int] = None, unique: bool = False) -> None:
        """Register a thread with a name for later enforcement.

        :param name: The name to register the thread under.
        :param thread_id: The thread ID (defaults to current thread).
        :param unique: If ``True``, ensure no other thread is registered under this name.
        :raises ThreadValidationError: If ``unique`` is ``True`` and name is already in use.
        """
        if unique:
            for nameset in cls._thread_to_name_map.values():
                if name in nameset:
                    raise ThreadValidationError(f"More than 1 instance of thread {name}")

        if thread_id is None:
            thread_id = threading.get_ident()

        if thread_id not in cls._thread_to_name_map:
            cls._thread_to_name_map[thread_id] = set()

        cls._thread_to_name_map[thread_id].add(name)

    @classmethod
    def unregister_thread(cls, name: str, thread_id: Optional[int] = None) -> None:
        """Unregister a thread name.

        :param name: The name to unregister.
        :param thread_id: The thread ID (defaults to current thread).
        :raises ThreadValidationError: If the thread or name is not registered.
        """
        if thread_id is None:
            thread_id = threading.get_ident()

        if thread_id not in cls._thread_to_name_map:
            raise ThreadValidationError(f"Thread ID {thread_id} is not registered")

        if name not in cls._thread_to_name_map[thread_id]:
            raise ThreadValidationError(f"Thread ID {thread_id} is not registered under the name {name}")

        cls._thread_to_name_map[thread_id].remove(name)

    @classmethod
    def assert_thread(cls, name: str) -> None:
        """Assert that the current thread is registered under the given name.

        :param name: The expected thread name.
        :raises ThreadValidationError: If the current thread is not registered under the name.
        """
        thread_id = threading.get_ident()
        if thread_id not in cls._thread_to_name_map:
            raise ThreadValidationError(f"Running from unknown thread. Expected {name}")

        thread_name_set = cls._thread_to_name_map[thread_id]
        if name not in thread_name_set:
            raise ThreadValidationError(
                f"Not running from thread {name}. Actual thread ID ({thread_id}) is associated with these names : {thread_name_set})")


T = TypeVar('T')
P = ParamSpec('P')


def enforce_thread(name: str) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator that ensures the function is called in the given thread.

    :param name: The expected thread name.
    :returns: A decorator function.
    :raises ThreadValidationError: If called from wrong thread.
    """
    def decorator(function: Callable[P, T]) -> Callable[P, T]:
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            ThreadEnforcer.assert_thread(name)
            result = function(*args, **kwargs)
            return result
        return wrapper
    return decorator


def thread_func(name: str) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator that registers a function as a thread.

    Used to enforce other function calls to run in the same thread.

    :param name: The name to register the thread under.
    :returns: A decorator function.
    """
    def decorator(function: Callable[P, T]) -> Callable[P, T]:
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            ThreadEnforcer.register_thread(name, unique=True)
            try:
                result = function(*args, **kwargs)
            finally:
                ThreadEnforcer.unregister_thread(name)
            return result
        return wrapper
    return decorator


def register_thread(name: str, thread_id: Optional[int] = None, unique: bool = False) -> None:
    """Register the given thread to a name for later enforcing.

    :param name: The name to register the thread under.
    :param thread_id: The thread ID (defaults to current thread).
    :param unique: If ``True``, ensure no other thread is registered under this name.
    :raises ThreadValidationError: If ``unique`` is ``True`` and name is already in use.
    """
    ThreadEnforcer.register_thread(name, thread_id, unique)


def unregister_thread(name: str, thread_id: Optional[int] = None) -> None:
    """Unregister the given thread.

    :param name: The name to unregister.
    :param thread_id: The thread ID (defaults to current thread).
    :raises ThreadValidationError: If the thread or name is not registered.
    """
    ThreadEnforcer.unregister_thread(name, thread_id)
