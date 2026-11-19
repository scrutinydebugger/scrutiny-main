#    codecs.py
#        Contains classes capable of encoding/decoding data exchanged with embedded side
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2022 Scrutiny Debugger

__all__ = [
    'Encodable',
    'BaseCodec',
    'SIntCodec',
    'UIntCodec',
    'SInt128Codec',
    'UInt128Codec',
    'FloatCodec',
    'BoolCodec',
    'Codecs'
]

from abc import ABC, abstractmethod
import struct
import math

from scrutiny.core.basic_types import Endianness, EmbeddedDataType
from scrutiny.tools.typing import *

Encodable: TypeAlias = Union[int, float, bool]


class BaseCodec(ABC):
    def __init__(self) -> None:
        pass

    @abstractmethod
    def decode(self, data: Union[bytes, bytearray]) -> Encodable:
        pass

    @abstractmethod
    def encode(self, value: Encodable) -> bytes:
        pass


class SIntCodec(BaseCodec):
    """A codec for signed integer (8/16/32/64 bits)"""

    str_map = {
        1: 'b',
        2: 'h',
        4: 'l',
        8: 'q'
    }

    def __init__(self, size: int, endianness: Endianness) -> None:
        super().__init__()
        if size not in self.str_map:
            raise NotImplementedError(f'Does not support signed int of {size} bytes')
        endianness_char = '<' if endianness == Endianness.Little else '>'
        packer = struct.Struct(endianness_char + self.str_map[size])
        # Precompiled struct with bound methods kept on the instance. Measured faster than struct.pack(fmt) and int.from_bytes
        self._unpack = packer.unpack
        self._pack = packer.pack

    def decode(self, data: Union[bytes, bytearray]) -> int:
        value: int = self._unpack(data)[0]
        return value

    def encode(self, value: Encodable) -> bytes:
        return self._pack(value)


class UIntCodec(BaseCodec):
    """A codec for unsigned integer (8/16/32/64 bits)"""

    str_map = {
        1: 'B',
        2: 'H',
        4: 'L',
        8: 'Q'
    }

    def __init__(self, size: int, endianness: Endianness) -> None:
        super().__init__()
        if size not in self.str_map:
            raise NotImplementedError(f'Does not support unsigned int of {size} bytes')
        endianness_char = '<' if endianness == Endianness.Little else '>'
        packer = struct.Struct(endianness_char + self.str_map[size])
        # Precompiled struct with bound methods kept on the instance. Measured faster than struct.pack(fmt) and int.from_bytes
        self._unpack = packer.unpack
        self._pack = packer.pack

    def decode(self, data: Union[bytes, bytearray]) -> int:
        value: int = self._unpack(data)[0]
        return value

    def encode(self, value: Encodable) -> bytes:
        return self._pack(value)


class SInt128Codec(SIntCodec):
    """A codec for signed 128 bits integer. struct has no 128 bits format, int.from_bytes/to_bytes is the fastest option"""

    def __init__(self, size: int, endianness: Endianness) -> None:
        BaseCodec.__init__(self)    # Skip SIntCodec.__init__ which only supports struct formats
        if size != 16:
            raise NotImplementedError(f'SInt128Codec only supports 16 bytes. Got {size}')
        self.byteorder: Literal['little', 'big'] = 'little' if endianness == Endianness.Little else 'big'

    def decode(self, data: Union[bytes, bytearray]) -> int:
        return int.from_bytes(data, self.byteorder, signed=True)

    def encode(self, value: Encodable) -> bytes:
        # Floats are rejected at runtime (AttributeError), same as struct.pack would reject them.
        return value.to_bytes(16, self.byteorder, signed=True)  # type: ignore[union-attr]


class UInt128Codec(UIntCodec):
    """A codec for unsigned 128 bits integer. struct has no 128 bits format, int.from_bytes/to_bytes is the fastest option"""

    def __init__(self, size: int, endianness: Endianness) -> None:
        BaseCodec.__init__(self)    # Skip UIntCodec.__init__ which only supports struct formats
        if size != 16:
            raise NotImplementedError(f'UInt128Codec only supports 16 bytes. Got {size}')
        self.byteorder: Literal['little', 'big'] = 'little' if endianness == Endianness.Little else 'big'

    def decode(self, data: Union[bytes, bytearray]) -> int:
        # signed=False is the default. Not passing the keyword is measurably faster
        return int.from_bytes(data, self.byteorder)

    def encode(self, value: Encodable) -> bytes:
        # Floats are rejected at runtime (AttributeError), same as struct.pack would reject them.
        return value.to_bytes(16, self.byteorder)  # type: ignore[union-attr]


class FloatCodec(BaseCodec):
    """A codec for float (32/64 bits)"""

    str_map = {
        4: 'f',
        8: 'd'
    }

    def __init__(self, size: int, endianness: Endianness) -> None:
        super().__init__()
        if size not in self.str_map:
            raise NotImplementedError(f'Does not support float of {size} bytes')
        endianness_char = '<' if endianness == Endianness.Little else '>'
        self.packstr = endianness_char + self.str_map[size]

    def decode(self, data: Union[bytes, bytearray]) -> float:
        return float(struct.unpack(self.packstr, data)[0])

    def encode(self, value: Encodable) -> bytes:
        return struct.pack(self.packstr, value)


class BoolCodec(UIntCodec):
    """A codec for boolean values"""

    def decode(self, data: Union[bytes, bytearray]) -> bool:
        uint_val = super().decode(data)
        return True if uint_val != 0 else False

    def encode(self, value: Encodable) -> bytes:
        v = 1 if value else 0
        return super().encode(v)


class Codecs:
    """
    Common interface to get the correct codec for a given embedded datatype
    """
    @staticmethod
    def get(vartype: EmbeddedDataType, endianness: Endianness) -> BaseCodec:
        """Return a shared codec instance, created at module load. Codecs are stateless and can be shared."""
        # Keyed by _value_ (int) instead of the Enum member: Enum.__hash__ is a Python function, int hash is native.
        try:
            if endianness is Endianness.Little:
                return _CODECS_LITTLE_ENDIAN[vartype._value_]
            return _CODECS_BIG_ENDIAN[vartype._value_]
        except KeyError:
            raise NotImplementedError(f"No codec defined for variable type {vartype.name}") from None

    @staticmethod
    def _create(vartype: EmbeddedDataType, endianness: Endianness) -> BaseCodec:
        datasize = vartype.get_size_8bits()

        if vartype in (EmbeddedDataType.sint8, EmbeddedDataType.sint16, EmbeddedDataType.sint32, EmbeddedDataType.sint64):
            return SIntCodec(datasize, endianness=endianness)
        elif vartype in (EmbeddedDataType.uint8, EmbeddedDataType.uint16, EmbeddedDataType.uint32, EmbeddedDataType.uint64):
            return UIntCodec(datasize, endianness=endianness)
        elif vartype == EmbeddedDataType.sint128:
            return SInt128Codec(datasize, endianness=endianness)
        elif vartype == EmbeddedDataType.uint128:
            return UInt128Codec(datasize, endianness=endianness)
        elif vartype in (EmbeddedDataType.float64, EmbeddedDataType.float32):
            return FloatCodec(datasize, endianness=endianness)
        elif vartype.is_bool():
            return BoolCodec(datasize, endianness=endianness)
        elif vartype in (EmbeddedDataType.ptr32, EmbeddedDataType.ptr8, EmbeddedDataType.ptr16, EmbeddedDataType.ptr64):
            return UIntCodec(datasize, endianness=endianness)

        raise NotImplementedError(f"No codec defined for variable type {vartype.name}")

    @staticmethod
    def make_value_valid(vartype: EmbeddedDataType, val: Encodable, bitsize: Optional[int] = None) -> Encodable:
        """Clamp a value between the boundaries defined by the embedded data type. Python values are unbound."""

        if not math.isfinite(val):
            raise ValueError("Does not support non-finite values")
        if vartype.is_bool():
            return False if int(val) == 0 else True

        if isinstance(val, bool):
            val = int(val)
        signed = vartype.is_signed()

        if vartype.is_integer() or vartype.is_pointer():
            data_size = vartype.get_size_bit()
            if bitsize is not None:
                data_size = min(data_size, bitsize)
            if data_size <= 0 or data_size > 256:
                raise ValueError(f"Does not support this data size: {data_size} bits")

            val = int(val)
            if signed:
                upper_limit = 1 << (data_size - 1)
                val = min(val, upper_limit - 1)
                val = max(val, -upper_limit)
            else:
                upper_limit = 1 << (data_size)
                val = min(val, upper_limit - 1)
                val = max(val, 0)

        elif vartype.is_float():
            val = float(val)
            if not math.isfinite(val):
                raise ValueError("Float values must be finite")

        return val


def _build_codec_cache(endianness: Endianness) -> Dict[int, BaseCodec]:
    cache: Dict[int, BaseCodec] = {}
    for vartype in EmbeddedDataType:
        try:
            cache[vartype._value_] = Codecs._create(vartype, endianness)
        except NotImplementedError:
            pass    # Unsupported type. Codecs.get() will raise when requested
    return cache


_CODECS_LITTLE_ENDIAN = _build_codec_cache(Endianness.Little)
_CODECS_BIG_ENDIAN = _build_codec_cache(Endianness.Big)
