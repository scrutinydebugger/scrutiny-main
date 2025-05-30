#    qt.py
#        A single entry point that initialize all the Scrutiny QT tools that the GUI relies
#        on
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from PySide6.QtWidgets import QApplication
from scrutiny.gui.core.threads import QT_THREAD_NAME
from scrutiny.tools.thread_enforcer import register_thread
from scrutiny.gui.tools.invoker import CrossThreadInvoker
from typing import List

def make_qt_app(args:List[str]) -> QApplication:
    register_thread(QT_THREAD_NAME)
    app = QApplication(args)
    CrossThreadInvoker.init()

    return app
