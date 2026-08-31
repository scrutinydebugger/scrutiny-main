

from test.gui.base_gui_test import ScrutinyBaseGuiTest
from scrutiny.gui.tools.signal_throttler import SignalThrottler
import time
from scrutiny.tools import MutableInt


class TestGUITools(ScrutinyBaseGuiTest):
    def test_signal_throttler(self):
        callcount = MutableInt(0)

        def func():
            callcount.val += 1

        throttler = SignalThrottler(1000)
        throttler.triggered.connect(func)

        def request():
            throttler.request()
            self.process_events()

        request()
        self.assertEqual(callcount.val, 1)
        request()
        request()
        request()
        self.assertEqual(callcount.val, 1)
        self.wait_with_event(1)
        self.assertEqual(callcount.val, 2)
        request()
        request()
        request()
        self.assertEqual(callcount.val, 2)
        self.wait_with_event(1)
        self.assertEqual(callcount.val, 3)
