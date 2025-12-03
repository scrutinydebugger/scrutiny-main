__all__ = ['ScrutinyQueue']


from scrutiny.tools.typing import *
import queue

T = TypeVar("T")


class ScrutinyQueue(Generic[T], queue.Queue[T]):
    def deplete(self) -> None:
        while True:
            try:
                self.get_nowait()
            except queue.Empty:
                break

    def get_or_none(self) -> Optional[T]:
        try:
            return self.get_nowait()
        except queue.Empty:
            return None

    def put_circular(self, obj: T) -> None:
        while True:
            try:
                self.put_nowait(obj)
                break
            except queue.Full:
                self.get_nowait()
