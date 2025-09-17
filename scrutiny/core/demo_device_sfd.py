#    demo_device_sfd.py
#        The Scrutiny Firmware Description file used for demo mode. This SFD is never saved
#        to disk, just loaded in RAM when needed
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

import binascii
from scrutiny.core.firmware_description import FirmwareDescription, SFDMetadata, SFDGenerationInfo
from scrutiny.core.variable import VariableLocation
from scrutiny.core.alias import Alias
from scrutiny.core.basic_types import EmbeddedDataType
from scrutiny.core.varmap import VarMap
from scrutiny.tools.typing import *
import scrutiny

DEMO_DEVICE_FIRMWAREID_STR = "deadbeefc001d00d0ff1cebaadf00d00"


class DemoDeviceSFD(FirmwareDescription):
    def __init__(self) -> None:
        metadata = SFDMetadata(
            project_name="Scrutiny Demo Device",
            author="Scrutiny Debugger",
            version=scrutiny.__version__,
            generation_info=SFDGenerationInfo.make()
        )

        varmap = VarMap()

        varmap.register_base_type("float", EmbeddedDataType.float32)
        varmap.register_base_type("int32", EmbeddedDataType.sint32)
        varmap.register_base_type("uint32", EmbeddedDataType.uint32)
        varmap.register_base_type("bool", EmbeddedDataType.boolean)

        varmap.add_variable(['static', 'main.cpp', "counter"], VariableLocation(0x1000), "float")
        varmap.add_variable(['static', 'main.cpp', "counter_enable"], VariableLocation(0x1004), "bool")

        varmap.add_variable(['global', 'device', "uptime"], VariableLocation(0x1008), "uint32")
        varmap.add_variable(['global', 'sinewave_generator', "output"], VariableLocation(0x100c), "float")
        varmap.add_variable(['global', 'sinewave_generator', "frequency"], VariableLocation(0x1010), "float")

        aliases = [
            Alias("/Up Time", target='/global/device/uptime'),
            Alias("/Sine Wave", target='/global/sinewave_generator/output'),
            Alias("/Counter/Enable", target='/static/main.cpp/counter_enable'),
            Alias("/Counter/Value", target='/static/main.cpp/counter'),
            Alias("/Alias To RPV2000", target='/rpv/x2000'),
            Alias("/RPV1000 with gain 1000", target='/rpv/x1000', gain=1000)
        ]
        super().__init__(firmwareid=binascii.unhexlify(DEMO_DEVICE_FIRMWAREID_STR), varmap=varmap, metadata=metadata)

        self.append_aliases(aliases)
