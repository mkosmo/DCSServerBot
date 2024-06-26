import argparse
import os
import platform
import sys

__all__ = [
    "COMMAND_LINE_ARGS"
]


COMMAND_LINE_ARGS = None

if not COMMAND_LINE_ARGS:
    program = os.path.basename(sys.argv[0])
    parser = argparse.ArgumentParser(prog=program, description="Welcome to DCSServerBot!",
                                     epilog='If unsure about the parameters, please check the documentation.')
    parser.add_argument('-n', '--node', help='Node name', default=platform.node())
    parser.add_argument('-c', '--config', help='Path to configuration', default='config')
    if program == 'run.py':
        parser.add_argument('-x', '--noupdate', action='store_true', help='Do not autoupdate')
        parser.add_argument('-s', '--secret', action='store_true', help='Reveal all stored passwords')
    elif program == 'update.py':
        parser.add_argument('-d', '--delete', action='store_true', help='remove obsolete local files')
        parser.add_argument('-r', '--no-restart', action='store_true', default=False,
                            help="don't start DCSServerBot after the update")

    COMMAND_LINE_ARGS = parser.parse_args()
