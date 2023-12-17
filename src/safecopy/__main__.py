#! /usr/bin/python3
"""
Simple secure file copy.

When you install "safecopy" from PyPI, all the dependencies, including the
client side, are automatically installed.

Copyright 2018-2023 TopDevPros
Last modified: 2023-10-01
"""

import doctest

from .cli import parse_args, show_version, start_safecopy
from .utils import error_exit


def main():
    """
    Main for safecopy.

    >>> from subprocess import run

    >>> PYTHON = 'python3'
    >>> TEST_LENGTH = 5

    >>> def test_safecopy(*args):
    ...     CURRENT_DIR = os.path.realpath(os.path.abspath(os.path.dirname(__file__)))
    ...     safecopy_cmd = os.path.join(CURRENT_DIR, 'safecopy')
    ...     command = [safecopy_cmd, '--verbose'] + list(args)
    ...     log_message(f'safecopy command: {command}')
    ...     run(command)

    >>> def diff(from_path, to_path):
    ...     with open(from_path, 'rb') as from_file:
    ...         with open(to_path, 'rb') as to_file:
    ...             from_data = from_file.read()
    ...             to_data = to_file.read()
    ...     assert from_data == to_data, f'from_data={from_data}, to_data={to_data}'

    >>> def safecopy_check(from_path, to_path):
    ...     test_safecopy(from_path, to_path)
    ...     assert os.path.getsize(from_path) == os.path.getsize(to_path)
    ...     assert os.path.getsize(from_path) == os.path.getsize(to_path)
    ...     diff(from_path, to_path)
    ...     from_stats = os.lstat(from_path)
    ...     to_stats = os.lstat(to_path)
    ...     assert from_stats.st_mtime == to_stats.st_mtime
    ...     assert from_stats.st_mode == to_stats.st_mode

    >>> _, from_path = mkstemp()
    >>> _, to_path = mkstemp()

    >>> with open(from_path, 'wb') as from_file:
    ...     file_length = from_file.write(bytes(range(TEST_LENGTH)))
    >>> file_length == TEST_LENGTH
    True
    >>> os.path.getsize(from_path) == TEST_LENGTH
    True
    >>> safecopy_check(from_path, to_path)

    >>> with open(from_path, 'ab') as from_file:
    ...     _ = from_file.write(b'more')
    >>> safecopy_check(from_path, to_path)

    >>> os.remove(from_path)
    >>> os.remove(to_path)
    """
    parser, args = parse_args()

    if args.test:
        doctest.testmod()

    elif args.version:
        show_version()

    else:
        if len(args.paths) >= 2:
            start_safecopy(args=args)

        else:
            parser.print_help()
            error_exit("need one or more source paths and the destination path")


if __name__ == "__main__":
    main()
