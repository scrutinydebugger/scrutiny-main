if __name__ != '__main__':
    raise RuntimeError("This script is expected to run from the command line")

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from manual_test_base import make_manual_test_app
app = make_manual_test_app()

import logging
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QDragEnterEvent, QDropEvent

from scrutiny.gui.components.locals.hmi.hmi_library import HMILibrary
from scrutiny.gui.core.scrutiny_drag_data import ScrutinyDragData


class _DropZone(QLabel):
    def __init__(self) -> None:
        super().__init__("Drop zone")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedHeight(64)
        self.setAcceptDrops(True)
        self.setStyleSheet("border: 2px dashed gray;")

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        data = ScrutinyDragData.from_mime(event.mimeData())
        if data is None:
            return
        if data.type != ScrutinyDragData.DataType.HMIWidgetClass:
            return

        event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        mime = event.mimeData()
        data = ScrutinyDragData.from_mime(mime)
        if data is None:
            logging.info("Drop received: No valid data")
            return

        if data.type != ScrutinyDragData.DataType.HMIWidgetClass:
            logging.info("Drop received: Wrong data type")
            return

        widget_class = HMILibrary.load_from_name(data.data_copy['class'])
        if widget_class is None:
            logging.info("Drop received: Invalid class name")
            return None

        logging.info(f"Drop received: Class = {widget_class.__name__}")
        event.acceptProposedAction()


window = QMainWindow()
window.setWindowTitle("HMILibrary - Manual Test")
window.setGeometry(200, 200, 400, 600)

central = QWidget()
main_layout = QVBoxLayout(central)
main_layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetNoConstraint)
library = HMILibrary()

main_layout.addWidget(_DropZone())
main_layout.addWidget(library)

window.setCentralWidget(central)
window.show()


sys.exit(app.exec())
