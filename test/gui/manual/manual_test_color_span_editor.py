if __name__ != '__main__':
    raise RuntimeError("This script is expected to run from the command line")

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from manual_test_base import make_manual_test_app
app = make_manual_test_app()

import logging
from PySide6.QtWidgets import QMainWindow, QPushButton, QVBoxLayout, QWidget, QGroupBox
from scrutiny.gui.components.locals.hmi.common.color_span_editor import ColorSpanEditor, ColorSpan, SpanColor


window = QMainWindow()
window.setWindowTitle("ColorSpanEditor - Manual Test")
window.setGeometry(200, 200, 400, 350)

central = QWidget()
layout = QVBoxLayout(central)

gb = QGroupBox("Color Spans")
gb_layout = QVBoxLayout(gb)
editor = ColorSpanEditor()
gb_layout.addWidget(editor)
layout.addWidget(gb)


def print_spans() -> None:
    spans = editor.get_span_objects()
    logging.info(f"get_span_objects() returned {len(spans)} span(s):")
    for i, span in enumerate(spans):
        logging.info(f"  [{i}] min={span.min_val}, max={span.max_val}, color={span.color}")


def load_preset() -> None:
    editor.set_from_spans_object([
        ColorSpan(min_val=0, max_val=30, color=SpanColor.DANGER),
        ColorSpan(min_val=30, max_val=70, color=SpanColor.WARNING),
        ColorSpan(min_val=70, max_val=100, color=SpanColor.GOOD),
    ])
    logging.info("Preset loaded")


btn_print = QPushButton("Print spans to log")
btn_print.clicked.connect(print_spans)

btn_preset = QPushButton("Load preset (Red/Yellow/Green)")
btn_preset.clicked.connect(load_preset)

btn_clear = QPushButton("Clear all")
btn_clear.clicked.connect(editor.clear)

layout.addWidget(btn_preset)
layout.addWidget(btn_print)
layout.addWidget(btn_clear)

window.setCentralWidget(central)
window.show()

sys.exit(app.exec())
