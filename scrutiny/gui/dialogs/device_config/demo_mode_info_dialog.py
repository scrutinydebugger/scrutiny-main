#    demo_mode_info_dialog.py
#        A dialog explaining what the demo device is and what it does
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

__all__ = ['DemoModeInfoDialog']

from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout
from PySide6.QtCore import Qt

from scrutiny.tools.typing import *
from scrutiny import tools

_TEXT = """
# Demo device
<br/>


The demo device is an emulated device run by the server. 
It is implemented in Python, runs in a separate thread, and communicates with the server through data queues.

<br/>

It supports all features available in ``scrutiny-embedded`` (data read/write, datalogging, RPVs, etc.) and has 1 KiB of memory, ranging from **0x1000** to **0x1FFF**.
Its main purpose is to showcase how Scrutiny works without having to go through the process of instrumenting a physical device.

<br/>

### Variables

  - ``/static/main.cpp/counter`` (float32) : A counter adding 0.1 at each thread iteration when enabled
  - ``/static/main.cpp/counter_enable`` (boolean) : Enable counting of ``/static/main.cpp/counter``
  - ``/global/device/uptime`` (uint32) : A counter counting time in seconds since the emulated device is started
  - ``/global/sinewave_generator/output`` (float32) : A sine wave computed by the device
  - ``/global/sinewave_generator/frequency`` (float32) : The frequency of the sine wave at ``/global/sinewave_generator/output``. Can be edited

<br/>

### Runtime Published Values

  - ``0x1000`` (float32) : A random value ranging from 0 to 1. 
  - ``0x2000`` (sint32) : A square wave oscillating between -1 and 1 at a rate of 1Hz

<br/>

### Aliases

  - ``/Up Time`` : Points to  ``/global/device/uptime``
  - ``/Sine Wave`` : Points to  ``/global/sinewave_generator/output``
  - ``/Counter/Enable`` : Points to  ``/static/main.cpp/counter_enable``
  - ``/Counter/Value`` : Points to  ``/static/main.cpp/counter``
  - ``/Alias To RPV2000`` : Points to  ``/rpv/x2000``
  - ``/RPV1000 with gain 1000`` : Points to  ``/rpv/x1000`` and apply a gain of 1000. (Random value ranging from 0 to 1000)

"""


class DemoModeInfoDialog(QDialog):

    content_label: QLabel

    @tools.copy_type(QDialog.__init__)
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        self.setWindowTitle("Demo device")
        self.content_label = QLabel(self)
        self.content_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByKeyboard | Qt.TextInteractionFlag.TextSelectableByMouse)
        self.content_label.setTextFormat(Qt.TextFormat.MarkdownText)
        self.content_label.setText(_TEXT)
        self.content_label.setWordWrap(True)

        self.setMinimumSize(800, 600)

        font = self.content_label.font()
        font.setPixelSize(max(font.pixelSize(), 16))
        self.content_label.setFont(font)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.content_label)

        self.setModal(True)
