__all__ = [
    'get',
    'load_bin',
    'load_text',
    'load_pixmap',
    'IconSet',
    'IconFormat',
    'icon_filename',
    'Icons',
    'load_icon',
    'load_icon_filename',
    'load_tiny_icon',
    'load_medium_icon',
    'load_large_icon',
]

import os
from scrutiny.gui.core.exceptions import GuiError
from pathlib import Path
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtCore import QDir
import enum

from scrutiny.tools.typing import *

ASSET_PATH = os.path.dirname(__file__)

QDir.addSearchPath('stylesheets', os.path.join(ASSET_PATH, 'stylesheets'))


def get(name: Union[str, Path, List[str]]) -> Path:
    if isinstance(name, list):
        name = os.path.join(*name)

    outpath = os.path.join(ASSET_PATH, name)
    if os.path.commonpath([outpath, ASSET_PATH]) != ASSET_PATH:
        raise GuiError("Directory traversal while reading an asset")
    return Path(outpath)


def load_bin(name: Union[str, List[str]]) -> bytes:
    with open(get(name), 'rb') as f:
        return f.read()


def load_text(name: Union[str, List[str]]) -> str:
    with open(get(name), 'r') as f:
        return f.read()


def load_pixmap(name: Union[str, Path]) -> QPixmap:
    if isinstance(name, Path):
        name = str(name)
    if name not in pixmap_cache:
        pixmap_cache[name] = QPixmap(str(get(name)))
    return pixmap_cache[name]


def load_icon_file(name: Union[str, Path]) -> QIcon:
    if isinstance(name, Path):
        name = str(name)
    if name not in icon_cache:
        icon_cache[name] = QIcon(str(get(name)))
    return icon_cache[name]


icon_cache: Dict[str, QIcon] = {}
pixmap_cache: Dict[str, QPixmap] = {}


class IconSet(enum.Enum):
    Light = 'light'
    Dark = 'dark'


class IconFormat(enum.Enum):
    Tiny = enum.auto()
    Medium = enum.auto()
    Large = enum.auto()


class Icons(enum.Enum):
    Folder = "folder"
    Var = "var"
    Rpv = "rpv"
    Alias = "alias"
    RedX = "redx"
    GraphAxis = "axis"
    Eye = "eye"
    EyeBar = "eye-bar"
    Image = "image"
    CSV = "csv"
    Warning = "warning"
    Error = "error"
    Info = "info"
    GraphCursor = "graph-cursor"
    GraphNoCursor = "graph-no-cursor"
    ZoomX = "zoom-x"
    ZoomY = "zoom-y"
    ZoomXY = "zoom-xy"
    Zoom100 = "zoom-100"
    SquareRed = "square-red"
    SquareYellow = "square-yellow"
    SquareGreen = "square-green"
    ScrutinyLogo = "scrutiny-logo"
    Download = "download"
    CursorArrow = "cursor-arrow"
    CursorHandDrag = "cursor-hand-drag"
    TestSquare = "test-square"
    TestVRect = "test-vrect"
    TestHRect = "test-hrect"
    ThreeDots = "threedots"
    TextEdit = "text-edit"
    Window = "window"
    Pin = "pin"
    Unpin = "unpin"
    SidebarLeft = "sidebar-left"
    SidebarRight = "sidebar-right"
    SidebarTop = "sidebar-top"
    SidebarBottom = "sidebar-bottom"
    StopWatch = "stopwatch"
    VarList = "varlist"
    EmbeddedGraph = "embedded-graph"
    ContinuousGraph = "continuous-graph"
    Watch = "watch"
    Copy = "copy"


def icon_filename(name: Icons, format: IconFormat, iconset: IconSet) -> Path:
    possible_formats = {
        IconFormat.Tiny: [
            (16, 16),
            (16, 12),
            (12, 16),
            (8, 16),
            (16, 8)
        ],
        IconFormat.Medium: [
            (64, 64),
            (64, 48),
            (48, 64),
            (64, 32),
            (32, 64)
        ],
        IconFormat.Large: [
            (256, 256),
            (256, 192),
            (192, 256),
            (256, 128),
            (128, 256)
        ]
    }

    for f in possible_formats[format]:
        candidate = get(['icons', iconset.value, f"{name.value}_{f[0]}x{f[1]}.png"])
        if os.path.isfile(candidate):
            return candidate

    raise FileNotFoundError(f"Could not find an icon candidate for {name.name}({name.value}) with format {format.name} in icon set {iconset.name}")


def load_icon(name: Icons, format: IconFormat, iconset: IconSet) -> QIcon:
    return load_icon_file(icon_filename(name, format, iconset))


def load_icon_as_pixmap(name: Icons, format: IconFormat, iconset: IconSet) -> QPixmap:
    return load_pixmap(icon_filename(name, format, iconset))


def load_stylesheet(name: str) -> str:
    if not name.endswith('.qss'):
        name += '.qss'
    return load_text(['stylesheets', name])
