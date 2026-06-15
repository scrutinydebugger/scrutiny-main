
class OutOfRange(Exception):
    pass


class C2000MemdumpParser:
    """
    Parser for C2000 memory dump files.

    File format:
      @<hex_address>       — starts a new region at that word address
      <word> <word> ...    — space-separated 4-hex-digit 16-bit words

    Each C2000 word is 16 bits. Little-endian encoding maps a C2000 word
    to two Python bytes as [low_byte, high_byte], e.g. word 0xCDAB → [0xAB, 0xCD].
    """

    _memory: dict[int, int]

    def __init__(self, filepath: str):
        # Maps C2000 word address (int) -> 16-bit word value (int)
        self._memory = {}
        self._parse(filepath)

    def _parse(self, filepath: str) -> None:
        current_addr = 0
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if line.startswith('@'):
                    current_addr = int(line[1:], 16)
                else:
                    for word_str in line.split():
                        self._memory[current_addr] = int(word_str, 16)
                        current_addr += 1

    def read_little_endian(self, address: int, size: int) -> bytes:
        """
        Read `size` C2000 words starting at `address`.

        Returns bytes of length size*2. Each C2000 word is encoded as
        [low_byte, high_byte] (little-endian).

        Raises OutOfRange if any address in the range has no data.
        """
        result = bytearray()
        for addr in range(address, address + size):
            if addr not in self._memory:
                raise OutOfRange(f"Address 0x{addr:X} is out of range")
            word = self._memory[addr]
            result.append(word & 0xFF)         # low byte
            result.append((word >> 8) & 0xFF)  # high byte
        return bytes(result)
