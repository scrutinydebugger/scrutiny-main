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
        """Create a config from the widgets content"""
        raise NotImplementedError("abstract method")

    def load_config(self, config: Optional[sdk.BaseLinkConfig]) -> None:    
        """Reads a config and fill the widgets from it"""
        raise NotImplementedError("abstract method")

    def visual_validation(self) -> None:    
        """Validate the widgets and highlight those with invalid content"""
        pass

    @classmethod
    def make_config_valid(cls, config: Optional[sdk.BaseLinkConfig]) -> sdk.BaseLinkConfig:
        """Return a valid version of the given config."""
        assert config is not None
        return config

    @classmethod
    def save_to_persistent_data(cls, config:sdk.BaseLinkConfig) -> None:
        """Save a configuration to persistent storage"""
        raise NotImplementedError("abstract method")
    
    @classmethod
    def initialize_config(cls) -> sdk.BaseLinkConfig:
        """Create the initial configuration with default settings or settings based on persistent storage"""
        raise NotImplementedError("abstract method")
