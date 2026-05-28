#    qt.py
#        A single entry point that initialize all the Scrutiny QT tools that the GUI relies
#        on
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2025 Scrutiny Debugger

__all__ = ['make_qt_app', 'cleanup_qt_app']

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QLocale
from scrutiny.gui.core.threads import QT_THREAD_NAME
from scrutiny.tools.thread_enforcer import register_thread
from scrutiny.gui.tools.invoker import CrossThreadInvoker
from scrutiny.tools.typing import *


def make_qt_app(args: List[str]) -> QApplication:
    register_thread(QT_THREAD_NAME)
    loc = QLocale.c()   # Forces C-style environment. Decimal points are "."
    # Prevent showing/interpreting commas as group separator
    loc.setNumberOptions(QLocale.NumberOption.RejectGroupSeparator | QLocale.NumberOption.OmitGroupSeparator)
    QLocale.setDefault(loc)

    app = QApplication(args)
    app.aboutToQuit.connect(cleanup_qt_app)
    CrossThreadInvoker.init()

    return app


def cleanup_qt_app() -> None:
    # Saw a segfault that looked like a race condition in the MimeData
    #  destructor. This can fix.
    QApplication.clipboard().clear()
