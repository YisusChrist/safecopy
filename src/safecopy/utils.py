from argparse import Namespace
import os
import re
import sys
import time
from glob import glob
from shutil import rmtree

from solidlibs.python.log import Log, get_log_path

try:
    log = Log()
except ImportError:
    log = None


def parse_paths(args: Namespace):
    """
    Parse the paths from args passed on the command line.
    """
    if len(args.paths) <= 1:
        log_message(f"more than one path needed: safecopy SOURCE... DEST; args: {args}")
        error_exit("More than one path needed: safecopy SOURCE... DEST")

    # get from_paths
    from_paths = []
    # the last path is the destination
    for raw_path in args.paths[:-1]:
        if os.path.isfile(raw_path):
            from_paths.append(raw_path.rstrip(os.sep))
        else:
            # expand wildcards in from_paths
            glob_paths = glob_dir(raw_path)
            if not glob_paths:
                if "[" in raw_path or "]" in raw_path:
                    error_exit(
                        f"Path contains wildcard chars, including []: {raw_path}\n  Try passing an arg without []"
                    )
                else:
                    error_exit(f"Unable to un-glob: {raw_path}")
            for path in glob_paths:
                from_paths.append(path.rstrip(os.sep))
    log_message(f"from {from_paths}")

    # the last path is the destination
    to_path = args.paths[-1]
    log_message(f"to {to_path}")

    for path in from_paths:
        if not os.path.exists(path):
            error_exit(f"Source not found: {path}")

    if not os.path.exists(to_path):
        to_path_parent = os.path.dirname(to_path)
        if not os.path.isdir(to_path_parent):
            error_exit(f"Destination directory not found {to_path_parent}")

    if len(from_paths) > 1:
        if not os.path.isdir(to_path):
            error_exit(
                f"With more than one source path, destination must be a dir: {to_path}"
            )

    to_path = os.path.abspath(to_path)
    if os.path.isdir(to_path):
        to_root = to_path
    else:
        to_root = os.path.dirname(to_path)
    log_message(f"to_root={to_root}")

    return from_paths, to_root, to_path


def glob_dir(raw_path):
    """
    Expand wildcards in raw_path.

    This might not handle an arg from the command line
    which includes * or ? *and* also [] because glob.glob()
    considers '[' and ']' wildcard chars
    """

    try:
        glob_paths = glob(raw_path)
    except re.error as re_err:
        glob_paths = None

    if not glob_paths:
        # see if listdir can handle the raw_path
        glob_paths = []
        filenames = os.listdir(raw_path)
        for filename in filenames:
            glob_paths.append(os.path.join(raw_path, filename))

    return glob_paths


def exclude_path(from_path, from_root, exclude_names):
    """Determine if this path should be excluded."""

    exclude = False
    if exclude_names:
        for exclude_name in exclude_names:
            exclude = from_path == os.path.abspath(
                os.path.join(from_root, exclude_name)
            )
            if exclude:
                break

    return exclude


def delete_files(from_paths, to_path):
    """Delete files in to_path that are not in any of the from_paths"""

    def relative_path(path, root):
        return path[len(root) :].strip(os.sep)

    def delete_paths_in_dir():
        """
        Get paths to delete in this dir
        use a list instead of set, so we delete in the expected order
        """

        to_root = os.path.abspath(to_path)
        for dirpath, dirnames, filenames in os.walk(to_root):
            for name in sorted(dirnames + filenames):
                path = os.path.join(dirpath, name)
                to_rel_path = relative_path(path, to_root)
                if to_rel_path not in shared_paths:
                    if args.dryrun:
                        verbose(f"would delete {path}")
                    else:
                        verbose(f"Deleted {path}")
                        delete(path)
                        delay()

    if os.path.isdir(to_path):
        # to do: for speed do as much as possible during the first pass over sources

        # get a list of all shared source paths in the source dirs

        # shouldn't be adding any dups, but set lookups are faster than lists
        shared_paths = set()

        verbose(f"Deleting extraneous files from: {to_path}")
        verbose_log(f"comparing to {from_paths}")
        for from_path in from_paths:
            if os.path.isdir(from_path):
                """Because to_path is a dir, we copy from_path into to_path.
                That means the shared_path must include the from_path
                basename, and so from_root must *not* include the from_path
                basename.
                To do that, from_root is the parent dir of from_path.
                """
                verbose_log(f"checking {from_path} for extraneous files")
                from_root = os.path.dirname(os.path.abspath(from_path))

                for dirpath, dirnames, filenames in os.walk(from_root):
                    for name in dirnames + filenames:
                        path = os.path.join(dirpath, name)
                        from_rel_path = relative_path(path, from_root)
                        shared_paths.add(from_rel_path)

                delete_paths_in_dir()


def delete(path):
    """Delete path.

    If dir, delete all files in dir.
    """

    verbose_log(f"delete {path}")
    if os.path.islink(path):
        os.remove(path)
        log_message(f"after remove, path {path} lexists: {os.path.lexists(path)}")
    elif os.path.isdir(path):
        rmtree(path)
    elif os.path.isfile(path):
        os.remove(path)


def verbose(msg):
    """Print and log verbose message"""

    if args.verbose:
        print(msg)
        log_message(msg)
        sys.stdout.flush()


def verbose_log(msg):
    """Log message if verbose is True."""

    if args.verbose:
        log_message(msg)


def warn(msg):
    """Print and log warning message"""

    if args and not args.nowarn:
        msg = "Warning: " + str(msg)
        print(msg)
        sys.stdout.flush()
        log_message(msg)


def log_message(message):
    """Log a message if the solidlibs package is available."""

    try:
        log(message)
    except TypeError:
        pass


def error_exit(why=None):
    """
    Exit on error.

    >>> why = PermissionError("[Errno 1] Operation not permitted: 'file-owned-by-root'")
    >>> try:
    ...     error_exit(why)
    ... except SystemExit as se:
    ...    se.code == 1
    <BLANKLINE>
    <BLANKLINE>
    Permission error: 'file-owned-by-root'
    <BLANKLINE>
    <BLANKLINE>
    <BLANKLINE>
    True
    >>> why = FileNotFoundError('No such file or directory: [test]')
    >>> try:
    ...     error_exit(why)
    ... except SystemExit as se:
    ...    se.code == 1
    <BLANKLINE>
    <BLANKLINE>
    No such file or directory: [test]
    <BLANKLINE>
    <BLANKLINE>
    <BLANKLINE>
    True
    >>> try:
    ...     error_exit()
    ... except SystemExit as se:
    ...    se.code == 1
    <BLANKLINE>
    <BLANKLINE>
    Error copying file(s)
    <BLANKLINE>
    <BLANKLINE>
    <BLANKLINE>
    True
    """
    NOT_PERMITTED = "[Errno 1] Operation not permitted: "
    ERROR_NUMBER2 = "[Errno 2] "
    DETAILS = "Error copying file(s)"

    if args and args.test:
        output = sys.stdout
    else:
        output = sys.stderr

    if why:
        if isinstance(why, FileNotFoundError):
            why_string = str(why)
            index = why_string.find(ERROR_NUMBER2)
            if index >= 0:
                why = why_string[index + len(ERROR_NUMBER2) :]
            full_details = why
        elif isinstance(why, PermissionError):
            why_string = str(why)
            index = why_string.find(NOT_PERMITTED)
            if index >= 0:
                why = why_string[index + len(NOT_PERMITTED) :]
            full_details = f"Permission error: {why}"
        else:
            full_details = f"{DETAILS}: {why}"
    else:
        full_details = DETAILS

    log_message(full_details)
    print(f"\n\n{full_details}", file=output)

    try:
        if args and args.verbose:
            log_message(f"See details in {get_log_path()}\n\n")
            print(f"See details in {get_log_path()}\n\n", file=sys.stderr)
        else:
            print("\n\n", file=output)
    except NameError:
        print("\n\n", file=output)

    sys.exit(1)


def delay():
    """Call delay() in a loop so the loop doesn't lock up the machine."""

    time.sleep(0.000001)
