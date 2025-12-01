
from scrutiny import sdk
from scrutiny.sdk.client import ScrutinyClient

client = ScrutinyClient()
with client.connect('localhost', 8765):
    # Serial example
    client.configure_device_link(
        link_type=sdk.DeviceLinkType.Serial,
        link_config=sdk.SerialLinkConfig(
            port='COM2',
            baudrate=115200,
            start_delay=0,
            stopbits=sdk.SerialLinkConfig.StopBits.ONE,
            databits=sdk.SerialLinkConfig.DataBits.EIGHT,
            parity=sdk.SerialLinkConfig.Parity.NONE
        )
    )

    # RTT example
    client.configure_device_link(
        link_type=sdk.DeviceLinkType.RTT,
        link_config=sdk.RTTLinkConfig(
            jlink_interface=sdk.RTTLinkConfig.JLinkInterface.SWD,
            target_device='cortex-M0'
        )
    )

    # UDP example
    client.configure_device_link(
        link_type=sdk.DeviceLinkType.UDP,
        link_config=sdk.UDPLinkConfig(
            host='localhost',
            port=12345
        )
    )

    # CAN SocketCAN example
    client.configure_device_link(
        link_type=sdk.DeviceLinkType.CAN,
        link_config=sdk.CANLinkConfig(
            interface=sdk.CANLinkConfig.CANInterface.SocketCAN,
            txid=0x100,
            rxid=0x200,
            bitrate_switch=False,
            fd=False,
            extended_id=False,
            interface_config=sdk.CANLinkConfig.SocketCANConfig(channel="vcan0")
        )
    )

    # CAN Vector example
    client.configure_device_link(
        link_type=sdk.DeviceLinkType.CAN,
        link_config=sdk.CANLinkConfig(
            interface=sdk.CANLinkConfig.CANInterface.Vector,
            txid=0x100,
            rxid=0x200,
            bitrate_switch=False,
            fd=False,
            extended_id=False,
            interface_config=sdk.CANLinkConfig.VectorConfig(
                channel=0,
                bitrate=500000,
                data_bitrate=500000  # Ignored if bitrate_switch = False
            )
        )
    )

    # CAN PCAN example
    client.configure_device_link(
        link_type=sdk.DeviceLinkType.CAN,
        link_config=sdk.CANLinkConfig(
            interface=sdk.CANLinkConfig.CANInterface.PCAN,
            txid=0x100,
            rxid=0x200,
            bitrate_switch=False,
            fd=True,
            extended_id=False,
            interface_config=sdk.CANLinkConfig.PCANConfig(
                channel="channel_name",
                bitrate=500000,
            )
        )
    )
