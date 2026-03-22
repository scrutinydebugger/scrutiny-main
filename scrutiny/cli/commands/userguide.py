__all__ = ['UserGuide']

import argparse

from .base_command import BaseCommand

import scrutiny
from scrutiny import tools
from scrutiny.tools.typing import *


class UserGuide(BaseCommand):
    _cmd_name_ = 'userguide'
    _brief_ = 'Get the Scrutiny user guide'
    _group_ = 'Development'

    parser: argparse.ArgumentParser
    parsed_args: Optional[argparse.Namespace] = None

    def __init__(self, args: List[str], requested_log_level: Optional[str] = None) -> None:
        self.args = args
        self.parser = argparse.ArgumentParser(prog=self.get_prog())
        self.parser.add_argument('action', choices=['show', 'location'], nargs='?', default='show',
                                 help="Action. 'show': Open the guide if available. 'location': Print the user guide location")
        self.parser.add_argument('--nocheck', action='store_true', help="Do not raise an error if the file is missing")

    def run(self) -> Optional[int]:
        import os

        args = self.parser.parse_args(self.args)

        def get_userguide_path_or_maybe_raise() -> str:
            path = scrutiny.expected_user_guide_path()
            if not os.path.isfile(path):
                if not args.nocheck:
                    raise FileNotFoundError(f"No user guide available. Expected path: {path}")
            return path

        if args.action == 'show':
            file = get_userguide_path_or_maybe_raise()
            self.getLogger().info(f"Opening {file}")
            tools.open_file_or_raise(file)
        elif args.action == 'location':
            print(get_userguide_path_or_maybe_raise())
        else:
            raise NotImplementedError(f"Unknown action {args.action}")

        return 0
