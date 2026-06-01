#    gauge.py
#        Common work between the linear and radial gauge
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

import enum


class GaugeOverflowBehavior(enum.Enum):
    """How to handle when a value is outside the min-max range.
    CLIP Set to min or max.
    NO_VALUE : Remove the pointer and display N/A if applicable"""
    CLIP = 1
    NO_VALUE = 2
