import enum


class GaugeOverflowBehavior(enum.Enum):
    """How to handle when a value is outside the min-max range.  CLIP Set to min or max. Show_NA : Remove the pointer and display N/A"""
    CLIP = 1
    SHOW_NA = 2
