
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
