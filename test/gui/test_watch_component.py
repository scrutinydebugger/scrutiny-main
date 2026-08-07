#    test_watch_component.py
#        A test suite for the Watch Component
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2025 Scrutiny Debugger

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QModelIndex
from test.gui.fake_server_manager import FakeServerManager
from test.gui.base_gui_test import ScrutinyBaseGuiTest
from scrutiny.gui.components.locals.watch.watch_component import WatchComponent, WatchComponentTreeModel, NumericFormat, SerializableTreeDescriptor
from scrutiny.gui.core.watchable_registry import WatchableRegistry
from scrutiny.gui.component_app_interface import AbstractComponentAppInterface
from scrutiny.gui.core.scrutiny_drag_data import WatchableListDescriptor, SingleWatchableDescriptor, ScrutinyDragData


from scrutiny.tools.typing import *


class MainWindowStub(QWidget):
    def __init__(self):
        super().__init__()
        self.registry = WatchableRegistry()
        self.server_manager = FakeServerManager(self.registry)

    def get_server_manager(self):
        return self.server_manager

    def get_watchable_registry(self):
        return self.registry


class DummyAppInterface(AbstractComponentAppInterface):
    def reveal_varlist_fqn(self, fqn: str) -> None:
        pass


class TestWatchComponent(ScrutinyBaseGuiTest):
    def setUp(self):
        super().setUp()

        self.main_window = MainWindowStub()
        app_interface = DummyAppInterface()
        app_interface.server_manager = self.main_window.get_server_manager()
        app_interface.watchable_registry = self.main_window.get_watchable_registry()
        self.watch1 = WatchComponent(
            self.main_window,
            'watch1',
            app_interface
        )
        self.watch1.setup()

    def tearDown(self):
        self.watch1.teardown()
        return super().tearDown()

    def test_column_order_state(self):
        colmap = self.watch1.get_column_logical_indexes_by_name()
        self.assertEqual(len(colmap), self.watch1.column_count() - 1)

        state = self.watch1.get_state()
        self.assertIn('cols', state)
        for col in ['value', 'type', 'enum']:
            self.assertIn(col, state['cols'])

        state['cols'] = ['enum', 'type', 'value']
        self.watch1.load_state(state)

        tree = self.watch1._tree
        self.assertEqual(tree.header().visualIndex(WatchComponentTreeModel.enum_col()), 1)
        self.assertEqual(tree.header().visualIndex(WatchComponentTreeModel.datatype_col()), 2)
        self.assertEqual(tree.header().visualIndex(WatchComponentTreeModel.value_col()), 3)

        state['cols'] = ['enum', 'value', 'type']
        self.watch1.load_state(state)
        self.assertEqual(tree.header().visualIndex(WatchComponentTreeModel.enum_col()), 1)
        self.assertEqual(tree.header().visualIndex(WatchComponentTreeModel.value_col()), 2)
        self.assertEqual(tree.header().visualIndex(WatchComponentTreeModel.datatype_col()), 3)

    def test_numeric_format_carried_in_drag_watchable_list(self):
        watchable_list_desc = WatchableListDescriptor([
            SingleWatchableDescriptor("aaa", "var:/xxx/yyy", custom_data={'fmt': 'hex'}),
            SingleWatchableDescriptor("bbb", "var:/xxx/yyy/zzz", custom_data={'fmt': 'bin'}),
            SingleWatchableDescriptor("bbb", "var:/xxx/yyy/zzz2", custom_data={'fmt': 'dec'})
        ])
        model = self.watch1.internal_model_for_unit_test()

        mime_data = watchable_list_desc.to_mime()
        model.dropMimeData(mime_data, Qt.DropAction.CopyAction, -1, 0, QModelIndex())
        self.assertEqual(model.rowCount(), 3)

        self.assertEqual(model.item(0, model.value_col()).get_numeric_format(), NumericFormat.Hexadecimal)
        self.assertEqual(model.item(1, model.value_col()).get_numeric_format(), NumericFormat.Binary)
        self.assertEqual(model.item(2, model.value_col()).get_numeric_format(), NumericFormat.Decimal)

        items = [
            model.item(0, model.nesting_col()),
            model.item(1, model.nesting_col()),
            model.item(2, model.nesting_col())
        ]
        mime_data = model.mimeData([item.index() for item in items])
        list_desc = WatchableListDescriptor.from_mime(mime_data)
        self.assertEqual(list_desc.data[0].custom_data['fmt'], 'hex')
        self.assertEqual(list_desc.data[1].custom_data['fmt'], 'bin')
        if list_desc.data[2].custom_data is not None:   # Decimal is default, so maybe not given
            self.assertIn(list_desc.data[2].custom_data['fmt'], ['dec', None])

    def test_numeric_format_carried_in_drag_fulltree(self):
        model = self.watch1.internal_model_for_unit_test()

        serializable_tree_descriptors: List[SerializableTreeDescriptor] = [
            {
                'node': {
                    'fqn': 'var:/xxx/yyy/zzz',
                    'text': 'aaa',
                    'type': 'watchable',
                    'custom_data': {'fmt': 'hex'}
                },
                'children': [],
                'sortkey': 0
            },
            {
                'node': {
                    'fqn': 'var:/xxx/yyy/zzz2',
                    'text': 'aaa2',
                    'type': 'watchable',
                    'custom_data': {'fmt': 'bin'}
                },
                'children': [],
                'sortkey': 1
            },
            {
                'node': {
                    'type': 'folder',
                    'text': 'folder1',
                    'fqn': None,
                    'custom_data': None
                },
                'sortkey': 2,
                'children': [
                    {
                        'node': {
                            'fqn': 'var:/xxx/yyy/zzz3',
                            'text': 'aaa3',
                            'type': 'watchable',
                            'custom_data': {'fmt': 'dec'}
                        },
                        'children': [],
                        'sortkey': 0
                    }
                ]
            }
        ]
        drag_data = ScrutinyDragData(
            type=ScrutinyDragData.DataType.WatchableFullTree,
            data_copy=serializable_tree_descriptors,
            data_move=None
        )

        mime_data = drag_data.to_mime()
        model.dropMimeData(mime_data, Qt.DropAction.CopyAction, -1, 0, QModelIndex())
        self.assertEqual(model.rowCount(), 3)

        self.assertEqual(model.item(0, model.value_col()).get_numeric_format(), NumericFormat.Hexadecimal)
        self.assertEqual(model.item(1, model.value_col()).get_numeric_format(), NumericFormat.Binary)
        self.assertEqual(model.item(2, model.nesting_col()).child(0, model.value_col()).get_numeric_format(), NumericFormat.Decimal)

        items = [
            model.item(0, model.nesting_col()),
            model.item(1, model.nesting_col()),
            model.item(2, model.nesting_col()).child(0, model.nesting_col())
        ]
        mime_data = model.mimeData([item.index() for item in items])
        list_desc = WatchableListDescriptor.from_mime(mime_data)
        self.assertEqual(list_desc.data[0].custom_data['fmt'], 'hex')
        self.assertEqual(list_desc.data[1].custom_data['fmt'], 'bin')
        if list_desc.data[2].custom_data is not None:   # Decimal is default, so maybe not given
            self.assertIn(list_desc.data[2].custom_data['fmt'], ['dec', None])
