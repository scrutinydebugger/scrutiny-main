#    hmi_status_bar.py
#        The status bar showned at the bottom of the GMI work zone when in edit mode
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

from PySide6.QtWidgets import QStatusBar, QLabel, QToolButton
from PySide6.QtCore import Signal, QObject, QSize

from scrutiny import tools
from scrutiny.tools.typing import *


class HMIStatusBar(QStatusBar):

    class _Signals(QObject):
        exit_edit_mode = Signal()

    _widget_resize_label: QLabel
    _selected_count_label: QLabel
    _mode_button: QToolButton
    _signals: _Signals

    @tools.copy_type(QStatusBar.__init__)
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        self._signals = self._Signals()

        self.setContentsMargins(10, 0, 10, 0)
        self._widget_resize_label = QLabel()
        self._selected_count_label = QLabel()

        for label in [self._widget_resize_label, self._selected_count_label]:
            margin = label.contentsMargins()
            margin.setRight(10)
            label.setContentsMargins(margin)

        self._mode_button = QToolButton()
        self._mode_button.setText("Exit edit mode")
        self._mode_button.clicked.connect(self._signals.exit_edit_mode)

        self.addWidget(self._widget_resize_label)
        self.addWidget(self._selected_count_label)
        self.addPermanentWidget(self._mode_button)

        self.set_resize_size(None)
        self.set_selected_count(None)

    def set_resize_size(self, size: Optional[QSize]) -> None:
        if size is not None:
            self._widget_resize_label.setText(f"W:{size.width()} H:{size.height()}")
            self._widget_resize_label.setVisible(True)
        else:
            self._widget_resize_label.setVisible(False)

    def set_selected_count(self, v: Optional[int]) -> None:
        if v is not None:
            self._selected_count_label.setText(f"Selected: {v} items")
            self._selected_count_label.setVisible(True)
        else:
            self._selected_count_label.setVisible(False)

    @property
    def signals(self) -> _Signals:
        return self._signals
