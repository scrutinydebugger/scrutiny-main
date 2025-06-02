#    uninstall_sfd.py
#        CLI Command to remove a Scrutiny Firmware Description file from the scrutiny storage
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2022 Scrutiny Debugger

__all__ = ['UninstallSFD']

import argparse

from .base_command import BaseCommand
from scrutiny.tools.typing import *


class UninstallSFD(BaseCommand):
    _cmd_name_ = 'uninstall-sfd'
    _brief_ = 'Uninstall a SFD file (Scrutiny Firmware Description) globally for the current user.'
    _group_ = 'Server'

    args: List[str]
    parser: argparse.ArgumentParser

    def __init__(self, args: List[str], requested_log_level: Optional[str] = None):
        self.args = args
        self.parser = argparse.ArgumentParser(prog=self.get_prog())
        self.parser.add_argument('firmwareid', help='Firmware ID of the Scrutiny Firmware Info')
        self.parser.add_argument('--quiet', action="store_true", help='Do not report error if not installed')

    def run(self) -> Optional[int]:
        from scrutiny.server.sfd_storage import SFDStorage
        args = self.parser.parse_args(self.args)
        is_installed = SFDStorage.is_installed(args.firmwareid)
        if is_installed:
            SFDStorage.uninstall(args.firmwareid, ignore_not_exist=args.quiet)
            self.getLogger().info(f"SFD {args.firmwareid} uninstalled")
        else:
            self.getLogger().info(f"SFD {args.firmwareid} was not installed")

        return 0
