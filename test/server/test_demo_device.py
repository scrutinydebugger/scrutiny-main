#    test_demo_device.py
#        A test suite for the demo device
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2025 Scrutiny Debugger

import time
from scrutiny.server.device.demo_device import DemoDevice
from scrutiny.server.device.links.dummy_link import DummyLink
from scrutiny.core.demo_device_sfd import DemoDeviceSFD, DEMO_DEVICE_FIRMWAREID_STR
from scrutiny.core.basic_types import WatchableType, EmbeddedDataType
from test import ScrutinyUnitTest


class TestActiveSFDHandler(ScrutinyUnitTest):

    def test_sfd(self):
        demo_sfd = DemoDeviceSFD()
        aliases = demo_sfd.get_aliases()

        def check_alias(path: str, target: str, wtype: WatchableType):
            self.assertIn(path, aliases)
            uptime_alias = aliases[path]
            self.assertEqual(uptime_alias.target, target)
            self.assertEqual(demo_sfd.get_alias_target_type(uptime_alias, demo_sfd.varmap), wtype)

        check_alias('/Up Time', '/global/device/uptime', WatchableType.Variable)
        check_alias('/Sine Wave', '/global/sinewave_generator/output', WatchableType.Variable)
        check_alias('/Counter/Enable', '/static/main.cpp/counter_enable', WatchableType.Variable)
        check_alias('/Counter/Value', '/static/main.cpp/counter', WatchableType.Variable)
        check_alias('/Alias To RPV2000', '/rpv/x2000', WatchableType.RuntimePublishedValue)
        check_alias('/RPV1000 with gain 1000', '/rpv/x1000', WatchableType.RuntimePublishedValue)

        self.assertEqual(aliases['/RPV1000 with gain 1000'].get_gain(), 1000)

        self.assertEqual(demo_sfd.get_firmware_id_ascii(), DEMO_DEVICE_FIRMWAREID_STR)
        varmap = demo_sfd.varmap

        def check_var(path: str, address: int, dtype: EmbeddedDataType):
            v = varmap.get_var(path)
            self.assertEqual(v.get_address(), address)
            self.assertEqual(v.get_type(), dtype)

        check_var("/static/main.cpp/counter", 0x1000, EmbeddedDataType.float32)
        check_var("/static/main.cpp/counter_enable", 0x1004, EmbeddedDataType.boolean)
        check_var("/global/device/uptime", 0x1008, EmbeddedDataType.uint32)
        check_var("/global/sinewave_generator/output", 0x100c, EmbeddedDataType.float32)
        check_var("/global/sinewave_generator/frequency", 0x1010, EmbeddedDataType.float32)

    def test_device_hold(self):
        link = DummyLink()
        device = DemoDevice(link)
        device.start()
        time.sleep(0.5)
        with device.additional_tasks_lock:
            for task in device.additional_tasks:
                task()
        device.stop()
