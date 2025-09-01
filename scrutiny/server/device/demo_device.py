#    demo_device.py
#        Extension of the emulated device used for the demo mode. Runs a fake device with
#        some artificial variables and RPV for the purpose of showcasing the UI
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

import random
import time
import math

from scrutiny.server.device.emulated_device import EmulatedDevice
from scrutiny.core.demo_device_sfd import DemoDeviceSFD
from scrutiny.core.basic_types import RuntimePublishedValue, EmbeddedDataType
from scrutiny.server.device.device_info import VariableFreqLoop, FixedFreqLoop
from scrutiny.core.codecs import Encodable

from scrutiny import tools
from scrutiny.tools.typing import *


_demo_device_sfd: Optional[DemoDeviceSFD] = None


def _get_demo_sfd() -> DemoDeviceSFD:
    global _demo_device_sfd
    if _demo_device_sfd is None:
        _demo_device_sfd = DemoDeviceSFD()

    return _demo_device_sfd


class DemoDevice(EmulatedDevice):
    sfd: DemoDeviceSFD

    rpv_2000_timer: tools.Timer
    monotonic_start: float
    perf_start: float

    @tools.copy_type(EmulatedDevice.__init__)
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.sfd = _get_demo_sfd()
        self.set_firmware_id(self.sfd.get_firmware_id())
        self.configure_rpvs({
            0x1000: {'definition': RuntimePublishedValue(0x1000, EmbeddedDataType.float32), 'value': 0},
            0x2000: {'definition': RuntimePublishedValue(0x2000, EmbeddedDataType.sint32), 'value': 1}
        })
        self.add_additional_task(self.task_update_mem)
        self.add_additional_task(self.task_update_rpv)
        self.add_forbidden_region(0, 0x1000)
        self.add_forbidden_region(0x2000, 0x100000000 - 0x2000)
        self.add_readonly_region(0x1800, 0x800)

        self.write_memory(0x1000, bytes([0] * 0x1000), check_access_rights=False)

        self._write_var('/global/sinewave_generator/frequency', 1)

        self.configure_loops([VariableFreqLoop("Python thread", support_datalogging=True)])
        self.configure_datalogger(buffer_size=4096)

        self.rpv_2000_timer = tools.Timer(0.5)
        self.rpv_2000_timer.start()
        self.monotonic_start = time.monotonic()
        self.perf_start = time.perf_counter()

    def _read_var(self, path: str) -> Encodable:
        v = self.sfd.varmap.get_var(path)
        data = self.read_memory(v.get_address(), v.get_size())
        return v.decode(data)

    def _write_var(self, path: str, val: Encodable) -> None:
        v = self.sfd.varmap.get_var(path)
        data, _ = v.encode(val)
        self.write_memory(v.get_address(), data)

    def task_update_mem(self) -> None:
        val_enable = cast(bool, self._read_var('/static/main.cpp/counter_enable'))
        if val_enable:
            val_counter = cast(float, self._read_var('/static/main.cpp/counter'))
            val_counter += 0.1
            self._write_var('/static/main.cpp/counter', val_counter)

        uptime = time.monotonic() - self.monotonic_start
        self._write_var('/global/device/uptime', int(round(uptime)))

        sinewave_freq = self._read_var('/global/sinewave_generator/frequency')
        sinewave = math.sin(2 * math.pi * (time.perf_counter() - self.perf_start) * sinewave_freq)
        self._write_var('/global/sinewave_generator/output', sinewave)

    def task_update_rpv(self) -> None:
        if self.rpv_2000_timer.is_timed_out():
            rpv2000_val = self.read_rpv(0x2000)
            newval = 1 if rpv2000_val < 0 else -1
            self.write_rpv(0x2000, newval)
            self.rpv_2000_timer.start()

        self.write_rpv(0x1000, random.random())
