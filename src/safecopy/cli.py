import os
from argparse import ArgumentParser, Namespace
from glob import glob

from solidlibs.python.elapsed_time import LogElapsedTime

from .actions import copy_files
from .consts import COPYRIGHT, CURRENT_VERSION, LICENSE
from .utils import (
    delay,
    delete_files,
    error_exit,
    log,
    log_message,
    parse_paths,
    verbose_log,
)


def show_version():
    """Show safecopy's name and version.

    >>> show_version()
    <BLANKLINE>
    Safecopy 1.3.1
    Copyright 2018-2023 solidlibs
    License: GPLv3
    <BLANKLINE>
    <BLANKLINE>
    """

    details = f"\nSafecopy {CURRENT_VERSION}\n{COPYRIGHT}\nLicense: {LICENSE}\n\n"

    print(details)


def start_safecopy(args: Namespace):
    """Housekeeping, error checking, then start the copy."""
    try:
        from_paths, to_root, to_path = parse_paths(args)

        if args.delete:
            with LogElapsedTime(log, "delete files"):
                delete_files(from_paths, to_path)

        exclude_paths = []
        if args.exclude:
            for exc_path in args.exclude.split(","):
                exclude_paths += glob(exc_path)
            log_message(f"exclude: {exclude_paths}")

        for path in from_paths:
            with LogElapsedTime(log, f"copying {path}"):
                from_path = os.path.abspath(path)
                verbose_log(f"from_path={from_path}")
                # from_root is the part of from_path that is definitely a dir
                # the basename may be a dir or file
                from_root = os.path.dirname(from_path)
                verbose_log(f"from_root={from_root}")

                # If the destination is a dir, the sources are copied into that dir
                if os.path.isdir(to_path):
                    full_to_path = os.path.join(to_path, os.path.basename(from_path))
                else:
                    full_to_path = to_path
                verbose_log(f"full_to_path={full_to_path}")

                copy_files(from_path, full_to_path, from_root, to_root, exclude_paths)

                delay()

    except KeyboardInterrupt:
        log.exception_only()

    except Exception as exc:
        log.exception()
        error_exit(exc)


def parse_args():
    """Parsed command line."""

    parser = ArgumentParser(description="Sync files.")

    parser.add_argument(
        "paths",
        nargs="*",
        help="Copy files to the destination. The last path is the destination.",
    )
    parser.add_argument("--verbose", help="Show progress", action="store_true")
    parser.add_argument(
        "--quick",
        help="Only update files if the size or last modified time is different",
        action="store_true",
    )
    # argparse does not allow dashes in flags, so --dryrun, not rsync's --dry-run
    parser.add_argument(
        "--dryrun",
        help="Show what would be done, but don't do anything",
        action="store_true",
    )
    parser.add_argument(
        "--delete",
        help="Delete all files that are not in the source before copying any files",
        action="store_true",
    )
    parser.add_argument("--nowarn", help="No warnings", action="store_true")
    parser.add_argument(
        "--test",
        help="Run tests. You must use --test to run doctests.",
        action="store_true",
    )
    parser.add_argument(
        "--exclude",
        nargs="?",
        help="Exclude the following files and/or directories (comma separated).",
    )
    parser.add_argument("--verify", help="Verify copies", action="store_true")
    parser.add_argument(
        "--persist",
        help="Continue on errors, except verify error.",
        action="store_true",
    )
    parser.add_argument(
        "--retries",
        help="How many times to retry a failed copy. Default is not to retry",
        type=int,
        default=0,
    )
    parser.add_argument(
        "--version", help="show the product and version number", action="store_true"
    )

    # print(f'type parser args: {parser.parse_args()}')
    return parser, parser.parse_args()
