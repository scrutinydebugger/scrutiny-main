#    text.py
#        Text manipulation tools
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtCore import QRectF


def set_font_size_to_fit_rect(font: QFont, text: str, rect: QRectF) -> None:
    font.setPixelSize(max(1, int(rect.size().height())))
    text_width = QFontMetrics(font).averageCharWidth() * len(text)
    if text_width > rect.size().width():
        font.setPixelSize(max(1, int(rect.size().height() * rect.size().width() / text_width)))

    # apply_font_size uses average char size. It might not be exact.
    # Decrease the size until we fit on one line
    while font.pixelSize() > 1:
        previous_size = font.pixelSize()
        required_width = QFontMetrics(font).size(0, text)
        if required_width.width() <= rect.width():
            break

        font.setPixelSize(previous_size - 1)
        if not font.pixelSize() < previous_size:
            break
