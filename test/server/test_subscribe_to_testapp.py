#    test_subscribe_to_testapp.py
#        A test suite that request the server to load the SFD of testapp project then tries
#        to subscribe to every single variable possible, including the array. Make sure the
#        pointer/array logic is solid
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

import json
import time
from test import ScrutinyUnitTest
from test.artifacts import get_artifact
from scrutiny.server.api import API
from scrutiny.server.server import ScrutinyServer, ServerConfig
from scrutiny.server.sfd_storage import SFDStorage
from scrutiny.server.api.dummy_client_handler import DummyConnection, DummyClientHandler
from scrutiny.server.datastore.datastore_entry import DatastoreRPVEntry
from scrutiny.core.basic_types import *
from scrutiny.tools.typing import *
from scrutiny.core import path_tools
import itertools
import math


class TestSubscribetoTestApp(ScrutinyUnitTest):

    def setUp(self) -> None:
        super().setUp()
        self.api_conn = None
        self.server=None
        try:
            config: ServerConfig = {
                'autoload_sfd': False,
                'api': {
                    'client_interface_type': 'dummy',
                    'client_interface_config': {}
                },
                'device': {
                    'link_type': 'none',
                    'link_config': {
                    }
                }
            }
            self.server = ScrutinyServer(config)
            self.server.device_handler.expect_no_timeout = True     # Will throw an exception on comm timeout
            self.server.api.handle_unexpected_errors = False        # Will throw an exception if one is raised during request process
            self.api_conn = DummyConnection()
            self.api_conn.open()    # Client
            cast(DummyClientHandler, self.server.api.get_client_handler()).set_connections([self.api_conn])
            self.server.init()  # Server
            self.wait_and_load_response(cmd=API.Command.Api2Client.WELCOME)
        except Exception:
            self.tearDown()
            raise
        
    def tearDown(self) -> None:
        if self.server is not None:
            self.server.close_all()
        if self.api_conn is not None:
            self.api_conn.close()

        super().tearDown()
    def wait_for_response(self, timeout=0.4):
        t1 = time.monotonic()
        self.server.process()
        while not self.api_conn.from_server_available():
            if (time.monotonic() - t1) >= timeout:
                break
            self.server.process()
            time.sleep(0.01)

        return self.api_conn.read_from_server()

    def wait_and_load_response(self, cmd=None, nbr=1, timeout=1, ignore_error=False):
        response = None
        t1 = time.monotonic()
        rcv_counter = 0
        while rcv_counter < nbr:
            new_timeout = max(0, timeout - (time.monotonic() - t1))
            json_str = self.wait_for_response(timeout=new_timeout)
            self.assertIsNotNone(json_str)
            response = json.loads(json_str)
            if cmd is None:
                rcv_counter += 1
            else:
                if isinstance(cmd, str):
                    cmd = [cmd]

                if not ignore_error:
                    if API.Command.Api2Client.ERROR_RESPONSE not in cmd and response['cmd'] == API.Command.Api2Client.ERROR_RESPONSE:
                        return response
                self.assertIn('cmd', response)
                if response['cmd'] in cmd:
                    rcv_counter += 1

        self.assertIsNotNone(response)
        return response

    def wait_true(self, func, timeout):
        t1 = time.monotonic()
        self.server.process()
        result = False
        while time.monotonic() - t1 < timeout:
            self.server.process()
            result = func()
            if result:
                break
            time.sleep(0.01)
        if not result:
            raise TimeoutError("Condition have not been fulfilled within %f sec" % timeout)

    def make_api_call(self, msg) -> None:
        self.api_conn.write_to_server(json.dumps(msg))

    def test_subscribe_to_all_testapp_var_from_api(self):
        with SFDStorage.use_temp_folder():
            test_sfd_filename = get_artifact('testapp_20260214.sfd')
            sfd = SFDStorage.install(test_sfd_filename)

            self.server.datastore.add_entries([  # There are aliases to those in the test .sfd
                DatastoreRPVEntry('/rpv/x5000', RuntimePublishedValue(0x5000, EmbeddedDataType.boolean)),
                DatastoreRPVEntry('/rpv/x5001', RuntimePublishedValue(0x5001, EmbeddedDataType.uint16)),
            ])

            self.server.process()

            self.make_api_call({
                'cmd': API.Command.Client2Api.LOAD_SFD,
                'firmware_id': sfd.get_firmware_id_ascii()
            })

            self.wait_true(lambda *args, **kwargs: self.server.sfd_handler.get_loaded_sfd() is not None, timeout=2)
            self.assertEqual(self.server.sfd_handler.get_loaded_sfd().get_firmware_id_ascii(), sfd.get_firmware_id_ascii())

            self.make_api_call({
                'cmd': API.Command.Client2Api.GET_WATCHABLE_LIST
            })

            all_watchable_path = []
            all_factories = {}
            expected_watched_count = 0

            t1 = time.monotonic()
            timeout = 10
            while True:
                dt = time.monotonic() - t1
                if dt > timeout:
                    raise TimeoutError("Timeout")
                response = self.wait_and_load_response(API.Command.Api2Client.GET_WATCHABLE_LIST_RESPONSE, timeout=2)
                self.assertNotEqual(response['cmd'], API.Command.Api2Client.ERROR_RESPONSE)

                for category in ['var', 'alias']:
                    for watchable in response['content'][category]:
                        all_watchable_path.append(watchable['path'])

                for factory in response['content']['var_factory']:
                    all_factories[factory['path']] = factory['factory_params']

                self.assertIn('done', response)
                if response['done'] == True:
                    break

            expected_watched_count += len(all_watchable_path)
            self.make_api_call({
                'cmd': API.Command.Client2Api.SUBSCRIBE_WATCHABLE,
                'watchables': all_watchable_path
            })

            response = self.wait_and_load_response(API.Command.Api2Client.SUBSCRIBE_WATCHABLE_RESPONSE, timeout=5)
            self.assertNotEqual(response['cmd'], API.Command.Api2Client.ERROR_RESPONSE)

            for path, params in all_factories.items():
                generated_paths = []
                segments = path_tools.make_segments(path)
                array_dims_sorted_by_path = sorted([(path, dims) for path, dims in params['array_nodes'].items()], key=lambda x: x[0])
                segments_position_lookup = [len(path_tools.make_segments(x[0])) - 1 for x in array_dims_sorted_by_path]
                dims_count_lookup = [len(x[1]) for x in array_dims_sorted_by_path]
                dims_iterator: List["range"] = []
                total = 1
                for path, dims in array_dims_sorted_by_path:
                    total *= math.prod(dims)
                if total > 4096:
                    continue  # prevent exploding if the numbers are crazy
                expected_watched_count += total
                for path, dims in array_dims_sorted_by_path:
                    dims_iterator.extend([range(x) for x in dims])

                # Each iteration is a variable with all dimensions in the same list
                # for /aa/bb[2][3]/cc[4].  this will iterate:  (0,0,0), (0,0,1), (0,0,2), (0,0,3), (0,1,0), etc...
                for pos in itertools.product(*dims_iterator):
                    segments_copy = segments.copy()
                    for i in range(len(array_dims_sorted_by_path)):
                        dim_count = dims_count_lookup[i]
                        segment_pos = pos[0:dim_count]
                        pos = pos[dim_count:]
                        segments_copy[segments_position_lookup[i]] += ''.join([f'[{p}]' for p in segment_pos])

                    generated_paths.append(path_tools.join_segments(segments_copy))

                # Subscribe to all generated path from this factory
                self.make_api_call({
                    'cmd': API.Command.Client2Api.SUBSCRIBE_WATCHABLE,
                    'watchables': generated_paths
                })

                response = self.wait_and_load_response(API.Command.Api2Client.SUBSCRIBE_WATCHABLE_RESPONSE, timeout=5)
                self.assertNotEqual(response['cmd'], API.Command.Api2Client.ERROR_RESPONSE)

        total_watched_var = len(self.server.datastore.get_watched_entries_id(WatchableType.Variable))
        total_watched_alias = len(self.server.datastore.get_watched_entries_id(WatchableType.Alias))

        self.assertEqual(expected_watched_count, total_watched_var + total_watched_alias)
