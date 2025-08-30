#    demo_device.py
#        Extension of the emulated device used for the demo mode. Runs a fake device with
#        some artificial variables and RPV for the purpose of showcasing the UI
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

from scrutiny.server.device.emulated_device import EmulatedDevice
from scrutiny.server.device.demo.demo_device_sfd import DemoDeviceSFD

from scrutiny import tools
from scrutiny.tools.typing import *


_demo_device_sfd:Optional[DemoDeviceSFD] = None
def _get_demo_sfd():
    global _demo_device_sfd
    if _demo_device_sfd is None:
        _demo_device_sfd = DemoDeviceSFD()
    
    return _demo_device_sfd

class DemoDevice(EmulatedDevice):
    sfd: DemoDeviceSFD

    @tools.copy_type(EmulatedDevice.__init__)
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.sfd = _get_demo_sfd()
        self.set_firmware_id(self.sfd.get_firmware_id())

        self.add_additional_task(self.task_update_mem)
        self.add_forbidden_region(0, 0x1000)
        self.add_forbidden_region(0x2000, 0x100000000-0x2000)
        self.add_readonly_region(0x1800, 0x800)

        self.write_memory(0x1000, bytes([0]*0x1000), check_access_rights=False)

    def task_update_mem(self) -> None:
        var_aaa = self.sfd.varmap.get_var('/static/main.cpp/float_counter')
        data = self.read_memory(var_aaa.get_address(), var_aaa.get_size())
        vfloat = var_aaa.decode(data)
        vfloat += 0.1
        data, _ = var_aaa.encode(vfloat)
        self.write_memory(var_aaa.get_address(), data)
