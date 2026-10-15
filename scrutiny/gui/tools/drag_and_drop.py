#    drag_and_drop.py
#        Some drag&drop tools shared across the GUI
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

__all__ = ['make_watchable_list_dragdata_if_possible']

from scrutiny.tools.typing import *
from scrutiny.gui.widgets.watchable_tree import BaseWatchableRegistryTreeStandardItem, WatchableStandardItem, CustomDataType
from scrutiny.gui.core.scrutiny_drag_data import ScrutinyDragData, WatchableListDescriptor, SingleWatchableDescriptor


def make_watchable_list_dragdata_if_possible(items: Iterable[Optional[BaseWatchableRegistryTreeStandardItem]],
                                             data_move: Optional[Any] = None,
                                             custom_data_maker: Optional[Callable[[WatchableStandardItem], CustomDataType]] = None
                                             ) -> Optional[ScrutinyDragData]:
    """Converts a list of tree nodes to a ScrutinyDragData that contains a list of watchable
    only if the given indexes points to watchables (leaf) nodes only. Return ``None`` if any of the element is not a watchable node

    :param items: The items to scan and embed in the drag data
    :param data_move: Additional data to attach to the ScrutinyDragData

    :return: A ScrutinyDragData containing the watchable list or ``None`` if any of the index pointed to something else than a watchable node

    """
    watchables_only = True
    for item in items:
        if item is None or not isinstance(item, WatchableStandardItem):
            watchables_only = False
            break

    if watchables_only:
        watchable_items = cast(List[WatchableStandardItem], items)
        if custom_data_maker is None:
            custom_data_maker = lambda item: None
        return WatchableListDescriptor(
            data=[SingleWatchableDescriptor(text=item.text(), fqn=item.fqn, custom_data=custom_data_maker(item)) for item in watchable_items]
        ).to_drag_data(data_move=data_move)
    return None
