import enum
from dataclasses import dataclass


class LibraryCategory(enum.Enum):
    Basics = enum.auto()


@dataclass
class CategoryInfo:
    display_name: str


HMI_LIBARY_CATEGORIES = {
    LibraryCategory.Basics: CategoryInfo(display_name='Basics')
}

assert len(HMI_LIBARY_CATEGORIES) == len(LibraryCategory)
