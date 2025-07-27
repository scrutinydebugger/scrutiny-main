
import unittest

from scrutiny.server.device.links import  canbus_link
import os
import can 
from can.interfaces.socketcan import SocketcanBus
from test import ScrutinyUnitTest
from scrutiny.tools.typing import *
import time
import random

TEST_VCAN = os.environ.get('UNITTEST_VCAN', 'vcan0')

def _check_vcan_possible():
    try:
        bus = SocketcanBus(TEST_VCAN)
        bus.shutdown()
        return (True, "")
    except OSError as e:
        return (False, f"Cannot use interface {TEST_VCAN} for testing. {str(e)}")


_vcan_possible, _vcan_impossible_reason = _check_vcan_possible()

def socketcan_vcan0_config() ->canbus_link.CanBusConfigDict:
    return  {
        'interface' : 'socketcan',
        'rxid' : 0x123,
        'txid' : 0x456,
        'extended_id' : False,
        'fd'  : False,
        'bitrate_switch': False,
        'subconfig' : {
            'channel' : 'vcan0',
        }
    }


class TestCanbusLink(ScrutinyUnitTest):
    bus:can.BusABC
    link:Optional[canbus_link.CanBusLink]

    def setUp(self):
        self.bus = None
        self.link = None
        try:
            self.bus = SocketcanBus(TEST_VCAN)
        except Exception:
            pass

    def tearDown(self) -> None:
        if self.bus is not None:
            self.bus.shutdown()
        if self.link is not None:
            self.link.destroy()
        return super().tearDown()

    def test_config(self):
        def base () -> canbus_link.CanBusConfigDict:
            return {
            'interface' : 'socketcan',
            'rxid' : 0x123,
            'txid' : 0x456,
            'extended_id' : False,
            'fd'  : False,
            'bitrate_switch' : False,
            'subconfig' : {
                'channel' : 'vcan0'
            }
        }
        config = canbus_link.CanBusConfig.from_dict(base())
        self.assertEqual(config.interface, 'socketcan')
        self.assertEqual(config.rxid, 0x123)
        self.assertEqual(config.txid, 0x456)
        self.assertEqual(config.extended_id, False)
        self.assertEqual(config.fd, False)
        self.assertIsInstance(config.subconfig, canbus_link.SocketCanSubConfig)
        self.assertEqual(config.subconfig.channel, 'vcan0')
        
        self.assertEqual(base(), config.to_dict())

        for k in  ['interface', 'rxid', 'txid', 'extended_id', 'subconfig', 'fd']:
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
            'channel' : 1,
            'bitrate' : 500000
        }
        config = canbus_link.CanBusConfig.from_dict(d)
        self.assertIsInstance(config.subconfig, canbus_link.VectorSubConfig)
        self.assertEqual(config.subconfig.channel, 1)
        self.assertEqual(config.subconfig.bitrate, 500000)


    def assert_msg_received(self, data:bytes, timeout:int=1):
        msg = self.bus.recv(timeout=timeout)
        self.assertIsNotNone(msg)
        self.assertEqual(msg.data, data)


    def read_nbytes(self, nbytes:int, timeout:float=1) -> bytes:
        data = bytearray()
        t1 = time.monotonic()
        while len(data) < nbytes:
            new_timeout = max(0, timeout - (time.monotonic() - t1))
            if new_timeout == 0:
                raise TimeoutError(f"Did not received {nbytes} bytes after {timeout} sec")
            msg = self.bus.recv(timeout=new_timeout)
            if msg is not None:
                data += msg.data
        
        return bytes(data)

    @unittest.skipUnless(_vcan_possible, _vcan_impossible_reason)
    def test_read_write(self):
        self.link = canbus_link.CanBusLink(socketcan_vcan0_config())
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

        config = socketcan_vcan0_config()
        self.bus.send(can.Message(arbitration_id=config['rxid'], data=b'ABCDEFGH', is_extended_id=False))
        data = self.link.read(1.0)
        self.assertEqual(data, b'ABCDEFGH')

    @unittest.skipUnless(_vcan_possible, _vcan_impossible_reason)
    def test_detect_broken(self):
        self.link = canbus_link.CanBusLink(socketcan_vcan0_config())
        self.link.initialize()
        self.assertTrue(self.link.operational())
        assert self.link._bus is not None
        self.link._bus.shutdown()
        self.assertFalse(self.link.operational())
    
    @unittest.skipUnless(_vcan_possible, _vcan_impossible_reason)
    def test_message_chunking_can_standard(self):
        
        self.bus.shutdown()
        self.bus = SocketcanBus(TEST_VCAN, fd=True)
        self.bus.shutdown()
        self.bus = SocketcanBus(TEST_VCAN)
    
        self.link = canbus_link.CanBusLink(socketcan_vcan0_config())
        self.link.initialize()

        for i in range(32):
            payload = random.randbytes(i)
            self.link.write(payload)
            payload2 = self.read_nbytes(i)
            self.assertIsNone(self.bus.recv(timeout=0))   # No extra message pending
            self.assertEqual(payload, payload2)

    
    @unittest.skipUnless(_vcan_possible, _vcan_impossible_reason)
    def test_message_chunking_can_fd(self):
        config = socketcan_vcan0_config()
        config['fd'] = True

        self.link = canbus_link.CanBusLink(config)
        self.link.initialize()

        self.bus.shutdown()
        self.bus = SocketcanBus(TEST_VCAN, fd=True)

        for i in range(1024):
            payload = random.randbytes(i)
            self.link.write(payload)
            payload2 = self.read_nbytes(i)
            self.assertIsNone(self.bus.recv(timeout=0))   # No extra message pending
            self.assertEqual(payload, payload2)
        
        self.assertIsNone(self.bus.recv(timeout=0.2))


if __name__ == '__main__':
    unittest.main()
