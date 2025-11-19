#    test_varlist_search.py
#        Test the varlist search behavior
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

import math
from PySide6.QtWidgets import QMainWindow
from test.gui.base_gui_test import ScrutinyBaseGuiTest
from scrutiny.tools.typing import *

from scrutiny.gui.components.globals.varlist.varlist_search import SearchResultWidget
from scrutiny.gui.core.watchable_registry import WatchableRegistry
from scrutiny import sdk


DUMMY_DATASET_RPV = {
    '/rpv/rpv1000': sdk.BriefWatchableConfiguration(watchable_type=sdk.WatchableType.RuntimePublishedValue, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/rpv/rpv1001': sdk.BriefWatchableConfiguration(watchable_type=sdk.WatchableType.RuntimePublishedValue, datatype=sdk.EmbeddedDataType.float32, enum=None)
}

DUMMY_DATASET_ALIAS = {
    '/alias/xxx/alias1': sdk.BriefWatchableConfiguration(watchable_type=sdk.WatchableType.Alias, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/alias/alias2': sdk.BriefWatchableConfiguration(watchable_type=sdk.WatchableType.Alias, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/alias/alias3': sdk.BriefWatchableConfiguration(watchable_type=sdk.WatchableType.Alias, datatype=sdk.EmbeddedDataType.float32, enum=None)
}

DUMMY_DATASET_VAR = {
    '/var/xxx/var1': sdk.BriefWatchableConfiguration(watchable_type=sdk.WatchableType.Variable, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/var/xxx/var2': sdk.BriefWatchableConfiguration(watchable_type=sdk.WatchableType.Variable, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/var/var3': sdk.BriefWatchableConfiguration(watchable_type=sdk.WatchableType.Variable, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/var/var4': sdk.BriefWatchableConfiguration(watchable_type=sdk.WatchableType.Variable, datatype=sdk.EmbeddedDataType.float32, enum=None)
}


class TestVarlistSearch(ScrutinyBaseGuiTest):

    def setUp(self) -> None:
        super().setUp()
        self.registry = WatchableRegistry()
        self.registry.write_content({
            sdk.WatchableType.Variable: DUMMY_DATASET_VAR,
            sdk.WatchableType.Alias: DUMMY_DATASET_ALIAS,
            sdk.WatchableType.RuntimePublishedValue: DUMMY_DATASET_RPV
        })
        self.main_window = QMainWindow()
        self.search_widget = SearchResultWidget(self.main_window, self.registry)

    def test_basic_search(self):
        self.search_widget.start_search("xxx")
        self.wait_true_with_events(self.search_widget.finished, 2)
        self.assertEqual(self.search_widget.count_found(), 3)
        self.assertEqual(self.search_widget.completion(), 1)

        expected = [
            'alias:/alias/xxx/alias1',
            'var:/var/xxx/var1',
            'var:/var/xxx/var2'
        ]

        found_fqn = list(self.search_widget.iterate_found_fqns())
        self.assertEqual(len(found_fqn), 3)

        self.assertIn(found_fqn[0], expected)
        self.assertIn(found_fqn[1], expected)
        self.assertIn(found_fqn[2], expected)

    def test_pause_mechanism(self):
        stats = self.registry.get_stats()
        nb_watchable = stats.rpv_count + stats.var_count + stats.alias_count

        self.search_widget.set_search_batch_size(1)
        self.search_widget.start_search("xxx")
        self.assertEqual(self.search_widget.completion(), 0)
        for i in range(nb_watchable):
            self.assertTrue(self.search_widget.searching())
            self.assertEqual(self.search_widget.completion(), i / nb_watchable)
            self.process_events()
        self.process_events()
        self.assertFalse(self.search_widget.searching())
        self.assertEqual(self.search_widget.get_pause_counter(), nb_watchable)
        self.assertEqual(self.search_widget.completion(), 1)

        self.search_widget.set_search_batch_size(2)
        self.search_widget.start_search("xxx")
        self.assertEqual(self.search_widget.completion(), 0)
        self.wait_true_with_events(self.search_widget.finished, 2)
        self.assertEqual(self.search_widget.get_pause_counter(), math.floor(nb_watchable / 2))
        self.assertEqual(self.search_widget.completion(), 1)

    def test_search_criteria(self):
        def test_search_result(text, expected_count):
            self.search_widget.start_search(text)
            self.wait_true_with_events(self.search_widget.finished, 2)
            found_fqn = list(self.search_widget.iterate_found_fqns())
            self.assertEqual(len(found_fqn), expected_count, f"criteria={text}")

        test_search_result("/rpv/rpv1000", 1)
        test_search_result("alias", 3)
        test_search_result("alias/alias", 2)
        test_search_result("/var", 4)
        test_search_result("var1", 1)
        test_search_result("var2", 1)
        test_search_result("var3", 1)
        test_search_result("var4", 1)
