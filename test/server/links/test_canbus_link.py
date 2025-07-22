
import unittest

from scrutiny.server.device.links import  canbus_link
import os
import can 
from can.interfaces.socketcan import SocketcanBus
from test import ScrutinyUnitTest
from scrutiny.tools.typing import *

TEST_VCAN = os.environ.get('UNITTEST_VCAN', 'vcan0')

def _check_vcan_possible():
    try:
        bus = SocketcanBus(TEST_VCAN)
        bus.shutdown()
        return (True, "")
    except OSError as e:
        return (False, f"Cannot use interface {TEST_VCAN} for testing. {str(e)}")


_vcan_possible, _vcan_impossible_reason = _check_vcan_possible()

socketcan_vcan0_config:canbus_link.CanBusConfigDict = {
    'interface' : 'socketcan',
    'rxid' : 0x123,
    'txid' : 0x456,
    'extended_id' : False,
    'fd'  : False,
    'subconfig' : {
        'channel' : 'vcan0',
    }
}


class TestCanbusLink(ScrutinyUnitTest):
    bus:can.BusABC

    def setUp(self):
        self.bus = None
        try:
            self.bus = SocketcanBus(TEST_VCAN)
        except Exception:
            pass

    def tearDown(self) -> None:
        if self.bus is not None:
            self.bus.shutdown()
        return super().tearDown()

    def test_config(self):
        def base() -> canbus_link.CanBusConfigDict:
            return {
            'interface' : 'socketcan',
            'rxid' : 0x123,
            'txid' : 0x456,
            'extended_id' : False,
            'fd'  : False,
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


    @unittest.skipUnless(_vcan_possible, _vcan_impossible_reason)
    def test_read_write(self):
        link = canbus_link.CanBusLink(socketcan_vcan0_config)
        self.assertFalse(link.operational())
        self.assertFalse(link.initialized())
        link.initialize()
        self.assertTrue(link.operational())
        self.assertTrue(link.initialized())

        link.write(b'asd')
        self.assert_msg_received(b'asd')

        link.write(b'123456789abcd')
        self.assert_msg_received(b'12345678')
        self.assert_msg_received(b'9abcd')

        self.bus.send(can.Message(arbitration_id=socketcan_vcan0_config['rxid'], data=b'ABCDEFGH', is_extended_id=False))
        data = link.read(1.0)
        self.assertEqual(data, b'ABCDEFGH')

    @unittest.skipUnless(_vcan_possible, _vcan_impossible_reason)
    def test_detect_broken(self):
        link = canbus_link.CanBusLink(socketcan_vcan0_config)
        link.initialize()
        self.assertTrue(link.operational())
        assert link._bus is not None
        link._bus.shutdown()
        self.assertFalse(link.operational())

if __name__ == '__main__':
    unittest.main()
