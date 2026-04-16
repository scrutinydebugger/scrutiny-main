#    hmi_theme.py
#        An abstraction layer to get the theming proeprties of the dashboard. Reduce possibilities,
#        ensure higher changes of uniformization
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

from scrutiny.gui.themes import scrutiny_get_theme, ScrutinyThemeProperties, scrutiny_get_theme_prop

from PySide6.QtGui import QColor
from scrutiny.tools.typing import *


class HMITheme:

    class Color:

        @staticmethod
        def workzone_background() -> QColor:
            return scrutiny_get_theme().palette().base().color()

        @staticmethod
        def green_good() -> QColor:
            return cast(QColor, scrutiny_get_theme_prop(ScrutinyThemeProperties.HMI_GREEN_GOOD))

        @staticmethod
        def yellow_warning() -> QColor:
            return cast(QColor, scrutiny_get_theme_prop(ScrutinyThemeProperties.HMI_YELLOW_WARNING))

        @staticmethod
        def red_danger() -> QColor:
            return cast(QColor, scrutiny_get_theme_prop(ScrutinyThemeProperties.HMI_RED_DANGER))

        @staticmethod
        def widget_background() -> QColor:
            return scrutiny_get_theme().palette().window().color()

        @staticmethod
        def text() -> QColor:
            return scrutiny_get_theme().palette().text().color()

        @staticmethod
        def select_frame_border() -> QColor:
            return scrutiny_get_theme().palette().text().color()

        @staticmethod
        def highlight_overlay() -> QColor:
            return scrutiny_get_theme().palette().highlight().color()

        @staticmethod
        def frame_border() -> QColor:
            return scrutiny_get_theme().palette().light().color()

        @staticmethod
        def dark() -> QColor:
            return scrutiny_get_theme().palette().dark().color()
