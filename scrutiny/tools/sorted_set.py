#    sorted_set.py
#        A custom implementation of a sorted set
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

__all__ = ['SortedSet']

from scrutiny.tools.typing import *
from bisect import bisect_left
from _typeshed import SupportsRichComparisonT
import typing


class SortedSet(Generic[SupportsRichComparisonT]):
    _storage: List[SupportsRichComparisonT]

    def __init__(self, data: Optional[Iterable[SupportsRichComparisonT]] = None) -> None:
        self._storage = list()
        if data is not None:
            for item in data:
                self.add(item)

    def add(self, item: SupportsRichComparisonT) -> None:
        index = bisect_left(self._storage, item)
        if index < len(self._storage):
            if hash(self._storage[index]) == hash(item):
                return
        self._storage.insert(index, item)

    def remove(self, item: SupportsRichComparisonT) -> None:
        index = bisect_left(self._storage, item)
        if index < len(self._storage):
            if hash(self._storage[index]) == hash(item):
                del self._storage[index]
                return
        raise ValueError(f"Element {item} not found")

    def __iter__(self) -> typing.Iterator[SupportsRichComparisonT]:
        return iter(self._storage)

    def __len__(self) -> int:
        return len(self._storage)

    def __getitem__(self, key: int) -> SupportsRichComparisonT:
        return self._storage[key]

    def __setitem__(self, key: int, val: SupportsRichComparisonT) -> None:
        self._storage[key] = val
