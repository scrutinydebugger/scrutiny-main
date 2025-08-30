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

        varmap.add_variable(['static', 'test'], "aaa", VariableLocation(0x1000), "float")

        super().__init__(firmwareid=binascii.unhexlify(DEMO_DEVICE_FIRMWAREID_STR), varmap=varmap, metadata=metadata)
