__all__ = [ 'Attrs', 'Tags', 'DwarfEncoding', 'TypeOfVar', 'Architecture', 'Compiler']

from enum import Enum, auto
from scrutiny.core.basic_types import *
from scrutiny.tools.typing import *

class Attrs:
    DW_AT_declaration = 'DW_AT_declaration'
    DW_AT_comp_dir = 'DW_AT_comp_dir'
    DW_AT_specification = 'DW_AT_specification'
    DW_AT_abstract_origin = 'DW_AT_abstract_origin'
    DW_AT_name = 'DW_AT_name'
    DW_AT_linkage_name = 'DW_AT_linkage_name'
    DW_AT_MIPS_linkage_name = 'DW_AT_MIPS_linkage_name'
    DW_AT_external = 'DW_AT_external'
    DW_AT_byte_size = 'DW_AT_byte_size'
    DW_AT_encoding = 'DW_AT_encoding'
    DW_AT_const_value = 'DW_AT_const_value'
    DW_AT_type = 'DW_AT_type'
    DW_AT_data_member_location = 'DW_AT_data_member_location'
    DW_AT_bit_offset = 'DW_AT_bit_offset'
    DW_AT_bit_size = 'DW_AT_bit_size'
    DW_AT_data_bit_offset = 'DW_AT_data_bit_offset'
    DW_AT_location = 'DW_AT_location'
    DW_AT_MIPS_fde = 'DW_AT_MIPS_fde'
    DW_AT_producer = 'DW_AT_producer'
    DW_AT_count = 'DW_AT_count'
    DW_AT_upper_bound = 'DW_AT_upper_bound'
    DW_AT_lower_bound = 'DW_AT_lower_bound'


class Tags:
    DW_TAG_structure_type = 'DW_TAG_structure_type'
    DW_TAG_enumeration_type = 'DW_TAG_enumeration_type'
    DW_TAG_union_type = 'DW_TAG_union_type'
    DW_TAG_compile_unit = 'DW_TAG_compile_unit'
    DW_TAG_variable = 'DW_TAG_variable'
    DW_TAG_enumerator = 'DW_TAG_enumerator'
    DW_TAG_base_type = 'DW_TAG_base_type'
    DW_TAG_class_type = 'DW_TAG_class_type'
    DW_TAG_array_type = 'DW_TAG_array_type'
    DW_TAG_pointer_type = 'DW_TAG_pointer_type'
    DW_TAG_member = 'DW_TAG_member'
    DW_TAG_inheritance = 'DW_TAG_inheritance'
    DW_TAG_typedef = 'DW_TAG_typedef'
    DW_TAG_subrange_type = 'DW_TAG_subrange_type'
    DW_TAG_subroutine_type = 'DW_TAG_subroutine_type'
    DW_TAG_subprogram = 'DW_TAG_subprogram'
    DW_TAG_unspecified_type = 'DW_TAG_unspecified_type'
    DW_TAG_formal_parameter = 'DW_TAG_formal_parameter'
    DW_TAG_namespace = 'DW_TAG_namespace'


class DwarfEncoding(Enum):
    DW_ATE_address = 0x1
    DW_ATE_boolean = 0x2
    DW_ATE_complex_float = 0x3
    DW_ATE_float = 0x4
    DW_ATE_signed = 0x5
    DW_ATE_signed_char = 0x6
    DW_ATE_unsigned = 0x7
    DW_ATE_unsigned_char = 0x8
    DW_ATE_imaginary_float = 0x9
    DW_ATE_packed_decimal = 0xa
    DW_ATE_numeric_string = 0xb
    DW_ATE_edited = 0xc
    DW_ATE_signed_fixed = 0xd
    DW_ATE_unsigned_fixed = 0xe
    DW_ATE_decimal_float = 0xf
    DW_ATE_UTF = 0x10
    DW_ATE_lo_user = 0x80
    DW_ATE_hi_user = 0xff


class TypeOfVar(Enum):
    BaseType = auto()
    Struct = auto()
    Class = auto()
    Union = auto()
    Pointer = auto()
    Array = auto()
    EnumOnly = auto()  # Clang dwarf v2
    Subroutine = auto()  # Clang dwarf v2
    Void = auto()


class Architecture(Enum):
    UNKNOWN = auto()
    TI_C28x = auto()


class Compiler(Enum):
    UNKNOWN = auto()
    TI_C28_CGT = auto()
    CLANG = auto()
    GCC = auto()
    Tasking = auto()
    IAR_ICC = auto()
    RUSTC = auto()

    def linkage_name_gives_path(self) -> bool:
        if self == Compiler.RUSTC:
            return False
        return True

    
# endregion