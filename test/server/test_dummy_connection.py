#    test_dummy_connection.py
#        Test the FakeConnection used for unit tests
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2022 Scrutiny Debugger

import json
import time

from scrutiny.server.api.abstract_client_handler import ClientHandlerMessage
from scrutiny.server.api.dummy_client_handler import DummyConnection, DummyClientHandler
from scrutiny import tools
from test import ScrutinyUnitTest


class TestDummyConnection(ScrutinyUnitTest):

    def test_read_write(self):
        conn = DummyConnection()
        conn.open()

        conn.write_to_server('aaa')
        self.assertEqual('aaa', conn.read_from_client())
        self.assertIsNone(conn.read_from_server())
        self.assertIsNone(conn.read_from_client())

        conn.write_to_client('bbb')
        self.assertEqual('bbb', conn.read_from_server())
        self.assertIsNone(conn.read_from_server())
        self.assertIsNone(conn.read_from_client())

    def test_close_no_write(self):
        conn = DummyConnection()
        conn.close()

        conn.write_to_server('aaa')
        self.assertIsNone(conn.read_from_client())

        conn.open()
        conn.write_to_client('bbb')
        self.assertEqual('bbb', conn.read_from_server())

    def test_id(self):
        conn = DummyConnection('xxx')
        self.assertEqual('xxx', conn.get_id())

        # no duplicates
        connections = set()
        for i in range(10000):
            conn = DummyConnection()
            self.assertNotIn(conn.get_id(), connections)
            connections.add(conn.get_id())


class TestDummyConnectionHandler(ScrutinyUnitTest):
    def setUp(self):

        self.connections = [DummyConnection(), DummyConnection(), DummyConnection()]

        config = {
        }
        for conn in self.connections:
            conn.open()

        self.handler = DummyClientHandler(config)
        self.handler.set_connections(self.connections)
        self.handler.start()

    def wait_handler_recv(self, timeout=0.4):
        t1 = time.monotonic()
        while not self.handler.available():
            if time.monotonic() - t1 >= timeout:
                break
            time.sleep(0.01)

        with tools.SuppressException():
            return self.handler.recv()

    def wait_conn_recv_from_server(self, conn, timeout=0.4):
        t1 = time.monotonic()
        while not conn.from_server_available():
            if time.monotonic() - t1 >= timeout:
                break
            time.sleep(0.01)

        with tools.SuppressException():
            return conn.read_from_server()

    def test_client_to_server(self):
        msg = json.dumps({'a': 'b'})
        self.connections[0].write_to_server(msg)
        container = self.wait_handler_recv()
        self.assertIsNotNone(container)
        self.assertEqual(container.conn_id, self.connections[0].get_id())
        self.assertIn('a', container.obj)
        self.assertEqual('b', container.obj['a'])

        self.assertFalse(self.handler.available())

        msg = json.dumps({'x': 'y'})
        self.connections[2].write_to_server(msg)
        container = self.wait_handler_recv()
        self.assertIsNotNone(container)
        self.assertEqual(container.conn_id, self.connections[2].get_id())
        self.assertIn('x', container.obj)
        self.assertEqual('y', container.obj['x'])
        self.assertFalse(self.handler.available())

    def test_server_to_client(self):
        msg = {'a': 'b'}
        self.handler.send(ClientHandlerMessage(conn_id=self.connections[0].get_id(), obj=msg))
        msg = self.wait_conn_recv_from_server(self.connections[0])
        self.assertIsNotNone(msg)
        obj = json.loads(msg)
        self.assertIn('a', obj)
        self.assertEqual('b', obj['a'])

        self.assertFalse(self.connections[1].from_server_available())
        self.assertFalse(self.connections[2].from_server_available())

    def tearDown(self):
        self.handler.stop()


if __name__ == '__main__':
    import unittest
    unittest.main()
