from scrutiny.sdk.client import ScrutinyClient
from binascii import hexlify

client = ScrutinyClient()
with client.connect('localhost', 8765):
    client.user_command(subfunction=1)  # C++ prints "Hello"
    client.user_command(subfunction=2)  # C++ prints " World"
    response = client.user_command(subfunction=3, data=bytes([0x11, 0x22]))  # C++ prints "Received: 1122"

    print(hexlify(response.data))    # Python prints : "AABBCC"
