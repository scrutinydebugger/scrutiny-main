#    base_config_pane.py
#        A base class for all configuration widget used in the device_config_dialog
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

import abc
from PySide6.QtWidgets import QWidget

from scrutiny import sdk
from scrutiny.tools.typing import *


class BaseConfigPane(QWidget):
    def get_config(self) -> Optional[sdk.BaseLinkConfig]:
        raise NotImplementedError("abstract method")

    def load_config(self, config: Optional[sdk.BaseLinkConfig]) -> None:
        raise NotImplementedError("abstract method")

    def visual_validation(self) -> None:
        pass

    @classmethod
    def make_config_valid(cls, config: Optional[sdk.BaseLinkConfig]) -> sdk.BaseLinkConfig:
        assert config is not None
        return config

    @classmethod
    def save_to_persistent_data(self, config:sdk.BaseLinkConfig) -> None:
        raise NotImplementedError("abstract method")
    
    @classmethod
    def initialize_config(cls) -> sdk.BaseLinkConfig:
        raise NotImplementedError("abstract method")
