#    test_invoker.py
#        A test suite to test the cross thread invocation helpers
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2024 Scrutiny Debugger

import threading
import functools
from test.gui.base_gui_test import ScrutinyBaseGuiTest
from scrutiny.gui.tools.invoker import invoke_in_qt_thread_synchronized, CrossThreadInvoker
from scrutiny import tools
import time


class TestInvoker(ScrutinyBaseGuiTest):
    def test_run_in_qt_thread_synchronized(self):
        CrossThreadInvoker.init()
        thread_id = tools.MutableNullableInt(None)

        def func():
            thread_id.val = threading.get_ident()

        finished = threading.Event()

        def thread_func():
            invoke_in_qt_thread_synchronized(func)
            finished.set()

        thread = threading.Thread(target=thread_func, daemon=True)
        thread.start()
        self.wait_true_with_events(finished.is_set, 1)
        self.assertTrue(finished.is_set())
        self.assertEqual(thread_id.val, threading.get_ident())

    def test_stress_test_invoker(self):
        CrossThreadInvoker.init()
        nbthread = 64
        iteration = 50
        threads_ids = [[] for x in range(nbthread)]

        def func(index):
            threads_ids[index].append(threading.get_ident())

        lock = threading.Lock()
        finished_count = tools.MutableInt(0)
        start_event = threading.Event()

        def thread_func(index):
            start_event.wait()
            for i in range(iteration):
                invoke_in_qt_thread_synchronized(functools.partial(func, index))
                with lock:
                    finished_count.val += 1
                time.sleep(0)

        threads = []
        for i in range(nbthread):
            thread = threading.Thread(target=thread_func, args=[i], daemon=True)
            thread.start()
            threads.append(thread)

        wanted_count = iteration * nbthread
        start_event.set()
        self.wait_true_with_events(lambda: finished_count.val == wanted_count, 10)
        self.assertEqual(finished_count.val, wanted_count)
        self.assertEqual(len(threads_ids), nbthread)
        for bucket in threads_ids:
            self.assertEqual(len(bucket), iteration)
            for thread_id in bucket:
                self.assertEqual(thread_id, threading.get_ident())
