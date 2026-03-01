#    validators.py
#        Some QT validators used across the project
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2024 Scrutiny Debugger

__all__ = ['IpPortValidator', 'NotEmptyValidator', 'QStandardNotationDoubleValidator']

from PySide6.QtGui import QValidator, QDoubleValidator
from PySide6.QtWidgets import QWidget

from scrutiny.tools.typing import *
from scrutiny import tools


class QStandardNotationDoubleValidator(QDoubleValidator):

    @tools.copy_type(QDoubleValidator.__init__)
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.setNotation(QDoubleValidator.Notation.StandardNotation)


class IpPortValidator(QValidator):
    def validate(self, val: Optional[str], pos: int) -> Tuple[QValidator.State, str, int]:
        assert val is not None

        if len(val) == 0:
            return (QValidator.State.Intermediate, val, pos)

        try:
            port = int(val)
        except Exception:
            return (QValidator.State.Invalid, val, pos)

        if port <= 0 or port > 0xFFFF:
            return (QValidator.State.Invalid, val, pos)

        return (QValidator.State.Acceptable, val, pos)


class NotEmptyValidator(QValidator):
    _empty_state: QValidator.State

    def __init__(self, empty_state: QValidator.State = QValidator.State.Intermediate, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._empty_state = empty_state

    def validate(self, val: Optional[str], pos: int) -> Tuple[QValidator.State, str, int]:
        assert val is not None
        if isinstance(val, str):
            if len(val) == 0:
                return (self._empty_state, val, pos)

        return (QValidator.State.Acceptable, val, pos)
