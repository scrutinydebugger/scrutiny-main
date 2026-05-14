#    serialization.py
#        HMI widget serialization tools
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

from PySide6.QtWidgets import QComboBox
from scrutiny.tools.typing import *
from scrutiny import tools


def deserialize_combobox_val(val: Any, dtype: Type[Any], cmbbox: QComboBox) -> bool:
    with tools.SuppressException(Exception):
        index = cmbbox.findData(dtype(val))
        if index != -1:
            cmbbox.setCurrentIndex(index)
            return True

    return False
