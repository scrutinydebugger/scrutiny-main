__all__ = ['ParseErrors']

from scrutiny.tools.typing import *


class ParseErrors:
    """A class that represent a parsing error.
    We keep track of all the error we find so that we can fail unit tests without stopping the parsing"""
    __slots__ = ('_exceptions', )

    _exceptions: List[Exception]
    """List of exception registered"""

    def __init__(self) -> None:
        self._exceptions = []

    def register_error(self, e: Exception) -> None:
        """Add a catched exception"""
        self._exceptions.append(e)

    def total_count(self, exclude: Optional[List[Type[Exception]]] = None) -> int:
        """Return the number of exception that are not excluded by ``exclude``"""
        if exclude is None:
            return len(self._exceptions)

        count = 0
        for e in self.iter_exc(exclude):
            count += 1
        return count

    def iter_exc(self, exclude: Optional[List[Type[Exception]]] = None) -> Generator[Exception, None, None]:
        """Iterate every exception registered with an exclude list"""
        exclude2 = tuple(exclude) if exclude is not None else tuple()
        for e in self._exceptions:
            if not isinstance(e, exclude2):
                yield e

    def get_first_exc(self, exclude: Optional[List[Type[Exception]]] = None) -> Optional[Exception]:
        """Return the first exception"""
        if exclude is None:
            exclude = []
        gen = self.iter_exc(exclude)
        return next(gen, None)
