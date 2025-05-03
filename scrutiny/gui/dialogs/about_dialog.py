#    about_dialog.py
#        About window, contains data about the software, including all versions numbers
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from PySide6.QtWidgets import QDialog, QFormLayout, QLabel, QWidget, QVBoxLayout, QGroupBox, QSizePolicy
from PySide6.QtCore import Qt
import os

import PySide6
import PySide6.QtCore

import sys
from typing import Optional

import scrutiny
from scrutiny.gui import assets

class AboutDialog(QDialog):

    def __init__(self, parent:Optional[QWidget] = None) -> None:
        super().__init__(parent) 

        self.setWindowTitle("About this software")
        self.setModal(True)
        self.setMaximumWidth(200)

        logo_pixmap = assets.load_pixmap('logo-text-2-lines')
        logo_label = QLabel("")
        logo_label.setPixmap(logo_pixmap.scaledToWidth(400, Qt.TransformationMode.SmoothTransformation))
        lines = [
            "Copyright (c) 2021 - Scrutiny Debugger",
            "Developped under MIT license",
            "",
            "More info at :",
            "scrutinydebugger.com",
            "github.com/scrutinydebugger"
        ]

        copyright_label = QLabel('\n'.join(lines))
        copyright_label.setWordWrap(True)
        copyright_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        copyright_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        version_gb = QGroupBox("Versions")
        version_gb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        gb_layout = QFormLayout(version_gb)
        gb_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout = QVBoxLayout()
        layout.addWidget(logo_label)
        layout.addWidget(copyright_label)
        layout.addWidget(version_gb)
        self.setLayout(layout)

        fields = [
            ("Scrutiny location", os.path.dirname(scrutiny.__file__)),
            ("Scrutiny version", scrutiny.__version__),
            ("Python version", "%d.%d.%d" % (sys.version_info.major, sys.version_info.minor, sys.version_info.micro)),
            ("QT version", getattr(PySide6.QtCore, "__version__", "N/A")),
            ("PySide6 version", PySide6.__version__)
        ]

        for i in range(len(fields)):
            property_label = QLabel(fields[i][0])
            value_label = QLabel(fields[i][1])
            value_label.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)
            gb_layout.addRow(property_label, value_label )

            for label in (property_label, value_label):
                label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
