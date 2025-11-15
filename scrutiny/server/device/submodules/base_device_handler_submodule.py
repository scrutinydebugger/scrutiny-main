
import abc


class BaseDeviceHandlerSubmodule(abc.ABC):
    @abc.abstractmethod
    def would_send_data(self) -> bool:
        pass

    @abc.abstractmethod
    def start(self) -> None:
        pass

    @abc.abstractmethod
    def stop(self) -> None:
        pass

    @abc.abstractmethod
    def fully_stopped(self) -> bool:
        pass

    @abc.abstractmethod
    def process(self) -> None:
        pass
