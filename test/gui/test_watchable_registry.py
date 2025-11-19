#    test_watchable_registry.py
#        A test suite for the WatchableRegistry object
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2024 Scrutiny Debugger

from scrutiny import sdk
from scrutiny.core.basic_types import EmbeddedDataType
from scrutiny.core.embedded_enum import EmbeddedEnum
from scrutiny.gui.core.watchable_registry import (WatchableRegistry, WatchableRegistryError, WatchableRegistryEntryNode,
                                                  WatchableRegistryIntermediateNode, ValueUpdate, WatcherNotFoundError,
                                                  WatchableRegistryNodeNotFoundError, ServerRegistryBidirectionalMap)
from scrutiny.tools.thread_enforcer import ThreadEnforcer
from scrutiny.gui.core.threads import QT_THREAD_NAME

from test import ScrutinyUnitTest
from datetime import datetime
from scrutiny.tools.typing import *
from uuid import uuid4

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


All_DUMMY_DATA = {
    sdk.WatchableType.Variable: DUMMY_DATASET_VAR,
    sdk.WatchableType.Alias: DUMMY_DATASET_ALIAS,
    sdk.WatchableType.RuntimePublishedValue: DUMMY_DATASET_RPV,
}


class StubbedWatchableHandle:
    server_path: str
    configuration: sdk.BaseDetailedWatchableConfiguration

    def __init__(self, server_path: str,
                 watchable_type: sdk.WatchableType,
                 datatype: EmbeddedDataType,
                 enum: Optional[EmbeddedEnum],
                 server_id: str
                 ) -> None:

        self.server_path = server_path
        self.configuration = sdk.BaseDetailedWatchableConfiguration(
            watchable_type=watchable_type,
            datatype=datatype,
            enum=enum,
            server_id=server_id,
            server_path=server_path
        )

    @property
    def server_id(self):
        return self.configuration.server_id

    @property
    def type(self):
        return self.configuration.watchable_type


class TestWatchableRegistry(ScrutinyUnitTest):
    def setUp(self) -> None:
        super().setUp()
        self.registry = WatchableRegistry()
        ThreadEnforcer.register_thread(QT_THREAD_NAME)

    def make_fake_watchable_from_registry(self, fqn: str) -> StubbedWatchableHandle:
        node = self.registry.read_fqn(fqn)
        assert isinstance(node, WatchableRegistryEntryNode)
        return StubbedWatchableHandle(
            server_path=WatchableRegistry.FQN.parse(fqn).path,
            watchable_type=node.configuration.watchable_type,
            datatype=node.configuration.datatype,
            server_id=uuid4().hex,
            enum=node.configuration.enum
        )

    def test_ignore_empty_data(self):
        self.registry.write_content({
            sdk.WatchableType.Alias: DUMMY_DATASET_ALIAS,
            sdk.WatchableType.RuntimePublishedValue: {}  # Should be ignored
        })

        self.assertTrue(self.registry.has_data(sdk.WatchableType.Alias))
        self.assertFalse(self.registry.has_data(sdk.WatchableType.RuntimePublishedValue))
        self.assertFalse(self.registry.has_data(sdk.WatchableType.Variable))

    def test_fqn(self):
        for wt in sdk.WatchableType.all():
            fqn = WatchableRegistry.FQN.make(wt, '/a/b/c')
            o = WatchableRegistry.FQN.parse(fqn)
            self.assertEqual(o.watchable_type, wt)
            self.assertEqual(o.path, '/a/b/c')

        with self.assertRaises(WatchableRegistryError):
            WatchableRegistry.FQN.parse('unknown:/a/b/c')

        with self.assertRaises(WatchableRegistryError):
            WatchableRegistry.FQN.parse('/a/b/c')

        self.assertEqual(WatchableRegistry.FQN.extend('var:/a/b/c', ['x', 'y']), 'var:/a/b/c/x/y')
        self.assertEqual(WatchableRegistry.FQN.extend('var:/a/b/c', 'x'), 'var:/a/b/c/x')
        self.assertEqual(WatchableRegistry.FQN.extend('var:', ['x', 'y']), 'var:x/y')

        self.assertTrue(WatchableRegistry.FQN.is_equal('var:/a/b/c', 'var:a/b//c/'))
        self.assertFalse(WatchableRegistry.FQN.is_equal('var:/a/b/c', 'alias:a/b//c/'))
        self.assertFalse(WatchableRegistry.FQN.is_equal('var:/a/b/c', 'alias:/a/b/c'))

        self.assertFalse(WatchableRegistry.FQN.is_equal('var:/a/b/c', 'var:/a/c'))
        self.assertFalse(WatchableRegistry.FQN.is_equal('var:/a/b/c', 'var:/a/b/d'))

    def test_internal_direct_add_get(self):
        obj1 = sdk.BriefWatchableConfiguration(
            watchable_type=sdk.WatchableType.Alias,
            datatype=sdk.EmbeddedDataType.float32,
            enum=None
        )

        obj2 = sdk.BriefWatchableConfiguration(
            watchable_type=sdk.WatchableType.Variable,
            datatype=sdk.EmbeddedDataType.float32,
            enum=None
        )

        self.registry._add_watchable('/a/b/c', obj1)
        self.registry._add_watchable('/a/b/d/e', obj2)   # type is optional when setting

        o1 = self.registry.read(sdk.WatchableType.Alias, '/a/b/c')
        self.assertIs(o1.configuration, obj1)
        self.assertIsNone(self.registry.read(sdk.WatchableType.Variable, '/a/b/c'))

        o2 = self.registry.read_fqn('var:/a/b/d/e')
        self.assertIs(obj2, o2.configuration)

    def test_root_not_writable(self):
        obj1 = sdk.BriefWatchableConfiguration(
            watchable_type=sdk.WatchableType.Alias,
            datatype=sdk.EmbeddedDataType.float32,
            enum=None
        )

        with self.assertRaises(WatchableRegistryError):
            self.registry._add_watchable('/', obj1)

    def test_query_node_type(self):
        self.registry.write_content(All_DUMMY_DATA)

        self.assertTrue(self.registry.get_watchable_count(sdk.WatchableType.Variable), len(DUMMY_DATASET_VAR))
        self.assertTrue(self.registry.get_watchable_count(sdk.WatchableType.Alias), len(DUMMY_DATASET_ALIAS))
        self.assertTrue(self.registry.get_watchable_count(sdk.WatchableType.RuntimePublishedValue), len(DUMMY_DATASET_RPV))

        self.assertTrue(self.registry.is_watchable_fqn('alias:/alias/xxx/alias1'))
        self.assertFalse(self.registry.is_watchable_fqn('alias:/alias/xxx'))
        self.assertFalse(self.registry.is_watchable_fqn('alias:Idontexist'))

    def test_cannot_overwrite_without_clear(self):
        obj1 = sdk.BriefWatchableConfiguration(
            watchable_type=sdk.WatchableType.Variable,
            datatype=sdk.EmbeddedDataType.float32,
            enum=None
        )

        obj2 = sdk.BriefWatchableConfiguration(
            watchable_type=sdk.WatchableType.Variable,
            datatype=sdk.EmbeddedDataType.float32,
            enum=None
        )

        self.registry._add_watchable('/aaa/bbb', obj1)
        with self.assertRaises(WatchableRegistryError):
            self.registry._add_watchable('/aaa/bbb', obj2)

    def test_can_have_same_path_if_different_type(self):
        obj1 = sdk.BriefWatchableConfiguration(
            watchable_type=sdk.WatchableType.Alias,
            datatype=sdk.EmbeddedDataType.float32,
            enum=None
        )

        obj2 = sdk.BriefWatchableConfiguration(
            watchable_type=sdk.WatchableType.Variable,
            datatype=sdk.EmbeddedDataType.float32,
            enum=None
        )

        self.registry._add_watchable('/aaa/bbb', obj1)
        self.registry._add_watchable('/aaa/bbb', obj2)

    def test_read_write(self):
        for path, desc in DUMMY_DATASET_VAR.items():
            self.registry._add_watchable(path, desc)
        for path, desc in DUMMY_DATASET_ALIAS.items():
            self.registry._add_watchable(path, desc)
        for path, desc in DUMMY_DATASET_RPV.items():
            self.registry._add_watchable(path, desc)

        node = self.registry.read_fqn('var:/')
        assert isinstance(node, WatchableRegistryIntermediateNode)
        self.assertEqual(len(node.watchables), 0)
        self.assertEqual(len(node.subtree), 1)

        self.assertIn('var', node.subtree)

        node = self.registry.read_fqn('var:/var')
        assert isinstance(node, WatchableRegistryIntermediateNode)
        self.assertEqual(len(node.watchables), 2)
        self.assertEqual(len(node.subtree), 1)

        self.assertIn('xxx', node.subtree)
        self.assertIn('var3', node.watchables)
        self.assertEqual(DUMMY_DATASET_VAR['/var/var3'], node.watchables['var3'].configuration)

        self.assertIn('var4', node.watchables)
        self.assertEqual(DUMMY_DATASET_VAR['/var/var4'], node.watchables['var4'].configuration)

        node = self.registry.read_fqn('var:/var/xxx')
        assert isinstance(node, WatchableRegistryIntermediateNode)
        self.assertEqual(len(node.watchables), 2)
        self.assertEqual(len(node.subtree), 0)

        self.assertIn('var1', node.watchables)
        self.assertEqual(DUMMY_DATASET_VAR['/var/xxx/var1'], node.watchables['var1'].configuration)
        self.assertIn('var2', node.watchables)
        self.assertEqual(DUMMY_DATASET_VAR['/var/xxx/var2'], node.watchables['var2'].configuration)

    def test_clear_by_type(self):
        self.registry.write_content(All_DUMMY_DATA)

        self.assertTrue(self.registry.has_data(sdk.WatchableType.Variable))
        self.assertTrue(self.registry.has_data(sdk.WatchableType.Alias))
        self.assertTrue(self.registry.has_data(sdk.WatchableType.RuntimePublishedValue))

        had_data = self.registry.clear_content_by_type(sdk.WatchableType.Variable)
        self.assertTrue(had_data)
        self.assertFalse(self.registry.has_data(sdk.WatchableType.Variable))
        self.assertTrue(self.registry.has_data(sdk.WatchableType.Alias))
        self.assertTrue(self.registry.has_data(sdk.WatchableType.RuntimePublishedValue))
        had_data = self.registry.clear_content_by_type(sdk.WatchableType.Variable)
        self.assertFalse(had_data)

        had_data = self.registry.clear_content_by_type(sdk.WatchableType.Alias)
        self.assertTrue(had_data)
        self.assertFalse(self.registry.has_data(sdk.WatchableType.Variable))
        self.assertFalse(self.registry.has_data(sdk.WatchableType.Alias))
        self.assertTrue(self.registry.has_data(sdk.WatchableType.RuntimePublishedValue))
        had_data = self.registry.clear_content_by_type(sdk.WatchableType.Alias)
        self.assertFalse(had_data)

        had_data = self.registry.clear_content_by_type(sdk.WatchableType.RuntimePublishedValue)
        self.assertTrue(had_data)
        self.assertFalse(self.registry.has_data(sdk.WatchableType.Variable))
        self.assertFalse(self.registry.has_data(sdk.WatchableType.Alias))
        self.assertFalse(self.registry.has_data(sdk.WatchableType.RuntimePublishedValue))
        had_data = self.registry.clear_content_by_type(sdk.WatchableType.RuntimePublishedValue)
        self.assertFalse(had_data)

        self.assertFalse(self.registry.clear())

    def test_clear(self):
        self.registry.write_content(All_DUMMY_DATA)
        self.assertTrue(self.registry.has_data(sdk.WatchableType.Variable))
        self.assertTrue(self.registry.has_data(sdk.WatchableType.Alias))
        self.assertTrue(self.registry.has_data(sdk.WatchableType.RuntimePublishedValue))

        had_data = self.registry.clear()
        self.assertTrue(had_data)

        self.assertFalse(self.registry.has_data(sdk.WatchableType.Variable))
        self.assertFalse(self.registry.has_data(sdk.WatchableType.Alias))
        self.assertFalse(self.registry.has_data(sdk.WatchableType.RuntimePublishedValue))

        self.assertFalse(self.registry.clear())

    def test_watcher_broadcast_logic(self):
        self.registry.write_content(All_DUMMY_DATA)

        update_val_callback_history = {
            'watcher1': [],
            'watcher2': [],
        }

        def update_val_callback(watcher, value_list):
            update_val_callback_history[watcher].append(value_list)

        self.registry.register_watcher('watcher1', update_val_callback, lambda *x, **y: None)
        self.registry.register_watcher('watcher2', update_val_callback, lambda *x, **y: None)

        var1fqn = f'var:/var/xxx/var1'
        var2fqn = f'var:/var/xxx/var2'

        var1_sdk_handle = self.make_fake_watchable_from_registry(var1fqn)
        var2_sdk_handle = self.make_fake_watchable_from_registry(var2fqn)

        self.registry.assign_serverid_to_node_fqn(var1fqn, var1_sdk_handle.server_id)
        self.registry.assign_serverid_to_node_fqn(var2fqn, var2_sdk_handle.server_id)

        self.registry.watch('watcher1', sdk.WatchableType.Variable, '/var/xxx/var1')
        self.registry.watch_fqn('watcher2', var1fqn)
        self.registry.watch_fqn('watcher2', var2fqn)
        self.assertEqual(self.registry.watched_entries_count(), 2)
        with self.assertRaises(WatcherNotFoundError):
            self.registry.watch_fqn('watcher_idontexist', var2fqn)

        registr_id_var1 = self.registry.read_fqn(var1fqn).registry_id
        registr_id_var2 = self.registry.read_fqn(var2fqn).registry_id

        # Check watcher states
        self.assertEqual(self.registry.watcher_count_by_registry_id(registr_id_var1), 2)
        self.assertEqual(self.registry.watcher_count_by_registry_id(registr_id_var2), 1)
        self.assertEqual(self.registry.node_watcher_count_fqn(var1fqn), 2)
        self.assertEqual(self.registry.node_watcher_count_fqn(var2fqn), 1)

        self.assertEqual(len(update_val_callback_history['watcher1']), 0)
        self.assertEqual(len(update_val_callback_history['watcher2']), 0)

        # Check value updates broadcast
        update1_1 = ValueUpdate(var1_sdk_handle, 123, datetime.now())
        update1_2 = ValueUpdate(var1_sdk_handle, 456, datetime.now())
        update2_1 = ValueUpdate(var2_sdk_handle, 789, datetime.now())
        self.registry.broadcast_value_updates_to_watchers([update1_1, update1_2])
        self.assertEqual(len(update_val_callback_history['watcher1']), 1)
        self.assertEqual(len(update_val_callback_history['watcher2']), 1)
        self.assertEqual([x.sdk_update for x in update_val_callback_history['watcher1'][0]], [update1_1, update1_2])
        self.assertEqual([x.sdk_update for x in update_val_callback_history['watcher2'][0]], [update1_1, update1_2])

        self.registry.broadcast_value_updates_to_watchers([update2_1])
        self.assertEqual(len(update_val_callback_history['watcher1']), 1)
        self.assertEqual(len(update_val_callback_history['watcher2']), 2)
        self.assertEqual([x.sdk_update for x in update_val_callback_history['watcher2'][1]], [update2_1])

        self.registry.unwatch_fqn('watcher2', var1fqn)
        self.assertEqual(self.registry.node_watcher_count_fqn(var1fqn), 1)
        self.assertEqual(self.registry.node_watcher_count_fqn(var2fqn), 1)

        update1_3 = ValueUpdate(var1_sdk_handle, 666, datetime.now())
        self.registry.broadcast_value_updates_to_watchers([update1_3])
        self.assertEqual(len(update_val_callback_history['watcher1']), 2)
        self.assertEqual(len(update_val_callback_history['watcher2']), 2)  # Did not receive the latest update
        self.assertEqual([x.sdk_update for x in update_val_callback_history['watcher1'][1]], [update1_3])

        self.registry.unwatch_fqn('watcher1', var1fqn)
        self.registry.unwatch_fqn('watcher2', var2fqn)
        self.assertEqual(self.registry.node_watcher_count_fqn(var1fqn), 0)
        self.assertEqual(self.registry.node_watcher_count_fqn(var2fqn), 0)

        update1_4 = ValueUpdate(var1_sdk_handle, 777, datetime.now())
        update2_3 = ValueUpdate(var2_sdk_handle, 888, datetime.now())
        self.registry.broadcast_value_updates_to_watchers([update1_4, update2_3])
        # Nothing updated, nobody watches
        self.assertEqual(len(update_val_callback_history['watcher1']), 2)
        self.assertEqual(len(update_val_callback_history['watcher2']), 2)

        self.registry.unwatch_fqn('watcher1', var1fqn)     # Already unwatched. No error

        self.registry.register_watcher('watcher3', lambda *x, **y: None, lambda *x, **y: None)
        with self.assertRaises(WatchableRegistryError):
            self.registry.watch_fqn('watcher3', 'var:/var/xxx')    # Path exists, but is not a watchable

        with self.assertRaises(WatchableRegistryNodeNotFoundError):
            self.registry.watch_fqn('watcher3', 'var:/idontexist')    # Path does not exist

        with self.assertRaises(WatcherNotFoundError):
            self.registry.watch_fqn('unknownwatcher', var1fqn)  # Watcher is not registered

    def test_unwatch_on_unregister(self):
        self.registry.write_content(All_DUMMY_DATA)

        update_val_callback_history = {
            'watcher1': [],
            'watcher2': [],
            123: []
        }

        unwatch_callback_history = {
            'watcher1': [],
            'watcher2': [],
            123: []
        }

        def update_val_callback(watcher, value_list):
            update_val_callback_history[watcher].append(value_list)

        def unwatch_callback(watcher, fqn, wc, registry_id):
            unwatch_callback_history[watcher].append(fqn)

        self.registry.register_watcher('watcher1', update_val_callback, unwatch_callback)
        self.registry.register_watcher('watcher2', update_val_callback, unwatch_callback)
        self.registry.register_watcher(123, update_val_callback, unwatch_callback)
        self.assertEqual(self.registry.registered_watcher_count(), 3)

        with self.assertRaises(WatcherNotFoundError):
            self.registry.unregister_watcher('idontexist')

        var1fqn = f'var:/var/xxx/var1'
        var2fqn = f'var:/var/xxx/var2'
        var3fqn = f'var:/var/var3'

        var1_sdk_handle = self.make_fake_watchable_from_registry(var1fqn)
        var2_sdk_handle = self.make_fake_watchable_from_registry(var2fqn)
        var3_sdk_handle = self.make_fake_watchable_from_registry(var3fqn)

        self.registry.assign_serverid_to_node_fqn(var1fqn, var1_sdk_handle.server_id)
        self.registry.assign_serverid_to_node_fqn(var2fqn, var2_sdk_handle.server_id)
        self.registry.assign_serverid_to_node_fqn(var3fqn, var3_sdk_handle.server_id)
        self.registry.watch_fqn('watcher1', var1fqn)
        self.registry.watch_fqn('watcher2', var1fqn)
        self.registry.watch_fqn('watcher2', var2fqn)
        self.registry.watch_fqn(123, var3fqn)

        update1 = ValueUpdate(var1_sdk_handle, 123, datetime.now())
        update2 = ValueUpdate(var2_sdk_handle, 456, datetime.now())
        update3 = ValueUpdate(var3_sdk_handle, 1.5, datetime.now())
        self.registry.broadcast_value_updates_to_watchers([update1, update2, update3])
        self.assertEqual(len(update_val_callback_history['watcher1']), 1)
        self.assertEqual(len(update_val_callback_history['watcher2']), 1)
        self.assertEqual(len(update_val_callback_history[123]), 1)
        self.assertEqual(self.registry.node_watcher_count_fqn(var1fqn), 2)
        self.assertEqual(self.registry.node_watcher_count_fqn(var2fqn), 1)
        self.assertEqual(self.registry.node_watcher_count_fqn(var3fqn), 1)

        self.registry.unregister_watcher('watcher2')
        self.assertEqual(self.registry.registered_watcher_count(), 2)
        self.assertCountEqual(unwatch_callback_history['watcher2'], [var1fqn, var2fqn])
        self.assertCountEqual(unwatch_callback_history['watcher1'], [])
        self.assertCountEqual(unwatch_callback_history[123], [])
        self.assertEqual(self.registry.node_watcher_count_fqn(var1fqn), 1)
        self.assertEqual(self.registry.node_watcher_count_fqn(var2fqn), 0)
        self.registry.broadcast_value_updates_to_watchers([update1, update2])
        self.assertEqual(len(update_val_callback_history['watcher1']), 2)
        self.assertEqual(len(update_val_callback_history['watcher2']), 1)
        unwatch_callback_history['watcher2'].clear()

        self.registry.unregister_watcher('watcher1')
        self.assertEqual(self.registry.registered_watcher_count(), 1)
        self.assertCountEqual(unwatch_callback_history['watcher2'], [])
        self.assertCountEqual(unwatch_callback_history['watcher1'], [var1fqn])
        self.assertCountEqual(unwatch_callback_history[123], [])
        self.assertEqual(self.registry.node_watcher_count_fqn(var1fqn), 0)
        self.assertEqual(self.registry.node_watcher_count_fqn(var2fqn), 0)
        self.assertEqual(self.registry.node_watcher_count_fqn(var3fqn), 1)
        self.registry.broadcast_value_updates_to_watchers([update1, update2])
        self.assertEqual(len(update_val_callback_history['watcher1']), 2)
        self.assertEqual(len(update_val_callback_history['watcher2']), 1)
        self.assertEqual(len(update_val_callback_history[123]), 1)
        unwatch_callback_history['watcher1'].clear()

        self.registry.unregister_watcher(123)
        self.assertEqual(self.registry.registered_watcher_count(), 0)
        self.assertCountEqual(unwatch_callback_history['watcher2'], [])
        self.assertCountEqual(unwatch_callback_history['watcher1'], [])
        self.assertCountEqual(unwatch_callback_history[123], [var3fqn])
        self.assertEqual(self.registry.node_watcher_count_fqn(var1fqn), 0)
        self.assertEqual(self.registry.node_watcher_count_fqn(var2fqn), 0)
        self.assertEqual(self.registry.node_watcher_count_fqn(var3fqn), 0)
        self.registry.broadcast_value_updates_to_watchers([update1, update2, update3])
        self.assertEqual(len(update_val_callback_history['watcher1']), 2)
        self.assertEqual(len(update_val_callback_history['watcher2']), 1)
        self.assertEqual(len(update_val_callback_history[123]), 1)
        unwatch_callback_history[123].clear()

    def test_watch_bad_values(self):
        self.registry.write_content(All_DUMMY_DATA)
        with self.assertRaises(ValueError):
            self.registry.register_watcher('watcher1', 'iamnotacallback', lambda *x, **y: None)
        with self.assertRaises(ValueError):
            self.registry.register_watcher('watcher1', lambda *x, **y: None, 'iamnotacallback')

        with self.assertRaises(ValueError):
            self.registry.register_watcher(None, lambda *x, **y: None, lambda *x, **y: None)

        with self.assertRaises(ValueError):
            self.registry.register_watcher([], lambda *x, **y: None, lambda *x, **y: None)

    def test_unwatch_on_clear(self):
        clear_funcs = [
            self.registry.clear,
            lambda: self.registry.clear_content_by_type(sdk.WatchableType.Variable)
        ]

        def val_update_callback(watcher, wc, value):
            pass

        def unwatch_callback(watcher, fqn, wc):
            pass

        self.registry.register_watcher('watcher1', val_update_callback, unwatch_callback)
        self.registry.register_watcher('watcher2', val_update_callback, unwatch_callback)

        with self.assertRaises(WatchableRegistryError):
            self.registry.register_watcher('watcher2', val_update_callback, unwatch_callback)  # No override allowed
        self.registry.register_watcher('watcher2', val_update_callback, unwatch_callback, ignore_duplicate=True)  # override allowed

        for clear_func in clear_funcs:
            self.registry.write_content(All_DUMMY_DATA)

            var1fqn = f'var:/var/xxx/var1'
            var2fqn = f'var:/var/xxx/var2'
            self.registry.watch('watcher1', sdk.WatchableType.Variable, '/var/xxx/var1')
            self.registry.watch_fqn('watcher2', var1fqn)
            self.registry.watch_fqn('watcher2', var2fqn)
            registry_id_var1 = self.registry.read_fqn(var1fqn).registry_id
            registry_id_var2 = self.registry.read_fqn(var2fqn).registry_id
            self.assertEqual(self.registry.node_watcher_count_fqn(var1fqn), 2)
            self.assertEqual(self.registry.node_watcher_count_fqn(var2fqn), 1)
            self.assertEqual(self.registry.watched_entries_count(), 2)

            clear_func()
            self.assertEqual(self.registry.watched_entries_count(), 0)

            with self.assertRaises(WatchableRegistryError):
                self.registry.node_watcher_count_fqn(var1fqn)
            with self.assertRaises(WatchableRegistryError):
                self.registry.node_watcher_count_fqn(var2fqn)

            self.assertEqual(self.registry.watcher_count_by_registry_id(registry_id_var1), 0)
            self.assertEqual(self.registry.watcher_count_by_registry_id(registry_id_var2), 0)

            self.registry.write_content({sdk.WatchableType.Variable: DUMMY_DATASET_VAR})
            self.assertEqual(self.registry.node_watcher_count_fqn(var1fqn), 0)
            self.assertEqual(self.registry.node_watcher_count_fqn(var2fqn), 0)
            self.assertEqual(self.registry.watched_entries_count(), 0)

            self.registry.clear()

    def test_bad_values(self):
        self.registry.write_content(All_DUMMY_DATA)

        self.assertIsNone(self.registry.node_watcher_count_fqn('var:/var/xxx'))

        with self.assertRaises(WatcherNotFoundError):
            self.registry.unwatch_fqn('watcher_xxx', 'var:/var/xxx')

    def test_global_watch_callbacks(self):
        self.registry.write_content(All_DUMMY_DATA)

        watch_calls_history = []
        unwatch_calls_history = []

        def watch_callback(watcher_id, display_path, watchable_config, registry_id):
            watch_calls_history.append((watcher_id, display_path, watchable_config, registry_id))

        def unwatch_callback(watcher_id, display_path, watchable_config, registry_id):
            unwatch_calls_history.append((watcher_id, display_path, watchable_config, registry_id))

        def dummy_callback(*args, **kwargs):
            pass

        self.registry.register_global_watch_callback(watch_callback, unwatch_callback)

        var1 = self.registry.read_fqn('var:/var/xxx/var1')
        self.registry.register_watcher('watcher1', dummy_callback, dummy_callback)
        self.registry.register_watcher('watcher2', dummy_callback, dummy_callback)

        self.assertEqual(len(watch_calls_history), 0)
        self.assertEqual(len(unwatch_calls_history), 0)
        self.registry.watch_fqn('watcher1', 'var:/var/xxx/var1')
        self.assertEqual(len(watch_calls_history), 1)
        self.assertEqual(len(unwatch_calls_history), 0)
        self.registry.watch_fqn('watcher2', 'var:/var/xxx/var1')
        self.assertEqual(len(watch_calls_history), 2)
        self.assertEqual(len(unwatch_calls_history), 0)

        self.assertEqual(watch_calls_history[0], ('watcher1', '/var/xxx/var1', var1.configuration, var1.registry_id))
        self.assertEqual(watch_calls_history[1], ('watcher2', '/var/xxx/var1', var1.configuration, var1.registry_id))

        self.registry.unwatch_fqn('watcher1', 'var:/var/xxx/var1')
        self.assertEqual(len(watch_calls_history), 2)
        self.assertEqual(len(unwatch_calls_history), 1)
        self.registry.unwatch_fqn('watcher2', 'var:/var/xxx/var1')
        self.assertEqual(len(watch_calls_history), 2)
        self.assertEqual(len(unwatch_calls_history), 2)

        self.assertEqual(unwatch_calls_history[0], ('watcher1', '/var/xxx/var1', var1.configuration, var1.registry_id))
        self.assertEqual(unwatch_calls_history[1], ('watcher2', '/var/xxx/var1', var1.configuration, var1.registry_id))

    def test_change_counter(self):
        self.assertEqual(self.registry.get_change_counters(), {
            sdk.WatchableType.Variable: 0,
            sdk.WatchableType.RuntimePublishedValue: 0,
            sdk.WatchableType.Alias: 0
        })
        self.registry.write_content({sdk.WatchableType.Variable: DUMMY_DATASET_VAR})
        self.assertEqual(self.registry.get_change_counters(), {
            sdk.WatchableType.Variable: 1,
            sdk.WatchableType.RuntimePublishedValue: 0,
            sdk.WatchableType.Alias: 0
        })

        self.registry.write_content({sdk.WatchableType.Alias: DUMMY_DATASET_ALIAS})
        self.assertEqual(self.registry.get_change_counters(), {
            sdk.WatchableType.Variable: 1,
            sdk.WatchableType.RuntimePublishedValue: 0,
            sdk.WatchableType.Alias: 1
        })

        self.registry.write_content({sdk.WatchableType.RuntimePublishedValue: DUMMY_DATASET_RPV})
        self.assertEqual(self.registry.get_change_counters(), {
            sdk.WatchableType.Variable: 1,
            sdk.WatchableType.RuntimePublishedValue: 1,
            sdk.WatchableType.Alias: 1
        })

        self.registry.clear_content_by_type(sdk.WatchableType.RuntimePublishedValue)
        self.assertEqual(self.registry.get_change_counters(), {
            sdk.WatchableType.Variable: 1,
            sdk.WatchableType.RuntimePublishedValue: 2,
            sdk.WatchableType.Alias: 1
        })

        self.registry.write_content({sdk.WatchableType.RuntimePublishedValue: DUMMY_DATASET_RPV})
        self.assertEqual(self.registry.get_change_counters(), {
            sdk.WatchableType.Variable: 1,
            sdk.WatchableType.RuntimePublishedValue: 3,
            sdk.WatchableType.Alias: 1
        })

        self.registry.clear()
        self.assertEqual(self.registry.get_change_counters(), {
            sdk.WatchableType.Variable: 2,
            sdk.WatchableType.RuntimePublishedValue: 4,
            sdk.WatchableType.Alias: 2
        })

        self.registry.write_content(All_DUMMY_DATA)
        self.assertEqual(self.registry.get_change_counters(), {
            sdk.WatchableType.Variable: 3,
            sdk.WatchableType.RuntimePublishedValue: 5,
            sdk.WatchableType.Alias: 3
        })

    def test_get_stats(self):
        self.registry.write_content(All_DUMMY_DATA)
        self.registry.register_watcher('watcher1', lambda *x, **y: None, lambda *x, **y: None)
        self.registry.register_watcher('watcher2', lambda *x, **y: None, lambda *x, **y: None)

        var1fqn = f'var:/var/xxx/var1'
        var2fqn = f'var:/var/xxx/var2'
        var3fqn = f'var:/var/var3'
        self.registry.watch_fqn('watcher1', var1fqn)
        self.registry.watch_fqn('watcher2', var1fqn)
        self.registry.watch_fqn('watcher2', var2fqn)
        self.registry.watch_fqn('watcher1', var3fqn)

        stats = self.registry.get_stats()
        self.assertEqual(stats.var_count, len(DUMMY_DATASET_VAR))
        self.assertEqual(stats.alias_count, len(DUMMY_DATASET_ALIAS))
        self.assertEqual(stats.rpv_count, len(DUMMY_DATASET_RPV))
        self.assertEqual(stats.registered_watcher_count, 2)
        self.assertEqual(stats.watched_entries_count, 3)

    def test_unregister_on_clear(self):
        self.registry.write_content(All_DUMMY_DATA)

        watcher_unwatch_list = {
            'watcher1': [],
            'watcher2': [],
        }

        def watcher_unwatch_callback(watcher_id, fqn: str, config: sdk.BriefWatchableConfiguration, registry_id: int):
            watcher_unwatch_list[watcher_id].append(fqn)

        self.registry.register_watcher('watcher1', lambda *x, **y: None, watcher_unwatch_callback)
        self.registry.register_watcher('watcher2', lambda *x, **y: None, watcher_unwatch_callback)

        global_watch_callback_list: List[Tuple[str, str]] = []
        global_unwatch_callback_list: List[Tuple[str, str]] = []

        def watch_callback(watcher_id: str, server_path: str, watchable_config: sdk.BriefWatchableConfiguration, registry_id: int):
            global_watch_callback_list.append((watcher_id, server_path))

        def unwatch_callback(watcher_id: str, server_path: str, watchable_config: sdk.BriefWatchableConfiguration, registry_id: int):
            global_unwatch_callback_list.append((watcher_id, server_path))

        self.registry.register_global_watch_callback(watch_callback, unwatch_callback)

        var1fqn = f'var:/var/xxx/var1'
        var2fqn = f'var:/var/xxx/var2'
        alias1fqn = f'alias:/alias/xxx/alias1'
        alias2fqn = f'alias:/alias/alias2'
        self.registry.watch_fqn('watcher1', var1fqn)
        self.registry.watch_fqn('watcher1', alias2fqn)
        self.registry.watch_fqn('watcher2', var1fqn)
        self.registry.watch_fqn('watcher2', var2fqn)
        self.registry.watch_fqn('watcher2', alias1fqn)

        self.assertEqual(self.registry.watched_entries_count(), 4)

        def fqn_to_args(fqn):
            parsed = WatchableRegistry.FQN.parse(fqn)
            return (parsed.watchable_type, parsed.path)

        self.assertEqual(self.registry.node_watcher_count(*fqn_to_args(var1fqn)), 2)
        self.assertEqual(self.registry.node_watcher_count(*fqn_to_args(var2fqn)), 1)
        self.assertEqual(self.registry.node_watcher_count(*fqn_to_args(alias1fqn)), 1)
        self.assertEqual(self.registry.node_watcher_count(*fqn_to_args(alias2fqn)), 1)

        self.assertEqual(len(global_watch_callback_list), 5)
        self.assertCountEqual(global_watch_callback_list, [
            ('watcher1', WatchableRegistry.FQN.parse(var1fqn).path),
            ('watcher1', WatchableRegistry.FQN.parse(alias2fqn).path),
            ('watcher2', WatchableRegistry.FQN.parse(var1fqn).path),
            ('watcher2', WatchableRegistry.FQN.parse(var2fqn).path),
            ('watcher2', WatchableRegistry.FQN.parse(alias1fqn).path)
        ])

        self.assertEqual(len(global_unwatch_callback_list), 0)
        self.assertEqual(len(watcher_unwatch_list['watcher1']), 0)
        self.assertEqual(len(watcher_unwatch_list['watcher2']), 0)
        global_watch_callback_list.clear()

        self.registry.clear_content_by_type(sdk.WatchableType.Alias)
        self.assertCountEqual(global_unwatch_callback_list, [
            ('watcher1', WatchableRegistry.FQN.parse(alias2fqn).path),
            ('watcher2', WatchableRegistry.FQN.parse(alias1fqn).path)
        ])
        self.assertCountEqual(watcher_unwatch_list['watcher1'], [alias2fqn])
        self.assertCountEqual(watcher_unwatch_list['watcher2'], [alias1fqn])
        global_unwatch_callback_list.clear()
        watcher_unwatch_list['watcher1'].clear()
        watcher_unwatch_list['watcher2'].clear()

        self.assertEqual(self.registry.node_watcher_count(*fqn_to_args(var1fqn)), 2)
        self.assertEqual(self.registry.node_watcher_count(*fqn_to_args(var2fqn)), 1)
        with self.assertRaises(WatchableRegistryNodeNotFoundError):
            self.registry.node_watcher_count(*fqn_to_args(alias1fqn))
        with self.assertRaises(WatchableRegistryNodeNotFoundError):
            self.registry.node_watcher_count(*fqn_to_args(alias2fqn))

        self.registry.clear_content_by_type(sdk.WatchableType.Variable)
        self.assertCountEqual(global_unwatch_callback_list, [
            ('watcher1', WatchableRegistry.FQN.parse(var1fqn).path),
            ('watcher2', WatchableRegistry.FQN.parse(var1fqn).path),
            ('watcher2', WatchableRegistry.FQN.parse(var2fqn).path)
        ])
        self.assertCountEqual(watcher_unwatch_list['watcher1'], [var1fqn])
        self.assertCountEqual(watcher_unwatch_list['watcher2'], [var1fqn, var2fqn])
        global_unwatch_callback_list.clear()

        with self.assertRaises(WatchableRegistryNodeNotFoundError):
            self.assertEqual(self.registry.node_watcher_count(*fqn_to_args(var1fqn)), 0)
        with self.assertRaises(WatchableRegistryNodeNotFoundError):
            self.assertEqual(self.registry.node_watcher_count(*fqn_to_args(var2fqn)), 0)
        with self.assertRaises(WatchableRegistryNodeNotFoundError):
            self.assertEqual(self.registry.node_watcher_count(*fqn_to_args(alias1fqn)), 0)
        with self.assertRaises(WatchableRegistryNodeNotFoundError):
            self.assertEqual(self.registry.node_watcher_count(*fqn_to_args(alias2fqn)), 0)

    def test_bidirectional_map(self):
        m = ServerRegistryBidirectionalMap()
        self.assertEqual(len(m), 0)
        m.map(123, 'hello')
        self.assertEqual(len(m), 1)
        self.assertEqual(m.get_registry_id('hello'), 123)
        self.assertEqual(m.get_server_id(123), 'hello')
        self.assertIsNone(m.get_registry_id_or_none('aaa'))
        self.assertIsNone(m.get_server_id_or_none(100))

        with self.assertRaises(KeyError):
            m.get_server_id(100)
        with self.assertRaises(KeyError):
            m.get_registry_id('idontexist')

        m.map(100, 'iexist')
        self.assertEqual(len(m), 2)

        self.assertEqual(m.get_registry_id('hello'), 123)
        self.assertEqual(m.get_server_id(123), 'hello')

        self.assertEqual(m.get_registry_id('iexist'), 100)
        self.assertEqual(m.get_server_id(100), 'iexist')

        m.unmap_by_registry_id(123)
        self.assertEqual(len(m), 1)
        self.assertIsNone(m.get_registry_id_or_none('hello'))
        self.assertIsNone(m.get_server_id_or_none(123))

        self.assertEqual(m.get_registry_id('iexist'), 100)
        self.assertEqual(m.get_server_id(100), 'iexist')

        m.unmap_by_server_id('iexist')
        self.assertEqual(len(m), 0)
        self.assertIsNone(m.get_registry_id_or_none('iexist'))
        self.assertIsNone(m.get_server_id_or_none(100))

        m.map(1, 'aaa')
        m.map(2, 'bbb')
        m.map(3, 'ccc')

        self.assertEqual(len(m), 3)
        m.clear()
        self.assertEqual(len(m), 0)
        self.assertIsNone(m.get_server_id_or_none(1))
        self.assertIsNone(m.get_server_id_or_none(2))
        self.assertIsNone(m.get_server_id_or_none(3))
        self.assertIsNone(m.get_registry_id_or_none('aaa'))
        self.assertIsNone(m.get_registry_id_or_none('bbb'))
        self.assertIsNone(m.get_registry_id_or_none('ccc'))

    def tearDown(self):
        super().tearDown()
