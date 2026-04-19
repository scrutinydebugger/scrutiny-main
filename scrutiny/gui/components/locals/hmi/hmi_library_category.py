#    hmi_library_category.py
#        A central place to define the different HMI widget categories used for display
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

import enum
from dataclasses import dataclass


class LibraryCategory(enum.Enum):
    Display = enum.auto()
    Control = enum.auto()
    Graphic = enum.auto()


@dataclass
class CategoryInfo:
    display_name: str


HMI_LIBARY_CATEGORIES = {
    LibraryCategory.Display: CategoryInfo(display_name='Display'),
    LibraryCategory.Control: CategoryInfo(display_name='Control'),
    LibraryCategory.Graphic: CategoryInfo(display_name='Graphic')
}

assert len(HMI_LIBARY_CATEGORIES) == len(LibraryCategory)
