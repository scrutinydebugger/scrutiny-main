__all__ = ['SortedSet']

from scrutiny.tools.typing import *
from bisect import bisect_left
import typing

T = TypeVar("T")

class SortedSet(Generic[T]):
    _storage : List[T]

    def __init__(self, data:Optional[Iterable[T]] = None) -> None:
        self._storage = list()
        if data is not None:
            for item in data:
                self.add(item)

    def add(self, item:T) -> None:
        index = bisect_left(self._storage, item)    #type: ignore
        if index < len(self._storage):
            if hash(self._storage[index]) == hash(item):
                return
        self._storage.insert(index, item)

    def remove(self, item:T) -> None:
        index = bisect_left(self._storage, item)    #type: ignore
        if index < len(self._storage):
            if hash(self._storage[index]) == hash(item):
                del self._storage[index]
                return

        raise ValueError(f"Element {item} not found")

    def __iter__(self) -> typing.Iterator[T]:
        return iter(self._storage)

    def __len__(self) -> int:
        return len(self._storage)

    def __getitem__(self, key:int) -> T:
        return self._storage[key]
