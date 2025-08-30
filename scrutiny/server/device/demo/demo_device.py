
from scrutiny.server.device.emulated_device import EmulatedDevice
from scrutiny.server.device.demo.demo_device_sfd import DemoDeviceSFD

from scrutiny import tools
from scrutiny.tools.typing import *


class DemoDevice(EmulatedDevice):
    sfd:DemoDeviceSFD
    @tools.copy_type(EmulatedDevice.__init__)
    def __init__(self, *args:Any, **kwargs:Any) -> None:
        super().__init__(*args, **kwargs)
        self.sfd = DemoDeviceSFD()
        self.set_firmware_id(self.sfd.get_firmware_id())
    
        self.add_additional_task(self.task_update_mem)

        var_aaa = self.sfd.varmap.get_var('/static/test/aaa')
        self.write_memory(var_aaa.get_address(), var_aaa.encode(0)[0])
    
    def task_update_mem(self) -> None:
        var_aaa = self.sfd.varmap.get_var('/static/test/aaa')
        data = self.read_memory(var_aaa.get_address(), var_aaa.get_size())
        vfloat = var_aaa.decode(data)
        vfloat += 1
        data, _ = var_aaa.encode(vfloat)
        self.write_memory(var_aaa.get_address(), data)
        
