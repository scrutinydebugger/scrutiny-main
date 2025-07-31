#    test_canbus_link.py
#        A test suite for testing the CAN bus communication
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

import unittest

from scrutiny.server.device.links import canbus_link
import os
import can
from can.interfaces.virtual import VirtualBus
from test import ScrutinyUnitTest
from scrutiny.tools.typing import *
import time
import random
import scrutiny.server.device.links.typing as link_typing

VIRTUIAL_CHANNEL_NAME = 'unittest'

def socketcan_config() -> canbus_link.CanBusConfigDict:
    return {
        'interface': 'socketcan',
        'rxid': 0x123,
        'txid': 0x456,
        'extended_id': False,
        'fd': False,
        'bitrate_switch': False,
        'subconfig': {
            'channel': 'can0',
        }
    }

def virtual_config() -> canbus_link.CanBusConfigDict:
    return {
        'interface': 'virtual',
        'rxid': 0x123,
        'txid': 0x456,
        'extended_id': False,
        'fd': False,
        'bitrate_switch': False,
        'subconfig': {
            'channel': VIRTUIAL_CHANNEL_NAME,
        }
    }

class TestCanbusLink(ScrutinyUnitTest):
    bus: can.BusABC
    link: Optional[canbus_link.CanBusLink]

    def setUp(self):
        self.bus = None
        self.link = None
        canbus_link.use_stubbed_canbus_class(False)
        try:
            self.bus = VirtualBus(VIRTUIAL_CHANNEL_NAME)
        except Exception:
            pass

    def tearDown(self) -> None:
        if self.bus is not None:
            self.bus.shutdown()
        if self.link is not None:
            self.link.destroy()
        canbus_link.use_stubbed_canbus_class(False)
        return super().tearDown()

    def test_config(self):
        def base() -> canbus_link.CanBusConfigDict:
            return {
                'interface': 'socketcan',
                'rxid': 0x123,
                'txid': 0x456,
                'extended_id': False,
                'fd': False,
                'bitrate_switch': False,
                'subconfig': {
                    'channel': 'vcan0'
                }
            }
        config = canbus_link.CanBusConfig.from_dict(base())
        self.assertEqual(config.interface, 'socketcan')
        self.assertEqual(config.rxid, 0x123)
        self.assertEqual(config.txid, 0x456)
        self.assertEqual(config.extended_id, False)
        self.assertEqual(config.fd, False)
        self.assertIsInstance(config.subconfig, canbus_link.SocketCanSubconfig)
        self.assertEqual(config.subconfig.channel, 'vcan0')

        self.assertEqual(base(), config.to_dict())

        for k in ['interface', 'rxid', 'txid', 'extended_id', 'subconfig', 'fd']:
            with self.assertRaises(Exception):
                d = base()
                del d[k]
                canbus_link.CanBusConfig.from_dict(d)

        with self.assertRaises(Exception):
            d = base()
            d['interface'] = 'idontexist'
            canbus_link.CanBusConfig.from_dict(d)

        with self.assertRaises(Exception):
            d = base()
            d['ishouldntbehere'] = 'hello'
            canbus_link.CanBusConfig.from_dict(d)

        d = base()
        d['interface'] = 'vector'
        d['subconfig'] = {
            'channel': 1,
            'bitrate': 500000,
            'data_bitrate': 500000
        }
        config = canbus_link.CanBusConfig.from_dict(d)
        self.assertIsInstance(config.subconfig, canbus_link.VectorSubConfig)
        self.assertEqual(config.subconfig.channel, 1)
        self.assertEqual(config.subconfig.bitrate, 500000)

    def assert_msg_received(self, data: bytes, timeout: int = 1):
        msg = self.bus.recv(timeout=timeout)
        self.assertIsNotNone(msg)
        self.assertEqual(msg.data, data)

    def read_nbytes(self, nbytes: int, timeout: float = 1) -> bytes:
        data = bytearray()
        t1 = time.monotonic()
        while len(data) < nbytes:
            new_timeout = max(0, timeout - (time.monotonic() - t1))
            if new_timeout == 0:
                raise TimeoutError(f"Did not received {nbytes} bytes after {timeout} sec")
            msg = self.bus.recv(timeout=new_timeout)
            if msg is not None:
                t1 = time.monotonic()
                data += msg.data

        return bytes(data)

    def test_read_write(self):
        self.link = canbus_link.CanBusLink(virtual_config())
        self.assertFalse(self.link.operational())
        self.assertFalse(self.link.initialized())
        self.link.initialize()
        self.assertTrue(self.link.operational())
        self.assertTrue(self.link.initialized())

        self.link.write(b'asd')
        self.assert_msg_received(b'asd')

        self.link.write(b'123456789abcd')
        self.assert_msg_received(b'12345678')
        self.assert_msg_received(b'9abcd')

        config = virtual_config()
        self.bus.send(can.Message(arbitration_id=config['rxid'], data=b'ABCDEFGH', is_extended_id=False))
        data = self.link.read(1.0)
        self.assertEqual(data, b'ABCDEFGH')

    def test_detect_broken(self):
        self.link = canbus_link.CanBusLink(virtual_config())
        self.link.initialize()
        self.assertTrue(self.link.operational())
        assert self.link._bus is not None
        self.link._bus.shutdown()
        self.assertFalse(self.link.operational())

    def test_message_chunking_can_standard(self):
        self.link = canbus_link.CanBusLink(virtual_config())
        self.link.initialize()

        for i in range(32):
            payload = random.randbytes(i)
            self.link.write(payload)
            payload2 = self.read_nbytes(i)
            self.assertIsNone(self.bus.recv(timeout=0), f"i={i}")   # No extra message pending
            self.assertEqual(payload, payload2, f"i={i}")

    def test_message_chunking_can_fd(self):
        config = virtual_config()
        config['fd'] = True

        self.link = canbus_link.CanBusLink(config)
        self.link.initialize()

        self.bus.shutdown()
        self.bus = VirtualBus(VIRTUIAL_CHANNEL_NAME, protocol=can.CanProtocol.CAN_FD)

        for i in range(1024):
            payload = random.randbytes(i)
            self.link.write(payload)
            payload2 = self.read_nbytes(i)
            self.assertIsNone(self.bus.recv(timeout=0), f"i={i}")   # No extra message pending
            self.assertEqual(payload, payload2, f"i={i}")

        self.assertIsNone(self.bus.recv(timeout=0.2))


    def test_socket_can_bus(self):
        canbus_link.use_stubbed_canbus_class(True)
        config:link_typing.CanBusConfigDict = {
            'interface' : 'socketcan',
            'txid' : 0x100,
            'rxid' : 0x200,
            'fd' : False,
            'extended_id' : False,
            'bitrate_switch' : False,
            'subconfig' : {
                'channel' : 'can0'
            }
            
        }
        link = canbus_link.CanBusLink(config)
        link.initialize()
        bus = link.get_bus()
        self.assertIsInstance(bus, canbus_link.StubbedCanBus)
        assert isinstance(bus, canbus_link.StubbedCanBus)
        kwargs = bus.get_init_kwargs()
        self.assertIn('channel', kwargs)
        self.assertIn(kwargs['channel'], 'can0')


    def test_vector_bus(self):
        canbus_link.use_stubbed_canbus_class(True)
        config:link_typing.CanBusConfigDict = {
            'interface' : 'vector',
            'txid' : 0x100,
            'rxid' : 0x200,
            'fd' : False,
            'extended_id' : False,
            'bitrate_switch' : False,
            'subconfig' : {
                'channel' : 0,
                'bitrate' : 500000,
                'data_bitrate' : 1000000
            }
            
        }
        link = canbus_link.CanBusLink(config)
        link.initialize()
        bus = link.get_bus()
        self.assertIsInstance(bus, canbus_link.StubbedCanBus)
        assert isinstance(bus, canbus_link.StubbedCanBus)
        self.assertEqual(len(bus.get_init_args()), 0)   # Just in case. 
        kwargs = bus.get_init_kwargs()
        self.assertIn('channel', kwargs)
        self.assertIn('bitrate', kwargs)
        self.assertIn('data_bitrate', kwargs)
        self.assertEqual(kwargs['channel'], 0)
        self.assertEqual(kwargs['bitrate'], 500000)
        self.assertEqual(kwargs['data_bitrate'], 1000000)

if __name__ == '__main__':
    unittest.main()
