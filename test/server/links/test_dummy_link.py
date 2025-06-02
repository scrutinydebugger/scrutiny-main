#    test_dummy_link.py
#        Make sure that dummy links transfer data and that global channels works (to simulate
#        switching of channels)
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2022 Scrutiny Debugger

from scrutiny.server.device.links.dummy_link import *
from test import ScrutinyUnitTest


class TestDummyLinkBaseClass():
    def __init__(self, test_class):
        self.TEST_CLASS = test_class

    def test_basic(self):

        link = self.TEST_CLASS.make()
        payload1 = 'hello'.encode('ascii')
        payload2 = 'potato'.encode('ascii')
        link.write(payload1)
        self.assertEqual(link.emulate_device_read(), payload1)
        self.assertEqual(link.emulate_device_read(), bytes())
        self.assertEqual(link.read(timeout=0), bytes())

        link.emulate_device_write(payload2)
        self.assertEqual(link.read(timeout=0), payload2)
        self.assertEqual(link.read(timeout=0), bytes())
        self.assertEqual(link.emulate_device_read(), bytes())

    def test_global_channels(self):
        config = {'channel_id': 1}
        payload1 = 'hello'.encode('ascii')
        payload2 = 'potato'.encode('ascii')

        link1 = self.TEST_CLASS.make(config)
        link2 = self.TEST_CLASS.make(config)
        link1.write(payload1)
        self.assertEqual(link2.emulate_device_read(), payload1)

        self.assertEqual(link1.emulate_device_read(), bytes())
        self.assertEqual(link2.emulate_device_read(), bytes())
        self.assertEqual(link1.read(timeout=0), bytes())
        self.assertEqual(link2.read(timeout=0), bytes())

        link1.emulate_device_write(payload2)
        self.assertEqual(link2.read(timeout=0), payload2)

        self.assertEqual(link1.read(timeout=0), bytes())
        self.assertEqual(link2.read(timeout=0), bytes())
        self.assertEqual(link1.emulate_device_read(), bytes())
        self.assertEqual(link2.emulate_device_read(), bytes())

    def test_global_channels_no_interference(self):
        config1 = {'channel_id': 1}
        config2 = {'channel_id': 2}
        payload1 = 'hello'.encode('ascii')
        payload2 = 'potato'.encode('ascii')

        link1 = self.TEST_CLASS.make(config1)
        link2 = self.TEST_CLASS.make(config2)

        link1.write(payload1)
        self.assertEqual(link2.emulate_device_read(), bytes())
        self.assertEqual(link1.emulate_device_read(), payload1)

        self.assertEqual(link1.emulate_device_read(), bytes())
        self.assertEqual(link2.emulate_device_read(), bytes())
        self.assertEqual(link1.read(timeout=0), bytes())
        self.assertEqual(link2.read(timeout=0), bytes())

        link2.write(payload2)
        self.assertEqual(link2.emulate_device_read(), payload2)
        self.assertEqual(link1.emulate_device_read(), bytes())

        self.assertEqual(link1.emulate_device_read(), bytes())
        self.assertEqual(link2.emulate_device_read(), bytes())
        self.assertEqual(link1.read(timeout=0), bytes())
        self.assertEqual(link2.read(timeout=0), bytes())


class TestDummyLink(ScrutinyUnitTest, TestDummyLinkBaseClass):
    def __init__(self, *args, **kwargs):
        TestDummyLinkBaseClass.__init__(self, test_class=DummyLink)
        ScrutinyUnitTest.__init__(self, *args, **kwargs)


if __name__ == '__main__':
    import unittest
    unittest.main()
