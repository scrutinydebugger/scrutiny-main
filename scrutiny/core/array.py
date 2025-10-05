#    array.py
#        Definition of arrays. Mostly used for parsing DWARF symbols and interpreting ScrutinyPath
#        with arrays information encoded
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

__all__ = [
    'Array',
    'UntypedArray',
    'TypedArray'
]


import math
import abc
from scrutiny.core.basic_types import EmbeddedDataType
from scrutiny.tools.typing import *
from scrutiny.core.struct import Struct


class Array(abc.ABC):
    __slots__ = ('dims', 'element_type_name', '_multipliers')

    dims: Tuple[int, ...]
    element_type_name: str
    _multipliers: Tuple[int, ...]

    def __init__(self, dims: Tuple[int, ...], element_type_name: str) -> None:
        if len(dims) == 0:
            raise ValueError("No dimensions set")
        for dim in dims:
            if dim <= 0:
                raise ValueError("Invalid dimension")

        self.dims = dims
        self.element_type_name = element_type_name
        self._multipliers = tuple([math.prod(dims[i + 1:]) for i in range(len(dims))])    # No need to check boundaries, prod([]) = 1

    @abc.abstractmethod
    def get_element_byte_size(self) -> int:
        raise NotImplementedError("Abstract method")

    def get_element_count(self) -> int:
        """Returns the total number of element in the array"""
        return math.prod(self.dims)

    def get_total_byte_size(self) -> int:
        """Return the total size in bytes of the array"""
        return self.get_element_count() * self.get_element_byte_size()

    def position_of(self, pos: Tuple[int, ...]) -> int:
        """Return the linear index that can be used to address an element based on a N-dimension position"""
        if len(pos) != len(self.dims):
            raise ValueError("Shape mismatch")

        nbdim = len(pos)
        index = 0
        for i in range(nbdim):
            if pos[i] >= self.dims[i] or pos[i] < 0:
                raise ValueError("Index out of bound")
            index += pos[i] * self._multipliers[i]

        return index

    def byte_position_of(self, pos: Tuple[int, ...]) -> int:
        """Return the linear bytes index that can be used to address an element based on a N-dimension position"""
        return self.position_of(pos) * self.get_element_byte_size()


class UntypedArray(Array):
    """Represent an N dimensions embedded array with no type, just a size available"""
    __slots__ = ('element_byte_size',)

    element_byte_size: int

    def __init__(self, dims: Tuple[int, ...], element_byte_size: int, element_type_name: str = "") -> None:
        super().__init__(dims, element_type_name)
        self.element_byte_size = element_byte_size

    def get_element_byte_size(self) -> int:
        """Return the size of a single element in bytes"""
        return self.element_byte_size


class TypedArray(Array):
    """Represent an N dimensions embedded array"""
    __slots__ = ('datatype', )

    datatype: Union["Struct", EmbeddedDataType]

    def __init__(self, dims: Tuple[int, ...], datatype: Union["Struct", EmbeddedDataType], element_type_name: str = "") -> None:
        super().__init__(dims, element_type_name)
        self.datatype = datatype

    def get_element_byte_size(self) -> int:
        """Return the size of a single element in bytes"""
        if isinstance(self.datatype, EmbeddedDataType):
            return self.datatype.get_size_byte()
        if isinstance(self.datatype, Struct):
            if self.datatype.byte_size is not None:
                return self.datatype.byte_size
            raise RuntimeError(f"No element size available for struct {self.datatype.name}")
        raise RuntimeError(f"Unsupported datatype {self.datatype.__class__.__name__}")

    def to_untyped_array(self) -> UntypedArray:
        return UntypedArray(
            self.dims,
            element_byte_size=self.get_element_byte_size(),
            element_type_name=self.element_type_name,
        )
