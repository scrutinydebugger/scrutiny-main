#    base_device_handler_submodule.py
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

import abc


class BaseDeviceHandlerSubmodule(abc.ABC):
    @abc.abstractmethod
    def would_send_data(self) -> bool:
        """Returns ``True`` if a call to ``process()`` would dispatch a request to the device"""
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
