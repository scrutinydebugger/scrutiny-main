#    sortedcontainers.pyi
#        A stub file for 3rdparty sorted containers module
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

from typing import Generic, TypeVar, Iterable, Iterator, Union, Optional, Callable

T = TypeVar('T')

class SortedSet(Generic[T]):
    def __init__(self, items:Optional[Iterable[T]]=None, key:Optional[Callable[[], T]]=None) -> None:...
    def add(self, item:T) -> None: ...
    def discard(self, item:T) -> None: ...
    def __contains__(self, item:T) -> bool: ...
    def __iter__(self) -> Iterator[T]:...
    def __len__(self) -> int: ...

    def __getitem__(self, index:int) -> T:...
    def __delitem__(self, index:Union[slice, int]) -> None: ...
    def __reversed__(self ) -> Iterator[T]: ...
    
    def remove(self, item:T) -> None: ...
    def clear(self) -> None: ...
    def pop(self) -> T: ...


#   * :func:`SortedSet.__contains__`
#   * :func:`SortedSet.__iter__`
#   * :func:`SortedSet.__len__`
#   * :func:`SortedSet.add`
#   * :func:`SortedSet.discard`
#
#   Sequence methods:
#
#   * :func:`SortedSet.__getitem__`
#   * :func:`SortedSet.__delitem__`
#   * :func:`SortedSet.__reversed__`
#
#   Methods for removing values:
#
#   * :func:`SortedSet.clear`
#   * :func:`SortedSet.pop`
#   * :func:`SortedSet.remove`
#
#   Set-operation methods:
#
#   * :func:`SortedSet.difference`
#   * :func:`SortedSet.difference_update`
#   * :func:`SortedSet.intersection`
#   * :func:`SortedSet.intersection_update`
#   * :func:`SortedSet.symmetric_difference`
#   * :func:`SortedSet.symmetric_difference_update`
#   * :func:`SortedSet.union`
#   * :func:`SortedSet.update`
#
#   Methods for miscellany:
#
#   * :func:`SortedSet.copy`
#   * :func:`SortedSet.count`
#   * :func:`SortedSet.__repr__`
#   * :func:`SortedSet._check`
#
#   Sorted list methods available:
#
#   * :func:`SortedList.bisect_left`
#   * :func:`SortedList.bisect_right`
#   * :func:`SortedList.index`
#   * :func:`SortedList.irange`
#   * :func:`SortedList.islice`
#   * :func:`SortedList._reset`
#
#   Additional sorted list methods available, if key-function used:
#
#   * :func:`SortedKeyList.bisect_key_left`
#   * :func:`SortedKeyList.bisect_key_right`
#   * :func:`SortedKeyList.irange_key`
