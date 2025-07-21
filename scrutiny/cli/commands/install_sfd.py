#    install_sfd.py
#        CLI Command to copy a Scrutiny Firmware Description file into the scrutiny storage
#        so it can be automatically loaded by the server upon connection with a device
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2022 Scrutiny Debugger

__all__ = ['InstallSFD']

import argparse
from .base_command import BaseCommand
from scrutiny.tools.typing import *
from scrutiny import tools


class InstallSFD(BaseCommand):
    _cmd_name_ = 'install-sfd'
    _brief_ = 'Install a SFD file (Scrutiny Firmware Description) globally for the current user so that it can be loaded automatically upon connection with a device.'
    _group_ = 'Server'

    args: List[str]
    parser: argparse.ArgumentParser

    def __init__(self, args: List[str], requested_log_level: Optional[str] = None):
        self.args = args
        self.parser = argparse.ArgumentParser(prog=self.get_prog())
        self.parser.add_argument('file', help='Scrutiny Firmware Description (SFD) file to be installed')
        self.parser.add_argument('-f', action='store_true', help='Do not print a warning if another SFD with the same ID is already installed')

    def run(self) -> Optional[int]:
        from scrutiny.server.sfd_storage import SFDStorage

        args = self.parser.parse_args(self.args)
        try:
            sfd = SFDStorage.install(args.file, args.f)
            self.getLogger().info(f"SFD file {args.file} installed. (ID: {sfd.get_firmware_id_ascii()})")
        except Exception as e:
            tools.log_exception(self.getLogger(), e, f"Failed to install the Scrutiny Firmware Description (SFD) file \"{args.file}\".")
            return 1
        
        return 0
