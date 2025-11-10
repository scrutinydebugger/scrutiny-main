#    manual_test_stylesheets.py
#        A window to visualize different custom stylesheets features
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

if __name__ != '__main__':
    raise RuntimeError("This script is expected to run from the command line")

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from manual_test_base import make_manual_test_app
app = make_manual_test_app()

import logging
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QGroupBox, QLineEdit, QSpinBox, QFormLayout
from scrutiny.gui.widgets.feedback_label import FeedbackLabel
from scrutiny.gui.themes import scrutiny_get_theme

window = QMainWindow()
central_widget = QWidget()

theme = scrutiny_get_theme()

window.setCentralWidget(central_widget)
layout = QVBoxLayout(central_widget)
feedback_label_gb = QGroupBox("Feedback Labels")
feedback_label_layout = QVBoxLayout(feedback_label_gb)

feedback_label_success = FeedbackLabel(window)
feedback_label_error = FeedbackLabel(window)
feedback_label_warning = FeedbackLabel(window)
feedback_label_info = FeedbackLabel(window)
feedback_label_normal = FeedbackLabel(window)
feedback_label_success.set_success('success')
feedback_label_error.set_error('error')
feedback_label_warning.set_warning('warning')
feedback_label_info.set_info('info')
feedback_label_normal.set_normal('normal')

feedback_label_layout.addWidget(feedback_label_success)
feedback_label_layout.addWidget(feedback_label_error)
feedback_label_layout.addWidget(feedback_label_warning)
feedback_label_layout.addWidget(feedback_label_info)
feedback_label_layout.addWidget(feedback_label_normal)


line_edit_gb = QGroupBox("Line Edit")
line_edit_layout = QVBoxLayout(line_edit_gb)
line_edit_normal = QLineEdit(window)
line_edit_error = QLineEdit(window)
line_edit_success = QLineEdit(window)

theme.set_default_state(line_edit_normal)
theme.set_error_state(line_edit_error)
theme.set_success_state(line_edit_success)

line_edit_normal.setText("normal")
line_edit_error.setText("error")
line_edit_success.setText("success")

line_edit_layout.addWidget(line_edit_normal)
line_edit_layout.addWidget(line_edit_error)
line_edit_layout.addWidget(line_edit_success)


spinbox_gb = QGroupBox("Spin boxes")
spinbox_layout = QFormLayout(spinbox_gb)
spinbox_normal = QSpinBox(window)
spinbox_error = QSpinBox(window)
spinbox_success = QSpinBox(window)

spinbox_normal.setValue(123456789)
spinbox_error.setValue(123456789)
spinbox_success.setValue(123456789)

theme.set_default_state(spinbox_normal)
theme.set_error_state(spinbox_error)
theme.set_success_state(spinbox_success)

spinbox_layout.addRow("Default", spinbox_normal)
spinbox_layout.addRow("Error", spinbox_error)
spinbox_layout.addRow("Success", spinbox_success)

layout.addWidget(feedback_label_gb)
layout.addWidget(line_edit_gb)
layout.addWidget(spinbox_gb)
window.show()

sys.exit(app.exec())
