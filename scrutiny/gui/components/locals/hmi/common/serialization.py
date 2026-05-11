
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
