#    elf2varmap.py
#        CLI Command to read and .elf file and generate a Scrutiny VarMap file that will be
#        included into the Firmware Description File.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2022 Scrutiny Debugger

__all__ = ['Elf2VarMap']

import argparse
import os
import logging

from .base_command import BaseCommand
from scrutiny.tools.typing import *


class Elf2VarMap(BaseCommand):
    _cmd_name_ = 'elf2varmap'
    _brief_ = 'Extract the variables definition from an ELF file through DWARF debugging symbols.'
    _group_ = 'Build Toolchain'

    args: List[str]
    parser: argparse.ArgumentParser

    def __init__(self, args: List[str], requested_log_level: Optional[str] = None):
        self.args = args
        self.parser = argparse.ArgumentParser(prog=self.get_prog())
        self.parser.add_argument('file', help='The ELF file to read')
        self.parser.add_argument('--cppfilt', default=None, help='The path to the c++filt demangler used when parsing a binary produced by GCC')
        self.parser.add_argument('--output', default=None, help='The varmap output file. Will go to STDOUT if not set')
        self.parser.add_argument('--indent', default=4, type=int, help='Number of spaces for JSON indentation')
        self.parser.add_argument('--cu_ignore_patterns', nargs="*", default=[], help='List of compile unit to ignore. Can be a filename or a glob pattern ')
        self.parser.add_argument('--path_ignore_patterns', nargs="*", default=[], help='List of variable paths to be ignored. Can be a glob pattern. example: /static/main.cpp/namespace1/*')

    def run(self) -> Optional[int]:
        from scrutiny.core.bintools.elf_dwarf_var_extractor import ElfDwarfVarExtractor

        args = self.parser.parse_args(self.args)
        extractor = ElfDwarfVarExtractor(args.file, 
                                         cppfilt=args.cppfilt, 
                                         ignore_cu_patterns=args.cu_ignore_patterns,
                                         path_ignore_patterns=args.path_ignore_patterns,
                                         )
        varmap = extractor.get_varmap()

        if args.output is None:
            print(varmap.get_json())
        else:
            if os.path.isdir(args.output):
                output_file = os.path.join(args.output, 'varmap.json')
            else:
                output_file = args.output

            if os.path.isfile(output_file):
                logging.warning('File %s already exist. Overwritting' % output_file)

            varmap.write(output_file, indent=args.indent)
            self.getLogger().info(f"Varmap file {output_file} written")

        return 0
